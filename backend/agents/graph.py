from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import TaskState
from agents.analyzer import analyzer
from agents.planner import planner
from agents.coder import coder
from agents.executor import executor
from agents.verifier import verifier
from agents.router_agent import router_agent
from agents.debugger import debugger
from agents.finalizer import finalizer


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_executor(state: TaskState) -> str:
    if state["exit_code"] != 0 and state.get("debug_attempts", 0) < 3:
        return "debugger"
    return "verifier"


def route_after_debugger(state: TaskState) -> str:
    return "executor"


def route_after_verifier(state: TaskState) -> str:
    if state["verifier_verdict"] == "sufficient":
        return "finalizer"
    if state["current_round"] >= state["max_rounds"]:
        return "finalizer"
    return "router_agent"


def route_after_router(state: TaskState) -> str:
    return "planner"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(TaskState)

    builder.add_node("analyzer",     analyzer)
    builder.add_node("planner",      planner)
    builder.add_node("coder",        coder)
    builder.add_node("executor",     executor)
    builder.add_node("verifier",     verifier)
    builder.add_node("router_agent", router_agent)
    builder.add_node("debugger",     debugger)
    builder.add_node("finalizer",    finalizer)

    builder.set_entry_point("analyzer")

    builder.add_edge("analyzer",     "planner")
    builder.add_edge("planner",      "coder")
    builder.add_edge("coder",        "executor")

    builder.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "debugger": "debugger",
            "verifier": "verifier",
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
            "finalizer":    "finalizer",
            "router_agent": "router_agent",
        }
    )

    builder.add_conditional_edges(
        "router_agent",
        route_after_router,
        {"planner": "planner"}
    )

    builder.add_edge("finalizer", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)