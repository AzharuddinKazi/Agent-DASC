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
    draft_report:               str         # JSON report from writer agent
    report_verdict:             str         # "sufficient" | "insufficient"
    report_gaps:                list        # list of missing dimensions
    report_rounds:              int         # writer iteration count
    max_report_rounds:          int
