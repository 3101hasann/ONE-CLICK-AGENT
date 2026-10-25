# Test Inventory and Allocation Matrix — Assignment 3

Group: M. Hassan Ahmad (24F-3101), M. Ahmad Asghar (24F-3016)
Project: ONE-CLICK-AGENT

## Selected modules and rationale

We selected the three modules proposed in the brief because each contains
self-contained, deterministic logic that can be tested without the network, a
real screen, or the GUI:

1. **`app/screen_change_detector.py`** — pure image-signature and threshold
   logic; perfect for BVA on the change threshold, cell-delta and settle timing.
2. **`app/response_models.py`** — Pydantic schemas with real validation and
   coercion rules; ideal for ECP (valid/invalid classes) and negative testing.
3. **`app/config.py`** — `AgentSettings.clamp()` has explicit numeric bounds on
   eight fields (strong BVA), and `load_config`/`load_settings` have clear
   decision logic that is easy to isolate with `monkeypatch`/`tmp_path`.

Other modules (`agent_controller`, `gemini_service`, `automation_service`,
`ui`) depend on threads, the Gemini client, PyAutoGUI or Tk; they are already
covered at the integration level by the existing `tests/test_agent_controller.py`
and are less suitable for isolated unit BVA/ECP, so they were not selected.

---

## Module 1 — `app/screen_change_detector.py`  (owner: Hassan, 24F-3101)

**Purpose.** Decide whether the screen changed enough to re-send to Gemini, so
continuous mode never re-uploads an unchanged screen.

| Target | Signature | Inputs | Output | Expected behavior |
|---|---|---|---|---|
| `compute_signature` | `(Image) -> Signature` | PIL image | `Signature(size, cells, digest)` | Downscale to 96×64 grayscale, quantize to multiples of 8; `cells` length = 6144; SHA-1 digest of cells; size preserved. |
| `difference` | `(Signature, Signature, cell_delta=24) -> float` | two signatures | fraction 0.0–1.0 | 1.0 if sizes differ; 0.0 if digests equal; else fraction of cells with `abs(x-y) > cell_delta` (strict `>`). |
| `ScreenChangeDetector.check` | `(Image) -> (ChangeStatus, Signature)` | PIL image | status + signature | UNCHANGED if diff vs processed `< threshold`; SETTLING until stable for `settle_time_s` (uses `>=`); then CHANGED. |
| `.reset` / `.mark_processed` | state mutators | — / Signature | None | reset clears baseline; mark_processed sets baseline and clears pending. |

**Case categories.** Normal (typical pages), boundary (cell_delta 23/24/25,
settle 0.99/1.0/1.5, threshold strict `<`), invalid/edge (resolution change →
1.0), equivalence (identical vs same-digest vs size-differ vs partial change).

**Existing coverage.** `tests/test_screen_change_detector.py` (4 tests):
identical screens, change after settling, cursor ignored, resolution change.
These are kept as regression. The new file adds finer boundary and
function-level tests.

**New tests.** `tests/unit/test_screen_change_detector_assignment3.py` — **27**.

---

## Module 2 — `app/response_models.py`  (owner: Ahmad, 24F-3016)

**Purpose.** Validate and normalize every structured Gemini response before the
app acts on it.

| Target | Inputs | Output | Expected behavior |
|---|---|---|---|
| `parse_model_output` | `(model_cls, raw)` where raw is str/dict/None | model instance or raises `AgentError` | None/blank → EMPTY_RESPONSE; invalid JSON / non-object / schema failure → MALFORMED_RESPONSE; code-fenced JSON accepted. |
| `FormField.confidence` | number or string | float 0.0–1.0 | `>1` treated as a percentage (`/100`), then clamped to `[0,1]`; non-numeric → 0.0. |
| `FeedbackQuestion.chosen_index` | number or string | int | `int(value)`; non-int (e.g. `"2.5"`, `"x"`) → -1. |
| `FeedbackQuestion.click_x/click_y` | number or string | float | kept if `0 ≤ v ≤ 1000`, else -1.0; non-numeric → -1.0. |
| `FeedbackQuestion.has_click` | — | bool | True only when both coords ≥ 0. |
| `_as_list` / null-normalizer | None/str/list | list / default | None → default; non-empty str → `[str]`; empty str → `[]`. |

**Case categories.** Valid classes (dict, JSON, fenced), invalid classes
(truncated JSON, lists, scalars, bad literal), missing required fields,
percentage vs fraction confidence, boundary coords (0, 1000, 1001, -0.01),
null normalization, model defaults.

**Existing coverage.** `tests/test_response_models.py` already tests the happy
path, fenced JSON, malformed/empty, missing fields, percentage confidence and
null normalization (kept as regression). The new file adds systematic
ECP/BVA/negative coverage of the coercion validators and `has_click`.

