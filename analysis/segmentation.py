"""
============================================================================
 The Purple Cup - Customer Segmentation (RFM + k-means)
============================================================================
 SIMULATED / SYNTHETIC DATA - PORTFOLIO PROJECT.
 Runs against data/brewmetrics.db.  The data is invented; the analysis is
 real.  Author: Erica Mathias
----------------------------------------------------------------------------
 WHAT THIS DOES
   1. Computes RFM for every customer who has purchased:
        Recency   - days since their last purchase (smaller = more recent)
        Frequency - number of purchases
        Monetary  - total revenue from that customer
   2. Log-transforms F and M (to tame a few big spenders) and standardizes all
      three features so k-means, which uses distance, treats them fairly.
   3. Runs k-means with k=4 (random_state fixed for reproducibility) to group
      customers by similarity.
   4. Reads each cluster's average RFM profile and assigns a business name:
        Champions - recent, frequent, high spend
        Loyal     - frequent, solid spend, slightly less recent
        At risk   - haven't bought in a long time (were customers, going quiet)
        New       - recent but only bought once or twice, low spend so far
   5. Reports segment sizes and value, and flags customers who have not yet
      purchased as a separate Prospects group (they have no RFM to cluster on).

 LEARNING GOAL: explain RFM, why distance-based clustering needs scaling, and
 what k-means is doing (grouping by similarity, no labels given in advance).
============================================================================
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "brewmetrics.db"
K = 4
RANDOM_STATE = 42


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


# ---------------------------------------------------------------------------
# 1. COMPUTE RFM
# ---------------------------------------------------------------------------
def compute_rfm(conn: sqlite3.Connection) -> tuple[pd.DataFrame, int, str]:
    """
    Return one row per PURCHASING customer with recency/frequency/monetary,
    plus the count of customers who have never purchased, plus the analysis
    'snapshot' date used for recency.
    """
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    purchases = pd.read_sql(
        """
        SELECT customer_id,
               timestamp,
               revenue
        FROM events
        WHERE event_type = 'purchase'
        """,
        conn,
        parse_dates=["timestamp"],
    )

    # Recency is measured from a fixed 'snapshot' - the day after the most
    # recent purchase in the data - so the analysis is reproducible.
    snapshot = purchases["timestamp"].max().normalize() + pd.Timedelta(days=1)

    rfm = purchases.groupby("customer_id").agg(
        last_purchase=("timestamp", "max"),
        frequency=("timestamp", "count"),
        monetary=("revenue", "sum"),
    )
    rfm["recency"] = (snapshot - rfm["last_purchase"]).dt.days
    rfm = rfm[["recency", "frequency", "monetary"]].reset_index()

    n_non_purchasers = total_customers - len(rfm)
    return rfm, n_non_purchasers, snapshot.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 2. CLUSTER
# ---------------------------------------------------------------------------
def run_kmeans(rfm: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize features (with a log on the skewed F and M) and run k-means.
    Adds a 'cluster' column. The clustering uses transformed features; all
    reporting later uses the raw dollar/day values so results stay readable.
    """
    features = pd.DataFrame(
        {
            "recency": rfm["recency"],
            # log1p compresses the long right tail of a few frequent/big spenders
            "frequency_log": np.log1p(rfm["frequency"]),
            "monetary_log": np.log1p(rfm["monetary"]),
        }
    )

    # Scale to mean 0 / std 1 so no single feature dominates the distance.
    scaled = StandardScaler().fit_transform(features)

    km = KMeans(n_clusters=K, random_state=RANDOM_STATE, n_init=10)
    rfm = rfm.copy()
    rfm["cluster"] = km.fit_predict(scaled)
    return rfm


