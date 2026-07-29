"""
DS-STAR graph state definition.

TaskState is the single source of truth for everything that happens
during a DS-STAR task. Every node reads from this and returns updates to it.
No node communicates with another node directly — only through state.
"""

from typing import TypedDict, Optional


class TaskState(TypedDict):
    # ── Core ──────────────────────────────────────────────────────────────────
    task_id:                    str
    query:                      str
    formatting_guidelines:      str
    task_type:                  str         # "qa" (default) | "report" (DS-STAR+)
    use_domain_knowledge:       bool        # gates Planner's per-round KB retrieval (the token/cost driver)
    domain_pack_id:             Optional[str]  # per-task pack override; None = use the globally active pack

    # ── DS-STAR QA pipeline ───────────────────────────────────────────────────
    data_descriptions:          dict        # {filename: description}
    cumulative_plan:            list        # growing list of plan steps
    current_script:             str         # most recent generated script
    execution_result:           str         # stdout from most recent execution
    exit_code:                  int
    debug_attempts:             int
    current_round:              int
    max_rounds:                 int
    verifier_verdict:           str         # "sufficient" | "insufficient"
    router_decision:            str         # "add_step" | "backtrack:N"
    status:                     str
    final_result:               Optional[str]

    # ── DS-STAR+ Report pipeline ──────────────────────────────────────────────
    sub_questions:              list        # generated sub-questions
    current_sub_idx:            int         # index of sub-question being processed
    sub_results:                dict        # {sub_question: parsed_result_dict}
    hypotheses:                 dict        # {sub_question: hypothesis statement it tests}
    draft_report:               str         # JSON report from writer agent
    report_verdict:             str         # "sufficient" | "insufficient"
    report_gaps:                list        # list of {question, hypothesis} gap objects
    report_rounds:              int         # writer iteration count
    max_report_rounds:          int


def current_objective(state: TaskState) -> str:
    """The question a mini-pipeline round (planner/verifier/router_agent) should actually
    be answering: the current sub-question/hypothesis in report mode, the top-level query
    otherwise.

    Without this, every sub-question's mini-pipeline received the same top-level query
    regardless of which sub-question it was supposedly working on — sub_questions was only
    ever used for UI progress labels, never as the actual driving objective. Falls back to
    state["query"] whenever sub_questions is empty or exhausted, so QA-mode behavior (no
    sub_questions) is unchanged.
    """
    sub_qs = state.get("sub_questions") or []
    idx = state.get("current_sub_idx", 0)
    return sub_qs[idx] if idx < len(sub_qs) else state["query"]
