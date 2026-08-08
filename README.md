# BrewMetrics: Marketing Analytics for *The Purple Cup*

**[▶ Open the live dashboard](https://the-purple-cup-mnxzcg2cphte2fq3hyqsqh.streamlit.app/)**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://the-purple-cup-mnxzcg2cphte2fq3hyqsqh.streamlit.app/)

> **Simulated data · portfolio project.** The Purple Cup is a fictional
> small-batch specialty drink brand (matcha, ube, coffee). All customers,
> campaigns, and purchases in this repository are synthetic data generated
> for demonstration. No real customer data is used anywhere in this project.

A marketing analytics engine and interactive dashboard for a fictional
direct-to-consumer beverage brand. It demonstrates the core skills of a
marketing / data analyst: SQL, funnel & conversion analysis, attribution
modeling, A/B testing with statistical significance, RFM + k-means customer
segmentation, ROAS, and dashboarding, end to end on data that is fully
controlled and reproducible.

**The skills demonstrated are real; the data is invented and labeled as such.**

## Status

Complete. The analysis, dashboard, deployment and write-up are all done.

- [x] Phase 0: Project setup (environment, dependencies, repo scaffolding)
- [x] Phase 1: Brand design + synthetic data generation
- [x] Phase 2: SQL analysis layer
- [x] Phase 3: Funnel & conversion analysis
- [x] Phase 4: Attribution modeling (first / last / linear touch)
- [x] Phase 5: Email A/B test (two-proportion z-test)
- [x] Phase 6: Customer segmentation (RFM + k-means)
- [x] Phase 7: Streamlit dashboard
- [x] Phase 8: Deploy to a public link (Streamlit Community Cloud)
- [x] Phase 9: README polish + written findings

## The headline numbers

Six months of activity across five campaigns and four channels.

| Metric | Value |
| --- | --- |
| Ad spend | $53,200 |
| Revenue | $92,091 |
| Blended ROAS | 1.73x |
| Impressions | 1,130,000 |
| Clicks | 27,452 |
| Purchases | 2,601 |
| Click to purchase | 9.5% |
| Average order value | $35.41 |
| Purchasing customers | 1,686 |

## Findings

### 1. The budget is close to inverted against channel efficiency

This is the most actionable result in the project. Instagram takes **49% of the
entire budget** ($26,000 of $53,200) and returns **0.51x on a last-touch basis**,
meaning it loses money on every dollar under the model most ad platforms report
by default. Email takes **6% of the budget** ($3,200) and returns **4.24x**.

Instagram is not actually worthless, though, and this is where attribution
matters. Credit it on first touch instead and its revenue jumps from $13,263 to
$37,897, the largest first-touch figure of any channel. It is the brand's main
discovery engine: it starts journeys it rarely closes. Under linear attribution,
which splits credit evenly across every touch, it lands at 0.99x, roughly
break-even.

| Channel | Spend | Last-touch ROAS | First-touch ROAS | Linear ROAS |
| --- | --- | --- | --- | --- |
| Email | $3,200 | 4.24x | 4.46x | 4.60x |
| Referral | $6,000 | 3.58x | 2.28x | 2.86x |
| Paid Search | $18,000 | 2.43x | 1.46x | 1.91x |
| Instagram | $26,000 | 0.51x | 1.46x | 0.99x |

Two things stand out. Email is the strongest channel under *every* model, which
is unusual and makes it the safest place to spend more. Instagram's verdict
depends entirely on which model you choose, so any decision about it is really a
decision about attribution, and **48% of purchases involve more than one
channel**, so single-touch models are misleading here by construction.

### 2. The fixable leak is on-site, not in the ads

The funnel loses 97.6% of impressions at the click step, but that is a media and
creative problem, and a 2.4% click rate is not unusual for paid social. The
interesting number is the next one.

| Stage | Count | Conversion from previous |
| --- | --- | --- |
| Impressions | 1,130,000 | |
| Clicks | 27,452 | 2.4% |
| Add to cart | 6,390 | 23.3% |
| Purchase | 2,601 | 40.7% |

**Clicks to add-to-cart loses 76.7%, or 21,062 people.** These are visitors who
already chose to arrive, so the cost of acquiring them is sunk, which makes this
the highest-leverage step a marketer actually controls. Lifting it by five
percentage points, from 23.3% to 28.3%, yields 559 more purchases and about
**$19,779 in additional revenue** at the current average order value, with no
extra ad spend.

Cart to purchase, at 40.7%, is the second candidate and typically responds to
checkout friction and shipping cost transparency.

### 3. The subject-line test wins, but the effect size is uncertain

Variant B ("A little purple surprise inside") converted at 3.70% against
variant A's 3.00%, a 23% relative lift, on roughly 6,000 recipients per arm.

| | Recipients | Conversions | Rate |
| --- | --- | --- | --- |
| Variant A | 6,033 | 181 | 3.00% |
| Variant B | 5,967 | 221 | 3.70% |

A two-proportion z-test gives z = 2.14 and **p = 0.032**, significant at the 95%
level. The honest caveat is the confidence interval: the true lift sits between
**+0.06 and +1.35 percentage points**, and the low end is close to zero. So the
direction is trustworthy and B should ship, but anyone forecasting revenue off a
23% lift is over-reading a result whose plausible floor is almost nothing. A
larger sample would be needed to pin the magnitude down.

### 4. Retention is worth more than the customer counts suggest

RFM scoring plus k-means (k = 4) splits 1,686 buyers into four groups that
behave differently enough to justify different marketing. Recency snapshot:
2025-07-01.

| Segment | Customers | % of buyers | Revenue | % of revenue | Avg orders | Median recency |
| --- | --- | --- | --- | --- | --- | --- |
| Champions | 205 | 12.2% | $24,282 | 26.4% | 3.20 | 34 days |
| Loyal | 481 | 28.5% | $33,851 | 36.8% | 1.94 | 56 days |
| At risk | 491 | 29.1% | $17,863 | 19.4% | 1.03 | 117 days |
| New | 509 | 30.2% | $16,095 | 17.5% | 1.00 | 52 days |

**Champions are 12% of buyers but 26% of revenue**, and they order more than
three times each against roughly one for everybody else. Champions and Loyal
together are 41% of customers and 63% of revenue.

The clearest opportunity is **At risk**: 491 customers, nearly a third of the
base, who bought once and have not returned in a median of 117 days, about four
months. They have already proven they will buy, so reactivating them costs far
less than acquiring a stranger. Separately, **1,314 people have never purchased
at all** and are held out of the segmentation entirely; they are an acquisition
problem, not a retention one, and mixing the two would distort both.

### What I would do next

1. **Move budget from Instagram to Email and Referral.** Email returns over 4x
   under every attribution model on only 6% of the budget, and it is the least
   ambiguous result in the analysis.
2. **Do not switch Instagram off.** It originates more revenue than any other
   channel on first touch. Judge it on assisted conversions, not last click.
3. **Fix the clicks to add-to-cart step first.** It is worth about $19,779 for
   five points of improvement and needs no additional spend.
4. **Ship variant B, but re-test at a larger sample** before building forecasts
   on the size of the lift.
5. **Build a win-back campaign for the 491 At risk customers** before spending
   more on acquisition.

## How the analysis works

- **Funnel** (`analysis/funnel.py`): counts each stage from the events log,
  computes step conversion and drop-off, then separates the largest raw drop
  from the largest *fixable* on-site drop, since impressions to clicks is a
  media lever rather than something a marketer changes on the site.
- **Attribution** (`analysis/attribution.py`): rebuilds each customer's touch
  sequence and assigns purchase revenue under first-touch, last-touch and
  linear rules, so the three can be compared side by side.
- **A/B test** (`analysis/ab_test.py`): a two-proportion z-test with a
  chi-square cross-check, reporting the p-value and the confidence interval for
  the difference rather than the point estimate alone.
- **Segmentation** (`analysis/segmentation.py`): computes recency, frequency
  and monetary value per customer, standardizes them, and clusters with k-means
  (k = 4, fixed random seed). Never-purchased prospects are excluded so they
  cannot drag the clusters.

The dashboard imports these modules directly rather than re-implementing
anything, so the numbers on screen and the numbers in the analysis layer cannot
drift apart.

## Tech stack

Python (pandas, numpy) · SQL (SQLite) · SciPy · scikit-learn · Streamlit · Plotly

## Getting started (local)

No install needed to look around, since the
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
