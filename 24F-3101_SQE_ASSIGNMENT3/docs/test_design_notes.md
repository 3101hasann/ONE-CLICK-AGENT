# Test Design Notes (ECP / BVA) — Assignment 3

These notes explain *why* each test exists: the equivalence classes and
boundary values were derived from the actual source, not invented. Every ID
below maps to a test function in the code. Parametrized functions cover several
cases under one ID range (the CSV cases use the CSV-0xx ids directly).

Legend: ECP = Equivalence Class Partitioning, BVA = Boundary Value Analysis,
NEG = negative/exception testing, DEC = decision testing, PARAM =
parameterized, REG = regression.

---

## Module 1 — screen_change_detector (IDs SCD-###, member: Hassan 24F-3101)

File: `tests/unit/test_screen_change_detector_assignment3.py`.

### compute_signature

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| SCD-001 | size preserved | ECP | 800×600 image | `sig.size == (800,600)` |
| SCD-002 | one byte per cell | BVA | any image | `len(cells) == 6144` (96×64) |
| SCD-003 | cells quantized | ECP | any image | every byte % 8 == 0 |
| SCD-004 | identical digest | ECP | same image twice | equal digests |
| SCD-005 | different digest | ECP | 3 lines vs 8 lines | unequal digests |
| SCD-006 | digest is SHA-1 hex | ECP | any image | 40 hex chars |

### difference (boundary at cell_delta = 24, strict `>`)

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| SCD-007 | identical → 0.0 | ECP | same signature | 0.0 |
| SCD-008 | equal digest short-circuit | DEC | diff cells, same digest | 0.0 |
| SCD-009 | size differs → 1.0 | ECP/PARAM | 3 size pairs | 1.0 |
| SCD-010 | cell_delta boundary | BVA/PARAM | delta 23/24/25 on a 24-gap | 1.0 / 0.0 / 0.0 |
| SCD-011 | full change → 1.0 | BVA | 0 vs 255 cells | 1.0 |
| SCD-012 | partial change fraction | ECP | 25 of 100 cells move | 0.25 |

### ScreenChangeDetector (threshold strict `<`, settle uses `>=`)

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| SCD-013 | first change settles | ECP | settle=1.0, one check | SETTLING |
| SCD-014 | change after settle | BVA | advance to 1.0 | CHANGED |
| SCD-015 | settle timing boundary | BVA/PARAM | 0.99 / 1.0 / 1.5 | SETTLING / CHANGED / CHANGED |
| SCD-016 | zero settle → immediate | BVA | settle=0.0 | CHANGED |
| SCD-017 | processed identical → unchanged | ECP | same page after mark | UNCHANGED |
| SCD-018 | meaningful change detected | ECP | 3→10 lines | CHANGED |
| SCD-019 | resolution change | ECP | resize to 1920×1080 | CHANGED |
| SCD-020 | reset clears baseline | DEC | reset then same page | CHANGED (not UNCHANGED) |
| SCD-021 | change below threshold | BVA | threshold 0.9 | UNCHANGED |

---

## Module 2 — response_models (IDs RM-###, member: Ahmad 24F-3016)

File: `tests/unit/test_response_models_assignment3.py`.

### parse_model_output

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| RM-001 | valid dict | ECP | valid practice dict | parsed; default `needs_user_review=True` |
| RM-002 | valid JSON string | ECP | JSON text | parsed |
| RM-003 | code-fenced JSON | ECP | ```json … ``` | parsed |
| RM-004 | empty/None | NEG/PARAM | None, "", "   ", "\n\t " | EMPTY_RESPONSE |
| RM-005 | malformed / non-object | NEG/PARAM | truncated, "not json", "[1,2,3]", "42", scalar, "true" | MALFORMED_RESPONSE |
| RM-006 | non-dict python object | NEG | `[1,2,3]` | MALFORMED_RESPONSE |
| RM-007 | missing required field | NEG | drop `suggested_answer` | MALFORMED; message names field |
| RM-008 | invalid literal | NEG/PARAM | task_type bad values | MALFORMED |

### normalizers

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| RM-009 | optional nulls → defaults | ECP | options/uncertainty = None | `[]` / `""` |
| RM-010 | `_as_list` | ECP/PARAM | None/"Clear"/""/list | `[]`/`["Clear"]`/`[]`/list |

### FormField.confidence (percentage vs fraction, clamp to [0,1])

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| RM-011 | confidence normalization | BVA/PARAM | 0, 0.0, 0.5, 1.0, 85, 100, 1.5, 150, -0.2, -50, "0.4", "abc", None | see test table |
| RM-012 | percent via parse | BVA | field confidence 85 | 0.85 |

