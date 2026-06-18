"""
DS-STAR graph state definition.

TaskState is the single source of truth for everything that happens
during a DS-STAR task. Every node reads from this and returns updates to it.
No node communicates with another node directly — only through state.
"""

from typing import TypedDict, Optional


class TaskState(TypedDict):
    """
    TaskState _summary_

    Args:
        TypedDict (_type_): _description_
    """
    task_id:                    str
    query:                      str
    formatting_guidelines:      str
    data_descriptions:          dict        # {filename: d_i description}
    cumulative_plan:            list        # [p_0, p_1, ...] — grows each round
    current_script:             str         # s_k — most recent script
    execution_result:           str         # r_k — stdout from most recent execution
    exit_code:                  int
    debug_attempts:             int
    current_round:              int
    max_rounds:                 int
    verifier_verdict:           str         # "sufficient" or "insufficient"
    router_decision:            str         # "add_step" or "backtrack:{l}"
    status:                     str
    final_result:               Optional[str]
