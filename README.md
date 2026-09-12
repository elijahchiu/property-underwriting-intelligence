# Property Underwriting Intelligence

**Seven underwriting engines. Traceable evidence. Explicit abstention.**

An offline, evidence-aware property underwriting portfolio project that carries structured property facts through condition review, rehab scope, comparable sales, rental/HCV evidence, financial analysis, and decision readiness. It calculates what the inputs support and explains what is still missing.

The public edition runs real reusable engine logic against **entirely fictional fixtures**. It is a reproducible engineering demonstration, not a nationwide address lookup service, an appraisal, or an autonomous acquisition product.

```text
Property / data trust → Condition → Rehab scope
          │                │            │
          └────────────────┴────────────┤
                                       ↓
                              ARV / comparable sales
                                       ↓
                               Market rent / HCV
                                       ↓
                            Evidence-based financials
                                       ↓
                               Decision readiness

Synthetic financial assumptions → separate scenario overlay
                                  (never clears evidence blockers)
```

## Run the seven-engine demo

Requires Python 3.11 or newer. Installation downloads Pydantic and its dependencies; running the demos needs **no credentials, network, database, private files, or property photos**.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
underwrite-demo
```

On Windows, activate with `.venv\Scripts\activate`.

The installed command works from any directory. Equivalent entry point:

```bash
python -m property_underwriting.demo
```

Default output excerpt:

```text
ENGINE / READINESS
1. PROPERTY_DATA      PARTIAL
2. CONDITION          PARTIAL
3. REHAB              PARTIAL
4. VALUATION          READY
5. RENT_HCV           PARTIAL
6. FINANCIALS         INSUFFICIENT
7. DECISION           DUE_DILIGENCE_REQUIRED

Synthetic ARV: 159965 | accepted sales: 3
Synthetic market rent/month: 1250
Priced rehab subset only: 2000.0

SEPARATE SYNTHETIC FINANCIAL SCENARIO (does not clear blockers)
Financial profile: SCENARIO_ONLY; sources and uses: BALANCED
TOTAL_PROJECT_COST: 116,000.00 [SCENARIO_ONLY]
NET_OPERATING_INCOME: 8,207.50 [SCENARIO_ONLY]
DSCR: 1.22 [SCENARIO_ONLY]
MONTHLY_CASH_FLOW: 124.59 [SCENARIO_ONLY]
```

`READY` for valuation means this **fictional comp set** meets the engine's configured support rules. It is not a verified real-property valuation. The $2,000 rehab figure prices only the fictional paint scope; the financial scenario separately assumes a complete $35,000 rehab base plus explicit allowances. The small priced subset is never promoted into a complete budget.

The full report lists 14 readiness blockers and orders the next actions by dependency. It deliberately does not turn profitable scenario arithmetic into an acquisition recommendation. See the [complete sample report](docs/demo_report.txt).

### See the engine refuse unsupported answers

```bash
# Remove sale/rental comps, condition evidence, quotes, and HCV reference.
underwrite-demo --case insufficient

# Conflicting equally authoritative area observations block identity and values.
underwrite-demo --case identity-conflict

# Inspect all six upstream records plus Engine 7, including provenance pointers.
underwrite-demo --json --output reports/seven_engine.json

