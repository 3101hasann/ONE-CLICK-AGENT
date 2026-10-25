"""Pydantic models for every structured Gemini response, plus safe parsing helpers.

Nothing produced by the model is shown as actionable (or acted on) until it has passed
through `parse_model_output`.
"""
from __future__ import annotations

import json
import re
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.error_handler import AgentError, ErrorCategory


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def _null_to_empty(cls, value, info):
        # Models sometimes send null for optional strings/lists; normalize instead of failing.
        field = cls.model_fields.get(info.field_name)
        if value is None and field is not None and not field.is_required():
            default = field.get_default(call_default_factory=True)
            return default
        return value


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return value


# --------------------------------------------------------------------------- practice
class PracticeResult(_Base):
    task_type: Literal["multiple_choice", "short_answer", "multi_part", "other",
                       "no_question_found"]
    detected_question: str
    options: list[str] = Field(default_factory=list)
    suggested_answer: str
    explanation: str
    confidence: Literal["high", "medium", "low"] = "low"
    uncertainty_notes: str = ""
    needs_user_review: bool = True
    graded_assessment_suspected: bool = False

    _lists = field_validator("options", mode="before")(_as_list)


# --------------------------------------------------------------------------- form
FieldType = Literal["text", "email", "phone", "date", "number", "textarea", "select",
                    "radio", "checkbox", "password", "file", "other"]
TEXT_LIKE_TYPES = {"text", "email", "phone", "date", "number", "textarea"}


class FormField(_Base):
    label: str
    field_type: FieldType = "other"
    suggested_value: str = ""
    source_of_value: Literal["user_provided", "visible_on_screen", "inferred", "missing"] = "missing"
    confidence: float = 0.0
    requires_confirmation: bool = True
    required: bool = False
    read_only: bool = False
    notes: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if value > 1.0:          # model answered as a percentage
            value = value / 100.0
        return min(max(value, 0.0), 1.0)


class FormResult(_Base):
    form_title: str = ""
    fields: list[FormField]
    missing_information: list[str] = Field(default_factory=list)
    notes: str = ""

    _lists = field_validator("missing_information", mode="before")(_as_list)


# --------------------------------------------------------------------------- feedback
class Improvement(_Base):
    category: Literal["grammar", "spelling", "clarity", "structure", "organization", "tone",
                      "relevance", "conciseness", "missing_detail", "unsupported_claim", "other"] = "other"
    issue: str
    suggestion: str


class FeedbackResult(_Base):
    text_found: bool = True
    original_text: str
    overall_feedback: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[Improvement] = Field(default_factory=list)
    corrected_version: str
    revision_notes: list[str] = Field(default_factory=list)
    uncertainty_notes: str = ""

    _lists = field_validator("strengths", "revision_notes", mode="before")(_as_list)


# ------------------------------------------------------------------ feedback form filler
FeedbackTone = Literal["very_good", "good", "normal", "bad", "very_bad"]


class FeedbackQuestion(_Base):
    question: str
    q_type: Literal["single_choice", "rating_scale", "multi_choice", "text", "other"] = "other"
    options: list[str] = Field(default_factory=list)   # selectable labels, in on-screen order
    chosen_index: int = -1                             # 0-based index into options; -1 = none/text
    chosen_option: str = ""                            # verbatim text of the chosen option
    comment: str = ""                                  # generated answer for free-text questions
    # Where to start clicking, normalized 0-1000 relative to the image (x=left→right,
    # y=top→bottom). For choice questions this is the FIRST option's control (leftmost/topmost,
    # which the model localizes reliably); for text questions it is the comment box. -1 unknown.
    click_x: float = -1.0
    click_y: float = -1.0
    orientation: Literal["horizontal", "vertical", "unknown"] = "unknown"
    required: bool = False
    notes: str = ""

    _lists = field_validator("options", mode="before")(_as_list)

    @field_validator("chosen_index", mode="before")
    @classmethod
    def _coerce_index(cls, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return -1

    @field_validator("click_x", "click_y", mode="before")
    @classmethod
    def _coerce_coord(cls, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return -1.0
        return value if 0.0 <= value <= 1000.0 else -1.0

    @property
    def has_click(self) -> bool:
        return self.click_x >= 0.0 and self.click_y >= 0.0


class FeedbackFormResult(_Base):
    form_found: bool = True
    form_title: str = ""
    tone: FeedbackTone = "good"
    questions: list[FeedbackQuestion] = Field(default_factory=list)
    notes: str = ""


# --------------------------------------------------------------------------- parsing
M = TypeVar("M", bound=BaseModel)
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


def parse_model_output(model_cls: type[M], raw: str | dict | None) -> M:
    """Validate raw model output. Raises AgentError(MALFORMED/EMPTY) on failure."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise AgentError(ErrorCategory.EMPTY_RESPONSE, "Gemini returned an empty response.",
                         "Try again, or capture a clearer region.", retryable=True)
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(_FENCE.sub("", raw))
        except json.JSONDecodeError as exc:
            raise AgentError(ErrorCategory.MALFORMED_RESPONSE,
                             f"The response was not valid JSON ({exc.msg}).",
                             "Use Retry — model output occasionally breaks format.",
                             retryable=True) from exc
    if not isinstance(data, dict):
        raise AgentError(ErrorCategory.MALFORMED_RESPONSE,
                         "The response had an unexpected structure (expected an object).",
                         "Use Retry.", retryable=True)
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'root'}: {err['msg']}"
            for err in exc.errors()[:4])
        raise AgentError(ErrorCategory.MALFORMED_RESPONSE,
                         f"The response failed validation ({problems}).",
                         "Nothing was acted on. Use Retry.", retryable=True) from exc
