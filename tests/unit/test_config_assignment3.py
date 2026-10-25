"""Assignment 3 — unit tests for app/config.py.

Shared ownership (M. Hassan Ahmad 24F-3101 & M. Ahmad Asghar 24F-3016).

Covers AgentSettings.clamp() (Boundary Value Analysis on every numeric field),
AppConfig.problem (decision/ECP), load_config() (environment-variable parsing,
isolated with monkeypatch + a temp .env), and load_settings/save_settings
(JSON round-trip, missing/malformed files, unknown-key filtering).

Test IDs: CFG-xxx (see docs/assignment3/test_design_notes.md).
"""
from __future__ import annotations

import json

import pytest

from app.config import (DEFAULT_MODEL, AgentSettings, AppConfig, load_config, load_settings,
                        save_settings)

pytestmark = [pytest.mark.unit, pytest.mark.config]

INT_FIELDS = {"max_image_side", "max_retries", "session_request_budget"}


# --------------------------------------------------------------- clamp (BVA)
@pytest.mark.parametrize("field,raw,expected", [
    # monitor_interval_s -> [0.5, 60.0]
    ("monitor_interval_s", 0.1, 0.5), ("monitor_interval_s", 0.5, 0.5),
    ("monitor_interval_s", 30, 30.0), ("monitor_interval_s", 60.0, 60.0),
    ("monitor_interval_s", 999, 60.0),
    # change_threshold -> [0.0005, 0.5]
    ("change_threshold", 0.0, 0.0005), ("change_threshold", 0.0005, 0.0005),
    ("change_threshold", 0.25, 0.25), ("change_threshold", 0.5, 0.5),
    ("change_threshold", 1.0, 0.5),
    # settle_time_s -> [0.0, 10.0]
    ("settle_time_s", -1, 0.0), ("settle_time_s", 0.0, 0.0), ("settle_time_s", 5, 5.0),
    ("settle_time_s", 10.0, 10.0), ("settle_time_s", 50, 10.0),
    # max_image_side -> [640, 4096] (int)
    ("max_image_side", 100, 640), ("max_image_side", 640, 640), ("max_image_side", 1280, 1280),
    ("max_image_side", 4096, 4096), ("max_image_side", 9999, 4096),
    # request_timeout_s -> [10.0, 300.0]
    ("request_timeout_s", 1, 10.0), ("request_timeout_s", 10.0, 10.0),
    ("request_timeout_s", 60, 60.0), ("request_timeout_s", 300.0, 300.0),
    ("request_timeout_s", 999, 300.0),
    # max_retries -> [0, 2] (int)
    ("max_retries", -5, 0), ("max_retries", 0, 0), ("max_retries", 1, 1),
    ("max_retries", 2, 2), ("max_retries", 9, 2),
    # min_request_gap_s -> [0.0, 600.0]
    ("min_request_gap_s", -1, 0.0), ("min_request_gap_s", 0.0, 0.0),
    ("min_request_gap_s", 20, 20.0), ("min_request_gap_s", 600.0, 600.0),
    ("min_request_gap_s", 9999, 600.0),
    # session_request_budget -> [1, 1000] (int)
    ("session_request_budget", 0, 1), ("session_request_budget", 1, 1),
    ("session_request_budget", 20, 20), ("session_request_budget", 1000, 1000),
    ("session_request_budget", 99999, 1000),
])
def test_clamp_keeps_each_field_within_bounds(field, raw, expected):
    settings = AgentSettings()
    setattr(settings, field, raw)
    settings.clamp()
    assert getattr(settings, field) == expected
    if field in INT_FIELDS:
        assert isinstance(getattr(settings, field), int)


@pytest.mark.smoke
def test_clamp_returns_self_for_chaining():
    settings = AgentSettings()
    assert settings.clamp() is settings


def test_default_settings_are_already_within_bounds():
    settings = AgentSettings()
    before = {f: getattr(settings, f) for f in AgentSettings.__dataclass_fields__}
    settings.clamp()
    after = {f: getattr(settings, f) for f in AgentSettings.__dataclass_fields__}
    assert before == after


