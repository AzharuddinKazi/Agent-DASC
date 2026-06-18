from agents.state import TaskState
from agents.executor import execute_script
from llm_router import LLMRouter

router = LLMRouter()

FINALIZER_PROMPT = """You are an expert data analyst.
You will answer a factoid question by loading and referencing the files listed below.
You also have a reference code and its execution result.
Your task is to make solution code to print out the answer following the given guidelines.

# Given data:
{summaries}

# Reference code
```python
{code}
```

# Execution result of reference code
{result}

# Question
{question}

# Guidelines
{guidelines}

# Your task
Modify the solution code to print out the answer following the given guidelines.
If the answer can be obtained from the execution result of the reference code, just generate a Python code that prints out the desired answer.
The code should be a single-file Python program that is self-contained and can be executed as-is.
Your response should only contain a single code block."""


def finalizer(state: TaskState) -> dict:
    question         = state["query"]
    summaries        = state["data_descriptions"]
    current_script   = state["current_script"]
    execution_result = state["execution_result"]
    guidelines       = state.get("formatting_guidelines", "Print the answer clearly.")

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    prompt = FINALIZER_PROMPT.format(
        summaries=summaries_text,
        code=current_script,
        result=execution_result,
        question=question,
        guidelines=guidelines
    )

    result       = router.complete(agent="finalizer", prompt=prompt)
    final_script = result["text"].strip()

    if final_script.startswith("```"):
        lines        = final_script.split("\n")
        final_script = "\n".join(lines[1:-1])

    stdout, stderr, exit_code = execute_script(final_script)
    final_output = stdout if exit_code == 0 else f"Execution failed:\n{stderr}"
    print(f"[Finalizer] Final script executed (exit {exit_code})")
    
    return {
        "final_result": final_output,
        "status":       "completed"
    }
