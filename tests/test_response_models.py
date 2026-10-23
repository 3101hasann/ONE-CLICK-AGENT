import json

import pytest

from app.config import AppConfig
from app.error_handler import AgentError, ErrorCategory, classify_exception
from app.form_mode import apply_safety_rules, default_approval, plan_sequential_fill
from app.gemini_service import GeminiService
from app.response_models import FeedbackResult, FormResult, PracticeResult, parse_model_output

VALID_PRACTICE = {
    "task_type": "multiple_choice", "detected_question": "2+2?", "options": ["A. 3", "B. 4"],
    "suggested_answer": "B. 4", "explanation": "Addition.", "confidence": "high",
}


def test_valid_practice_response_parses():
    result = parse_model_output(PracticeResult, json.dumps(VALID_PRACTICE))
    assert result.suggested_answer == "B. 4"
    assert result.needs_user_review is True


def test_code_fenced_json_is_accepted():
    raw = "```json\n" + json.dumps(VALID_PRACTICE) + "\n```"
    assert parse_model_output(PracticeResult, raw).task_type == "multiple_choice"


@pytest.mark.parametrize("raw", ['{"detected_question": "trunc', "[1, 2]", "not json"])
def test_malformed_responses_are_rejected(raw):
    with pytest.raises(AgentError) as info:
        parse_model_output(PracticeResult, raw)
    assert info.value.category == ErrorCategory.MALFORMED_RESPONSE


def test_empty_response_is_rejected():
    with pytest.raises(AgentError) as info:
        parse_model_output(FeedbackResult, "   ")
    assert info.value.category == ErrorCategory.EMPTY_RESPONSE


def test_missing_required_fields_are_handled():
    data = dict(VALID_PRACTICE)
    del data["suggested_answer"]
    with pytest.raises(AgentError) as info:
        parse_model_output(PracticeResult, data)
    assert "suggested_answer" in info.value.message


def test_invalid_types_are_rejected():
    data = dict(VALID_PRACTICE, task_type="delete_all_files")
    with pytest.raises(AgentError):
        parse_model_output(PracticeResult, data)


def test_optional_nulls_and_strings_are_normalized():
    data = dict(VALID_PRACTICE, options=None, uncertainty_notes=None)
    result = parse_model_output(PracticeResult, data)
    assert result.options == [] and result.uncertainty_notes == ""
    fb = parse_model_output(FeedbackResult, {"original_text": "x", "overall_feedback": "y",
                                             "corrected_version": "z", "strengths": "Clear"})
    assert fb.strengths == ["Clear"]


def test_form_confidence_percent_is_normalized():
    form = parse_model_output(FormResult, {"fields": [{"label": "Team", "confidence": 85}]})
    assert form.fields[0].confidence == pytest.approx(0.85)


# ---------------------------------------------------------------- form safety
def _form(fields):
    return apply_safety_rules(parse_model_output(FormResult, {"fields": fields}))


def test_uncertain_form_fields_are_not_auto_approved():
    form = _form([
        {"label": "Team name", "field_type": "text", "suggested_value": "Null Pointers",
         "source_of_value": "user_provided", "confidence": 0.95, "requires_confirmation": False},
        {"label": "Team size", "field_type": "number", "suggested_value": "4",
         "source_of_value": "inferred", "confidence": 0.5, "requires_confirmation": True},
        {"label": "Motto", "field_type": "text", "suggested_value": "Go",
         "source_of_value": "user_provided", "confidence": 0.4, "requires_confirmation": False},
    ])
    assert [default_approval(f) for f in form.fields] == [True, False, False]


def test_sensitive_and_invented_personal_values_are_removed():
    form = _form([
        {"label": "Password", "field_type": "password", "suggested_value": "hunter2",
         "source_of_value": "user_provided", "confidence": 1.0},
        {"label": "Card number", "field_type": "text", "suggested_value": "4111",
         "source_of_value": "user_provided", "confidence": 1.0},
        {"label": "Email", "field_type": "email", "suggested_value": "made.up@example.com",
         "source_of_value": "inferred", "confidence": 0.9},
    ])
    assert all(f.suggested_value == "" for f in form.fields)
    assert not any(default_approval(f) for f in form.fields)


def test_sequential_fill_stops_before_non_text_fields():
    form = _form([
        {"label": "Name", "field_type": "text", "suggested_value": "Alex",
         "source_of_value": "user_provided", "confidence": 0.9},
        {"label": "Org", "field_type": "text", "suggested_value": "",
         "source_of_value": "missing"},
        {"label": "Team", "field_type": "text", "suggested_value": "NP",
         "source_of_value": "user_provided", "confidence": 0.9},
        {"label": "Size", "field_type": "select", "suggested_value": "M",
         "source_of_value": "user_provided", "confidence": 0.9},
        {"label": "Why", "field_type": "textarea", "suggested_value": "Learn",
         "source_of_value": "user_provided", "confidence": 0.9},
    ])
    values = [f.suggested_value for f in form.fields]
    steps, note = plan_sequential_fill(form.fields, [True, False, True, True, True], values)
    assert [(s.label, s.fill) for s in steps] == [("Name", True), ("Org", False), ("Team", True)]
    assert "Size" in note


def test_unapproved_fields_are_never_planned():
    form = _form([{"label": "Name", "field_type": "text", "suggested_value": "Alex",
                   "source_of_value": "user_provided", "confidence": 0.9}])
    steps, _ = plan_sequential_fill(form.fields, [False], ["Alex"])
    assert steps == []


# ---------------------------------------------------------------- errors & config
class FakeApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def test_rate_limit_is_translated_to_readable_message():
    err = classify_exception(FakeApiError(429, "RESOURCE_EXHAUSTED. Please retry in 17.5s."))
    assert err.category == ErrorCategory.RATE_LIMIT
    assert "quota" in err.message.lower()
    assert err.retry_after == pytest.approx(17.5)
    assert not err.retryable


@pytest.mark.parametrize("code,category", [(401, ErrorCategory.AUTH), (404, ErrorCategory.CONFIG),
                                           (503, ErrorCategory.SERVER)])
def test_http_errors_are_categorized(code, category):
    assert classify_exception(FakeApiError(code, "boom")).category == category


def test_timeout_is_retryable():
    class ReadTimeout(Exception):
        pass
    err = classify_exception(ReadTimeout("timed out"))
    assert err.category == ErrorCategory.TIMEOUT and err.retryable


def test_missing_api_key_is_handled_gracefully():
    config = AppConfig(api_key=None, model="gemini-3.8-flash", mock_mode=False, mock_scenario="ok")
    assert "GEMINI_API_KEY" in config.problem
    service = GeminiService(config)
    with pytest.raises(AgentError) as info:
        service.verify()
    assert info.value.category == ErrorCategory.CONFIG


def test_daily_quota_message_is_human_readable():
    err = classify_exception(FakeApiError(429, "RESOURCE_EXHAUSTED quota exceeded. Please retry in 68377s."))
    assert "daily" in err.message and "~19.0 h" in err.message
