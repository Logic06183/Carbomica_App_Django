# Wellcome grant-carbon roadmap (improvement loop)

Goal: make this app the tool a Wellcome applicant or grant holder uses to plan,
monitor and report the carbon footprint of one award, in the terms Wellcome's
policy uses.

Primary source: Wellcome, *Environmental sustainability funding policy*,
https://wellcome.org/research-funding/guidance/policies-grant-conditions/environmental-sustainability-funding-policy
(page last updated 1 July 2025; read 2026-10-17). Key requirements, quoted:

- Applicants: "design their research using the most sustainable approach they can
  access" and explain how in the application; "demonstrate how they will reduce the
  emissions and natural resources used in their research"; all travel must be justified.
- Holders: "use a tool appropriate to their setting to assess the environmental impact
  of their work"; labs reach minimum LEAF / My Green Lab accreditation "by the end of 2025".
- Travel: train "for journeys of up to 10 hours (total travel time including
  connections)"; economy by default; "Wellcome does not fund business class flights";
  "Mitigate the remaining carbon emissions of all journeys using accredited carbon credits".
- Organisations: arrangements to buy third-party accredited credits; UK orgs sign the
  Concordat (end 2024); high-income orgs have a science-based net-zero plan for scope 1
  and 2 (end 2024); keep logs of existing and left-over resources.
- Eligible costs: staff time to "advise, assess, measure and report on the award's
  emissions and resource usage"; credits for travel; accreditation of the lead lab;
  second-hand / efficient equipment; hybrid meeting tools; LCAs.
- Future: scope 3 reporting to Wellcome, no date given.

## Loop rules (read every iteration)

1. Work only in this worktree on branch `wellcome-loop`. Never push, deploy, or change
   any other branch. Never commit `db.sqlite3`, `staticfiles/` or `.venv/`.
2. Take the first unchecked item below. One item per iteration, one commit per item.
3. No invented numbers. Every emission factor, threshold or policy claim cites a primary
   source (URL + date read) in code comments and on the methodology page. If a value
   cannot be verified from a primary source, leave the feature out and add it to
   *Open questions for Craig*.
4. Read the existing code first and match its style. Reuse existing models, factors and
   templates. `origin/consortium` holds a CARBOMICA version of the offset register,
   reduction planning and Wellcome checklist; read it with `git show origin/consortium:<path>`
   and adapt, do not copy the CARBOMICA branding.
5. Every item adds tests that pin the behaviour (calculations, validation, access control,
   page renders). Done means: `DEBUG=True .venv/bin/python manage.py test appname` passes in
   full, `makemigrations --check` is clean, and the item's acceptance line below is met.
6. Commit as `feat(wellcome): <item>` with a body saying what changed, the sources used,
   and the test count. Then tick the item here with the short SHA and add a line to the log.
7. If an item fails twice, or needs a decision only Craig can make, mark it `[blocked]`
   with the reason, add it to *Open questions*, and move on.
8. When every item is ticked or blocked, stop the loop and send Craig a one-line summary.

## Items

- [x] 1. (`100d5cf`) **Award travel log.** Per-project journeys: date, traveller role, origin,
  destination, mode (air/rail/car/bus), cabin class, distance km, door-to-door hours by
  rail, purpose. tCO2e from existing verified factors (add class-specific air factors only
  from DEFRA's published table). Accept: journeys roll into the award report; tests cover
  each mode.
- [x] 2. (`3b1aecd`) **Travel policy checks.** Flag flights where rail would take ≤10 h door to door,
  any business/first class ("not funded"), and journeys with no justification. Accept:
  flags show on the journey list and the award report; tests pin each rule at the 10 h edge.
- [x] 3. (`0b86f27`) **Credits for travel emissions.** Port the consortium offset register to award
  level: required whole credits for the award's travel, purchases (registry, reference,
  cost, retired), net position, accredited-registry check. Accept: net position correct
  for over/under/zero purchases; unaccredited purchase fails the check.
- [x] 4. (`15570d0`) **Wellcome alignment checklist per award.** Pass/warn/fail rows for each policy
  requirement the app can evidence (impact assessed, travel justified, rail rule, no
  business class, travel credits covered and retired, lab accreditation, reduction plan).
  Each row quotes the policy line it tests. Accept: every row has a test for each state.
- [x] 5. (`d49060b`) **Lab accreditation tracker.** Per site: scheme (LEAF / My Green Lab / other),
  level, date awarded, evidence link, and a flag against the end-of-2025 deadline.
  Accept: feeds checklist row; tests cover missing, achieved, and overdue.
- [x] 6. (`9871422`) **Application-stage estimate.** Before an award starts: planned trips, planned
  equipment and consumables spend, planned sites and FTE share. Produce an estimated
  footprint, the credit cost for travel to put in the budget, and the reduction measures
  chosen. Accept: estimate and actuals sit side by side on the award page once the award runs.
