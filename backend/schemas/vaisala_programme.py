"""Validated programme API boundaries; source evidence remains in the item payload."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Action = Literal["engineer_assessment", "evidence_validation", "treatment_appraisal", "monitor", "no_action_indicated"]
ReviewStatus = Literal["unreviewed", "accepted", "assigned", "completed", "deferred"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProgrammePolicy(StrictInput):
    version: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    localised_threshold_pct: float = Field(default=5, ge=0, le=100, allow_inf_nan=False)
    surface_threshold_pct: float = Field(default=5, ge=0, le=100, allow_inf_nan=False)
    qc_adequacy_pct: float = Field(default=85, ge=85, le=100, allow_inf_nan=False)
    automatic_monitoring_enabled: Literal[False] = False


class SaveProgramme(StrictInput):
    merge_scale: Literal["section", "100m", "10m"] = "section"
    split: Literal["combined", "urban", "rural"] = "combined"
    policy_version: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=120)


class ReviewInput(StrictInput):
    expected_sequence: int = Field(ge=0)
    status: ReviewStatus
    client_action: Action | None = None
    comment: str = Field(default="", max_length=5000)
    assignee: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def workflow_fields(self):
        if self.status == "deferred" and not self.comment:
            raise ValueError("A deferral reason is required")
        if self.status == "assigned" and not self.assignee:
            raise ValueError("An assignee is required for assigned status")
        return self


class ProgrammeItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    item_key: str
    recommended_action: Action
    reason_codes: list[str]
    brief: str
    next_question: str
    prerequisite_tasks: list[Any]
    evidence_status: str
    queue_rank: int | None
    queue_size: int
    priority_explanation: str


class ProgrammeResponse(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())
    model_version: str
    policy_version: str
    survey_id: int
    summary: dict[str, Any]
    cohorts: list[dict[str, Any]]
    items: list[ProgrammeItem]
    total: int
    filtered_total: int
    page: int
    page_size: int
