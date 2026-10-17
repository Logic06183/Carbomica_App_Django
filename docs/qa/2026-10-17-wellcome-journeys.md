# QA: applicant and grant-holder journeys (17 October 2026)

Branch `wellcome-loop`, after roadmap items 1–13. Run against a local server
(`DEMO_MODE=True`, seeded demo data in a scratch database), driven in a
headless browser. Each step was done through the page's own forms.

## Journeys walked

**Applicant**
1. Created a new Wellcome award from the awards page.
2. Added a site with a 12.5% FTE share and its evidence.
3. Planned a Johannesburg–Geneva return leg (economy, 2 people), $15,000 of
   lab plastics, and an HPC job (Green Algorithms inputs, South African grid).
4. Chose six reduction measures and entered a credit price of $22, then
   added the credit budget to the costs with one click.
5. Read the draft application text.
6. Set a 25% reduction target from 2024 to 2029.

**Grant holder**
1. Logged an actual business-class flight with no justification.
2. Recorded accredited credits; the form pre-filled the 3 required.
3. Read the alignment checklist, the funder report and the CSV.
4. Checked the facility lab accreditation and organisation readiness pages
   (built and checked in items 5 and 11).
5. Checked every award page, report and the awards list at 390 px wide.

Hand checks that matched the app: business-class flight 8,000 km × 0.31656
kg/pkm = 2.532 t; HPC job 507 kWh × 0.928 kg/kWh = 0.471 t; footprint
91.61 t = 89.08 t site share + 2.53 t logged travel; report and CSV equal
the page.

## Findings and fixes

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | High (correctness) | The draft application text said the 97.3 t estimate was "made up of" parts that summed to 96.8 t. Planned computing was in the total but not in the list. | `75e16a5`: the overview lists planned computing and names its method; a test checks the parts sum to the total. |
| 2 | High (data) | An actual journey dated seven months ahead was accepted and counted in the footprint, credits and checklist. | `8cc45eb`: future-dated actual journeys and compute jobs are refused, with a pointer to plan them instead. |
| 3 | Medium (layout) | On a 390 px phone the award page was 451 px wide and the funder report 509 px, so both scrolled sideways. | `0ae6f4e`: headers and readiness items wrap; every report table scrolls inside its own container. All pages measured 390 px after the fix. |
| 4 | Medium (UX) | A new award opened on a nine-row checklist, mostly "n/a", with no route to the sites form or the estimate. | `0e46ea8`: a "Jump to" bar for every section, plus four getting-started steps while the award is empty. |
| 5 | Low (copy) | Adding a planned trip said it was "logged". | `04e6483`: the message says "planned" for planned trips. |

Tests: 234 pass after the fixes (8 regression tests added).

## Not fixed, for later

- The award page is long because applicant and holder tools share one page.
  The jump bar makes it workable. Splitting it into "Plan" and "Report"
  tabs is a design choice for Craig rather than a bug.
- The three factor questions from item 13 (non-UK grid source, refrigerant
  GWP set, site flight factor definition) remain open in the roadmap.
