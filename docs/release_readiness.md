# Public portfolio release status

**Checked:** 2026-10-15
**Published app commit:** [`599d352`](https://github.com/elijahchiu/property-underwriting-intelligence/commit/599d352f282c129fc92aa004f1cfa4b3c5246235)

## Included

- A local interactive website for fictional market and property research, renovation scenarios, financial calculations, timing comparisons, and reports.
- A seven-stage Python underwriting pipeline with synthetic examples.
- Installation instructions, screenshots, a sample PDF report, method notes, and tests.

## Verified

- Installed the Python package in a clean virtual environment and checked its examples.
- Ran all **55 tests** successfully.
- Exercised the website's market, property, renovation, financial, timing, and report pages in a browser; no console errors appeared.
- Checked the layout at 390 × 844 and reviewed the two-page sample PDF. These were spot checks, not a full accessibility audit.
- Scanned the published files for credentials and private Roof4All records. The app and tests made no live property-data or paid-provider requests.
- Verified that commit `599d352` and the `portfolio_demo/` files are on GitHub `main`.

## Limits

- The website runs on the user's computer; there is no hosted demo URL. Its server listens on loopback and makes no external requests.
- The tests, cost estimates, and six-project holdout exercise use fictional examples. They do not establish real-world prediction accuracy or Roof4All performance.
- The repository has no open-source license. Company permission to publish this portfolio version was confirmed by the user; this document is not a legal review.
- GitHub Actions is configured for Python 3.11–3.13, but no hosted CI run is claimed here.

## Release status

The source is public and locally validated. The public demo is suitable for code review and local use with the README instructions. A hosted site, full WCAG audit, and new model-performance claims are outside this release.
