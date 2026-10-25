"""Assignment 3 — unit tests for app/response_models.py.

Owner: M. Ahmad Asghar (24F-3016).

Covers parse_model_output (the safe-parsing entry point) and the Pydantic
validation rules on the schema classes: FormField.confidence normalization,
FeedbackQuestion.chosen_index / click-coordinate coercion and the has_click
property, the null-to-empty / _as_list normalizers, and model defaults.
Techniques: ECP, BVA, negative/exception testing, decision testing and
parameterization.

Test IDs: RM-xxx (see docs/assignment3/test_design_notes.md).
"""
from __future__ import annotations

import json

import pytest

from app.error_handler import AgentError, ErrorCategory
from app.response_models import (FeedbackFormResult, FeedbackQuestion, FormField, FormResult,
                                  PracticeResult, parse_model_output)

pytestmark = [pytest.mark.unit, pytest.mark.validation]

VALID_PRACTICE = {
    "task_type": "multiple_choice", "detected_question": "2+2?", "options": ["A. 3", "B. 4"],
    "suggested_answer": "B. 4", "explanation": "Addition.", "confidence": "high",
}


# --------------------------------------------------------------- parse_model_output (ECP)
@pytest.mark.smoke
def test_valid_dict_is_parsed():
    result = parse_model_output(PracticeResult, dict(VALID_PRACTICE))
    assert result.suggested_answer == "B. 4"
    assert result.needs_user_review is True   # default applied


def test_valid_json_string_is_parsed():
    assert parse_model_output(PracticeResult, json.dumps(VALID_PRACTICE)).task_type == "multiple_choice"


def test_code_fenced_json_is_accepted():
    raw = "```json\n" + json.dumps(VALID_PRACTICE) + "\n```"
    assert parse_model_output(PracticeResult, raw).suggested_answer == "B. 4"


@pytest.mark.parametrize("raw", [None, "", "   ", "\n\t "])
def test_empty_or_none_is_empty_response(raw):
    with pytest.raises(AgentError) as info:
        parse_model_output(PracticeResult, raw)
    assert info.value.category == ErrorCategory.EMPTY_RESPONSE


@pytest.mark.parametrize("raw", ['{"detected_question": "trunc', "not json", "[1, 2, 3]", "42",
                                 '"just a string"', "true"])
def test_malformed_or_non_object_json_is_rejected(raw):
    with pytest.raises(AgentError) as info:
        parse_model_output(PracticeResult, raw)
    assert info.value.category == ErrorCategory.MALFORMED_RESPONSE


def test_non_dict_python_object_is_rejected():
    with pytest.raises(AgentError) as info:
        parse_model_output(PracticeResult, [1, 2, 3])
    assert info.value.category == ErrorCategory.MALFORMED_RESPONSE


def test_missing_required_field_names_the_field():
    data = dict(VALID_PRACTICE)
    del data["suggested_answer"]
    with pytest.raises(AgentError) as info:
        parse_model_output(PracticeResult, data)
    assert info.value.category == ErrorCategory.MALFORMED_RESPONSE
    assert "suggested_answer" in info.value.message


@pytest.mark.parametrize("bad_type", ["delete_all_files", "", "MULTIPLE_CHOICE", 7])
def test_invalid_literal_task_type_is_rejected(bad_type):
    with pytest.raises(AgentError):
        parse_model_output(PracticeResult, dict(VALID_PRACTICE, task_type=bad_type))


# --------------------------------------------------------------- null/list normalizers
def test_optional_nulls_become_defaults():
    result = parse_model_output(PracticeResult, dict(VALID_PRACTICE, options=None,
                                                     uncertainty_notes=None))
    assert result.options == [] and result.uncertainty_notes == ""


@pytest.mark.parametrize("value,expected", [(None, []), ("Clear", ["Clear"]), ("", []),
                                            (["a", "b"], ["a", "b"])])
def test_as_list_normalizes_strings_and_nulls(value, expected):
    fb = parse_model_output(FeedbackFormResult,
                            {"questions": [], "notes": ""})  # sanity: empty questions allowed
    assert fb.questions == []
    practice = parse_model_output(PracticeResult, dict(VALID_PRACTICE, options=value))
    assert practice.options == expected


# --------------------------------------------------------------- FormField.confidence (BVA)
@pytest.mark.parametrize("raw,expected", [
    (0, 0.0), (0.0, 0.0), (0.5, 0.5), (1.0, 1.0),      # already-fraction range
    (85, 0.85), (100, 1.0), (1.5, 0.015), (150, 1.0),  # percentage inputs (>1 -> /100, clamp)
    (-0.2, 0.0), (-50, 0.0),                           # negatives clamp up
    ("0.4", 0.4), ("abc", 0.0), (None, 0.0),           # strings / non-numeric / null
])
def test_form_field_confidence_normalization(raw, expected):
    assert FormField(label="X", confidence=raw).confidence == pytest.approx(expected)


def test_form_confidence_percent_via_parse():
    form = parse_model_output(FormResult, {"fields": [{"label": "Team", "confidence": 85}]})
    assert form.fields[0].confidence == pytest.approx(0.85)


# --------------------------------------------------------------- FeedbackQuestion coercion
@pytest.mark.parametrize("raw,expected", [(2, 2), ("3", 3), (-1, -1), (0, 0),
                                          ("x", -1), ("2.5", -1), (2.0, 2)])
def test_chosen_index_coercion(raw, expected):
    assert FeedbackQuestion(question="q", chosen_index=raw).chosen_index == expected


@pytest.mark.parametrize("raw,expected", [
    (500, 500.0), (0, 0.0), (1000, 1000.0),            # inside / on the 0..1000 bounds
    (1001, -1.0), (-5, -1.0), (-0.01, -1.0),           # just outside the bounds
    ("250.5", 250.5), ("nope", -1.0),                  # string parsing
])
def test_click_coordinate_coercion(raw, expected):
    assert FeedbackQuestion(question="q", click_x=raw).click_x == pytest.approx(expected)


@pytest.mark.parametrize("x,y,expected", [(100, 200, True), (-1, 200, False),
                                          (100, -1, False), (-1, -1, False), (0, 0, True)])
def test_has_click_property(x, y, expected):
    assert FeedbackQuestion(question="q", click_x=x, click_y=y).has_click is expected


# --------------------------------------------------------------- model defaults
def test_feedback_form_result_defaults():
    r = parse_model_output(FeedbackFormResult, {"questions": []})
    assert r.form_found is True and r.tone == "good" and r.questions == []


def test_feedback_question_defaults():
    q = FeedbackQuestion(question="How was it?")
    assert q.chosen_index == -1 and q.click_x == -1.0 and q.has_click is False
    assert q.options == [] and q.q_type == "other"