### FeedbackQuestion coercion

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| RM-013 | chosen_index coercion | ECP/NEG/PARAM | 2,"3",-1,0,"x","2.5",2.0 | 2,3,-1,0,-1,-1,2 |
| RM-014 | click coord coercion | BVA/PARAM | 500,0,1000,1001,-5,-0.01,"250.5","nope" | kept / -1.0 |
| RM-015 | has_click | DEC/PARAM | coord combinations | True only if both ≥ 0 |
| RM-016 | feedback form defaults | ECP | `{questions: []}` | form_found=True, tone="good" |
| RM-017 | feedback question defaults | ECP | only question | chosen_index=-1, has_click=False |

---

## Module 3 — config (IDs CFG-###, shared)

File: `tests/unit/test_config_assignment3.py`.

### AgentSettings.clamp — BVA per field (below-min / at-min / mid / at-max / above-max)

| ID | Field | Boundaries tested | Expected |
|---|---|---|---|
| CFG-001 | monitor_interval_s | 0.1 / 0.5 / 30 / 60.0 / 999 | 0.5 / 0.5 / 30.0 / 60.0 / 60.0 |
| CFG-002 | change_threshold | 0.0 / 0.0005 / 0.25 / 0.5 / 1.0 | clamped to [0.0005, 0.5] |
| CFG-003 | settle_time_s | -1 / 0.0 / 5 / 10.0 / 50 | clamped to [0.0, 10.0] |
| CFG-004 | max_image_side | 100 / 640 / 1280 / 4096 / 9999 | clamped to [640, 4096], int |
| CFG-005 | request_timeout_s | 1 / 10.0 / 60 / 300.0 / 999 | clamped to [10.0, 300.0] |
| CFG-006 | max_retries | -5 / 0 / 1 / 2 / 9 | clamped to [0, 2], int |
| CFG-007 | min_request_gap_s | -1 / 0.0 / 20 / 600.0 / 9999 | clamped to [0.0, 600.0] |
| CFG-008 | session_request_budget | 0 / 1 / 20 / 1000 / 99999 | clamped to [1, 1000], int |
| CFG-009 | clamp returns self | — | same object |
| CFG-010 | defaults already in bounds | REG | unchanged by clamp |

### AppConfig.problem — decision table

| ID | mock | key | model | Expected |
|---|---|---|---|---|
| CFG-011 | True | None | "" | None (usable) |
| CFG-012 | False | None | set | message contains GEMINI_API_KEY |
| CFG-013 | False | set | "" | message contains GEMINI_MODEL |
| CFG-014 | False | set | set | None |

### load_config — environment parsing (isolated with monkeypatch + temp .env)

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| CFG-015 | api key placeholder | ECP/PARAM | "your_api_key_here","","   ","real" | None / None / None / kept |
| CFG-016 | model default/override | ECP/PARAM | "", placeholder, real | DEFAULT_MODEL / DEFAULT_MODEL / kept |
| CFG-017 | mock flag parsing | ECP/PARAM | 1,true,YES,Yes,0,no,"",maybe | True×4 / False×4 |
| CFG-018 | thinking default | ECP | unset | "minimal" |
| CFG-019 | scenario default/lowercase | ECP | "Rate_Limit" / unset | "rate_limit" / "ok" |

### load_settings / save_settings

| ID | Test | Technique | Input | Expected |
|---|---|---|---|---|
| CFG-020 | save/load round-trip | ECP | custom settings | values preserved |
| CFG-021 | missing file | NEG | nonexistent path | defaults |
| CFG-022 | malformed JSON | NEG | bad json file | defaults |
| CFG-023 | unknown keys ignored | ECP | extra key in file | key dropped |
| CFG-024 | clamp on load | BVA | out-of-range in file | clamped |

---

## CSV-driven (IDs CSV-### — see `tests/data/assignment3_test_data.csv`)

File: `tests/data/test_csv_driven_cases.py`. Each CSV row id (CSV-001 … CSV-018)
is the pytest test id for that case. Four functions consume the file:

| Function | CSV rows consumed | Module exercised |
|---|---|---|
| test_clamp_from_csv | CSV-001 … CSV-008 | config.AgentSettings.clamp |
| test_confidence_from_csv | CSV-009 … CSV-012 | response_models.FormField.confidence |
| test_chosen_index_from_csv | CSV-013 … CSV-015 | response_models.FeedbackQuestion.chosen_index |
| test_difference_cell_delta_from_csv | CSV-016 … CSV-018 | screen_change_detector.difference |

`test_csv_file_is_wellformed` checks the header and reports any malformed row.