**New tests.** `tests/unit/test_response_models_assignment3.py` — **60**.

---

## Module 3 — `app/config.py`  (shared: Hassan + Ahmad)

**Purpose.** Load configuration from `.env` + `settings.json` and keep settings
within safe bounds.

| Target | Inputs | Output | Expected behavior |
|---|---|---|---|
| `AgentSettings.clamp` | self | self | Clamp 8 numeric fields to documented bounds; int fields stay int; returns self. |
| `AppConfig.problem` | self | str or None | mock → None; no key → mentions GEMINI_API_KEY; key but no model → mentions GEMINI_MODEL; full → None. |
| `load_config` | optional env file | `AppConfig` | Placeholder key → None; empty/placeholder model → DEFAULT_MODEL; mock flag parses `1/true/yes`; thinking defaults to `minimal`; scenario lowercased, defaults `ok`. |
| `load_settings` / `save_settings` | JSON path | `AgentSettings` / file | Missing/malformed file → defaults; unknown keys ignored; values clamped on load; round-trips. |

**Clamp bounds (used for BVA):**

| Field | Min | Max | Type |
|---|---|---|---|
| monitor_interval_s | 0.5 | 60.0 | float |
| change_threshold | 0.0005 | 0.5 | float |
| settle_time_s | 0.0 | 10.0 | float |
| max_image_side | 640 | 4096 | int |
| request_timeout_s | 10.0 | 300.0 | float |
| max_retries | 0 | 2 | int |
| min_request_gap_s | 0.0 | 600.0 | float |
| session_request_budget | 1 | 1000 | int |

**Existing coverage.** `AppConfig.problem`/missing-key is touched by
`tests/test_response_models.py::test_missing_api_key_is_handled_gracefully`
(regression). The new file adds full BVA of `clamp`, decision tests of
`problem`, env parsing, and settings I/O.

**New tests.** `tests/unit/test_config_assignment3.py` — **69**.

---

## CSV-driven tests (Task 3, shared)

`tests/data/test_csv_driven_cases.py` reads
`tests/data/assignment3_test_data.csv` and turns each row into a test. It spans
all three modules so the external data is genuinely exercised. — **20 tests**.

---

## Test-count matrix

Counts are from `pytest --collect-only` (each parametrized case counts as one
test, which is how pytest reports them). The minimum required is 5–10 per
function; every selected function meets or exceeds it.

| Module / class | Function | New tests | Existing (regression) | Member |
|---|---|---:|---:|---|
| screen_change_detector | compute_signature | 6 | 0 | Hassan |
| screen_change_detector | difference | 10 | 0 | Hassan |
| ScreenChangeDetector | check/reset/mark_processed | 11 | 4 | Hassan |
| **Module 1 subtotal** | | **27** | **4** | **Hassan** |
| response_models | parse_model_output | 19 | ~6 | Ahmad |
| response_models | null/_as_list normalizers | 5 | 1 | Ahmad |
| FormField | confidence | 14 | 1 | Ahmad |
| FeedbackQuestion | chosen_index/click/has_click | 20 | 0 | Ahmad |
| response_models | model defaults | 2 | 0 | Ahmad |
| **Module 2 subtotal** | | **60** | **~8** | **Ahmad** |
| AgentSettings | clamp | 42 | 0 | Shared |
| AppConfig | problem | 5 | 1 | Shared |
| config | load_config | 17 | 0 | Shared |
| config | load/save_settings | 5 | 0 | Shared |
| **Module 3 subtotal** | | **69** | **1** | **Shared** |
| CSV-driven (3 modules) | 4 data-driven functions | 20 | 0 | Shared |
| **TOTAL NEW** | | **176** | | |
| Existing regression total | | | **39** | |
| **GRAND TOTAL** | | **215** | | |

### Per-member summary

| Member | Owned module | New tests owned | Shared (config + CSV) |
|---|---:|---:|---:|
| M. Hassan Ahmad (24F-3101) | screen_change_detector | 27 | config + CSV (joint) |
| M. Ahmad Asghar (24F-3016) | response_models | 60 | config + CSV (joint) |

**Counting interpretation (flagged).** We read "5–10 per person per function /
class/module" as: the modules are split between the two members (Hassan →
screen detector, Ahmad → response models), each member writes 5–10+ tests for
every function and for the class/module they own, and `config.py`, the CSV
suite and the pytest configuration are shared. This matches the rubric's
"different for all group members, based on individual contribution." If the
instructor intends each member to independently write 5–10 tests for every
function of all modules, the split should be revisited — please confirm.
