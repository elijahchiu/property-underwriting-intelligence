# Public portfolio feature comparison

This comparison was prepared from the private application's operational README and UI/navigation source and a read-only inspection of its current local Scope workspace at `127.0.0.1:8783`, then checked against the published repository at commit `599d352`. The private project was not changed. No private datasets, application modules, branding assets, or provider code were copied into the public demo. The public screenshots in `docs/` show the demo; private application views are not packaged with this portfolio because they display private property and provider-budget information.

| Capability | Private Roof4All application | Published public GitHub edition (`main`, `599d352`) |
|---|---|---|
| Market and neighborhood research | Integrated local and public-source workflow; coverage varies by geography | Three fabricated markets with comparison cards, indicators, and a small visual |
| Property discovery | Address intake plus supported listing/property search | Search and filter five fictional listings |
| Property workspace | Evidence-aware facts, local records, condition, sales, rent, scope, and underwriting sections | Browser workspace with fictional facts, source labels, sale comps, and asking-rent examples; seven-engine Python pipeline available separately |
| Sale and rent analysis | Evidence-admission and comparable review; live provider is optional and guarded | Three synthetic sales and rental observations per property; median references are shown as simulated |
| Renovation scope | Historical scope corpus, user review, manual inputs, and contractor-review status | Editable itemized scope generated from six synthetic reference projects with disclosed feature weights |
| Data preparation / evaluation | Private source normalization and historical-estimate workflows | Fictional record validation/integration plus six-record leave-one-project-out method demo; not Roof4All performance |
| Financial underwriting | Integrated evidence and scenario engines; missing evidence can withhold metrics | Browser form for purchase, rent, vacancy, operating costs, debt, NOI, DSCR, cash flow, and cash-on-cash |
| Scenario comparison | Saved versions and property-specific comparisons | Live recalculation of assumptions plus four/six-week timing sensitivity |
| Acquisition report | Browser report and print-to-PDF flow with evidence and blockers | Print-ready report preview with property, comps, scope, financials, timing, and review items |
| Live data/provider integrations | Local/public connectors and separately guarded optional provider calls | Absent; the app makes no external requests |
| Historical/company records | Private evidence and source-document corpus | Excluded; all visible fixtures are invented |

## Release boundaries

The interactive website is a separately authored public demonstration of the same high-level research sequence. It does not claim feature parity with the private system, use its logo or visual assets, or reuse its internal application code. All values are synthetic.

The published public edition contains both the interactive synthetic website and the seven-engine Python pipeline. The website is locally run and loopback-only; it is not hosted as a public service. The repository has no open-source license, and no license was added as part of the publication.

The app is a local portfolio demonstration, not a hosted service. It binds to loopback only and has no user accounts, saved server-side cases, live feeds, or real-world property resolution.
