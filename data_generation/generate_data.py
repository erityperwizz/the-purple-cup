"""
============================================================================
 The Purple Cup - Synthetic Marketing Data Generator
============================================================================
 SIMULATED / SYNTHETIC DATA - PORTFOLIO PROJECT.

 The Purple Cup is a FICTIONAL small-batch specialty drink brand (matcha,
 ube, coffee). Every customer, campaign, event, and dollar produced by this
 script is INVENTED for demonstration. No real people and no real customer
 data are involved anywhere in this project.

 The analytical skills demonstrated downstream (SQL, funnel analysis,
 attribution, A/B testing, RFM/k-means segmentation) are real and are
 performed on the data this script builds.

 Author: Erica Mathias
----------------------------------------------------------------------------
 WHAT THIS SCRIPT DOES
   Builds a small SQLite database (data/brewmetrics.db) with four tables:
     - products   : the catalog (dimension table)
     - customers  : who they are, where, when they signed up (dimension)
     - campaigns  : our 5 marketing pushes, their spend AND impressions
                    delivered (dimension)
     - events     : the identified-user event log - one row per click,
                    add_to_cart, or purchase (the FACT table)

 A MODELING DECISION worth explaining in an interview:
   Ad IMPRESSIONS are stored as an aggregate count on each campaign row,
   not as ~1.1M individual event rows. Real ad impressions arrive
   pre-aggregated (there is no identified row per anonymous ad view), while
   clicks / carts / purchases are identified user events stored one row
   each. This mirrors how marketing data actually arrives and keeps the
   database tiny enough to deploy for free. The funnel still covers all four
   stages: the impressions stage is a SUM over campaigns; clicks -> cart ->
   purchase are COUNTs over the events table.

 REPRODUCIBILITY:
   We seed NumPy's random generator (SEED below). The data is random in
   shape but identical every run, so anyone can reproduce these exact
   numbers.
============================================================================
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 0. CONFIGURATION  (all the knobs in one place)
# ---------------------------------------------------------------------------

SEED = 42                       # seed -> identical "random" data every run
RNG = np.random.default_rng(SEED)

# Where the database is written (…/brewmetrics/data/brewmetrics.db)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "brewmetrics.db"

# The 6-month simulated window.
SIM_START = pd.Timestamp("2025-01-01")
SIM_END = pd.Timestamp("2025-06-30 23:59:59")

N_CUSTOMERS = 3000

# The four marketing channels. Order matters: it indexes the per-customer
# channel-affinity matrix built later.
CHANNELS = ["Email", "Instagram", "Paid Search", "Referral"]

# Customer home regions and how likely a new customer is from each.
REGIONS = ["West", "Midwest", "Northeast", "South", "International"]
REGION_WEIGHTS = [0.34, 0.20, 0.22, 0.18, 0.06]

# ---------------------------------------------------------------------------
# 1. PRODUCT CATALOG  (14 SKUs, $15-$45)
#    Each product also carries a "popularity" weight so purchases are not
#    spread evenly - matcha staples sell more than accessories, like reality.
# ---------------------------------------------------------------------------

PRODUCTS = [
    # sku,     name,                               category,     price, popularity
    ("PC-M01", "Ceremonial Matcha Tin",            "Matcha",     32.00, 10),
    ("PC-M02", "Everyday Matcha Pouch",            "Matcha",     22.00, 14),
    ("PC-M03", "Matcha Latte Starter Kit",         "Matcha",     45.00, 6),
    ("PC-M04", "Hojicha Roast Pouch",              "Matcha",     20.00, 7),
    ("PC-U05", "Ube Coconut Latte Blend",          "Ube",        26.00, 9),
    ("PC-U06", "Ube Syrup Bottle",                 "Ube",        18.00, 8),
    ("PC-U07", "Ube Cookie Butter Spread",         "Ube",        16.00, 5),
    ("PC-C08", "Purple Reign Single-Origin Beans", "Coffee",     24.00, 9),
    ("PC-C09", "Cold Brew Concentrate",            "Coffee",     21.00, 8),
    ("PC-C10", "Lavender Mocha Blend",             "Coffee",     25.00, 6),
    ("PC-B11", "Butterfly Pea Flower Tea",         "Botanical",  19.00, 5),
    ("PC-B12", "The Purple Cup Ceramic Mug",       "Accessory",  28.00, 4),
    ("PC-B13", "Starter Sampler Box",              "Bundle",     38.00, 7),
    ("PC-B14", "Reusable Milk Frother",            "Accessory",  15.00, 4),
]

# ---------------------------------------------------------------------------
# 2. CAMPAIGNS  (5 campaigns over 6 months, all four channels represented)
#    Each row carries the ad SPEND and the IMPRESSIONS delivered (top of the
#    funnel). Impression volume roughly tracks channel + spend.
# ---------------------------------------------------------------------------

CAMPAIGNS = [
    # name,                    channel,       start,        end,          spend,   impressions
    ("New Year Matcha Reset",  "Instagram",   "2025-01-01", "2025-02-28",  12000,  260_000),
    ("Always-On Search",       "Paid Search", "2025-01-01", "2025-06-30",  18000,  300_000),
    ("Ube Season Launch",      "Instagram",   "2025-03-01", "2025-04-30",  14000,  320_000),
    ("Loyalty & Winback",      "Email",       "2025-01-01", "2025-06-30",   3200,  180_000),
    ("Refer-a-Friend",         "Referral",    "2025-02-01", "2025-06-30",   6000,   70_000),
]

# ---------------------------------------------------------------------------
# 3. CHANNEL FUNNEL BEHAVIOR  (this is what makes channels perform DIFFERENTLY)
#    For each channel:
#      ctr        = P(click | impression)          how enticing the ad is
#      cart_rate  = P(add_to_cart | click)         product-page appeal
#      buy_rate   = P(purchase   | add_to_cart)    checkout intent
#    Paid Search / Referral are high-intent (people asked for it); Instagram
#    is discovery (great reach, weak immediate conversion).
# ---------------------------------------------------------------------------

CHANNEL_FUNNEL = {
    "Email":       dict(ctr=0.026, cart_rate=0.22, buy_rate=0.38),
    "Instagram":   dict(ctr=0.013, cart_rate=0.16, buy_rate=0.30),
    "Paid Search": dict(ctr=0.038, cart_rate=0.26, buy_rate=0.42),
    "Referral":    dict(ctr=0.055, cart_rate=0.32, buy_rate=0.48),
}

# Journey-timing bias per channel, expressed as Beta(a, b) shape parameters
# used to place a touchpoint within its campaign window (0 = start, 1 = end).
#   a<b  -> skews EARLY  (discovery channels people meet first)
#   a>b  -> skews LATE   (intent channels people hit right before buying)
# This nudges Instagram/Referral toward being FIRST touches and Paid
# Search/Email toward LAST touches, which creates a real attribution story
# in Phase 4 (Instagram looks weak on last-touch but drives first discovery).
CHANNEL_TIMING = {
    "Instagram":   (1.5, 3.0),   # early
    "Referral":    (1.8, 2.6),   # early-ish
    "Email":       (2.2, 2.2),   # spread out
    "Paid Search": (3.0, 1.6),   # late
}


# ===========================================================================
# BUILDERS
# ===========================================================================

def build_products() -> pd.DataFrame:
    """The product catalog dimension table."""
    df = pd.DataFrame(
        PRODUCTS, columns=["sku", "name", "category", "price", "popularity"]
    )
    df.insert(0, "product_id", range(1, len(df) + 1))
    return df


def build_customers() -> pd.DataFrame:
    """
    The customers dimension table.

    Each customer gets a random 'channel affinity' - a set of weights over the
    four channels drawn from a Dirichlet distribution. A low concentration
    (alpha < 1) makes most customers lean heavily toward one or two channels,
    like real people who mostly live on Instagram OR mostly find brands via
    search. These affinities decide who is most likely to click each campaign,
    which in turn gives customers VARIED multi-channel journeys for attribution.
    """
    ids = np.arange(1, N_CUSTOMERS + 1)

    # Signup dates: spread from 60 days before the window through its end.
    signup_span_days = (SIM_END - (SIM_START - pd.Timedelta(days=60))).days
    signup_offsets = RNG.integers(0, signup_span_days, size=N_CUSTOMERS)
    signup_dates = (SIM_START - pd.Timedelta(days=60)) + pd.to_timedelta(
        signup_offsets, unit="D"
    )

    regions = RNG.choice(REGIONS, size=N_CUSTOMERS, p=REGION_WEIGHTS)

    # Channel-affinity matrix, shape (N_CUSTOMERS, 4). Kept in-memory only;
    # it drives event generation and is not stored in the database.
    affinity = RNG.dirichlet(alpha=[0.6, 0.6, 0.6, 0.6], size=N_CUSTOMERS)

    customers = pd.DataFrame(
        {
            "customer_id": ids,
            "signup_date": signup_dates.strftime("%Y-%m-%d"),
            "region": regions,
        }
    )
    return customers, affinity


def build_campaigns() -> pd.DataFrame:
    """The campaigns dimension table (spend + impressions delivered)."""
    df = pd.DataFrame(
        CAMPAIGNS,
        columns=["name", "channel", "start_date", "end_date", "spend", "impressions"],
    )
    df.insert(0, "campaign_id", range(1, len(df) + 1))
    return df


def build_events(campaigns: pd.DataFrame, products: pd.DataFrame,
                 affinity: np.ndarray) -> pd.DataFrame:
    """
    Build the identified-user event log: one row per click, add_to_cart, and
    purchase. Impressions live on the campaigns table (see header note).

    For each campaign we:
      1. Draw the number of CLICKS as Binomial(impressions, channel CTR).
         (Binomial = flip a weighted coin once per impression.)
      2. Assign each click to a customer, weighted by that customer's affinity
         for the campaign's channel -> realistic, varied journeys.
      3. Time each click inside the campaign window using the channel's Beta
         timing bias (discovery channels early, intent channels late).
      4. Thin clicks -> add_to_cart -> purchase using the channel's stage
         rates, so the funnel narrows.
      5. Give each purchase a product (popularity-weighted), a quantity, and
         revenue = price * quantity.
    """
    product_ids = products["product_id"].to_numpy()
    product_prices = products.set_index("product_id")["price"]
    product_probs = (
        products["popularity"] / products["popularity"].sum()
    ).to_numpy()

    frames: list[pd.DataFrame] = []

    for camp in campaigns.itertuples(index=False):
        channel = camp.channel
        rates = CHANNEL_FUNNEL[channel]
        ch_idx = CHANNELS.index(channel)

        start = pd.Timestamp(camp.start_date)
        end = pd.Timestamp(camp.end_date) + pd.Timedelta(hours=23, minutes=59)
        duration_s = (end - start).total_seconds()

        # --- Stage 1: how many clicks did this campaign earn? ---------------
        n_clicks = int(RNG.binomial(camp.impressions, rates["ctr"]))
        if n_clicks == 0:
            continue

        # --- Stage 2: which customer made each click? ----------------------
        # Weight by affinity for THIS channel, normalized to a probability.
        p_customer = affinity[:, ch_idx]
        p_customer = p_customer / p_customer.sum()
        click_customers = RNG.choice(
            N_CUSTOMERS, size=n_clicks, p=p_customer
        ) + 1  # +1 -> customer_ids are 1-based

        # --- Stage 3: when did each click happen? --------------------------
        a, b = CHANNEL_TIMING[channel]
        positions = RNG.beta(a, b, size=n_clicks)          # 0..1 in the window
        click_offsets = (positions * duration_s).astype("int64")
        click_times = start + pd.to_timedelta(click_offsets, unit="s")

        # Click rows (no product, no revenue).
        clicks = pd.DataFrame(
            {
                "customer_id": click_customers,
                "campaign_id": camp.campaign_id,
                "product_id": pd.NA,
                "event_type": "click",
                "timestamp": click_times,
                "revenue": 0.0,
            }
        )
        frames.append(clicks)

        # --- Stage 4: which clicks became add_to_cart? ---------------------
        cart_mask = RNG.random(n_clicks) < rates["cart_rate"]
        n_carts = int(cart_mask.sum())
        if n_carts == 0:
            continue

        cart_customers = click_customers[cart_mask]
        # Carts happen minutes-to-hours after the click, still in-window.
        cart_delay = pd.to_timedelta(RNG.integers(60, 7200, n_carts), unit="s")
        cart_times = click_times[cart_mask] + cart_delay

        carts = pd.DataFrame(
            {
                "customer_id": cart_customers,
                "campaign_id": camp.campaign_id,
                "product_id": pd.NA,
                "event_type": "add_to_cart",
                "timestamp": cart_times,
                "revenue": 0.0,
            }
        )
        frames.append(carts)

        # --- Stage 5: which carts became purchases? ------------------------
        buy_mask = RNG.random(n_carts) < rates["buy_rate"]
        n_buys = int(buy_mask.sum())
        if n_buys == 0:
            continue

        buy_customers = cart_customers[buy_mask]
        buy_times = cart_times[buy_mask] + pd.to_timedelta(
            RNG.integers(30, 1800, n_buys), unit="s"
        )
        bought_products = RNG.choice(product_ids, size=n_buys, p=product_probs)
        # Quantity 1-3, weighted toward single-item orders.
        quantities = RNG.choice([1, 2, 3], size=n_buys, p=[0.7, 0.22, 0.08])
        revenue = product_prices.loc[bought_products].to_numpy() * quantities

        purchases = pd.DataFrame(
            {
                "customer_id": buy_customers,
                "campaign_id": camp.campaign_id,
                "product_id": bought_products,
                "event_type": "purchase",
                "timestamp": buy_times,
                "revenue": np.round(revenue, 2),
            }
        )
        frames.append(purchases)

    events = pd.concat(frames, ignore_index=True)

    # Sort chronologically so the event log reads like a real timeline, then
    # assign a clean sequential event_id.
    events = events.sort_values("timestamp").reset_index(drop=True)
    events.insert(0, "event_id", range(1, len(events) + 1))
    events["timestamp"] = events["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return events


# ===========================================================================
# WRITE + REPORT
# ===========================================================================

def write_database(products, customers, campaigns, events) -> None:
    """Write all four tables into a fresh SQLite database file."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()  # start clean so re-runs are deterministic

    with sqlite3.connect(DB_PATH) as conn:
        # 'popularity' is a generation-only weight; drop it from the stored
        # catalog so the database reflects only real business columns.
        products.drop(columns=["popularity"]).to_sql(
            "products", conn, index=False
        )
        customers.to_sql("customers", conn, index=False)
        campaigns.to_sql("campaigns", conn, index=False)
        events.to_sql("events", conn, index=False)

        # A couple of indexes so downstream SQL/dashboard queries stay fast.
        conn.execute("CREATE INDEX idx_events_customer ON events(customer_id)")
        conn.execute("CREATE INDEX idx_events_campaign ON events(campaign_id)")
        conn.execute("CREATE INDEX idx_events_type ON events(event_type)")


