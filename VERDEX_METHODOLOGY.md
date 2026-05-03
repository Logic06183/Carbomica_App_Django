# Verdex — Methodology Reference

This file documents the carbon accounting methodology Verdex builds on,
including what we inherit from CARBOMICA (HIGH Horizons / AKDN tradition)
and what we borrow from current best-in-class commercial tools.

**Status:** Reference document for the Verdex commercial edition.
The preview deployment uses CARBOMICA's existing engine. The improvements
listed here are Phase 2 work, scoped here for traceability.

---

## What we inherit from CARBOMICA (kept as-is for v1)

1. **GHG Protocol scope structure (1/2/3).** All 11 emission categories
   are mapped to the appropriate scope. Universal across sectors.
2. **AKDN Carbon Management Tool methodology** for emission category
   definitions. Defensible in any health-adjacent grant context.
3. **Country-specific grid emission factors** (currently Zimbabwe, South
   Africa, Kenya, Other). Stored in `appname/modeling.py:EMISSION_FACTORS`.
4. **Greedy knapsack optimisation** maximising tCO₂e reduction per USD,
   with three comparative scenarios (full coverage / fixed budget /
   optimised).
5. **Intervention library** of 59 evidence-based interventions sourced
   from HIGH Horizons D3.7. ~70% are universal (LED, solar, fleet,
   HVAC, waste segregation, training, policy); ~30% are clinical-
   specific (anaesthetics, inhalers, medical refrigerants).
6. **GWP100 values** for halogenated gases:
   - Sevoflurane ~130
   - Isoflurane ~500
   - Desflurane ~2,500
   - HFC-134a ~1,430 (IPCC AR4)
   - HFC-410A blends per refrigerant inventory

---

## Methodology improvements borrowed from leading commercial tools

These are the most-cited differentiators in the carbon accounting market
as of 2026. Each is a candidate for Phase 2 implementation in Verdex.

