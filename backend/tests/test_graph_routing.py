from agents.graph import (
    route_after_analyzer,
    route_after_executor,
    route_after_debugger,
    route_after_verifier,
    route_after_router,
    route_after_sub_collector,
    route_after_writer,
    route_after_report_evaluator,
    route_after_human_review_gate,
)


# ── route_after_analyzer ─────────────────────────────────────────────────────

def test_route_after_analyzer_report_mode_goes_to_question_generator():
    assert route_after_analyzer({"task_type": "report"}) == "question_generator"


def test_route_after_analyzer_qa_mode_goes_to_planner():
    assert route_after_analyzer({"task_type": "qa"}) == "planner"


def test_route_after_analyzer_defaults_to_planner_when_task_type_missing():
    assert route_after_analyzer({}) == "planner"


# ── route_after_executor ─────────────────────────────────────────────────────

def test_route_after_executor_success_goes_to_verifier():
    assert route_after_executor({"exit_code": 0, "debug_attempts": 0}) == "verifier"


def test_route_after_executor_failure_under_debug_limit_goes_to_debugger():
    assert route_after_executor({"exit_code": 1, "debug_attempts": 0}) == "debugger"
    assert route_after_executor({"exit_code": 1, "debug_attempts": 1}) == "debugger"


def test_route_after_executor_failure_at_debug_limit_qa_mode_goes_to_finalizer():
    """Boundary: debug_attempts == 2 (the limit) must stop retrying, not allow one more."""
    assert route_after_executor({"exit_code": 1, "debug_attempts": 2}) == "finalizer"
    assert route_after_executor({"exit_code": 1, "debug_attempts": 5}) == "finalizer"
    assert route_after_executor({"exit_code": 1, "debug_attempts": 2, "task_type": "qa"}) == "finalizer"


def test_route_after_executor_failure_at_debug_limit_report_mode_goes_to_sub_result_collector():
    """Regression test: one sub-question exhausting its debug retries in report mode
    used to route to the QA-only finalizer, discarding every already-verified
    sub-analysis for the whole report the moment a single later sub-question failed."""
    assert route_after_executor(
        {"exit_code": 1, "debug_attempts": 2, "task_type": "report"}) == "sub_result_collector"
    assert route_after_executor(
        {"exit_code": 1, "debug_attempts": 5, "task_type": "report"}) == "sub_result_collector"


def test_route_after_executor_defaults_debug_attempts_to_zero():
    assert route_after_executor({"exit_code": 1}) == "debugger"


# ── route_after_debugger ─────────────────────────────────────────────────────

def test_route_after_debugger_always_goes_to_executor():
    assert route_after_debugger({}) == "executor"


# ── route_after_verifier ─────────────────────────────────────────────────────

def test_route_after_verifier_sufficient_qa_mode_goes_to_finalizer():
    state = {"verifier_verdict": "sufficient", "task_type": "qa"}
    assert route_after_verifier(state) == "finalizer"


def test_route_after_verifier_sufficient_report_mode_goes_to_sub_result_collector():
    state = {"verifier_verdict": "sufficient", "task_type": "report"}
    assert route_after_verifier(state) == "sub_result_collector"


def test_route_after_verifier_insufficient_under_round_limit_goes_to_router_agent():
    state = {"verifier_verdict": "insufficient", "current_round": 1, "max_rounds": 3, "task_type": "qa"}
    assert route_after_verifier(state) == "router_agent"


def test_route_after_verifier_insufficient_at_round_limit_qa_mode_goes_to_finalizer():
    """Boundary: current_round == max_rounds must stop looping, not allow one more round."""
    state = {"verifier_verdict": "insufficient", "current_round": 3, "max_rounds": 3, "task_type": "qa"}
    assert route_after_verifier(state) == "finalizer"


def test_route_after_verifier_insufficient_at_round_limit_report_mode_goes_to_sub_result_collector():
    """Report mode must still hand off a (possibly-insufficient) result to the collector
    rather than dead-ending at the QA-only finalizer when the round budget is exhausted."""
    state = {"verifier_verdict": "insufficient", "current_round": 3, "max_rounds": 3, "task_type": "report"}
    assert route_after_verifier(state) == "sub_result_collector"


# ── route_after_router ────────────────────────────────────────────────────────

def test_route_after_router_always_goes_to_planner():
    assert route_after_router({}) == "planner"


