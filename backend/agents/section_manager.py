from agents.state import TaskState
from db import supabase

def section_manager(state: TaskState) -> dict:
    task_id = state["task_id"]
    idx = state["current_question_index"]
    questions = state["sub_questions"]
    current_question = questions[idx]
    
    supabase.table("tasks").update({"current_agent": "section_manager"}).eq("task_id", task_id).execute()

    # Save the approved result of the current section
    completed = state.get("completed_sections", {})
    completed[str(current_question["question_id"])] = {
        "question_text": current_question["question_text"],
        "needs_chart": current_question.get("needs_chart", False),
        "text_content": state.get("execution_result", ""),
        "chart_data": None # We will populate this when we update the executor/coder
    }

    print(f"[SectionManager] Saved Section {idx + 1}/{len(questions)}. Advancing...")

    # Reset the core loop variables for the next question and increment index
    return {
        "completed_sections": completed,
        "current_question_index": idx + 1,
        "cumulative_plan": [],
        "current_script": "",
        "execution_result": "",
        "exit_code": 0,
        "debug_attempts": 0,
        "current_round": 0,
        "verifier_verdict": "",
        "router_decision": ""
    }