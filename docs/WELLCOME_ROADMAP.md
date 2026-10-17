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
- [x] 2. **Travel policy checks.** Flag flights where rail would take ≤10 h door to door,
  any business/first class ("not funded"), and journeys with no justification. Accept:
  flags show on the journey list and the award report; tests pin each rule at the 10 h edge.
- [ ] 3. **Credits for travel emissions.** Port the consortium offset register to award
  level: required whole credits for the award's travel, purchases (registry, reference,
  cost, retired), net position, accredited-registry check. Accept: net position correct
  for over/under/zero purchases; unaccredited purchase fails the check.
- [ ] 4. **Wellcome alignment checklist per award.** Pass/warn/fail rows for each policy
  requirement the app can evidence (impact assessed, travel justified, rail rule, no
  business class, travel credits covered and retired, lab accreditation, reduction plan).
  Each row quotes the policy line it tests. Accept: every row has a test for each state.
- [ ] 5. **Lab accreditation tracker.** Per site: scheme (LEAF / My Green Lab / other),
  level, date awarded, evidence link, and a flag against the end-of-2025 deadline.
  Accept: feeds checklist row; tests cover missing, achieved, and overdue.
- [ ] 6. **Application-stage estimate.** Before an award starts: planned trips, planned
  equipment and consumables spend, planned sites and FTE share. Produce an estimated
  footprint, the credit cost for travel to put in the budget, and the reduction measures
  chosen. Accept: estimate and actuals sit side by side on the award page once the award runs.
- [ ] 7. **Application text helper.** From the estimate, draft the "how this project uses
  the most sustainable approach" section: energy, reuse of equipment, waste, travel. Plain
  template text filled from the user's own numbers, no generated claims. Accept: copyable
  text, every number traceable to an input.
- [ ] 8. **Eligible-cost lines.** List the sustainability costs Wellcome says are eligible
  (staff time for measurement, credits, lead-lab accreditation, hybrid tools, LCA) as budget
  lines the user can fill in. Accept: totals appear in the estimate and the export.
- [ ] 9. **Reduction plan per award.** Port consortium reduction planning: baseline,
  target, straight-line trajectory, actuals. Accept: trajectory maths tested.
- [ ] 10. **Funder report export.** CSV and print view of the award: footprint by scope and
  category, travel log with flags, credits, checklist, statement of method with sources.
  Accept: export numbers equal the page numbers in a test.
- [ ] 11. **Organisation readiness page.** Org-level policy items: Concordat signatory,
  science-based net-zero plan for scope 1 and 2, credit-purchase arrangement, resource log.
  Accept: self-declared with evidence link and date; shown on every award of that org.
- [ ] 12. **Computing emissions.** HPC / cloud compute for desk-based research using a
  published, citable method (e.g. Green Algorithms) only if its factors can be verified.
  Accept: method and factors cited on the methodology page, or item blocked with reason.
- [ ] 13. **Factor currency audit.** Check every factor in `modeling.py` against its source
  and the latest published edition. Update where a newer official value exists and record
  the edition used. Accept: methodology page lists each factor with edition and URL.
- [ ] 14. **QA pass.** Run the app, click through applicant and holder journeys end to end,
  fix what breaks. Accept: QA notes in `docs/qa/` and fixes committed one per issue.

## Open questions for Craig

(none yet)

## Log

- 2026-10-17 Loop set up on `wellcome-loop` from `origin/verdex` (49af791). Baseline 99 tests pass.
- 2026-10-17 Item 1 done (`100d5cf`): award travel log, DEFRA 2026 factors, journeys replace apportioned site travel. 114 tests.