# ── route_after_sub_collector ────────────────────────────────────────────────

def test_route_after_sub_collector_more_sub_questions_goes_to_planner():
    state = {"sub_questions": ["Q1?", "Q2?"], "current_sub_idx": 1}
    assert route_after_sub_collector(state) == "planner"


def test_route_after_sub_collector_all_done_goes_to_writer():
    """Boundary: current_sub_idx == len(sub_questions) means every sub-question has
    already been collected."""
    state = {"sub_questions": ["Q1?", "Q2?"], "current_sub_idx": 2}
    assert route_after_sub_collector(state) == "writer"


def test_route_after_sub_collector_empty_sub_questions_goes_to_writer():
    assert route_after_sub_collector({"sub_questions": [], "current_sub_idx": 0}) == "writer"


# ── route_after_writer ───────────────────────────────────────────────────────

def test_route_after_writer_under_round_limit_goes_to_report_evaluator():
    state = {"report_rounds": 0, "max_report_rounds": 2}
    assert route_after_writer(state) == "report_evaluator"


def test_route_after_writer_at_round_limit_goes_to_report_finalizer():
    state = {"report_rounds": 2, "max_report_rounds": 2}
    assert route_after_writer(state) == "report_finalizer"


def test_route_after_writer_defaults_max_rounds_to_two():
    assert route_after_writer({"report_rounds": 1}) == "report_evaluator"
    assert route_after_writer({"report_rounds": 2}) == "report_finalizer"


# ── route_after_report_evaluator ─────────────────────────────────────────────

def test_route_after_report_evaluator_sufficient_goes_to_report_finalizer():
    state = {"report_verdict": "sufficient", "report_rounds": 0, "max_report_rounds": 2}
    assert route_after_report_evaluator(state) == "report_finalizer"


def test_route_after_report_evaluator_insufficient_under_limit_goes_to_gap_question_generator():
    state = {"report_verdict": "insufficient", "report_rounds": 0, "max_report_rounds": 2}
    assert route_after_report_evaluator(state) == "gap_question_generator"


def test_route_after_report_evaluator_insufficient_at_limit_goes_to_report_finalizer():
    """Boundary: report_rounds == max_report_rounds must force a finalize even though
    the evaluator is still unhappy — otherwise the gap loop never terminates."""
    state = {"report_verdict": "insufficient", "report_rounds": 2, "max_report_rounds": 2}
    assert route_after_report_evaluator(state) == "report_finalizer"


def test_route_after_report_evaluator_human_review_flag_off_is_unaffected():
    """require_human_review defaults to False/absent — existing automatic routing must be
    bit-for-bit unchanged when the flag isn't set."""
    state = {"report_verdict": "sufficient", "report_rounds": 0, "max_report_rounds": 2}
    assert route_after_report_evaluator(state) == "report_finalizer"
    state = {"report_verdict": "insufficient", "report_rounds": 0, "max_report_rounds": 2}
    assert route_after_report_evaluator(state) == "gap_question_generator"


def test_route_after_report_evaluator_human_review_flag_on_under_limit_goes_to_gate():
    """Regardless of the evaluator's own verdict, a human should get to weigh in when
    refining is still actually possible."""
    for verdict in ("sufficient", "insufficient"):
        state = {"report_verdict": verdict, "report_rounds": 0, "max_report_rounds": 2,
                  "require_human_review": True}
        assert route_after_report_evaluator(state) == "human_review_gate"


def test_route_after_report_evaluator_human_review_flag_on_at_limit_skips_gate():
    """At the round limit there's no real choice left (refine isn't an option) — skip the
    gate and finalize automatically, same as the flag-off path."""
    state = {"report_verdict": "insufficient", "report_rounds": 2, "max_report_rounds": 2,
              "require_human_review": True}
    assert route_after_report_evaluator(state) == "report_finalizer"


# ── route_after_human_review_gate ────────────────────────────────────────────

def test_route_after_human_review_gate_refine_goes_to_gap_question_generator():
    assert route_after_human_review_gate({"human_review_decision": "refine"}) == "gap_question_generator"


def test_route_after_human_review_gate_finalize_goes_to_report_finalizer():
    assert route_after_human_review_gate({"human_review_decision": "finalize"}) == "report_finalizer"


def test_route_after_human_review_gate_missing_decision_defaults_to_finalizer():
    assert route_after_human_review_gate({}) == "report_finalizer"
