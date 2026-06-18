import os
import subprocess
import tempfile
from agents.state import TaskState
from llm_router import LLMRouter

router = LLMRouter()

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


def analyze_file(filename: str, filepath: str) -> str:
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    nrows = 10000 if file_size_mb > 50 else None
    prompt = ANALYZER_PROMPT.format(filename=filename, nrows=nrows or "all")

    result = router.complete(agent="analyzer", prompt=prompt)
    script = result["text"].strip()

    if script.startswith("```"):
        lines  = script.split("\n")
        script = "\n".join(lines[1:-1])

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        exec_result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network=none",
                "--memory=2g",
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
            description = exec_result.stdout[:3000]
        else:
            description = f"Analysis failed: {exec_result.stderr[:500]}"

        print(f"[Analyzer] {filename}: {len(description)} chars captured")
        return description

    finally:
        os.unlink(script_path)


def analyzer(state: TaskState) -> dict:
    data_path = f"{os.getenv('DSSTAR')}/data"
    descriptions = {}

    for fname in os.listdir(data_path):
        if fname.startswith("."):
            continue

        filepath = os.path.join(data_path, fname)
        if not os.path.isfile(filepath):
            continue

        print(f"[Analyzer] Analyzing {fname}...")
        descriptions[fname] = analyze_file(fname, filepath)

    return {"data_descriptions": descriptions}