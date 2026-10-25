# Member Contributions and Git Workflow — Assignment 3

Group members:
- **M. Hassan Ahmad — 24F-3101** (GitHub: `3101hasann`)
- **M. Ahmad Asghar — 24F-3016**

The rubric awards 2 marks for task distribution verifiable from the Git commit
history, and Tasks 2–4 are graded per member. So each member must commit **their
own** files under **their own Git identity**. This document records the agreed
split and the exact commands. We have not fabricated commits for either member.

## Ownership split

| Area | Files | Owner |
|---|---|---|
| Screen-change detection tests + its design notes | `tests/unit/test_screen_change_detector_assignment3.py`; SCD rows in `test_design_notes.md` | **Hassan (3101)** |
| Response-model validation tests + its design notes | `tests/unit/test_response_models_assignment3.py`; RM rows in `test_design_notes.md` | **Ahmad (3016)** |
| Configuration tests | `tests/unit/test_config_assignment3.py` (CFG) | **Shared** |
| CSV data + CSV-driven tests | `tests/data/assignment3_test_data.csv`, `tests/data/test_csv_driven_cases.py` | **Shared** |
| Excel workbook | `docs/assignment3/test_cases.xlsx`, `generate_excel.py` | **Shared** |
| Pytest config: markers, parallel, order | `pytest.ini`, `conftest.py`, `requirements-dev.txt` | **Shared** |
| Setup guide, video script, execution guide | `docs/assignment3/setup_guide.md`, `setup_video_script.md`, `test_execution_guide.md` | **Shared** |
| Inventory, design notes, summary, checklist | the remaining `docs/assignment3/*.md` | **Shared** |
| Setup video recording | `docs/assignment3/setup_video.mp4` | **Shared (not yet recorded)** |

For shared items, the two members should split the individual commits between
them (for example, Hassan commits the config tests and the CSV suite; Ahmad
commits the pytest configuration and the Excel workbook) so both identities
appear in the history. Decide this together and keep it honest.

## Git identity (set once per member, per machine)

```powershell
git config user.name  "M. Hassan Ahmad"      # on Hassan's machine
git config user.email "hassan-github-email@example.com"
```
```powershell
git config user.name  "M. Ahmad Asghar"      # on Ahmad's machine
git config user.email "ahmad-github-email@example.com"
```
Use each member's real GitHub-linked email so commits attribute correctly.

## Suggested commit sequence

Work on a branch, each member committing their own files:

```powershell
# Hassan (3101)
git add tests/unit/test_screen_change_detector_assignment3.py
git commit -m "test(screen-detector): ECP/BVA unit tests for change detection (A3)"

# Ahmad (3016) — on his machine / session
git add tests/unit/test_response_models_assignment3.py
git commit -m "test(response-models): ECP/BVA validation tests (A3)"

# Shared (split between members, each committing their part)
git add tests/unit/test_config_assignment3.py
git commit -m "test(config): BVA clamp + load_config + settings I/O (A3)"

git add tests/data/assignment3_test_data.csv tests/data/test_csv_driven_cases.py
git commit -m "test(data): external CSV + data-driven tests (A3)"

git add pytest.ini conftest.py requirements-dev.txt
git commit -m "chore(test): markers, parallel (xdist), ordering config (A3)"

git add docs/assignment3/
git commit -m "docs(a3): inventory, design notes, setup, execution, summary"
```

## Verifying the split after committing

```powershell
git log --oneline --author="Hassan"
git log --oneline --author="Ahmad"
git shortlog -sne
```

## Honesty statement

These test files and documents were prepared in a shared working session with
tooling assistance. The ownership table reflects who is responsible for
understanding, explaining and committing each part during the evaluation. No
commit should claim a member authored work they cannot explain. If the real
division of labour differs from the table above, update this file to match
before submitting — the Git history must reflect what actually happened.
