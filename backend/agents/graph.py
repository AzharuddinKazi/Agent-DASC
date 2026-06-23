from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agents.state import TaskState
from agents.analyzer import analyzer
from agents.question_generator import question_generator
from agents.planner import planner
from agents.coder import coder
from agents.executor import executor
from agents.verifier import verifier
from agents.router_agent import router_agent
from agents.debugger import debugger
from agents.section_manager import section_manager
from agents.compiler import compiler # We will build this later, replacing finalizer
import os


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_executor(state: TaskState) -> str:
    if state["exit_code"] != 0:
        if state.get("debug_attempts", 0) < 3:
            return "debugger"
        else:
            # If a single section fails irreparably, we log it and move to the next section
            return "section_manager" 
    return "verifier"

def route_after_debugger(state: TaskState) -> str:
    return "executor"

def route_after_verifier(state: TaskState) -> str:
    if state["verifier_verdict"] == "sufficient":
        return "section_manager"
    if state["current_round"] >= state["max_rounds"]:
        return "section_manager" # Maxed out rounds, cut losses and move on
    return "router_agent"

def route_after_router(state: TaskState) -> str:
    return "planner"

def route_after_section_manager(state: TaskState) -> str:
    # If there are still questions left, go back to the planner
    if state["current_question_index"] < len(state["sub_questions"]):
        return "planner"
    # Otherwise, all sections are done. Compile the final report.
    return "compiler"

# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    builder = StateGraph(TaskState)

    builder.add_node("analyzer",           analyzer)
    builder.add_node("question_generator", question_generator)
    builder.add_node("planner",            planner)
    builder.add_node("coder",              coder)
    builder.add_node("executor",           executor)
    builder.add_node("verifier",           verifier)
    builder.add_node("router_agent",       router_agent)
    builder.add_node("debugger",           debugger)
    builder.add_node("section_manager",    section_manager)
    builder.add_node("compiler",           compiler)

    builder.set_entry_point("analyzer")

    builder.add_edge("analyzer",           "question_generator")
    builder.add_edge("question_generator", "planner")
    builder.add_edge("planner",            "coder")
    builder.add_edge("coder",              "executor")

    builder.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "debugger": "debugger",
            "verifier": "verifier",
            "section_manager": "section_manager"
        }
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
            "section_manager": "section_manager",
            "router_agent":    "router_agent",
        }
    )

    builder.add_conditional_edges(
        "router_agent",
        route_after_router,
        {"planner": "planner"}
    )
    
    builder.add_conditional_edges(
        "section_manager",
        route_after_section_manager,
        {
            "planner":  "planner",
            "compiler": "compiler"
        }
    )

    builder.add_edge("compiler", END)

    return builder.compile(checkpointer=checkpointer)