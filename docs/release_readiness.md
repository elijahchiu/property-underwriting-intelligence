# Local portfolio candidate release checklist

Status date: 2026-10-15. This records local verification only and does not authorize a GitHub push.

## Implemented and verified locally

- [x] Independently authored, loopback-only interactive site with fictional markets, listings, properties, comparable sales, rental references, and renovation analogs.
- [x] Complete demo path from market/property selection through property evidence, editable scope, financial recalculation, timing scenarios, and report preview.
- [x] Final package built and installed as a non-editable wheel in a new Python 3.12 virtual environment using locally available build/runtime dependencies; installed imports resolve from that environment's `site-packages`.
- [x] All **55 tests** pass after the final review; coverage includes fixture preparation/integration, property-level synthetic scope holdouts, and exact project-use reconciliation.
- [x] Installed CLI and financial/timing examples run; the default CLI output matches the checked-in sample byte-for-byte.
- [x] Browser checks cover market selection, property details, scope override, financial recalculation, timing sensitivity, and report preview; no browser console errors were observed.
- [x] Responsive check at 390 × 844 has no horizontal overflow and the navigation drawer opens; a keyboard focus spot check reaches the home link. This is not a full WCAG audit.
- [x] Print layout produces a visually reviewed two-page letter PDF. Synthetic notice, assumptions, scope, financial outputs, and review items remain legible.
- [x] Overview and financial-analysis screenshots plus the refreshed two-page sample PDF are included in `docs/`; the sample report shows the updated synthetic-analogs label.
- [x] README now gives recruiters an inspectable synthetic data-preparation example, analog formula, leave-one-property-out results, and explicit limits. The scope table labels the count as “Synthetic analogs” to avoid implying real Roof4All project support. All evaluation records are fictional and cannot substantiate Roof4All performance claims.
- [x] Candidate/history confidentiality scan found no credentials, private company records, private Roof4All source files, or personal local paths in this candidate. The public base repository was already public; this audit does not establish ownership of its existing commit.
- [x] No live property, RentCast, or other metered provider requests were made by the application or its tests. The local package build and install required no package-index access.

## Remaining release gates

- [x] The user confirms that company permission to publish the portfolio version has been obtained. The candidate uses a neutral identity and no company logo or private company material.
- [x] No open-source license is included, as requested.
- [ ] Review the final local commit and explicitly approve the GitHub push. No push has been made.
- [ ] Verify the current remote `main` head immediately before publishing. This environment could not resolve `github.com`, so remote freshness is not confirmed here.

## Candidate boundaries

The pending candidate includes the interactive demo, fully fictional data, the README and feature comparison, validation/release notes, screenshots, and sample PDF, alongside the timing-sensitivity addition already in this checkout. The private Roof4All repository was inspected read-only and is not part of this change set. The site makes no external requests, contains no company historical dataset, and is a local portfolio demonstration rather than the production Roof4All service.

## Release decision

**Locally verified; awaiting final push approval and remote-head check.** The user has confirmed company publication permission and asked to keep the repository without a license. Installation, tests, browser workflow, responsive spot check, and sample report are verified. The candidate is not yet published.
