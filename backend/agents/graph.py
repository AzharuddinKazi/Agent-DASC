from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agents.state import TaskState
from agents.analyzer import analyzer
from agents.planner import planner
from agents.coder import coder
from agents.executor import executor
from agents.verifier import verifier
from agents.router_agent import router_agent
from agents.debugger import debugger
from agents.finalizer import finalizer
from agents.question_generator import question_generator
from agents.writer import writer
from agents.report_evaluator import report_evaluator
import json


# ── DS-STAR QA routing ────────────────────────────────────────────────────────

def route_after_analyzer(state: TaskState) -> str:
    """After analyzing data: branch into QA or DS-STAR+ report mode."""
    if state.get("task_type") == "report":
        return "question_generator"
    return "planner"


def route_after_executor(state: TaskState) -> str:
    if state["exit_code"] != 0:
        if state.get("debug_attempts", 0) < 3:
            return "debugger"
        return "finalizer"
    return "verifier"


def route_after_debugger(state: TaskState) -> str:
    return "executor"


def route_after_verifier(state: TaskState) -> str:
    if state["verifier_verdict"] == "sufficient":
        # In report mode, store result and move to next sub-question
        if state.get("task_type") == "report":
            return "sub_result_collector"
        return "finalizer"
    if state["current_round"] >= state["max_rounds"]:
        if state.get("task_type") == "report":
            return "sub_result_collector"
        return "finalizer"
    return "router_agent"


def route_after_router(state: TaskState) -> str:
    return "planner"


# ── DS-STAR+ report routing ───────────────────────────────────────────────────

def sub_result_collector(state: TaskState) -> dict:
    """Store the current sub-question result and prepare state for the next one."""
    from db import supabase

    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)
    sub_results     = dict(state.get("sub_results", {}))

    # Parse and store the result for the current sub-question
    current_q = sub_questions[current_sub_idx] if current_sub_idx < len(sub_questions) else None
    if current_q:
        raw = state.get("final_result") or state.get("execution_result", "")
        parsed = {}
        try:
            s = raw.strip()
            if s.startswith("```"):
                import re
                s = re.sub(r"^```[a-z]*\n?", "", s).rstrip("`").strip()
            parsed = json.loads(s)
        except Exception:
            parsed = {"summary": raw, "key_findings": [], "columns": [], "rows": []}
        sub_results[current_q] = parsed

    next_idx = current_sub_idx + 1

    supabase.table("tasks").update({
        "current_agent": f"sub_result_{current_sub_idx + 1}_of_{len(sub_questions)}"
    }).eq("task_id", state["task_id"]).execute()

    return {
        "sub_results":      sub_results,
        "current_sub_idx":  next_idx,
        # Reset QA pipeline state for the next sub-question
        "cumulative_plan":  [],
        "current_script":   "",
        "execution_result": "",
        "exit_code":        0,
        "debug_attempts":   0,
        "current_round":    0,
        "verifier_verdict": "",
        "router_decision":  "",
        "final_result":     None,
    }


def route_after_sub_collector(state: TaskState) -> str:
    """After collecting a sub-result: run next sub-question or move to Writer."""
    sub_questions   = state.get("sub_questions", [])
    current_sub_idx = state.get("current_sub_idx", 0)

    if current_sub_idx < len(sub_questions):
        return "planner"   # Process next sub-question
    return "writer"        # All done — generate report


def route_after_writer(state: TaskState) -> str:
    max_rounds = state.get("max_report_rounds", 2)
    if state.get("report_rounds", 0) >= max_rounds:
        return "report_finalizer"
    return "report_evaluator"


def route_after_report_evaluator(state: TaskState) -> str:
    if state.get("report_verdict") == "sufficient":
        return "report_finalizer"
    max_rounds = state.get("max_report_rounds", 2)
    if state.get("report_rounds", 0) >= max_rounds:
        return "report_finalizer"
    # Add gap sub-questions and loop
    return "gap_question_generator"


