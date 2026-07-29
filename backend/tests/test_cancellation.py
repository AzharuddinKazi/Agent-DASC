import pytest
from agents import cancellation
from agents.cancellation import (
    request_stop, request_pause, is_cancelled, is_paused,
    check_interrupt, clear, TaskCancelled, TaskPaused,
)


@pytest.fixture(autouse=True)
def clean_state():
    cancellation._cancelled.clear()
    cancellation._paused.clear()
    yield
    cancellation._cancelled.clear()
    cancellation._paused.clear()


def test_is_cancelled_false_by_default():
    assert is_cancelled("task-1") is False


def test_is_paused_false_by_default():
    assert is_paused("task-1") is False


def test_request_stop_marks_task_cancelled():
    request_stop("task-1")
    assert is_cancelled("task-1") is True
    assert is_paused("task-1") is False


def test_request_pause_marks_task_paused():
    request_pause("task-1")
    assert is_paused("task-1") is True
    assert is_cancelled("task-1") is False


def test_request_stop_does_not_affect_other_tasks():
    request_stop("task-1")
    assert is_cancelled("task-2") is False


def test_request_pause_does_not_affect_other_tasks():
    request_pause("task-1")
    assert is_paused("task-2") is False


def test_check_interrupt_raises_task_cancelled_when_stopped():
    request_stop("task-1")
    with pytest.raises(TaskCancelled):
        check_interrupt("task-1")


def test_check_interrupt_raises_task_paused_when_paused():
    request_pause("task-1")
    with pytest.raises(TaskPaused):
        check_interrupt("task-1")


def test_check_interrupt_stop_takes_priority_over_pause():
    """A stronger signal (permanent stop) should win if somehow both were requested."""
    request_stop("task-1")
    request_pause("task-1")
    with pytest.raises(TaskCancelled):
        check_interrupt("task-1")


def test_check_interrupt_does_nothing_when_neither_requested():
    check_interrupt("task-1")  # must not raise


def test_clear_removes_both_flags():
    request_stop("task-1")
    request_pause("task-2")
    clear("task-1")
    clear("task-2")
    assert is_cancelled("task-1") is False
    assert is_paused("task-2") is False


def test_clear_on_unknown_task_id_does_not_raise():
    clear("never-existed")


def test_clearing_pause_flag_allows_resume_to_proceed_without_re_pausing():
    """The scenario clear() exists to prevent: if the pause flag weren't cleared after
    the paused run unwound, a resumed run would immediately re-raise TaskPaused on its
    very first node check and never make progress."""
    request_pause("task-1")
    with pytest.raises(TaskPaused):
        check_interrupt("task-1")
    clear("task-1")
    check_interrupt("task-1")  # simulated resume — must not raise again
