"""Mode 3 — Feedback Form Filler.

Reads a feedback / survey / evaluation form on screen and, for a tone the user picks, chooses
the matching option for each question and drafts any free-text comments. Choices are shown for
the user to click (selecting radios/scales can't be automated safely); comments can be typed
into the focused box via the same clipboard-paste path the Form Filler uses.
"""
from __future__ import annotations

from app.response_models import FeedbackFormResult

TONE_LABELS = {
    "very_good": "Very good (highly positive)",
    "good": "Good (positive)",
    "normal": "Normal (neutral)",
    "bad": "Bad (negative)",
    "very_bad": "Very bad (highly negative)",
}

FEEDBACK_FORM_PROMPT = """\
Task: help the user fill out the feedback / survey / evaluation form shown on screen so it
expresses the overall sentiment given in the user's message. Read EVERY visible question in
top-to-bottom order. For each question return:
- question: the question text, verbatim ([unclear] for unreadable parts).
- q_type: single_choice (one radio option), rating_scale (1-5, Likert, stars, etc.),
  multi_choice (checkboxes), text (free comment box), or other.
- options: the selectable labels verbatim, in the order shown. Empty list for text questions.
- chosen_index: 0-based index into options of the option that best matches the desired
  sentiment. For a rating scale, map sentiment to position (very_good = the most positive
  end, very_bad = the most negative end, normal = the middle). Use -1 for text questions.
- chosen_option: the verbatim text of that chosen option. "" for text questions.
- comment: for text questions ONLY, a short, natural, honest-sounding answer that matches the
  desired sentiment and the question. Keep it specific but safe and generic. "" for choices.
- click_x, click_y: for CHOICE questions, the center of the FIRST option's clickable control
  (the LEFTMOST option in a horizontal row, or the TOPMOST in a vertical list) — NOT the chosen
  one. For TEXT questions, the center of the comment input box. Numbers 0-1000 normalized to the
  image (x: 0=left, 1000=right; y: 0=top, 1000=bottom). Use -1 if you cannot tell.
- orientation: for choice questions, "horizontal" if the options run left-to-right in a row,
  "vertical" if they are stacked top-to-bottom. "unknown" for text/other.
- required: true if the question is marked required.
Rules:
- Use ONLY the options and questions actually visible. NEVER invent options or questions.
- Keep the sentiment consistent across all questions.
- If no feedback/survey form is visible, set form_found=false and explain in notes."""


def build_prompt(tone: str) -> tuple[str, str]:
    label = TONE_LABELS.get(tone, TONE_LABELS["good"])
    user = (f"Desired overall sentiment for this feedback: {label}.\n"
            "Fill out the feedback form shown in the screenshot to express exactly that "
            "sentiment, choosing the matching option for every question.")
    return FEEDBACK_FORM_PROMPT, user


def reconcile(result: FeedbackFormResult) -> FeedbackFormResult:
    """Keep chosen_index and chosen_option consistent, and clamp anything out of range."""
    for q in result.questions:
        n = len(q.options)
        if n == 0:
            q.chosen_index, q.chosen_option = -1, ""
            continue
        if not (0 <= q.chosen_index < n):
            # Try to recover the index from the option text the model returned.
            match = next((i for i, opt in enumerate(q.options)
                          if opt.strip().lower() == q.chosen_option.strip().lower()), -1)
            q.chosen_index = match
        if 0 <= q.chosen_index < n:
            q.chosen_option = q.options[q.chosen_index]
        else:
            q.chosen_option = ""
        q.comment = ""  # choice questions never carry a comment
    return result


def copy_text(result: FeedbackFormResult) -> str:
    lines = []
    for q in result.questions:
        answer = q.chosen_option or q.comment
        if answer:
            lines.append(f"{q.question} -> {answer}")
    return "\n".join(lines)
