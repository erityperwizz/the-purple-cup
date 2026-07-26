"""
============================================================================
 The Purple Cup - Funnel & Conversion Analysis
============================================================================
 SIMULATED / SYNTHETIC DATA - PORTFOLIO PROJECT.
 Runs against data/brewmetrics.db (built by data_generation/generate_data.py).
 The data is invented; the analysis is real.  Author: Erica Mathias
----------------------------------------------------------------------------
 WHAT THIS DOES
   1. Builds the four-stage funnel (impressions -> clicks -> add_to_cart ->
      purchase) with stage-to-stage conversion AND drop-off.
   2. Distinguishes the raw biggest drop from the biggest FIXABLE, on-site
      leak (the marketer's lever), because low ad click-through is normal
      and is a media problem, not a product-page problem.
   3. Sizes the OPPORTUNITY: what closing that leak would be worth in extra
      purchases and revenue.
   4. Prints a plain-English FINDING you can say out loud in an interview.

 The compute_* functions return DataFrames so the Streamlit dashboard
 (Phase 7) can import and reuse them instead of duplicating logic.
============================================================================
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "brewmetrics.db"

# Order and display names of the funnel stages.
STAGES = ["Impressions", "Clicks", "Add to cart", "Purchase"]


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


# ---------------------------------------------------------------------------
# 1. THE OVERALL FUNNEL
# ---------------------------------------------------------------------------
def compute_funnel(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Return one row per funnel stage with:
      count          - people/events at this stage
      step_conv_pct  - % of the PREVIOUS stage that reached this one
      drop_pct       - % of the previous stage lost here (100 - step_conv_pct)
      dropped_count  - raw number of people lost at this step
    Impressions come from the campaigns table (a SUM); the other stages are
    COUNTs over the events log.
    """
    impressions = conn.execute("SELECT SUM(impressions) FROM campaigns").fetchone()[0]
    counts = dict(
        conn.execute(
            "SELECT event_type, COUNT(*) FROM events GROUP BY event_type"
        ).fetchall()
    )

    rows = [
        ("Impressions", impressions),
        ("Clicks", counts.get("click", 0)),
        ("Add to cart", counts.get("add_to_cart", 0)),
        ("Purchase", counts.get("purchase", 0)),
    ]
    df = pd.DataFrame(rows, columns=["stage", "count"])

    prev = df["count"].shift(1)
    df["step_conv_pct"] = (100.0 * df["count"] / prev).round(2)
    df["drop_pct"] = (100.0 - df["step_conv_pct"]).round(2)
    df["dropped_count"] = (prev - df["count"]).astype("Int64")
    # Share of the very top of the funnel surviving to each stage.
    df["pct_of_impressions"] = (100.0 * df["count"] / df["count"].iloc[0]).round(4)
    return df