def print_summary(campaigns, events) -> None:
    """Print a plain-English sanity check of the funnel we just built."""
    impressions = int(campaigns["impressions"].sum())
    clicks = int((events["event_type"] == "click").sum())
    carts = int((events["event_type"] == "add_to_cart").sum())
    purchases = int((events["event_type"] == "purchase").sum())
    revenue = float(events.loc[events["event_type"] == "purchase", "revenue"].sum())
    spend = float(campaigns["spend"].sum())

    print("\n" + "=" * 60)
    print(" THE PURPLE CUP - synthetic data generated (SIMULATED)")
    print("=" * 60)
    print(f" Customers            : {N_CUSTOMERS:>12,}")
    print(f" Campaigns            : {len(campaigns):>12,}")
    print(f" Event rows (log)     : {len(events):>12,}")
    print("-" * 60)
    print(" FUNNEL (each stage should be smaller than the one above):")
    print(f"   Impressions        : {impressions:>12,}")
    print(f"   Clicks             : {clicks:>12,}   ({clicks/impressions:6.2%} of impressions)")
    print(f"   Add to cart        : {carts:>12,}   ({carts/clicks:6.2%} of clicks)")
    print(f"   Purchases          : {purchases:>12,}   ({purchases/carts:6.2%} of carts)")
    print("-" * 60)
    print(f" Ad spend             : ${spend:>12,.0f}")
    print(f" Revenue              : ${revenue:>12,.0f}")
    print(f" Blended ROAS         : {revenue/spend:>12.2f}   (${revenue/spend:.2f} back per $1)")
    print("=" * 60)
    print(f" Database written to  : {DB_PATH}")
    print(" Reminder: this data is SIMULATED for a portfolio project.\n")


def main() -> None:
    products = build_products()
    customers, affinity = build_customers()
    campaigns = build_campaigns()
    events = build_events(campaigns, products, affinity)

    write_database(products, customers, campaigns, events)
    print_summary(campaigns, events)


if __name__ == "__main__":
    main()
