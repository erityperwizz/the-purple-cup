# BrewMetrics — Marketing Analytics for *The Purple Cup*

**[▶ Open the live dashboard](https://the-purple-cup-mnxzcg2cphte2fq3hyqsqh.streamlit.app/)**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://the-purple-cup-mnxzcg2cphte2fq3hyqsqh.streamlit.app/)

> **Simulated data · portfolio project.** The Purple Cup is a fictional
> small-batch specialty drink brand (matcha, ube, coffee). All customers,
> campaigns, and purchases in this repository are synthetic data generated
> for demonstration. No real customer data is used anywhere in this project.

A marketing analytics engine and interactive dashboard for a fictional
direct-to-consumer beverage brand. It demonstrates the core skills of a
marketing / data analyst — SQL, funnel & conversion analysis, attribution
modeling, A/B testing with statistical significance, RFM + k-means customer
segmentation, ROAS, and dashboarding — end to end on data that is fully
controlled and reproducible.

**The skills demonstrated are real; the data is invented and labeled as such.**

## Status

The analysis, dashboard and deployment are complete.

- [x] Phase 0 — Project setup (environment, dependencies, repo scaffolding)
- [x] Phase 1 — Brand design + synthetic data generation
- [x] Phase 2 — SQL analysis layer
- [x] Phase 3 — Funnel & conversion analysis
- [x] Phase 4 — Attribution modeling (first / last / linear touch)
- [x] Phase 5 — Email A/B test (two-proportion z-test)
- [x] Phase 6 — Customer segmentation (RFM + k-means)
- [x] Phase 7 — Streamlit dashboard
- [x] Phase 8 — Deploy to a public link (Streamlit Community Cloud)
- [ ] Phase 9 — README polish + written findings

## Selected findings

All figures below come from the synthetic dataset in `data/brewmetrics.db`.

- **Blended ROAS is 1.73x** — $92,091 in revenue on $53,200 of spend across five
  campaigns and six months.
- **The biggest fixable leak is clicks → add to cart**, which loses 77% of the
  prior stage. Lifting it five points is worth roughly $19,779 in revenue.
- **Last-touch attribution undervalues Instagram.** It is credited $13,263 on a
  last-touch basis but $37,897 on first touch: it starts journeys it rarely
  closes, and 48% of purchases involve more than one channel.
- **The email subject-line test is a real win** — 3.00% → 3.70% conversion, a
  23% relative lift, significant at 95% (p = 0.032), though the low end of the
  confidence interval is modest.

## Tech stack

Python (pandas, numpy) · SQL (SQLite) · SciPy · scikit-learn · Streamlit · Plotly

## Getting started (local)

No install needed to look around — the
[live dashboard](https://the-purple-cup-mnxzcg2cphte2fq3hyqsqh.streamlit.app/)
runs the same code. To run it yourself:

```bash
# 1. create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate    # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt

# 3. (optional) rebuild the synthetic database from scratch
python data_generation/generate_data.py

# 4. run the dashboard
streamlit run app/streamlit_app.py
```

The dashboard reads `data/brewmetrics.db`, which is committed to this repo so
the app runs immediately after cloning. Step 3 regenerates it and is only
needed if you want to change the simulation.

## Project layout

```
analysis/           funnel, attribution, A/B test and segmentation modules
app/                the Streamlit dashboard
data/               the generated SQLite database
data_generation/    the seeded synthetic-data generator
sql/                standalone analysis queries
```

## Author

Erica Mathias
