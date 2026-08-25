import logging
import os
import subprocess
import tempfile
from agents.state import TaskState
from agents.code_fences import strip_code_fences
from agents.executor import SANDBOX_MEMORY_LIMIT
from agents.logger import log_event
from agents.prompt_store import get_prompt
from db import supabase
from llm_router import LLMRouter

router = LLMRouter()
logger = logging.getLogger(__name__)

ANALYZER_PROMPT = """You are an expert data analyst.

Generate a Python script that loads and describes the content of {filename}.

# File location
The file is located at: /workspace/data/{filename}
Always use the full path /workspace/data/{filename} when opening the file.
If nrows is not 'all', use pd.read_csv('/workspace/data/{filename}', nrows={nrows}) to limit rows.

# Requirements
- Print all column names and their data types for structured data
- Print the shape (rows, columns) of the data
- Print the first 5 rows
- Print basic statistics (null counts, unique values for key columns)
- For CSV files, try comma as separator first, then semicolon, then tab
- For Excel files, print all sheet names and describe each sheet
- For JSON files, print the keys and structure
- For unstructured text, print the first 500 characters and total length

# Rules
- Always use full file paths: /workspace/data/{filename}
- Never use shell commands like !head or !cat
- Write pure Python only — no shell syntax
- Do not use try/except blocks
- The script must be self-contained and runnable as-is
- Your response should only contain a single Python code block"""


def analyze_file(filename: str, filepath: str, task_id: str) -> str:
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    # Threshold scales with SANDBOX_MEMORY_LIMIT's headroom (executor.py) — was 50MB
    # when the sandbox was capped at 2GB, raised alongside it. Still capped rather than
    # removed outright: this step's only job is a quick profile/preview, not the final
    # aggregate answer, so a very large file gains nothing from a full read here even
    # with memory to spare.
    nrows = 10000 if file_size_mb > 300 else None
    prompt = get_prompt("analyzer", ANALYZER_PROMPT).format(filename=filename, nrows=nrows or "all")

    result = router.complete(agent="analyzer", prompt=prompt, task_id=task_id)
    script = strip_code_fences(result["text"].strip())

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name
    # See agents/executor.py's execute_script for why this is needed: NamedTemporaryFile
    # always creates the file mode 0600, which the sandbox's non-root UID 1000 can't read
    # through the :ro mount below when this process runs containerized as root.
    os.chmod(script_path, 0o644)

    try:
        exec_result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network=none",
                f"--memory={SANDBOX_MEMORY_LIMIT}",
                "-v", f"{os.getenv('DSSTAR')}/data:/workspace/data:ro",
                "-v", f"{script_path}:/workspace/scripts/analyze.py:ro",
                "dsstar-sandbox:latest",
                "python3", "/workspace/scripts/analyze.py"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if exec_result.returncode == 0:
            description = exec_result.stdout[:8_000]
        else:
            description = f"Analysis failed: {exec_result.stderr[:2_000]}"

        logger.info(f"{filename}: {len(description)} chars captured")
        return description

    finally:
        os.unlink(script_path)


def analyzer(state: TaskState) -> dict:
    data_path    = f"{os.getenv('DSSTAR')}/data"
    descriptions = {}

    supabase.table("tasks").update({"current_agent": "analyzer"}).eq("task_id", state["task_id"]).execute()
    log_event(state["task_id"], "analyzer", "Scanning data files...", "running")

    for fname in os.listdir(data_path):
        if fname.startswith("."):
            continue
        filepath = os.path.join(data_path, fname)
        if not os.path.isfile(filepath):
            continue

        file_size = os.path.getsize(filepath)

        # check cache
        cached = supabase.table("file_descriptions") \
            .select("description, file_size_bytes") \
            .eq("filename", fname) \
            .execute()

        if cached.data and cached.data[0]["file_size_bytes"] == file_size:
            logger.info(f"{fname}: using cached description")
            descriptions[fname] = cached.data[0]["description"]
            continue

        # analyze and cache
        logger.info(f"Analyzing {fname}...")
        description = analyze_file(fname, filepath, state["task_id"])
        descriptions[fname] = description

        supabase.table("file_descriptions").upsert({
            "filename":        fname,
            "description":     description,
            "file_size_bytes": file_size,
        }).execute()

    file_names = list(descriptions.keys())
    log_event(state["task_id"], "analyzer",
              f"Analyzed {len(file_names)} file(s): {', '.join(file_names)}",
              "success", {"files": file_names})
    return {"data_descriptions": descriptions}