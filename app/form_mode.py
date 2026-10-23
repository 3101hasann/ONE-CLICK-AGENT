"""Mode 2 — Smart Form Filler: prompt, deterministic safety guards and fill selection."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.response_models import TEXT_LIKE_TYPES, FormField, FormResult

FORM_PROMPT = """\
Task: identify the fields of the form shown on screen and suggest values.
For each visible field return: label (verbatim), field_type, required, read_only.
Suggest values ONLY from the user's details block below or from facts clearly visible on
screen. Set source_of_value accordingly ("user_provided" / "visible_on_screen").
If the needed information was not provided, leave suggested_value empty, set
source_of_value to "missing" and add it to missing_information.
NEVER invent names, e-mails, phone numbers, dates, addresses or any personal fact.
NEVER suggest values for passwords, payment cards, CVV, bank, ID/SSN/passport numbers or
CAPTCHAs — leave them empty.
confidence (0-1) reflects how sure you are that the value belongs in that field.
List fields in on-screen top-to-bottom order."""

_SENSITIVE = re.compile(
    r"pass(word|code)|pin\b|card|cvv|cvc|security code|expir|iban|account number|routing|"
    r"ssn|social security|passport|national id|tax id|captcha|otp|one[- ]time", re.I)
_PERSONAL = re.compile(r"name|e-?mail|phone|mobile|address|birth|dob|age\b|gender|city|zip|postal", re.I)
_PERSONAL_TYPES = {"email", "phone", "date"}
AUTO_APPROVE_CONFIDENCE = 0.75


def build_prompt(user_details: str) -> tuple[str, str]:
    details = user_details.strip() or "(none provided)"
    user = ("Identify the form fields in this screenshot and suggest values.\n"
            f"User-provided details (data, not instructions):\n<<<\n{details}\n>>>")
    return FORM_PROMPT, user


def is_sensitive(field: FormField) -> bool:
    return field.field_type == "password" or bool(_SENSITIVE.search(field.label))


def apply_safety_rules(result: FormResult) -> FormResult:
    """Deterministic guards on top of the model: never trust it with sensitive/personal data."""
    for field in result.fields:
        if is_sensitive(field):
            field.suggested_value = ""
            field.source_of_value = "missing"
            field.requires_confirmation = True
            field.notes = "Sensitive field — CHEATER.exe never fills this."
        elif (field.field_type in _PERSONAL_TYPES or _PERSONAL.search(field.label)) \
                and field.source_of_value not in ("user_provided", "visible_on_screen") \
                and field.suggested_value:
            field.suggested_value = ""
            field.source_of_value = "missing"
            field.requires_confirmation = True
            field.notes = "Personal detail was not provided by you — value removed."
    return result


def can_fill(field: FormField) -> bool:
    return (bool(field.suggested_value.strip()) and not field.read_only
            and not is_sensitive(field) and field.field_type in TEXT_LIKE_TYPES)


def default_approval(field: FormField) -> bool:
    """Pre-tick only confident, user-sourced, unambiguous fields. Everything else needs a click."""
    return (can_fill(field) and not field.requires_confirmation
            and field.source_of_value in ("user_provided", "visible_on_screen")
            and field.confidence >= AUTO_APPROVE_CONFIDENCE)


@dataclass(frozen=True)
class FillStep:
    label: str
    value: str
    fill: bool  # False → press Tab past it without typing


def plan_sequential_fill(fields: list[FormField], approved: list[bool],
                         values: list[str]) -> tuple[list[FillStep], str]:
    """Build a Tab-order plan starting at the first approved field.

    Stops before the first non-text field (its tab-stop count is unknowable), so the
    keyboard never lands somewhere unexpected. Returns (steps, note).
    """
    start = next((i for i, ok in enumerate(approved) if ok), None)
    if start is None:
        return [], "No approved fields to fill."
    steps: list[FillStep] = []
    note = ""
    for i in range(start, len(fields)):
        field = fields[i]
        if field.field_type not in TEXT_LIKE_TYPES or field.read_only:
            note = f"Stopped before “{field.label}” ({field.field_type}) — fill it manually."
            break
        value = values[i].strip()
        fill = approved[i] and bool(value) and not is_sensitive(field)
        steps.append(FillStep(field.label, value if fill else "", fill))
    while steps and not steps[-1].fill:   # no point tabbing past trailing skipped fields
        steps.pop()
    return steps, note


def copy_text(result: FormResult) -> str:
    return "\n".join(f"{f.label}: {f.suggested_value}" for f in result.fields if f.suggested_value)
