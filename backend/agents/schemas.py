"""Pydantic schemas for the JSON shapes the Finalizer and Writer agents ask the LLM to
produce (see FINALIZER_PROMPT / writer._writer_prompt_template). These don't gate
storage — a shape violation still gets stored and shown, same as today — they exist so a
violation is logged with the actual offending fields instead of only surfacing later as an
unexplained frontend rendering glitch (the gap the audit flagged: nothing checks the LLM's
JSON against the shape the frontend assumes before it gets there).
"""
import logging
from typing import Any
from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    title: str | None = None
    x_key: str | None = None
    x_label: str | None = None
    y_key: str | None = None
    y_label: str | None = None
    data: list[dict[str, Any]] = []


class FinalizerOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str
    key_findings: list[str] = []
    columns: list[str] = []
    rows: list[list[Any]] = []
    chart: ChartSpec | None = None
    raw: str | None = None


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="allow")
    heading: str
    body: str
    key_stat: str | None = None


class RiskMatrixEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    entity: str
    dimensions: dict[str, Any] = {}
    overall: str | None = None
    priority_action: str | None = None


class DataCoverage(BaseModel):
    model_config = ConfigDict(extra="allow")
    sub_questions_answered: int | None = None
    total_records_analysed: int | None = None
    datasets_used: list[str] = []


class WriterReport(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    executive_summary: str
    sections: list[ReportSection] = []
    risk_matrix: list[RiskMatrixEntry] = []
    conclusions: str | None = None
    recommendations: list[str] = []
    data_coverage: DataCoverage | None = None


def validate_and_log(model_cls: type[BaseModel], parsed: dict, *, task_id: str, agent: str) -> bool:
    """Validates `parsed` against `model_cls`. Returns True if it matches the shape the
    frontend expects; on mismatch, logs the concrete field errors (not just "invalid") and
    returns False. Callers keep using the original `parsed` dict either way — this is a
    visibility check, not a repair or a gate."""
    try:
        model_cls.model_validate(parsed)
        return True
    except ValidationError as e:
        errors = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())
        logger.warning(f"{agent} output for task {task_id} doesn't match expected schema: {errors}")
        return False