# ---------------------------------------------------------------------------
# 2. THE FUNNEL BROKEN OUT BY CHANNEL
#    (Impressions here are per-channel; the on-site steps come from events.)
# ---------------------------------------------------------------------------
def compute_channel_funnel(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per-channel clicks, carts, purchases and the two on-site conversion rates."""
    q = """
        SELECT c.channel,
               SUM(e.event_type = 'click')       AS clicks,
               SUM(e.event_type = 'add_to_cart') AS carts,
               SUM(e.event_type = 'purchase')    AS purchases
        FROM events    AS e
        JOIN campaigns AS c ON c.campaign_id = e.campaign_id
        GROUP BY c.channel
    """
    df = pd.read_sql(q, conn)
    df["click_to_cart_pct"] = (100.0 * df["carts"] / df["clicks"]).round(2)
    df["cart_to_buy_pct"] = (100.0 * df["purchases"] / df["carts"]).round(2)
    return df.sort_values("click_to_cart_pct", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. FIND THE BIGGEST LEAK  (raw vs. fixable/on-site)
# ---------------------------------------------------------------------------
def identify_biggest_leak(funnel: pd.DataFrame) -> dict:
    """
    Identify (a) the largest raw drop across the whole funnel and (b) the
    largest drop among ON-SITE steps a marketer can actually fix - i.e.
    excluding Impressions->Clicks, which is a media/creative lever.
    """
    steps = funnel.iloc[1:].copy()  # skip Impressions (no prior stage)
    steps["from_stage"] = STAGES[:-1]

    raw = steps.loc[steps["drop_pct"].idxmax()]

    onsite = steps[steps["stage"] != "Clicks"]  # exclude Impressions->Clicks
    fixable = onsite.loc[onsite["drop_pct"].idxmax()]

    return {
        "raw_step": f"{raw['from_stage']} -> {raw['stage']}",
        "raw_drop_pct": float(raw["drop_pct"]),
        "raw_dropped": int(raw["dropped_count"]),
        "fixable_step": f"{fixable['from_stage']} -> {fixable['stage']}",
        "fixable_drop_pct": float(fixable["drop_pct"]),
        "fixable_dropped": int(fixable["dropped_count"]),
        "fixable_from": fixable["from_stage"],
        "fixable_to": fixable["stage"],
    }


# ---------------------------------------------------------------------------
# 4. SIZE THE OPPORTUNITY
# ---------------------------------------------------------------------------
def opportunity_scenario(conn: sqlite3.Connection, funnel: pd.DataFrame,
                         leak: dict, uplift_points: float = 5.0) -> dict:
    """
    Illustrative 'what if' for the biggest fixable leak: if we lifted its
    conversion rate by `uplift_points` percentage points, how many extra
    purchases and dollars would follow (holding later stages constant)?

    This is a scenario, NOT a promise - it frames the leak in money so a
    non-analyst can grasp why it matters.
    """
    fstage = leak["fixable_from"]   # e.g. "Add to cart"
    tstage = leak["fixable_to"]     # e.g. "Purchase"
    f_count = int(funnel.loc[funnel["stage"] == fstage, "count"].iloc[0])
    current_rate = float(funnel.loc[funnel["stage"] == tstage, "step_conv_pct"].iloc[0])

    # Extra conversions gained at THIS step from the uplift.
    extra_at_step = f_count * (uplift_points / 100.0)

    # Carry those extra users through any remaining downstream steps at
    # today's rates, so the payoff lands as extra PURCHASES.
    downstream_stages = STAGES[STAGES.index(tstage) + 1:]
    extra_purchases = extra_at_step
    for s in downstream_stages:
        rate = float(funnel.loc[funnel["stage"] == s, "step_conv_pct"].iloc[0]) / 100.0
        extra_purchases *= rate

    # Average order value from the data, to translate purchases into revenue.
    aov = conn.execute(
        "SELECT AVG(revenue) FROM events WHERE event_type = 'purchase'"
    ).fetchone()[0]

    return {
        "step": leak["fixable_step"],
        "current_rate": current_rate,
        "uplift_points": uplift_points,
        "extra_purchases": round(extra_purchases),
        "extra_revenue": round(extra_purchases * aov, 0),
        "aov": round(aov, 2),
    }


# ---------------------------------------------------------------------------
# 5. REPORT
# ---------------------------------------------------------------------------
def main() -> None:
    conn = get_connection()
    funnel = compute_funnel(conn)
    channels = compute_channel_funnel(conn)
    leak = identify_biggest_leak(funnel)
    opp = opportunity_scenario(conn, funnel, leak)
    conn.close()

    print("\n" + "=" * 68)
    print(" THE PURPLE CUP - FUNNEL & CONVERSION ANALYSIS  (SIMULATED DATA)")
    print("=" * 68)

    print("\nOVERALL FUNNEL")
    print("-" * 68)
    show = funnel.copy()
    show["count"] = show["count"].map("{:,}".format)
    print(show.to_string(index=False, na_rep="-"))

    overall = 100.0 * funnel["count"].iloc[-1] / funnel["count"].iloc[0]
    print(f"\nOverall impression -> purchase conversion: {overall:.3f}%")

    print("\nON-SITE FUNNEL BY CHANNEL  (where does each channel lose people?)")
    print("-" * 68)
    print(channels.to_string(index=False))

    print("\n" + "=" * 68)
    print(" FINDING")
    print("=" * 68)
    print(
        f"- The single largest drop is {leak['raw_step']} "
        f"({leak['raw_drop_pct']:.1f}% lost, {leak['raw_dropped']:,} people). "
        f"That is the ad click-through step: low click-through is normal for\n"
        f"  paid media, so this is a targeting/creative lever, not a site fix."
    )
    print(
        f"\n- The largest FIXABLE, on-site leak is {leak['fixable_step']}: "
        f"{leak['fixable_drop_pct']:.1f}% of the previous stage is lost here "
        f"({leak['fixable_dropped']:,} people).\n"
        f"  This points at the product page / merchandising / pricing - the\n"
        f"  highest-leverage place to improve conversion."
    )
    print(
        f"\n- OPPORTUNITY (illustrative): lifting {opp['step']} by "
        f"{opp['uplift_points']:.0f} percentage points would yield roughly "
        f"{opp['extra_purchases']:,} more purchases\n"
        f"  and about ${opp['extra_revenue']:,.0f} in added revenue "
        f"(at the current ${opp['aov']:.2f} average order value)."
    )
    print(
        "\nWhy this matters more than the 0.23% headline rate: the overall rate\n"
        "says the funnel is leaky; the biggest fixable leak says WHERE a fix pays\n"
        "off most. Impact = how many people flow through a step x how much of\n"
        "that step you can realistically recover."
    )
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
