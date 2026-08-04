import hashlib
import logging
import os
import subprocess
import tempfile
from agents.state import TaskState
from agents.code_fences import strip_code_fences
from agents.logger import log_event
from agents.sandbox_security import docker_security_args
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
- Use nrows=5000 when loading any CSV to avoid memory issues
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


_HASH_SAMPLE_BYTES = 65_536


def _content_fingerprint(filepath: str, file_size: int) -> str:
    """Cheap stand-in for a full content hash: size + a sample of the first/last 64KB.
    A true full-file SHA256 would mean re-reading every byte of every dataset on every
    single analyzer run just to validate the cache — including the 470MB file this repo
    already ships with real data (see CLAUDE.md) — which defeats the point of caching (the
    whole read would cost more than the Docker+LLM call the cache exists to skip). Sampling
    the head/tail is enough to catch the actual failure mode this closes (two files that
    happen to share both a filename and a byte size), without that cost.
    """
    h = hashlib.sha256()
    h.update(str(file_size).encode())
    with open(filepath, "rb") as f:
        h.update(f.read(_HASH_SAMPLE_BYTES))
        if file_size > _HASH_SAMPLE_BYTES:
            f.seek(max(file_size - _HASH_SAMPLE_BYTES, 0))
            h.update(f.read(_HASH_SAMPLE_BYTES))
    return h.hexdigest()


def analyze_file(filename: str, filepath: str, task_id: str) -> str:
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    nrows = 10000 if file_size_mb > 50 else None
    prompt = ANALYZER_PROMPT.format(filename=filename, nrows=nrows or "all")

    result = router.complete(agent="analyzer", prompt=prompt, task_id=task_id)
    script = strip_code_fences(result["text"].strip())

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        exec_result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=2g",
                *docker_security_args(),
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
        content_hash = _content_fingerprint(filepath, file_size)

        # check cache
        cached = supabase.table("file_descriptions") \
            .select("description, file_size_bytes, content_hash") \
            .eq("filename", fname) \
            .execute()

        if (cached.data
                and cached.data[0]["file_size_bytes"] == file_size
                and cached.data[0].get("content_hash") == content_hash):
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
            "content_hash":    content_hash,
        }).execute()

    file_names = list(descriptions.keys())
    log_event(state["task_id"], "analyzer",
              f"Analyzed {len(file_names)} file(s): {', '.join(file_names)}",
              "success", {"files": file_names})
    return {"data_descriptions": descriptions}