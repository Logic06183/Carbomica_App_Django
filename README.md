# Verdex — Grant-Ready Emissions Reporting

A carbon emissions baseline + budget-aware reduction planner for any
organisation. Designed to produce defensible reports you can attach to
grant applications.

**Live preview:** https://verdex-app.web.app
**Status:** Preview deployment (DEMO_MODE bypasses authentication; data is
ephemeral and resets on every Cloud Run cold start).

---

## What Verdex does

Given an organisation's annual emissions across 11 categories and a budget
ceiling, Verdex identifies the **optimal package of carbon-reduction
interventions** through three comparative scenarios:

| Scenario | Logic |
|---|---|
| **Full coverage** | All interventions applied — shows maximum possible reduction |
| **Fixed budget** | Cheapest interventions first until budget is exhausted |
| **Optimised** | Greedy knapsack: maximises tCO₂e reduced per USD spent |

Aligned with the **GHG Protocol Corporate Standard**, **IPCC AR6** GWP
values, IEA country grid factors, and DEFRA conversion factors.

---

## Who Verdex is for

Any organisation under pressure to disclose emissions in a grant
application:

- Health NGOs and clinical facilities
- Research labs and university departments
- Government and public-sector bodies
- Education organisations
- Small and medium businesses
- Foundation grantees of any sector

22 organisation types and 13 countries are supported out of the box
(Sub-Saharan Africa, South Asia, OECD donor countries).

---

## Emission categories (11 — GHG Protocol scope structure)

| # | Category | Scope |
|---|---|---|
| 1 | Grid electricity | 2 |
| 2 | Grid / piped gas | 1 |
| 3 | Bottled gas (LPG) | 1 |
| 4 | Liquid fuel (diesel) | 1 |
| 5 | Vehicle fuel — owned fleet | 1 |
| 6 | Business travel | 3 |
| 7 | Anaesthetic gases (clinical only) | 1 |
| 8 | Refrigeration gases (HFCs) | 1 |
| 9 | Waste management | 3 |
| 10 | Medical inhalers (clinical only) | 1 |
| 11 | Contractor logistics | 3.4 |

Non-applicable categories (e.g. anaesthetics for a research office) accept
0 — the optimiser works on partial data.

---

## Intervention library

59 interventions covering universal infrastructure (LED lighting, solar
PV, fleet electrification, refrigerant swaps, insulation, training) and
clinical-specific items (low-GWP anaesthetics, dry-powder inhaler swaps).
Each entry has cost defaults sourced from the HIGH Horizons D3.7 case
studies; users override with site-specific costs as they refine.

On organisation creation, all 59 are auto-attached so the optimiser works
in the very first session — no manual setup required.

---

## Technical stack

- **Backend:** Django 5.1 · Python 3.12 · SQLite (preview) · PostgreSQL via Supabase (production)
- **Optimisation engine:** `appname/modeling.py` — `CarbomicaOptimizer` class
- **Frontend:** Bootstrap 5 · Plotly.js
- **Deployment:** Firebase Hosting → Cloud Run (`verdex-backend` service)

---

## Local setup

```bash
git clone https://github.com/Logic06183/Carbomica_App_Django.git
cd Carbomica_App_Django
git checkout verdex
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_interventions
python manage.py createsuperuser         # for /admin access
DEMO_MODE=True python manage.py runserver
```

Open http://127.0.0.1:8000 — DEMO_MODE auto-logs you in as a demo guest.

### Environment variables

| Variable | Default | Notes |
|---|---|---|
| `BRAND_NAME` | `Verdex` | Brand displayed in templates |
| `BRAND_EDITION` | `verdex` | Branch identifier |
| `DEMO_MODE` | `False` | Set `True` to bypass Google OAuth (preview only) |
| `DATABASE_URL` | SQLite | Supabase Postgres pooler URI in production |
| `DJANGO_SECRET_KEY` | insecure default | Override in production |
| `GOOGLE_CLIENT_ID` | empty | Required for production OAuth |
| `GOOGLE_SECRET` | empty | Required for production OAuth |

---

## Deploy

The `deploy.sh` script handles everything for the standard preview
deployment:

```bash
./deploy.sh                  # Cloud Run + Firebase Hosting
./deploy.sh --backend-only   # Cloud Run rebuild only
./deploy.sh --hosting-only   # static files only

# Production deploy (requires Supabase + OAuth env vars):
PRODUCTION=1 ./deploy.sh
```

---

## Methodology references

- **GHG Protocol Corporate Standard** — scope structure
- **IPCC AR6 (Working Group I, 2021)** — GWP100 values for halogenated gases
- **IEA Emissions Factors 2023** — country grid emission factors
- **UK BEIS / DEFRA 2023** — fuel and transport conversion factors
- **HIGH Horizons D3.7** (Luchters et al., 2024) — intervention cost
  catalogue and Carbon/Cost Calculator. DOI: [10.5281/zenodo.12730527](https://zenodo.org/records/12730527)
- **HIGH Horizons D2.11** (Sulaiman et al., 2024) — emission baseline
  methodology. DOI: [10.5281/zenodo.12703876](https://zenodo.org/records/12703876)

See `VERDEX_METHODOLOGY.md` for the full breakdown of what each source
contributes to the calculation chain and where Phase 2 will add
spend-based fallback / sector benchmarks / Climatiq API integration.