# Inspect readiness without the scenario overlay.
underwrite-demo --no-scenario
```

The insufficient case produces no ARV, market rent, or rehab estimate, and no scenario NOI/DSCR. The identity-conflict case returns `BLOCKED_PROPERTY_IDENTITY`. The original financial-only example also remains runnable:

```bash
python examples/run_financial_demo.py
```

## What is implemented

| Engine | Public capability | Boundary retained |
|---|---|---|
| 1. Property/data trust | Typed observations, source-priority reconciliation, area-basis conflicts, missing/future/failed evidence handling | No live address/parcel resolution; fixture identity and regulatory/hazard states are explicit synthetic inputs |
| 2. Condition | Component taxonomy, dated evidence admission, remote observability limits, conflict-aware aggregation | No images or automated vision; one fictional inspection record, with unobserved systems remaining unknown |
| 3. Rehab | Scope grouping, inspection exposures, quantity-authority rules, contractor-evidence selection, cost overlap ledger | Only reviewed compatible scope can be priced; no private historical cost library or complete rehab inference |
| 4. ARV/valuation | Closed-sale admission, deduplication, expanding comp tiers, similarity weights, outlier downweighting, weighted value ranges | Minimum support required; no invented dollar adjustments or calibrated accuracy claims |
| 5. Rent/HCV | Separate asking/achieved rental cohorts, comp admission/deduplication, reference-only HCV arithmetic | No PHA lookup, schedule ingestion, utility schedule selection, or contract-rent approval |
| 6. Financials | Evidence gates, NOI, DSCR, cash flow, cash-on-cash, sources/uses, debt, exit/refinance and scenario utilities | Missing inputs stay unavailable; synthetic pipeline outputs enter evidence mode only as references |
| 7. Decision/readiness | Contract and identity checks, weakest-domain readiness, provenance-linked blockers, ordered next actions | Combined ARV/HCV review path; human acquisition policy disabled |

The public pipeline executes all seven stages. It uses small public adapters around extracted generic algorithms instead of importing the internal application's file loaders or orchestration dependencies. The [architecture and extraction notes](docs/architecture.md) describe exactly what is reused and what is newly adapted.

## Evidence is part of the output

- Source IDs, original observations, effective/retrieval dates, excluded evidence, and conflict reasons remain inspectable.
- Condition evidence cannot establish concealed-system condition from an absence of visible defects.
- One physical sale/rental comparable contributes one weight; repeated documents do not multiply support.
- Rehab scope cannot be charged twice through overlapping packages. Unknown work is not zero-cost work.
- Asking rents remain asking evidence. HCV reference values never become approved owner revenue.
- Financial inputs retain units, evidence classes, acceptance, and scope coverage. Scenario values stay `SCENARIO_ONLY`.
- Decision blockers point to upstream JSON fields and semantic SHA-256 hashes. These hashes detect changed content; they do not authenticate a source or prove its truth.

Fixtures use an explicitly invalid state (`ZZ`), county sentinel (`00000`), labels saying “NOT AN ADDRESS,” and artificial coordinates around the equator. No example represents a real parcel. Authority/inspection labels inside the fixture describe **simulated roles**. The public integration rejects `synthetic=false`, and every exported engine record carries `synthetic=true`.

## Public versus internal scope and geographic coverage

This edition contains the reusable offline computational portions of a broader internal system. It excludes private data, internal archives, provider implementations/credentials, client-specific adapters, historical renovation datasets, and property media. No internal test totals or internal production-readiness claims apply here.

**Real-address ingestion is not exposed in this edition.** The source application's address work was concentrated in Kansas City, Missouri / Jackson County. That is background scope, not a public support promise: no current source availability, zoning clearance, or city-case completeness is established by this repository. Arbitrary US addresses are unsupported.

Adding a connector requires independent source/usage review, geography-specific routing, explicit identity resolution, failure/staleness handling, and tests using publishable fixtures. Copying source labels into a JSON file does not make them authoritative evidence.

## Tests and reproducibility

```bash
python -m unittest discover -s tests -v
python -m pip check
```

The public suite tests the seven-engine flow, deterministic output, no-network execution, identity/contract drift, missing/future evidence, condition conflicts, rehab overlap, comparable deduplication, asking-versus-achieved rent, HCV reference separation, and scenario isolation. The original three financial regressions remain included. Tests are independently constructed with fictional data; they are not a claim about a larger private suite.

The CLI's fixtures are included in the installed wheel. Its fixed analysis date is **2026-01-15**, so results do not silently change as the clock advances. [Validation results](docs/validation.md) record the clean-install run and dependency versions. CI is configured to run the public tests and demos on Python 3.11–3.13; configured CI is not a claim that a hosted run has already passed.

## Limitations

- This is a developer-facing portfolio/research edition, not consumer-ready underwriting software.
- Similarity weights, thresholds, and confidence labels are explicit engineering policy, not statistically calibrated prediction intervals.
- The integrated condition review is intentionally sparse. No computer-vision performance or comprehensive physical inspection is demonstrated.
- Valuation and rent model a hypothetical ordinary rental-ready target; they do not certify that repairs occurred or that hidden systems work.
- The retained readiness policy requires ARV and HCV evidence together. Strategy-specific exemptions are not implemented.
- Evidence-mode financials in this synthetic integration stay insufficient. Numerical scenario success cannot verify real evidence.
- The reusable low-level modules assume their input contracts; the demo is not a hardened public API for arbitrary untrusted data.

## Reuse and licensing

No open-source license has been selected yet. The repository is prepared as a public portfolio edition, but broad reuse rights should not be assumed until the code owner approves a license. Third-party packages retain their own licenses. No proprietary data or provider response samples are distributed.
