"""Error categories and translation of raw exceptions into readable, actionable errors."""
from __future__ import annotations

import re
from enum import Enum


class ErrorCategory(str, Enum):
    CONFIG = "Configuration"
    AUTH = "Authentication"
    RATE_LIMIT = "Rate limit"
    BUDGET = "Request budget"
    NETWORK = "Network"
    TIMEOUT = "Timeout"
    SERVER = "Server error"
    EMPTY_RESPONSE = "Empty response"
    MALFORMED_RESPONSE = "Malformed response"
    UNSUPPORTED_CONTENT = "Unsupported content"
    SCREENSHOT = "Screenshot"
    AUTOMATION = "Automation"
    CANCELLED = "Cancelled"
    UNKNOWN = "Unexpected error"


class AgentError(Exception):
    """An error that is safe to show the user."""

    def __init__(self, category: ErrorCategory, message: str, hint: str = "",
                 retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.category = category
        self.message = message
        self.hint = hint
        self.retryable = retryable
        self.retry_after = retry_after

    def user_text(self) -> str:
        text = f"{self.category.value}: {self.message}"
        if self.hint:
            text += f"\n{self.hint}"
        return text


_RETRY_DELAY = re.compile(r"retry(?:[ _]?delay)?['\"]?\s*[:=]?\s*['\"]?(\d+(?:\.\d+)?)\s*s", re.I)
_RETRY_IN = re.compile(r"retry in\s+(\d+(?:\.\d+)?)\s*s", re.I)


def format_wait(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    if seconds >= 3600:
        return f"~{seconds / 3600:.1f} h"
    if seconds >= 60:
        return f"~{seconds // 60} min"
    return f"~{seconds} s"


def _retry_after(text: str) -> float | None:
    for pattern in (_RETRY_DELAY, _RETRY_IN):
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


_API_MESSAGE = re.compile(r"['\"]message['\"]\s*:\s*['\"](.+?)['\"]", re.S)


def _api_message(text: str) -> str | None:
    """Pull the human-readable 'message' out of a Google API error payload, if present."""
    match = _API_MESSAGE.search(text)
    if match:
        return match.group(1).strip()[:200]
    return None


def _status_code(exc: BaseException) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def classify_exception(exc: BaseException) -> AgentError:
    """Translate SDK/network exceptions into an AgentError with a readable message."""
    if isinstance(exc, AgentError):
        return exc

    text = str(exc)
    lowered = text.lower()
    code = _status_code(exc)
    names = " ".join(cls.__name__ for cls in type(exc).__mro__).lower()

    if code == 429 or "resource_exhausted" in lowered or "quota" in lowered or "rate limit" in lowered:
        wait = _retry_after(text)
        if wait is not None and wait > 3600:
            return AgentError(
                ErrorCategory.RATE_LIMIT,
                f"The daily Gemini quota for this model is used up (resets in {format_wait(wait)}).",
                "No more requests will be sent until then. Options: wait for the reset, set "
                "GEMINI_MODEL to another model (quotas are usually per model), or use a key "
                "with billing enabled.", retry_after=wait)
        return AgentError(
            ErrorCategory.RATE_LIMIT,
            "The Gemini API rate limit or quota has been reached.",
            f"Requests are blocked for {format_wait(wait or 60)}, then you can Retry. "
            "Check your quota at https://aistudio.google.com.",
            retryable=False, retry_after=wait)
    if code in (401, 403) or "api key not valid" in lowered or "api_key_invalid" in lowered \
            or "permission_denied" in lowered or "unauthenticated" in lowered:
        return AgentError(ErrorCategory.AUTH, "Gemini rejected the API key or permissions.",
                          "Check GEMINI_API_KEY in your .env file, then restart the app.")
    if code == 404 or ("not found" in lowered and "model" in lowered):
        return AgentError(ErrorCategory.CONFIG, "The configured Gemini model was not found.",
                          "Set GEMINI_MODEL in .env to a model that supports images "
                          "(e.g. gemini-3.5-flash-lite).")
    if code == 504 or "deadline_exceeded" in lowered:
        return AgentError(ErrorCategory.TIMEOUT, "Gemini did not answer before the deadline (504).",
                          "Gemini may be overloaded or the screenshot is large — retry, capture a "
                          "smaller region, or raise the request timeout in ⚙ Settings.",
                          retryable=True)
    if code is not None and 500 <= code < 600:
        return AgentError(ErrorCategory.SERVER, f"Gemini returned a server error ({code}).",
                          "This is usually temporary — try again shortly.", retryable=True)
    if code == 400:
        detail = _api_message(text)
        message = "Gemini rejected the request (400)."
        if detail:
            message = f"Gemini rejected the request (400): {detail}"
        return AgentError(ErrorCategory.UNSUPPORTED_CONTENT, message,
                          "Often a model setting (e.g. GEMINI_THINKING_LEVEL) or the capture — "
                          "check the message above, or try a smaller/clearer region.")
    if "timeout" in names or "timed out" in lowered or "deadline" in lowered:
        return AgentError(ErrorCategory.TIMEOUT, "The Gemini request timed out.",
                          "Check your connection and try again.", retryable=True)
    if any(n in names for n in ("connecterror", "networkerror", "connectionerror", "gaierror")) \
            or "getaddrinfo" in lowered or "connection" in lowered:
        return AgentError(ErrorCategory.NETWORK, "Could not reach the Gemini API.",
                          "Check your internet connection and try again.", retryable=True)
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return AgentError(ErrorCategory.CONFIG, f"A required dependency is missing: {exc}",
                          "Run: pip install -r requirements.txt")
    return AgentError(ErrorCategory.UNKNOWN, f"{type(exc).__name__}: {text[:200]}",
                      "The app is still running — you can retry.")
