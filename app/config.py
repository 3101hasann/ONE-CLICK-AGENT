"""Configuration: environment variables (.env) plus a small JSON settings file."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# When packaged with PyInstaller, .env / settings.json / logs live next to CHEATER.exe.
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
LOG_DIR = PROJECT_ROOT / "logs"

DEFAULT_MODEL = "gemini-3.8-flash"


@dataclass
class AgentSettings:
    """User-tunable agent behaviour, persisted to settings.json (no secrets)."""

    monitor_interval_s: float = 2.0      # how often continuous mode samples the screen
    change_threshold: float = 0.02       # fraction of normalized cells that must change
    settle_time_s: float = 1.5           # debounce: screen must be stable this long
    max_image_side: int = 2000           # downscale uploads beyond this (keeps text legible)
    request_timeout_s: float = 60.0
    max_retries: int = 0                 # auto-retries cost quota; the user retries manually
    min_request_gap_s: float = 20.0      # continuous mode: minimum time between API requests
    session_request_budget: int = 20     # hard cap on API requests per app session

    def clamp(self) -> "AgentSettings":
        self.monitor_interval_s = min(max(self.monitor_interval_s, 0.5), 60.0)
        self.change_threshold = min(max(self.change_threshold, 0.0005), 0.5)
        self.settle_time_s = min(max(self.settle_time_s, 0.0), 10.0)
        self.max_image_side = int(min(max(self.max_image_side, 640), 4096))
        self.request_timeout_s = min(max(self.request_timeout_s, 10.0), 300.0)
        self.max_retries = int(min(max(self.max_retries, 0), 2))
        self.min_request_gap_s = min(max(self.min_request_gap_s, 0.0), 600.0)
        self.session_request_budget = int(min(max(self.session_request_budget, 1), 1000))
        return self


@dataclass
class AppConfig:
    api_key: str | None
    model: str
    mock_mode: bool
    mock_scenario: str
    thinking_level: str = "low"
    settings: AgentSettings = field(default_factory=AgentSettings)

    @property
    def problem(self) -> str | None:
        """A human-readable configuration problem, or None when usable."""
        if self.mock_mode:
            return None
        if not self.api_key:
            return (
                "GEMINI_API_KEY is not set. Copy .env.example to .env, add your key from "
                "https://aistudio.google.com/apikey and restart. (Or set CHEATER_MOCK_MODE=1 "
                "to explore the UI with clearly-labelled mock responses.)"
            )
        if not self.model:
            return "GEMINI_MODEL is empty. Set it in .env (e.g. gemini-3.8-flash)."
        return None


def load_settings(path: Path = SETTINGS_PATH) -> AgentSettings:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {k: v for k, v in data.items() if k in AgentSettings.__dataclass_fields__}
        return AgentSettings(**known).clamp()
    except (OSError, ValueError, TypeError):
        return AgentSettings()


def save_settings(settings: AgentSettings, path: Path = SETTINGS_PATH) -> None:
    path.write_text(json.dumps(asdict(settings.clamp()), indent=2), encoding="utf-8")


def load_config(env_file: Path | None = None) -> AppConfig:
    load_dotenv(env_file or PROJECT_ROOT / ".env")
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if api_key in ("", "your_api_key_here"):
        api_key = None
    model = (os.getenv("GEMINI_MODEL") or "").strip()
    if model in ("", "your_supported_gemini_model"):
        model = DEFAULT_MODEL
    mock = (os.getenv("CHEATER_MOCK_MODE") or "").strip().lower() in ("1", "true", "yes")
    scenario = (os.getenv("CHEATER_MOCK_SCENARIO") or "ok").strip().lower()
    thinking = (os.getenv("GEMINI_THINKING_LEVEL") or "low").strip().lower()
    return AppConfig(api_key=api_key, model=model, mock_mode=mock, mock_scenario=scenario,
                     thinking_level=thinking, settings=load_settings())
