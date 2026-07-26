"""
============================================================================
 The Purple Cup - Attribution Modeling (first / last / linear touch)
============================================================================
 SIMULATED / SYNTHETIC DATA - PORTFOLIO PROJECT.
 Runs against data/brewmetrics.db.  The data is invented; the analysis is
 real.  Author: Erica Mathias
----------------------------------------------------------------------------
 THE QUESTION
   When several channels touch one customer before they buy, which channel
   gets credit for the revenue? There is no physically correct answer, so we
   compare three standard models and show how the choice changes which
   channel looks best - and therefore where budget should go.

 WHAT COUNTS AS A TOUCHPOINT
   A customer's CLICK events are their engaged touchpoints (each click's
   channel comes from its campaign). Anonymous ad impressions are not
   identified per-customer, so - as in real attribution - we attribute on
   clicks, not impressions.

 HOW A JOURNEY IS DEFINED
   We order each customer's events in time and accumulate their clicks. When
   a purchase occurs, the clicks since that customer's PREVIOUS purchase form
   the journey for this conversion; we credit the purchase revenue, then
   reset. So a repeat buyer contributes one journey per purchase (early
   touches are not re-credited to every later sale).

 THE THREE MODELS (each distributes 100% of every purchase's revenue)
   first-touch : all credit to the journey's first click's channel
   last-touch  : all credit to the last click before the purchase
   linear      : revenue split evenly across every click in the journey
============================================================================
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "brewmetrics.db"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


# ---------------------------------------------------------------------------
# 1. LOAD TOUCHPOINTS  (clicks + purchases, each tagged with its channel)
# ---------------------------------------------------------------------------
def load_events(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Return every click and purchase with its customer, timestamp, channel and
    revenue, sorted so we can walk each customer's journey in order.
    """
    q = """
        SELECT e.customer_id,
               e.timestamp,
               e.event_type,
               c.channel,
               e.revenue
        FROM events    AS e
        JOIN campaigns AS c ON c.campaign_id = e.campaign_id
        WHERE e.event_type IN ('click', 'purchase')
        ORDER BY e.customer_id, e.timestamp, e.event_id
    """
    return pd.read_sql(q, conn)


# ---------------------------------------------------------------------------
# 2. BUILD JOURNEYS AND ATTRIBUTE REVENUE
# ---------------------------------------------------------------------------
def attribute(events: pd.DataFrame) -> dict:
    """
    Walk each customer's timeline, form a journey per purchase, and credit the
    revenue under all three models. Returns per-channel revenue dicts plus
    journey statistics.
    """
    first_touch: dict[str, float] = defaultdict(float)
    last_touch: dict[str, float] = defaultdict(float)
    linear: dict[str, float] = defaultdict(float)

    n_conversions = 0
    n_multitouch = 0          # journeys with 2+ clicks
    n_cross_channel = 0       # journeys where first channel != last channel
    total_touches = 0

    current_journey: list[str] = []      # channels of clicks since last purchase
    current_customer = None

    for row in events.itertuples(index=False):
        if row.customer_id != current_customer:
            current_customer = row.customer_id
            current_journey = []

        if row.event_type == "click":
            current_journey.append(row.channel)
            continue

        # --- a purchase: credit the journey that led here ------------------
        journey = current_journey if current_journey else [row.channel]
        # (fallback: a purchase with no preceding click in this segment is
        #  credited to its own campaign's channel as a single touch)

        revenue = row.revenue
        first_touch[journey[0]] += revenue
        last_touch[journey[-1]] += revenue
        share = revenue / len(journey)
        for ch in journey:
            linear[ch] += share

        n_conversions += 1
        total_touches += len(journey)
        if len(journey) >= 2:
            n_multitouch += 1
        if journey[0] != journey[-1]:
            n_cross_channel += 1

        current_journey = []   # reset for this customer's next journey

    return {
        "first_touch": dict(first_touch),
        "last_touch": dict(last_touch),
        "linear": dict(linear),
        "n_conversions": n_conversions,
        "n_multitouch": n_multitouch,
        "n_cross_channel": n_cross_channel,
        "avg_touches": total_touches / n_conversions if n_conversions else 0,
    }