# ---------------------------------------------------------------------------
# 3. NAME THE CLUSTERS from their average RFM profile
# ---------------------------------------------------------------------------
def label_clusters(rfm: pd.DataFrame) -> pd.DataFrame:
    """
    Turn anonymous cluster numbers into business names by reading each
    cluster's centroid (average recency/frequency/monetary). Deterministic
    rules so the mapping is explainable, not eyeballed:
      - Champions : best overall (recent + frequent + high spend)
      - At risk   : longest time since last purchase
      - Loyal     : of the two remaining, the more frequent buyers
      - New       : of the two remaining, the less frequent buyers
    """
    centroids = rfm.groupby("cluster").agg(
        recency=("recency", "mean"),
        frequency=("frequency", "mean"),
        monetary=("monetary", "mean"),
    )

    # z-score the centroids ACROSS clusters so the three metrics are comparable.
    z = (centroids - centroids.mean()) / centroids.std(ddof=0)
    # Higher is better: frequent + high spend + recent (recency inverted).
    value_score = z["frequency"] + z["monetary"] - z["recency"]

    remaining = list(centroids.index)

    champions = value_score.idxmax()
    remaining.remove(champions)

    at_risk = centroids.loc[remaining, "recency"].idxmax()
    remaining.remove(at_risk)

    # Of the last two: the more frequent = Loyal, the other = New.
    loyal = centroids.loc[remaining, "frequency"].idxmax()
    remaining.remove(loyal)
    new = remaining[0]

    names = {champions: "Champions", at_risk: "At risk", loyal: "Loyal", new: "New"}
    rfm = rfm.copy()
    rfm["segment"] = rfm["cluster"].map(names)
    return rfm


# ---------------------------------------------------------------------------
# 4. SUMMARIZE
# ---------------------------------------------------------------------------
def summarize(rfm: pd.DataFrame) -> pd.DataFrame:
    """Segment sizes, average RFM, and total/average value per segment."""
    order = ["Champions", "Loyal", "At risk", "New"]
    summary = rfm.groupby("segment").agg(
        customers=("customer_id", "count"),
        avg_recency_days=("recency", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
        total_revenue=("monetary", "sum"),
    )
    summary["pct_of_customers"] = 100 * summary["customers"] / summary["customers"].sum()
    summary["pct_of_revenue"] = 100 * summary["total_revenue"] / summary["total_revenue"].sum()
    return summary.reindex(order).round(2)


def main() -> None:
    conn = get_connection()
    rfm, n_non_purchasers, snapshot = compute_rfm(conn)
    conn.close()

    rfm = run_kmeans(rfm)
    rfm = label_clusters(rfm)
    summary = summarize(rfm)

    print("\n" + "=" * 78)
    print(" THE PURPLE CUP - CUSTOMER SEGMENTATION  (RFM + k-means, SIMULATED DATA)")
    print("=" * 78)
    print(f"\nRecency snapshot date : {snapshot}")
    print(f"Purchasing customers  : {len(rfm):,}  (clustered into k={K} segments)")
    print(f"Prospects (no purchase yet): {n_non_purchasers:,}  (kept separate - no RFM to cluster)")

    print("\nSEGMENT PROFILES  (raw averages; named from each cluster's RFM centroid)")
    print("-" * 78)
    view = summary.copy()
    view["avg_monetary"] = view["avg_monetary"].map("${:,.2f}".format)
    view["total_revenue"] = view["total_revenue"].map("${:,.0f}".format)
    view["pct_of_customers"] = view["pct_of_customers"].map("{:.1f}%".format)
    view["pct_of_revenue"] = view["pct_of_revenue"].map("{:.1f}%".format)
    print(view.to_string())

    champ = summary.loc["Champions"]
    atrisk = summary.loc["At risk"]

    print("\n" + "=" * 78)
    print(" FINDING")
    print("=" * 78)
    print(
        f"- Champions are {champ['pct_of_customers']:.1f}% of buyers but drive "
        f"{champ['pct_of_revenue']:.1f}% of revenue (avg ${champ['avg_monetary']:,.0f} each,\n"
        f"  {champ['avg_frequency']:.1f} orders, last seen ~{champ['avg_recency_days']:.0f} days ago). "
        f"Protect them: loyalty perks, early access."
    )
    print(
        f"\n- At risk are {atrisk['pct_of_customers']:.1f}% of buyers who spent "
        f"${atrisk['avg_monetary']:,.0f} on average but have not bought in "
        f"~{atrisk['avg_recency_days']:.0f} days.\n"
        f"  This is the win-back target - a 'we miss you' offer here is higher ROI than\n"
        f"  chasing brand-new prospects."
    )
    print(
        "\n- New buyers need a second-purchase nudge to graduate toward Loyal/Champions;\n"
        f"  the {n_non_purchasers:,} never-purchased prospects are a separate acquisition problem."
    )
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
