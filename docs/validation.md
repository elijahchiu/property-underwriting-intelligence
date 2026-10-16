# Public edition validation

All checks below were run locally. The first check covered the seven-engine package; the later check covered the package and interactive website. GitHub Actions is configured for Python 3.11–3.13, but this record does not claim a hosted CI run.

For the initial package check, I built and installed a wheel in a fresh Python 3.12.7 environment on macOS arm64. Tests ran outside the source tree, and imports came from the installed package.

## Initial seven-engine package check

- Installation: succeeded; built and installed `property-underwriting-intelligence 0.2.0`.
- Public tests: **38 tests passed** (`Ran 38 tests in 0.630s`, `OK`). Includes the original 3 financial tests and 35 new pipeline/evidence tests.
- Dependency check: `No broken requirements found.`
- Installed populated CLI: exit 0; output matched `docs/demo_report.txt` byte-for-byte.
- Installed insufficient-evidence CLI: exit 0; correctly abstained.
- Installed identity-conflict CLI with JSON output: exit 0; valid JSON with blocked identity.
- Original financial demo: exit 0; scenario-only profile and balanced sources/uses.
- No hosted CI run claimed. Python 3.11 and 3.13 are configured in CI but were not locally exercised.

| Synthetic case | ARV | Monthly market rent | Priced rehab subset | Scenario NOI | Scenario DSCR | Evidence readiness | Blockers |
|---|---:|---:|---:|---:|---:|---|---:|
| Populated | 159,965 | 1,250 | 2,000 | 8,207.50 | 1.22272623 | DUE_DILIGENCE_REQUIRED | 14 |
| Insufficient | unavailable | unavailable | unavailable | unavailable | unavailable | DUE_DILIGENCE_REQUIRED | 15 |
| Identity conflict | unavailable | unavailable | 2,000* | unavailable | unavailable | BLOCKED_PROPERTY_IDENTITY | 17 |

*The identity-conflict case retains the separately supplied fictional condition/quote context. It cannot clear identity, support valuation/rent, or enable acquisition. Its next action is identity resolution.

The populated financial scenario reports total project cost **116,000.00**, monthly cash flow **124.59**, and balanced sources/uses. The separate evidence-mode financial path has no eligible real inputs and does not calculate NOI. All listed amounts are fictional demonstrations, not recommended underwriting assumptions.

## Installed dependency versions

```text
annotated-types==0.8.0
pydantic==2.13.5
pydantic_core==2.46.5
typing-inspection==0.4.4
typing_extensions==4.16.0
```

These are the versions actually tested, not a promise that all future compatible dependency releases produce identical behavior. Runtime requirements remain declared in `pyproject.toml`.

## Interactive portfolio edition check (2026-10-15)

I built and installed a wheel in a fresh Python 3.12 environment using locally available dependencies; no package-index access was needed. I launched the installed website outside the source checkout and opened it in a browser on loopback.

- Final package build/install: succeeded as `property-underwriting-intelligence 0.2.0`; installed wheel SHA-256 `1e92cb71a79c5ff1f4cbb37975fba839ba1616cf136f2d2a4e4deb89a014bba5`.
- Dependency check: `No broken requirements found.`
- Full test suite after the final evidence-label change: **55 tests passed**. New tests cover synthetic data preparation, unknown market and conflicting-ID rejection, project-use reconciliation, and six property-level holdouts.
- Installed website runtime: started from the installed wheel outside the source checkout; market/property selection, evidence review, scope generation, financial calculation, timing comparison, and acquisition-report preview completed in the browser.
- Installed CLI: populated output matches `docs/demo_report.txt` byte-for-byte; insufficient-evidence case runs; identity-conflict JSON parses.
- Installed financial and timing examples: both exit successfully.
- Browser workflow: verified market selection, property workspace, scope edit, financial recalculation, timing comparison, and acquisition-report preview. No browser console errors were observed.
- Current local website screenshots show the overview and financial assumptions/results. The financial page itemizes `$153,303` into `$118,000` acquisition, `$30,763` synthetic rehab scope, `$3,540` closing costs, and `$1,000` initial reserves. The refreshed report shows the same traceable component table and labels its counts as synthetic analogs.
- Synthetic-model method demo: six leave-one-project-out predictions, 53 tracked component comparisons, $911.66 component-cost MAE, and 15.00% mean absolute percentage error for tracked-component sums. This is fictional, very small-sample method evidence only, not Roof4All or real-world performance. Basement-finish category was excluded from evaluation because synthetic area quantities are missing.
- Responsive/keyboard spot checks: at 390 × 844 there was no horizontal overflow and the navigation drawer opened; keyboard focus reached the home link. This is a spot check, not a complete accessibility audit.
- PDF: refreshed and visually checked as a clean two-page letter sample. The scope table labels its count “Synthetic analogs,” the complete $153,303 uses table reconciles on page two, and browser date/address headers are omitted.
- Network boundary: no live property data, RentCast, or other metered provider calls. The application itself is offline-only. Package build and installation used locally available build tooling and dependencies.

The portfolio website uses only fictional examples. Its similarity-weighted scope estimator and financial/timing calculations demonstrate software behavior; they do not measure out-of-sample property value, rent, or renovation-cost prediction accuracy and do not use Roof4All's private historical contractor dataset.

The separate construction-timing example compares four and six weeks under explicit fictional no-rent and carry assumptions. Its six-week case rounds to two repair-carry months. The stabilized annual cash flow remains $1,495.04 in both cases, while first-year operating cash flow changes from -$1,556.21 to -$3,081.84. Additional project uses rise by $350.00. See [the exact sample output and formulas](timing_sensitivity_report.txt).

The website and pipeline were published on GitHub `main` in commit [`599d352`](https://github.com/elijahchiu/property-underwriting-intelligence/commit/599d352f282c129fc92aa004f1cfa4b3c5246235), verified in the repository browser on 2026-10-15. The site is a local demo; GitHub does not host this Python app. No license was added. The test and browser results above are local checks, not GitHub Actions results.

## Reproduce

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m pip check
python -m unittest discover -s tests -v
underwrite-demo
underwrite-demo --case insufficient
underwrite-demo --case identity-conflict --json
python examples/run_financial_demo.py
python examples/run_timing_sensitivity.py
```

No property data service is contacted by any demo. The regression suite also runs the integrated calculation with socket creation disabled.
