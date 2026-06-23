import json
from agents.state import TaskState
from llm_router import LLMRouter
from db import supabase

router = LLMRouter()

QUESTION_GENERATOR_PROMPT = """You are an expert data analyst. 
Your task is to write a comprehensive data science report to answer the user's open-ended query.
To do this effectively, you must break down the main query into a logical sequence of specific, executable sub-questions.

# Open-Ended Query
{query}

# Available Data Files and Summaries:
{summaries}

# Your Task
Generate a sequence of sub-questions that will collectively form the comprehensive report. 
- Each question must be specific enough to be solved via a Python script (pandas, etc.).
- Order the questions logically (e.g., overview first, then deep dives).
- Indicate if a question's answer should be visualized with a chart.

# Output Format
Return a JSON array of objects:
[
  {{
    "question_id": 1,
    "question_text": "...",
    "needs_chart": true/false
  }}
]
Return ONLY the JSON array."""

def question_generator(state: TaskState) -> dict:
    
    supabase.table("tasks").update({"current_agent": "question_generator"}).eq("task_id", state["task_id"]).execute()

    query = state["query"]
    summaries = state["data_descriptions"]

    summaries_text = "\n".join(
        f"File: {fname}\n{desc}"
        for fname, desc in summaries.items()
    )

    prompt = QUESTION_GENERATOR_PROMPT.format(
        query=query,
        summaries=summaries_text
    )

    result = router.complete(agent="question_generator", prompt=prompt)
    
    try:
        raw_text = result["text"].strip()
        if raw_text.startswith("```json"):
            raw_text = "\n".join(raw_text.split("\n")[1:-1])
        elif raw_text.startswith("```"):
             raw_text = "\n".join(raw_text.split("\n")[1:-1])
             
        generated_questions = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"[QuestionGenerator] JSON parsing failed: {e}. Falling back.")
        generated_questions = [{"question_id": 1, "question_text": query, "needs_chart": False}]

    print(f"[QuestionGenerator] Generated {len(generated_questions)} sub-questions.")

    return {
        "sub_questions": generated_questions,
        "current_question_index": 0,
        "completed_sections": {},
        "status": "questions_generated"
    }