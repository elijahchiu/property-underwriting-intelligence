# Property Underwriting Intelligence

An interactive real-estate research demo and a reproducible Python underwriting pipeline.

The demo follows a sample property from market research through renovation scope, financing scenarios, and a printable report. The Python pipeline shows how property evidence moves through seven underwriting steps.

> **Demo only:** All properties, markets, sales, rents, renovation costs, and outcomes are fictional. This is not the private Roof4All application, a live address lookup, an appraisal, or investment advice.

## Run the website

Requires Python 3.11 or newer. The website uses the Python standard library and makes no external requests.

```bash
python3 -m portfolio_demo.server --port 8790
```

Then open [http://127.0.0.1:8790](http://127.0.0.1:8790). The app runs on your computer; this repository does not host a public website. Press `Ctrl-C` in the terminal to stop it.

Try this path:

1. Compare the fictional markets and browse sample listings.
2. Open a property workspace to review sample facts, sales, and asking rents.
3. Choose a renovation strategy, review the itemized estimate, and edit its amounts.
4. Change financing and operating assumptions to see NOI, DSCR, cash flow, and cash-on-cash update.
5. Compare four- and six-week construction scenarios, then print or save the report as a PDF.

![Property research dashboard with fictional neighborhood comparisons and sample listings](docs/portfolio_overview.png)

![Editable financial assumptions, modeled outcomes, and reconciled project uses](docs/portfolio_financials.png)

[View the two-page sample acquisition report](docs/portfolio_report_sample.pdf) (fictional data).

## How the renovation estimate works

The estimate uses six fictional project records. It ranks them by market (30%), property type (15%), construction era (15%), living area (25%), and basement presence (15%). For each selected work category, the app uses a similarity-weighted average of the five closest records. Flooring, paint, and basement-finish work use fictional per-square-foot rates; other items use package prices from the sample records.

Each line shows its estimate, supporting sample count, method, and observed range. The low and high are the smallest and largest values among the selected examples; they are not confidence bounds. The selected strategy controls which work packages appear. The estimate is editable and labeled `SYNTHETIC_SCENARIO_ONLY`; it is not an inspection, quote, paid cost, or recommendation for a real property.

### Small synthetic holdout exercise

Run the reproducible evaluation:

```bash
python -m portfolio_demo.evaluation
```

The evaluator holds out each of the six fictional projects in turn and predicts its recorded work categories from the other five. In this small fixture, it compares 53 component costs and reports $911.66 mean absolute error across those components and 15.00% mean absolute percentage error on tracked-component sums. Basement-finish costs are excluded because the fixture has no basement-area quantities.

These results describe only six invented examples. They do not measure Roof4All performance, contractor-cost accuracy, or real-world renovation-cost accuracy. See [the method and full results](docs/synthetic_data_and_model_evaluation.md).

## Financial and timing scenarios

The calculator uses the values entered in the demo to show rent, vacancy, expenses, leverage, interest rate, term, closing costs, and reserves flowing into NOI, debt service, DSCR, cash flow, and project uses. The timing comparison holds the selected scenario constant, with rent paused during repair and lease-up and a separate carry cost applied. These are calculations on fictional assumptions, not rent forecasts or construction-duration predictions.

## Run the Python pipeline

The pipeline runs seven stages: property-data review, condition, renovation scope, comparable sales/value, rent/HCV, financials, and decision readiness. It keeps missing evidence visible, separates asking rent from achieved rent, prevents duplicate comparable and scope contributions, and leaves scenario assumptions separate from evidence-based outputs.

Install the package and run its examples:

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

The pipeline uses fictional fixtures. It is not a trained nationwide prediction service and does not include Roof4All's private historical contractor records or realized construction outcomes. A `READY` result means only that a synthetic fixture passed the configured checks; it is not a verified property valuation or acquisition approval. See the [sample report](docs/demo_report.txt) and [validation record](docs/validation.md).

## Data and licensing

- The website and pipeline use fictional example data; no live sources, APIs, provider credentials, company files, or property photos are included.
- The synthetic figures are not measured market performance or validated real-world predictions.
- Asking rent, HCV references, provider AVMs, and scenario returns are not achieved rent, approved contract rent, verified appraisals, or investment outcomes.
- Unknown expenses and concealed repair needs remain unknown; they are not treated as zero.
- The report is a planning example, not a lender-certified Scope of Work or contractor quote.
- The public repository has no open-source license. Ask the repository owner before reusing its code; company rights may also apply.

## Project notes

- [Architecture](docs/architecture.md)
- [Synthetic data and holdout results](docs/synthetic_data_and_model_evaluation.md)
- [Construction timing example](docs/timing_sensitivity_report.txt)
- [Validation record](docs/validation.md)
- [Feature comparison and release boundaries](docs/public_portfolio_feature_comparison.md)
- [Release record](docs/release_readiness.md)

The interactive demo and pipeline are published on GitHub `main`. The website runs locally; it does not have a public hosted URL.
