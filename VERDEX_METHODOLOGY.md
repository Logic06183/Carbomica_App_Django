# Verdex — Methodology Reference

This file documents the carbon accounting methodology Verdex implements
today and the planned improvements borrowed from current best-in-class
commercial tools.

**Status:** Reference document. The preview deployment uses the methodology
described in section "Current methodology". The improvements listed under
"Planned improvements" are Phase 2 work, scoped here for traceability.

---

## Current methodology (live in the preview deployment)

### Framework alignment

- **GHG Protocol Corporate Standard** — emission category structure and
  scope definitions (Scope 1, 2, 3) for all 11 categories.
- **IEA Emissions Factors 2023** — country-specific grid electricity
  factors for 13 countries (Sub-Saharan Africa, South Asia, OECD donor
  geographies).
- **UK BEIS / DEFRA 2023 Conversion Factors** — fuel combustion
  (diesel, petrol, LPG, natural gas), transport, and waste factors.
- **IPCC AR4 GWP100 values** for halogenated gases (Phase 2 will
  migrate to AR6 — see below).
- **HIGH Horizons D3.7** (Luchters et al., 2024;
  DOI: 10.5281/zenodo.12730527) — intervention catalogue with
  cost/CO₂e/ROI metadata.

### Greedy knapsack optimisation

Three-scenario comparative analysis maximises tCO₂e reduction per USD
within a user-supplied budget:

| Scenario | Logic |
|---|---|
| Full coverage | All interventions applied — theoretical maximum reduction |
| Fixed budget | Cheapest interventions first until budget exhausted |
| Optimised | Greedy ranking by tCO₂e per USD until budget exhausted |

### Intervention library (59 entries)

Sourced from HIGH Horizons D3.7 case studies. ~70% are universal
(LED lighting, solar PV, fleet electrification, HVAC efficiency, waste
segregation, training, policy); ~30% are clinical-specific (anaesthetic
gas substitution, dry-powder inhaler swaps, medical refrigerant
conversions). Non-applicable interventions for non-clinical organisations
remain in the library but contribute zero to their optimisation.

### GWP100 values currently in use (AR4)

- Sevoflurane ~130
- Isoflurane ~510
- Desflurane ~2,540
- HFC-134a ~1,430
- HFC-410A blends per refrigerant inventory

---

## Planned improvements (Phase 2)

These are the patterns that distinguish leading commercial carbon
accounting tools (Watershed, Sweep, Persefoni, Climatiq, Greenly, Plan A)
from generic GHG calculators. Each is a self-contained sprint.

### 1. Spend-based fallback for missing activity data
**Why:** First-time users bounce because they don't have the kWh /
litres / kg figures. Letting them enter spend (currency they DO have)
removes the bounce.

**How:**
- Add a "Don't have activity data?" toggle per emission category.
- When toggled, show a currency input + spend-emissions intensity
  factor (kgCO₂e per USD spent on electricity / fuel / etc.)
- Source factors from EXIOBASE 3.x or EPA US EEIO 2.0 — both open
  data, well-documented.
- Tag the entry with `data_source: 'spend-based'` so the audit export
  is honest about it.

### 2. Sector + size benchmarks for instant baseline
**Why:** First-screen value. User sees a number before typing anything.

**How:**
- After picking sector + country + headcount, show a typical baseline
  using published benchmarks (CDP Climate Reports, GHG Protocol Sector
  Guides).
- Default the emission category fields to benchmark values; user
  refines from there.
- Tag entries with `data_source: 'benchmark-default'`.

### 3. Climatiq API integration
**Why:** Audit-grade defensibility. Every emission factor has a
trace-back to source + version + URL.

**How:**
- Sign up for Climatiq free tier (climatiq.io) — generous limits.
- Replace hardcoded `ELECTRICITY_EF` / `EMISSION_FACTORS` dict lookups
  with API calls (cached per request to avoid hitting rate limits).
- Cache the API response in DB so audit export can show "this used
  factor X from Climatiq API call on YYYY-MM-DD, source YYYY".

### 4. Generate grant report PDF export (the wedge feature)
**Why:** This is what a grant applicant actually attaches to their
submission. Until this exists, Verdex is "neat tool" not "essential
tool."

**How:**
- Add a `Generate report` button on the optimisation results page.
- Render a professional PDF using WeasyPrint (Django-friendly).
- Sections: Org profile, methodology overview, baseline by category,
  recommended intervention package with cost/CO₂e/ROI, methodology
  citations (factors used, GWP source, framework alignment),
  reviewer sign-off lines.
- Funder template variants (Wellcome, EU Horizon Europe, NIH) as
  separate Jinja templates the user picks at export time.

### 5. IPCC AR6 GWP migration
**Why:** Currently using AR4 GWPs. AR6 (2021) is the current
most-defensible reference for new tools.

| Gas | AR4 GWP100 | AR6 GWP100 |
|-----|-----------|-----------|
| HFC-134a | 1,430 | 1,530 |
| HFC-32 | 675 | 771 |
| HFC-410A | 2,088 | 2,256 |
| Methane (CH₄) | 25 | 29.8 (fossil) / 27.0 (non-fossil) |
| Sevoflurane | 130 | 144 |
| Isoflurane | 510 | 491 |
| Desflurane | 2,540 | 2,540 |

**How:**
- Update `EMISSION_FACTORS` in `modeling.py` with AR6 values.
- Add a `GWP_REVISION` constant ('AR4' | 'AR5' | 'AR6') for the
  audit export to cite which cycle was used.
- Note: many regulatory frameworks (EU ETS, UNFCCC reporting) still
  use AR5; the choice is one of audience preference, not technical
  correctness.

### 6. Scope 3 expansion: cats 1, 7, 12
**Why:** Current Verdex covers Scope 3 categories 4 (transport) and 6
(business travel). Modern carbon tools want categories 1 (purchased
goods), 7 (employee commuting), and 12 (end-of-life).

### 7. Reference framework alignment
The "Verdex grant report" should let the user pick which framework's
template to export against:

- **GHG Protocol** Corporate Standard (already aligned)
- **CDP** disclosure questionnaire structure
- **TCFD** (Task Force on Climate-related Financial Disclosures)
- **SBTi** (Science Based Targets initiative)
- **GRI 305** (Global Reporting Initiative — Emissions standard)
- **ISO 14064-1** for organisational GHG inventories

### 8. Time-based emission factors (advanced — Phase 3+)
For organisations claiming renewable energy procurement, hourly
matched grid factors instead of annual averages. Most users don't have
hourly meter data, so this is low priority for v1.

---

## Sources to cite in any audit-grade export

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
  industry associations.
