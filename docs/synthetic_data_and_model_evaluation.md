# Synthetic data preparation and renovation-cost evaluation

This public example demonstrates reproducible processing and model evaluation without exposing Roof4All's private project records. **Every input and result described here is fictional. None is evidence of Roof4All model performance.**

## Preparation and integration

`portfolio_demo/data.json` contains separate market, property, comp, and scope-project records. `portfolio_demo/data_pipeline.py` creates a derived analytical view while preserving that source file:

1. Trims IDs and normalizes join keys such as market IDs.
2. Removes exact duplicate IDs and rejects conflicting duplicate IDs.
3. Parses numeric property and cost fields and rejects invalid/non-finite values.
4. Checks property and project references against the market table.
5. Joins each fictional property to its market label and counts its linked sale and rental observations.
6. Reports row counts and exact duplicate removals in a quality summary.

The scope estimator and holdout evaluator both consume the prepared scope-project records. Tests cover whitespace normalization, joins, unknown market references, and conflicting identifiers. The pipeline deliberately does not represent document extraction, real property matching, outside source verification, or the private Roof4All corpus.

## Estimate method

For a subject and each selected work category, the app ranks all six fictional renovation records using these fixed, readable weights: market 30%, property type 15%, construction era 15%, living area 25%, and basement presence 15%. It selects the five closest examples and computes a similarity-weighted mean of observed package costs. Flooring and paint multiply synthetic per-square-foot rates by the subject's stated area; bathroom costs scale by the subject-to-analog bath count. The displayed low and high are the minimum and maximum among the selected observations, not statistical confidence bounds.

## Property-level holdout

Run the reproducible evaluation from the repository root:

```bash
python -m portfolio_demo.evaluation
```

For each of the six fictional scope projects, the evaluator removes that entire project, predicts its recorded categories using only the other five projects, and compares the estimates to the held-out fixture. This avoids using the held-out project's own costs as analogs. Category costs are evaluated at the held-out property's feature values. Basement-finish costs are excluded from this calculation because the fixture records contain no basement-area quantity; full project totals also contain no contingency, concealed conditions, or unrecorded categories.

| Held-out synthetic record | Observed tracked components | Tracked-component sum | Predicted sum | Absolute error | Absolute percentage error |
|---|---:|---:|---:|---:|---:|
| SIM-SCOPE-01 | 9 | $30,832 | $36,944 | $6,112 | 19.82% |
| SIM-SCOPE-02 | 9 | $35,337 | $35,986 | $649 | 1.84% |
| SIM-SCOPE-03 | 9 | $28,730 | $37,247 | $8,517 | 29.64% |
| SIM-SCOPE-04 | 8 | $37,910 | $40,182 | $2,272 | 5.99% |
| SIM-SCOPE-05 | 9 | $42,691 | $42,637 | $54 | 0.13% |
| SIM-SCOPE-06 | 9 | $58,043 | $38,950 | $19,093 | 32.89% |

Aggregate descriptive results across this six-record synthetic exercise:

- 53 tracked line-item comparisons
- Component cost MAE: **$911.66**
- Tracked-component-sum MAE: **$6,116.17**
- Median absolute tracked-component-sum error: **$4,192.00**
- Mean absolute percentage error of tracked-component sums: **15.00%**

The full reproducible output is saved in [synthetic_holdout_evaluation.json](synthetic_holdout_evaluation.json). These figures describe only this tiny, deliberately fictional fixture. They must not be presented as contractor-cost accuracy, construction-cost accuracy, or Roof4All holdout performance. Six observations are too few to support a reliable performance claim, and this is a method demonstration rather than a validated production estimator.

## Reconcile modeled project uses

The sample report's $153,303 uses total is now itemized on the Financials page and in the PDF:

| Component | Formula / basis | Amount |
|---|---|---:|
| Purchase assumption | Employee-entered scenario input | $118,000 |
| Preliminary rehab scope | Selected synthetic scope total | $30,763 |
| Closing-cost assumption | 3.0% × $118,000 | $3,540 |
| Initial reserves | Employee-entered assumption | $1,000 |
| **Total project uses** | **Sum of four components** | **$153,303** |

Financing proceeds determine modeled cash invested separately. Construction-period carry is excluded from this base uses figure and shown separately in the timing scenarios.
