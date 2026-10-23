"""Registry tying each mode's prompt, schema, post-processing and copy behaviour together."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from app import feedback_mode, form_mode, practice_mode
from app.gemini_service import AnalysisRequest
from app.response_models import FeedbackResult, FormResult, PracticeResult, parse_model_output


@dataclass(frozen=True)
class ModeContext:
    """User-supplied input for the active mode (snapshotted per task)."""
    input_text: str = ""
    study_only: bool = False


@dataclass(frozen=True)
class ModeSpec:
    key: str
    title: str
    description: str
    icon: str
    response_model: type[BaseModel]
    input_label: str
    input_placeholder: str
    supports_text_input: bool          # can analyze pasted text instead of a screenshot
    pause_for_review: bool             # continuous mode pauses after each result
    _prompt: Callable[[ModeContext], tuple[str, str]]
    _post: Callable[[BaseModel], BaseModel]
    copy_text: Callable[[BaseModel], str]

    def build_request(self, ctx: ModeContext, image_png: bytes | None) -> AnalysisRequest:
        system, user = self._prompt(ctx)
        return AnalysisRequest(self.key, system, user, self.response_model, image_png)

    def parse(self, raw: str) -> BaseModel:
        return self._post(parse_model_output(self.response_model, raw))


MODES: dict[str, ModeSpec] = {
    "practice": ModeSpec(
        key="practice", title="Practice Quiz Solver", icon="✔",
        description="Explains & answers practice questions on screen",
        response_model=PracticeResult,
        input_label="Extra context (optional)",
        input_placeholder="e.g. 'Chapter 4: kinematics' — helps interpret the question",
        supports_text_input=False, pause_for_review=False,
        _prompt=lambda c: practice_mode.build_prompt(c.input_text, c.study_only),
        _post=lambda r: r,
        copy_text=practice_mode.copy_text,
    ),
    "form": ModeSpec(
        key="form", title="Smart Form Filler", icon="✎",
        description="Maps your details onto visible form fields",
        response_model=FormResult,
        input_label="Your details (the ONLY values that will be used)",
        input_placeholder="Name: Alex Example\nEmail: alex@example.com\nPhone: ...",
        supports_text_input=False, pause_for_review=True,
        _prompt=lambda c: form_mode.build_prompt(c.input_text),
        _post=form_mode.apply_safety_rules,
        copy_text=form_mode.copy_text,
    ),
    "feedback": ModeSpec(
        key="feedback", title="Instant Feedback", icon="✉",
        description="Grammar, clarity & a polished rewrite",
        response_model=FeedbackResult,
        input_label="Paste text instead of capturing (optional)",
        input_placeholder="Paste your paragraph, e-mail or answer here, then click Analyze Text",
        supports_text_input=True, pause_for_review=False,
        _prompt=lambda c: feedback_mode.build_prompt(c.input_text),
        _post=lambda r: r,
        copy_text=feedback_mode.copy_text,
    ),
}