# ---------------------------------------------------------------------------
# 3. ASSEMBLE THE COMPARISON TABLE  (revenue + ROAS under each model)
# ---------------------------------------------------------------------------
def comparison_table(conn: sqlite3.Connection, attr: dict) -> pd.DataFrame:
    """One row per channel: spend and the revenue + ROAS under each model."""
    spend = dict(
        conn.execute("SELECT channel, SUM(spend) FROM campaigns GROUP BY channel").fetchall()
    )
    channels = sorted(spend)

    df = pd.DataFrame({"channel": channels})
    df["spend"] = df["channel"].map(spend)
    for model in ("first_touch", "last_touch", "linear"):
        rev = attr[model]
        df[f"{model}_rev"] = df["channel"].map(lambda c: round(rev.get(c, 0.0), 0))
        df[f"{model}_roas"] = (df[f"{model}_rev"] / df["spend"]).round(2)
    return df.sort_values("last_touch_rev", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. REPORT
# ---------------------------------------------------------------------------
def main() -> None:
    conn = get_connection()
    events = load_events(conn)
    attr = attribute(events)
    table = comparison_table(conn, attr)
    conn.close()

    print("\n" + "=" * 72)
    print(" THE PURPLE CUP - ATTRIBUTION MODELING  (SIMULATED DATA)")
    print("=" * 72)

    print(
        f"\nConversions analyzed : {attr['n_conversions']:,}"
        f"\nAvg touchpoints/conv : {attr['avg_touches']:.2f}"
        f"\nMulti-touch journeys : {attr['n_multitouch']:,} "
        f"({100*attr['n_multitouch']/attr['n_conversions']:.1f}% had 2+ clicks)"
        f"\nCross-channel journeys: {attr['n_cross_channel']:,} "
        f"({100*attr['n_cross_channel']/attr['n_conversions']:.1f}% started and ended on different channels)"
    )

    print("\nREVENUE CREDITED BY MODEL")
    print("-" * 72)
    rev_view = table[["channel", "first_touch_rev", "last_touch_rev", "linear_rev"]].copy()
    for col in rev_view.columns[1:]:
        rev_view[col] = rev_view[col].map("${:,.0f}".format)
    print(rev_view.to_string(index=False))

    print("\nROAS BY MODEL  ($ credited per $1 spent)")
    print("-" * 72)
    roas_view = table[["channel", "spend", "first_touch_roas", "last_touch_roas", "linear_roas"]]
    print(roas_view.to_string(index=False))

    # --- find the channel most under-credited by last-touch vs first-touch --
    table["first_minus_last"] = table["first_touch_rev"] - table["last_touch_rev"]
    undervalued = table.loc[table["first_minus_last"].idxmax()]
    overvalued = table.loc[table["first_minus_last"].idxmin()]

    print("\n" + "=" * 72)
    print(" FINDING")
    print("=" * 72)
    print(
        f"- {undervalued['channel']} is the most UNDERVALUED by last-touch: it is\n"
        f"  credited ${undervalued['last_touch_rev']:,.0f} on last-touch "
        f"(ROAS {undervalued['last_touch_roas']:.2f}) but ${undervalued['first_touch_rev']:,.0f} "
        f"on first-touch (ROAS {undervalued['first_touch_roas']:.2f}).\n"
        f"  It is a DISCOVERY channel - it starts journeys it rarely closes, so the\n"
        f"  ad-platform default (last-touch) makes it look like a money-loser."
    )
    print(
        f"\n- {overvalued['channel']} is the most flattered by last-touch: it CLOSES\n"
        f"  journeys that other channels started, so last-touch over-credits it."
    )
    print(
        "\n- BUDGET IMPLICATION: judging channels only on last-touch would cut the\n"
        "  very channel that fills the top of the funnel. Linear (or a first-touch\n"
        "  cross-check) protects discovery spend. The 'right' model depends on the\n"
        "  goal: last-touch for efficiency, first-touch for growth, linear to balance."
    )
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