- [x] 7. (`a2b8fd2`) **Application text helper.** From the estimate, draft the "how this project uses
  the most sustainable approach" section: energy, reuse of equipment, waste, travel. Plain
  template text filled from the user's own numbers, no generated claims. Accept: copyable
  text, every number traceable to an input.
- [x] 8. (`0bac869`) **Eligible-cost lines.** List the sustainability costs Wellcome says are eligible
  (staff time for measurement, credits, lead-lab accreditation, hybrid tools, LCA) as budget
  lines the user can fill in. Accept: totals appear in the estimate and the export.
- [x] 9. (`02250f2`) **Reduction plan per award.** Port consortium reduction planning: baseline,
  target, straight-line trajectory, actuals. Accept: trajectory maths tested.
- [x] 10. (`867a599`) **Funder report export.** CSV and print view of the award: footprint by scope and
  category, travel log with flags, credits, checklist, statement of method with sources.
  Accept: export numbers equal the page numbers in a test.
- [x] 11. (`837829d`) **Organisation readiness page.** Org-level policy items: Concordat signatory,
  science-based net-zero plan for scope 1 and 2, credit-purchase arrangement, resource log.
  Accept: self-declared with evidence link and date; shown on every award of that org.
- [x] 12. (`5b97ede`) **Computing emissions.** HPC / cloud compute for desk-based research using a
  published, citable method (e.g. Green Algorithms) only if its factors can be verified.
  Accept: method and factors cited on the methodology page, or item blocked with reason.
- [x] 13. **Factor currency audit.** Check every factor in `modeling.py` against its source
  and the latest published edition. Update where a newer official value exists and record
  the edition used. Accept: methodology page lists each factor with edition and URL.
- [ ] 14. **QA pass.** Run the app, click through applicant and holder journeys end to end,
  fix what breaks. Accept: QA notes in `docs/qa/` and fixes committed one per issue.

## Open questions for Craig

1. **Non-UK grid factors (from item 13).** They cite IEA 2023, whose emission-factor dataset is
   licensed, so the audit could not check them. Options: buy IEA access, or switch to an open
   source (for example Ember's country data) and record the edition. Your call; nothing changed.
2. **Refrigerant GWPs (from item 13).** The refrigerant blend uses IPCC AR4 values (R-410A 2088,
   R-134a 1430, R-22 1810) while the file header says AR6. Which GWP set should the app use
   throughout? DEFRA's own refrigerant tables are one consistent option.
3. **Site flight factor definition (from item 13).** Site-level "passenger-km flown" uses DEFRA's
   long-haul *economy* factor (2026: 0.11704 kg/pkm). When cabin class is unknown, DEFRA's
   "average passenger" row (0.15282) is the usual choice and is 31% higher. Kept as economy to
   change only the edition; say if you want average passenger.

## Log

- 2026-10-17 Loop set up on `wellcome-loop` from `origin/verdex` (49af791). Baseline 99 tests pass.
- 2026-10-17 Item 1 done (`100d5cf`): award travel log, DEFRA 2026 factors, journeys replace apportioned site travel. 114 tests.
- 2026-10-17 Item 2 done (`3b1aecd`): per-journey Wellcome travel flags with verbatim policy quotes; 10 h edge tested. 125 tests.
- 2026-10-17 Item 3 done (`0b86f27`): award credit register; only accredited credits count as cover. 138 tests.
- 2026-10-17 Item 4 done (`15570d0`): per-award checklist, verbatim quotes; retirement labelled good practice (policy silent). 148 tests.
- 2026-10-17 Item 5 done (`d49060b`): lab accreditation per site, MGL 2-yr recertification, checklist row with end-2025 deadline. 162 tests.
- 2026-10-17 Item 6 done (`9871422`): planned trips/purchases, estimate vs actual (reconciles), credit budget at user price, 15 policy-quoted measures. 172 tests.
- 2026-10-17 Item 7 done (`a2b8fd2`): draft application text from estimate and chosen measures; breaches surfaced as warnings. 181 tests.
- 2026-10-17 Item 8 done (`0bac869`): eligible sustainability cost lines with verbatim headings; totals in estimate and draft text. 189 tests. Note for item 14: award page is now long; consider splitting applicant vs holder views.
- 2026-10-17 Item 9 done (`02250f2`): per-year award footprints, straight-line target, incomplete years never judged. 198 tests.
- 2026-10-17 Item 10 done (`867a599`): printable funder report + CSV from one shared context; export equals page in tests. 204 tests.
- 2026-10-17 Item 11 done (`837829d`): org duties self-declared with evidence; HIC scope declared not inferred; shown on awards, report, CSV. 213 tests.
- 2026-10-17 Item 12 done (`5b97ede`): Green Algorithms compute jobs, constants verified in the paper via PMC. 223 tests.