### 1. Spend-based fallback for missing activity data
**From:** Watershed, Persefoni, Sweep, Plan A.
**Pattern:** When a user can't provide activity data (kWh, litres, kg),
let them enter the financial spend in their currency (e.g. annual
electricity bill in USD/EUR/local). The tool applies a sector-specific
spend-emissions intensity factor (e.g. `kgCO₂e per USD spent on
electricity`) to estimate emissions.
**Source:** EXIOBASE, GTAP, EPA EEIO database.
**Why it matters:** Removes the most common bounce reason ("I don't
have the kWh figure"). Activity data refines the estimate later.

### 2. Sector + size benchmarks for instant baseline
**From:** Greenly, Sustain.Life, Sweep.
**Pattern:** Ask sector + headcount + country at signup. Show an
instant "typical baseline" using published benchmarks (e.g. CDP, GHG
Protocol Sector Guides, DEFRA Conversion Factors). User refines from
there with real data.
**Source:** CDP Climate Reports, GHG Protocol Sector Guides, World
Resources Institute datasets.
**Why it matters:** First-screen value. User sees a number before
typing anything.

### 3. API-driven emission factors (vs hardcoded)
**From:** Climatiq, Carbon Interface, IBM Environmental Intelligence Suite.
**Pattern:** Look up emission factors at calculation time from an
external API rather than embedding them in code. Country grid factors,
fuel factors, transport factors all update automatically when sources
publish revisions (annual cycle for IEA, DEFRA, US EPA).
**Source:** Climatiq API (climatiq.io) — most comprehensive open
source aggregator. Free tier available.
**Why it matters:** Audit-grade defensibility. "Where did this number
come from?" → the API response includes source citation.

### 4. Audit-grade methodology export
**From:** Persefoni, Watershed.
**Pattern:** A single-click PDF export per reporting period that
includes: organisation profile, scope structure, every emission factor
used (with source + version + URL), every assumption made, the
calculation chain, and reviewer sign-off lines.
**Why it matters:** This IS the grant submission attachment. Removes
the consultant from the equation.

### 5. Reference framework alignment
**From:** All major tools.
**Frameworks to align with:**
- **GHG Protocol** Corporate Standard (already done)
- **CDP** disclosure questionnaire structure
- **TCFD** (Task Force on Climate-related Financial Disclosures) —
  required by many funders now
- **SBTi** (Science Based Targets initiative) — for setting reduction targets
- **GRI 305** (Global Reporting Initiative — Emissions standard)
- **ISO 14064-1** for organisational GHG inventories

The "Verdex grant report" should let the user pick which framework's
template to export against (Wellcome wants A, EU Horizon Europe wants B).

### 6. Scope 3 deeper coverage
**From:** Persefoni, Sweep.
**Current Verdex coverage:** Scope 3 categories 1 (purchased goods —
implicit in waste/contractor data), 4 (transport), 6 (business
travel). Missing: 1 (purchased goods), 7 (employee commuting), 11
(use of sold products), 12 (end-of-life), 15 (financed emissions).
**Phase 2:** Add Scope 3 categories 1, 7, 12 with simple spend-based
estimation. 11 and 15 are advanced and not relevant for most Verdex
users.

### 7. Time-based emission factors (advanced)
**From:** Watershed, Climatiq.
**Pattern:** Grid emissions vary hour-by-hour with renewable
penetration. For orgs claiming renewable energy procurement, use
hourly matched factors instead of annual averages.
**Why it matters (Verdex):** Probably not for v1. Most Verdex users
don't have hourly meter data. Worth tracking as Phase 3+.

---

## Updated GWP values (IPCC AR6 vs AR4)

CARBOMICA's existing values come from AR4. AR6 (2021) updated several:

| Gas | AR4 GWP100 | AR6 GWP100 | Δ |
|-----|-----------|-----------|---|
| HFC-134a | 1,430 | 1,530 | +7% |
| HFC-32 | 675 | 771 | +14% |
| HFC-410A | 2,088 | 2,256 | +8% |
| Methane (CH₄) | 25 | 29.8 (fossil) / 27.0 (non-fossil) | +19%/+8% |
| Sevoflurane | 130 | 144 | +11% |
| Isoflurane | 510 | 491 | -4% |
| Desflurane | 2,540 | 2,540 | 0% |

**Decision for Verdex preview:** Inherit CARBOMICA's AR4 values for v1.
Document AR6 update as Phase 2 work — it's a one-line factor change
per gas in `modeling.py` once we agree on which AR cycle to standardise.

Note: AR6 GWPs are currently the most defensible for new tools, but
many existing regulatory frameworks (EU ETS, UNFCCC reporting) still
use AR5 values. Tools should pick one AR cycle and document the choice.

---

## Sources to cite in any Verdex audit-grade export

When Phase 2 ships the methodology export, every emission factor used
must trace back to:

- **Country grid factors:** IEA Emissions Factors annual report
  (latest); Climate Transparency country fact sheets; national grid
  operator publications.
- **Fuel emission factors:** IPCC 2006 Guidelines (Volume 2: Energy)
  with AR6 GWP updates; UK BEIS / DEFRA Conversion Factors annual.
- **Refrigerant GWPs:** IPCC AR6 Working Group I Annex VII Table 7.SM.7.
- **Anaesthetic gas GWPs:** Sherman et al. (2012, 2024 update); WHO
  Health Care Climate Footprint reports; AAGBI green sustainability
  guidelines.
- **Spend-based factors:** EXIOBASE 3.x (most recent release); EPA
  US EEIO 2.0; GHG Protocol Sector Guides.
- **Sector benchmarks:** CDP Climate Reports; WBCSD; sector-specific
  industry associations (HCWH for healthcare, etc.).

---

## Distinguishing Verdex from CARBOMICA

| Dimension | CARBOMICA (EU) | Verdex (commercial) |
|---|---|---|
| Funder | EU Horizon Europe Grant 101057843 | Independent, commercial |
| Brand owner | HIGH Horizons consortium | Independent |
| Target user | LMIC clinical facilities | Any organisation, grant-application focused |
| Methodology | AKDN + HIGH Horizons D3.7 | GHG Protocol + AKDN + spend-based + sector benchmarks |
| Emission categories | 11 (universal) | Same 11 + Scope 3 expansion (Phase 2) |
| Intervention library | 59 (clinical-weighted) | Same 59 + sector-agnostic curation tagging (Phase 2) |
| Output | Optimisation results in-app | Optimisation + grant-ready report export (Phase 2) |
| Deployment | carbomica-tool.web.app | verdex.web.app (planned) |
| Database | Supabase (shared instance) | Supabase (separate instance/project) |
| Auth | Google OAuth, real users | DEMO MODE for preview, OAuth for production |
