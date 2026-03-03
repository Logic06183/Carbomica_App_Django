# CARBOMICA — CARBOn Mitigation Intervention for healthCare fAcilities

A resource-allocation modelling tool for healthcare decision-makers who need to
reduce their facility's carbon footprint within real budget constraints.

**Funded by:** European Union — Horizon Europe Grant No. 101057843
**Project:** HIGH Horizons — Heat Indicators for Global Health
**Coordinator:** Ghent University (Stanley Luchters)
**Partners:** Wits Planetary Health (ZA) · CeSHHAR Zimbabwe (ZW) · Aga Khan Health Service Kenya (KE) · Burnet Institute (AU)

---

## What CARBOMICA does

Given a facility's current carbon emissions and a budget ceiling, CARBOMICA
identifies the **optimal package of carbon mitigation interventions** through
three comparative scenarios:

| Scenario | Logic |
|---|---|
| **Full coverage** | All interventions applied — shows maximum possible reduction |
| **Fixed budget** | Cheapest interventions first until budget is exhausted |
| **Optimised** | Greedy knapsack: maximises tCO₂e reduced per USD spent |

Health managers can compare scenarios side-by-side to make evidence-grade
investment decisions aligned with SDGs, national climate policy, and EU funding criteria.

The tool builds on **ATOMICA** (a resource-allocation simulation framework),
adapting its optimisation engine for the healthcare sustainability context.
Carbon emission data follows the **AKDN Carbon Management Tool** methodology,
covering 10 emission categories across Scope 1, 2, and 3.

---

## Emission categories (10 — matching AKDN methodology)

| # | Category | Scope |
|---|---|---|
| 1 | Grid electricity | 2 |
| 2 | Grid / piped gas | 1 |
| 3 | Bottled gas (LPG) | 1 |
| 4 | Liquid fuel (diesel) | 1 |
| 5 | Vehicle fuel — owned fleet | 1 |
| 6 | Business travel | 3 |
| 7 | Anaesthetic gases | 1 |
| 8 | Refrigeration gases (HFCs) | 1 |
| 9 | Waste management | 3 |
| 10 | Medical inhalers (MDI propellants) | 1 |

---

## CARBOMICA intervention library

Eight evidence-based interventions from the HIGH Horizons D3.7 case studies:

| Intervention | Primary SDGs | Typical LMIC payback |
|---|---|---|
| Solar PV System | 7, 13 | 5 years |
| Low-GWP Anaesthetic Gases | 3, 13 | 18 months |
| LED Lighting Upgrade | 7, 11 | 2 years |
| Medical Waste Segregation | 3, 12 | 12 months |
| Water-Efficient Fixtures | 6, 11 | 3 years |
| Low-GWP Refrigerant Conversion | 13 | 4 years |
| Switch to Dry-Powder Inhalers | 3, 13 | 12 months |
| Fleet & Travel Optimisation | 11, 13 | 18 months |

---

## Current study sites

| Facility | Country | Type |
|---|---|---|
| Mt Darwin District Hospital | Zimbabwe | District hospital |
| Aga Khan Hospital Mombasa | Kenya | Provincial hospital |
| Chris Hani Baragwanath Academic Hospital | South Africa | Central hospital |
| Mashonaland Central Provincial Hospital | Zimbabwe | Provincial hospital |
| Soweto Community Health Centre | South Africa | Health centre |
| Kenyatta National Hospital Nairobi | Kenya | Central hospital |

---

## Technical stack

- **Backend:** Django 5.1 · Python 3.12 · SQLite (dev) · PostgreSQL (prod)
- **Optimisation engine:** `appname/modeling.py` — `CarbomicaOptimizer` class
- **Frontend:** Bootstrap 5 · Plotly.js (CDN, no server-side Dash)
- **Deployment:** Heroku (Procfile + whitenoise for static files)

---

## Local setup

```bash
git clone https://github.com/Logic06183/Carbomica_App_Django.git
cd Carbomica_App_Django
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data          # loads representative LMIC demo data
python manage.py createsuperuser         # for /admin access
python manage.py runserver
```

Open http://127.0.0.1:8000

### Environment variables (optional for local dev)

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite | Set for PostgreSQL in production |
| `DJANGO_SECRET_KEY` | insecure default | Override in production |
| `DJANGO_DEBUG` | `True` | Set `False` in production |

---

## Key published deliverables

1. **CARBOMICA tool report (D3.7)** — Luchters S et al. (2024).
   DOI: [10.5281/zenodo.12730527](https://zenodo.org/records/12730527)

2. **Carbon emission assessment (D2.11)** — Sulaiman Z et al. (2024).
   DOI: [10.5281/zenodo.12703876](https://zenodo.org/records/12703876)

3. **Evaluation protocol (D5.7)** — Luchters S et al. (2024).
   DOI: [10.5281/zenodo.12819289](https://zenodo.org/records/12819289)

4. **COP28 case study** — [ClimaHealth resource library](https://climahealth.info/resource-library/carbomica-a-carbon-mitigation-and-resource-allocation-modelling-tool-for-the-healthcare-sector-in-east-africa/)

---

## Project website

https://www.high-horizons.eu/reducing-emissions/