# --------------------------------------------------------------- AppConfig.problem (decision)
@pytest.mark.parametrize("mock,api_key,model,expect_none,contains", [
    (True, None, "", True, None),                       # mock mode: always usable
    (True, None, "", True, None),
    (False, None, "m", False, "GEMINI_API_KEY"),        # no key
    (False, "k", "", False, "GEMINI_MODEL"),            # key but no model
    (False, "k", "m", True, None),                      # fully configured
])
def test_problem_reports_configuration_gaps(mock, api_key, model, expect_none, contains):
    cfg = AppConfig(api_key=api_key, model=model, mock_mode=mock, mock_scenario="ok")
    if expect_none:
        assert cfg.problem is None
    else:
        assert cfg.problem is not None and contains in cfg.problem


# --------------------------------------------------------------- load_config (env parsing)
def _env(monkeypatch, **values):
    for name in ("GEMINI_API_KEY", "GEMINI_MODEL", "CHEATER_MOCK_MODE",
                 "CHEATER_MOCK_SCENARIO", "GEMINI_THINKING_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def _blank_env_file(tmp_path):
    path = tmp_path / "empty.env"
    path.write_text("", encoding="utf-8")
    return path


@pytest.mark.parametrize("raw_key,expected", [
    ("your_api_key_here", None), ("", None), ("   ", None), ("AIza-real-key", "AIza-real-key"),
])
def test_api_key_placeholder_becomes_none(monkeypatch, tmp_path, raw_key, expected):
    _env(monkeypatch, GEMINI_API_KEY=raw_key)
    assert load_config(_blank_env_file(tmp_path)).api_key == expected


@pytest.mark.parametrize("raw_model,expected", [
    ("", DEFAULT_MODEL), ("your_supported_gemini_model", DEFAULT_MODEL),
    ("gemini-3.5-flash-lite", "gemini-3.5-flash-lite"),
])
def test_model_default_and_override(monkeypatch, tmp_path, raw_model, expected):
    _env(monkeypatch, GEMINI_API_KEY="k", GEMINI_MODEL=raw_model)
    assert load_config(_blank_env_file(tmp_path)).model == expected


@pytest.mark.parametrize("flag,expected", [
    ("1", True), ("true", True), ("YES", True), ("Yes", True),
    ("0", False), ("no", False), ("", False), ("maybe", False),
])
def test_mock_mode_flag_parsing(monkeypatch, tmp_path, flag, expected):
    _env(monkeypatch, GEMINI_API_KEY="k", CHEATER_MOCK_MODE=flag)
    assert load_config(_blank_env_file(tmp_path)).mock_mode is expected


def test_thinking_level_defaults_to_minimal(monkeypatch, tmp_path):
    _env(monkeypatch, GEMINI_API_KEY="k")
    assert load_config(_blank_env_file(tmp_path)).thinking_level == "minimal"


def test_scenario_defaults_to_ok_and_lowercases(monkeypatch, tmp_path):
    _env(monkeypatch, GEMINI_API_KEY="k", CHEATER_MOCK_SCENARIO="Rate_Limit")
    cfg = load_config(_blank_env_file(tmp_path))
    assert cfg.mock_scenario == "rate_limit"
    _env(monkeypatch, GEMINI_API_KEY="k")
    assert load_config(_blank_env_file(tmp_path)).mock_scenario == "ok"


# --------------------------------------------------------------- settings JSON I/O
@pytest.mark.smoke
def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    settings = AgentSettings(monitor_interval_s=3.0, max_retries=2, session_request_budget=50)
    save_settings(settings, path)
    loaded = load_settings(path)
    assert loaded.monitor_interval_s == 3.0
    assert loaded.max_retries == 2
    assert loaded.session_request_budget == 50


def test_load_settings_missing_file_returns_defaults(tmp_path):
    loaded = load_settings(tmp_path / "does_not_exist.json")
    assert loaded == AgentSettings()


def test_load_settings_malformed_json_returns_defaults(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ not valid json", encoding="utf-8")
    assert load_settings(path) == AgentSettings()


def test_load_settings_ignores_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"monitor_interval_s": 2.5, "totally_unknown": 123}),
                    encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.monitor_interval_s == 2.5
    assert not hasattr(loaded, "totally_unknown")


def test_load_settings_clamps_out_of_range_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"session_request_budget": 99999, "max_retries": 9}),
                    encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.session_request_budget == 1000   # clamped max
    assert loaded.max_retries == 2                  # clamped max
