# Public edition validation

Validated locally on Python 3.12.7 / macOS arm64 using a second fresh virtual environment and a clean export of the applied public files. The export contained no Git history, private repository files, previous virtual environment, caches, bytecode or build output.

The package was installed normally (not editable). Tests ran from a separate directory containing only the public test files; the CLI ran outside the source tree. Imports resolved to the installed `site-packages` package. This verifies independence from the source checkout and private application.

## Results

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
```

No property data service is contacted by any demo. The regression suite also runs the integrated calculation with socket creation disabled.