def gap_question_generator(state: TaskState) -> dict:
    """Add new sub-questions for identified gaps and loop back through DS-STAR."""
    from db import supabase
    gaps          = state.get("report_gaps", [])
    sub_questions = list(state.get("sub_questions", []))

    # Convert gaps into sub-questions
    new_qs = [f"{gap}" if "?" in gap else f"{gap}?" for gap in gaps]
    sub_questions.extend(new_qs)

    supabase.table("tasks").update({"current_agent": "gap_question_generator"}).eq("task_id", state["task_id"]).execute()

    return {
        "sub_questions":   sub_questions,
        "cumulative_plan": [],
        "current_script":  "",
        "execution_result": "",
        "exit_code":       0,
        "debug_attempts":  0,
        "current_round":   0,
        "verifier_verdict": "",
        "router_decision": "",
        "final_result":    None,
    }


def report_finalizer(state: TaskState) -> dict:
    """Store the final report in Supabase as the task's final_result."""
    from db import supabase
    draft = state.get("draft_report", "{}")
    supabase.table("tasks").update({
        "current_agent": "report_finalizer",
        "final_result":  draft,
    }).eq("task_id", state["task_id"]).execute()

    return {"final_result": draft, "status": "completed"}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    builder = StateGraph(TaskState)

    # ── DS-STAR base nodes ────────────────────────────────────────────────────
    builder.add_node("analyzer",          analyzer)
    builder.add_node("planner",           planner)
    builder.add_node("coder",             coder)
    builder.add_node("executor",          executor)
    builder.add_node("verifier",          verifier)
    builder.add_node("router_agent",      router_agent)
    builder.add_node("debugger",          debugger)
    builder.add_node("finalizer",         finalizer)

    # ── DS-STAR+ nodes ────────────────────────────────────────────────────────
    builder.add_node("question_generator",   question_generator)
    builder.add_node("sub_result_collector", sub_result_collector)
    builder.add_node("writer",               writer)
    builder.add_node("report_evaluator",     report_evaluator)
    builder.add_node("gap_question_generator", gap_question_generator)
    builder.add_node("report_finalizer",     report_finalizer)

    # ── Entry ─────────────────────────────────────────────────────────────────
    builder.set_entry_point("analyzer")

    # Analyzer branches: QA → planner, Report → question_generator
    builder.add_conditional_edges(
        "analyzer",
        route_after_analyzer,
        {"planner": "planner", "question_generator": "question_generator"}
    )

    # ── DS-STAR QA loop ───────────────────────────────────────────────────────
    builder.add_edge("planner",  "coder")
    builder.add_edge("coder",    "executor")

    builder.add_conditional_edges(
        "executor",
        route_after_executor,
        {"debugger": "debugger", "verifier": "verifier", "finalizer": "finalizer"}
    )

    builder.add_conditional_edges(
        "debugger",
        route_after_debugger,
        {"executor": "executor"}
    )

    builder.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "finalizer":          "finalizer",
            "router_agent":       "router_agent",
            "sub_result_collector": "sub_result_collector",
        }
    )

    builder.add_conditional_edges(
        "router_agent",
        route_after_router,
        {"planner": "planner"}
    )

    builder.add_edge("finalizer", END)

    # ── DS-STAR+ report loop ──────────────────────────────────────────────────
    builder.add_edge("question_generator", "planner")  # first sub-question → planner

    builder.add_conditional_edges(
        "sub_result_collector",
        route_after_sub_collector,
        {"planner": "planner", "writer": "writer"}
    )

    builder.add_conditional_edges(
        "writer",
        route_after_writer,
        {"report_evaluator": "report_evaluator", "report_finalizer": "report_finalizer"}
    )

    builder.add_conditional_edges(
        "report_evaluator",
        route_after_report_evaluator,
        {
            "report_finalizer":      "report_finalizer",
            "gap_question_generator": "gap_question_generator",
        }
    )

    builder.add_edge("gap_question_generator", "planner")
    builder.add_edge("report_finalizer", END)

    return builder.compile(checkpointer=checkpointer)
