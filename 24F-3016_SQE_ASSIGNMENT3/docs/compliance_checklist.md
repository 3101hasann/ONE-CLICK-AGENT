# Assignment 3 — Compliance Checklist

This maps every explicit requirement in `Assignment_3_Unit_Test_Automation.pdf`
to where it is satisfied and how it was verified. The PDF is the source of
truth; the longer task brief we were given is treated as implementation
guidance, not as additional instructor rules.

Project: **ONE-CLICK-AGENT** — https://github.com/3101hasann/ONE-CLICK-AGENT
Group: M. Hassan Ahmad (24F-3101), M. Ahmad Asghar (24F-3016)

| # | Requirement (from PDF) | Where it is satisfied | Verification | Status |
|---|---|---|---|---|
| Sub-1 | Commit project files, tests, config, docs to the group repo | Whole `docs/assignment3/`, `tests/`, `pytest.ini`, `conftest.py` | `git log` after each member commits | Pending commits (see note A) |
| Sub-2 | Make repo public, submit link on GCR | Repo settings | Manual — group action | Pending (group) |
| Sub-3 | No updates after due date | — | Manual | See note B (date) |
| Sub-4 | Excel sheet + recorded setup video in the repo | `docs/assignment3/test_cases.xlsx`, video file | Excel done; video pending recording | Excel done / video pending |
| T1 | Set up local dev environment | `docs/assignment3/setup_guide.md` | Followed on Windows; tests run in `.venv` | Done |
| T1 | Record a short setup video | `docs/assignment3/setup_video_script.md` (script + steps) | Recording is a manual group step | Script done / recording pending |
| T2 | Identify 3 different modules | `docs/assignment3/test_inventory.md` | 3 modules selected with rationale | Done |
| T2 | Apply ECP/BVA and commit notes | `docs/assignment3/test_design_notes.md` | Notes trace to real tests | Done |
| T2 | 5–10 tests per person per function of a class | `tests/unit/*`, counts in `test_inventory.md` | `pytest --collect-only` counts | Done (exceeds minimum) |
| T2 | 5–10 tests per person per class/module | `tests/unit/*` | collect-only counts | Done |
| T3 | ≥4 test cases in Excel | `docs/assignment3/test_cases.xlsx` | Opened with openpyxl; 18 cases | Done |
| T3 | Consume test data from external CSV | `tests/data/assignment3_test_data.csv` + `test_csv_driven_cases.py` | 4 CSV-driven test functions read the file | Done |
| T4 | Config for parallel + different suites | `pytest.ini`, `requirements-dev.txt` (pytest-xdist) | `pytest -n auto` passes | Done |
| T4 | Divide tests into groups | markers in `pytest.ini` + `conftest.py` | `pytest -m <group>` counts | Done |
| T4 | Parameterization / data-driven | `@pytest.mark.parametrize` across all files | collect-only shows parametrized ids | Done |
| T4 | Set execution order of groups/cases | `conftest.py` `pytest_collection_modifyitems` | documented order runs sequentially | Done |
| Rpt | Summary report before due date | `docs/assignment3/summary_report.md` | Reviewed | Done |
| Dist | Commit history shows each member | `docs/assignment3/member_contributions.md` + git history | `git log --author` | Pending commits (note A) |

## Notes / flags for the instructor

**A. Commit authorship.** The assignment grades individual contribution through
commit history. These files were prepared together in one working session. Each
member must make and verify their own commits under their own Git identity (see
`member_contributions.md` for the exact file split and commands). We have **not**
fabricated commits under another member's name.

**B. Due date.** The PDF prints the due date as **Oct 21, 2026**. If that date
has passed at submission time, the "no updates after due date" rule is a direct
conflict and needs instructor confirmation before anything is pushed.

**C. Counting interpretation for Task 2.** "5–10 tests per person for each
function of a class / each class/module" can be read two ways: (i) each member
independently writes 5–10 tests for every function, or (ii) the modules are
divided between members and each writes 5–10 per function within their own
module. Because the rubric says Task 2 is "different for all group members, based
on individual contribution", we used interpretation (ii) and documented the
per-member counts. This is flagged for confirmation in `test_inventory.md`.

**D. License.** The repository has **no LICENSE file**. "Open source" in the
task is interpreted as a public repository. We did not add a license because
that is an ownership decision for the authors; `setup_guide.md` records this and
recommends the team add one (e.g. MIT) if required.
