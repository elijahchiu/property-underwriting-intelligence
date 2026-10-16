# Public demo and private application

This summary compares the public portfolio demo with the private Roof4All application. I reviewed the private app's documentation and navigation read-only. No private files, data, logo, provider code, or application code were copied into the public demo.

| Area | Private Roof4All app | Public portfolio demo |
|---|---|---|
| Market research | Local and public-source research; coverage varies by market | Three fictional markets with comparison cards and charts |
| Property search | Address intake and supported property/listing search | Five fictional listings with search and filters |
| Property workspace | Property facts, local records, condition, sales, rent, renovation, underwriting | Fictional property facts, sale comps, and asking-rent examples; separate seven-engine Python pipeline |
| Sales and rent | Evidence review and comparable analysis; guarded provider calls may be available | Three fictional sales and rental records per sample property |
| Renovation | Historical scopes, property-specific review, and contractor follow-up | Editable estimates from six fictional projects; methods and limitations are shown |
| Data evaluation | Private source and historical-estimate workflows | Synthetic record checks and a six-project holdout exercise; not Roof4All model performance |
| Financials | Evidence and scenario engines that can withhold unsupported results | Editable fictional assumptions for NOI, DSCR, cash flow, and cash-on-cash |
| Scenarios | Saved property comparisons | Recalculated financing assumptions and four-/six-week timing examples |
| Report | Property evidence, scope, and readiness review | Printable sample report with comps, scope, financials, timing, and review items |
| Live data | Local/public sources and separately guarded providers | None; the demo makes no external requests |
| Company records | Historical and current internal evidence | None; all example records are fictional |

## What the public demo is

The public site shows a similar research sequence, but it is a separate portfolio project—not a copy of the Roof4All application. It uses no Roof4All logo, private data, or internal code. The demo and Python pipeline are in GitHub `main` at commit [`599d352`](https://github.com/elijahchiu/property-underwriting-intelligence/commit/599d352f282c129fc92aa004f1cfa4b3c5246235).

The site runs locally and listens only on the local computer. It is not a hosted service and has no account system, live data, or real address lookup. The repository has no open-source license.
