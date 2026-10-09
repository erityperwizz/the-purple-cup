# Databricks notebook source
# MAGIC %md
# MAGIC # The Purple Cup on Databricks | 05 Reconciliation
# MAGIC **Simulated / synthetic data. Portfolio project by Erica Mathias.**
# MAGIC
# MAGIC A migration is only finished when the new system produces the **same numbers** as the old one.
# MAGIC This notebook checks two things:
# MAGIC 1. **No rows lost:** bronze and silver row counts match the source files.
# MAGIC 2. **Same answers:** the gold marts match the figures from the original SQLite queries and pandas analysis.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "purple_cup")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
NS = f"{CATALOG}.{SCHEMA}"

# COMMAND ----------

import os
import pandas as pd

checks = []

def check(name, actual, expected, tol=0.0):
    ok = abs(float(actual) - float(expected)) <= tol
    checks.append({"check": name, "expected": float(expected), "actual": float(actual),
                   "status": "PASS" if ok else "FAIL"})

# 1. Row counts: source CSV -> bronze -> silver
repo_data_dir = os.path.join(os.getcwd(), "data")
for t in ["products", "customers", "campaigns", "events"]:
    src = len(pd.read_csv(os.path.join(repo_data_dir, f"{t}.csv")))
    check(f"bronze_{t} rows = source file", spark.table(f"{NS}.bronze_{t}").count(), src)
    check(f"silver_{t} rows = source file", spark.table(f"{NS}.silver_{t}").count(), src)

# 2. Headline numbers from the original analysis (README)
fun = {r.stage: r["count"] for r in spark.table(f"{NS}.gold_funnel").collect()}
check("impressions", fun["Impressions"], 1_130_000)
check("clicks", fun["Clicks"], 27_452)
check("add to cart", fun["Add to cart"], 6_390)
check("purchases", fun["Purchase"], 2_601)

tot = spark.sql(f"SELECT SUM(revenue) rev, SUM(spend) spend FROM {NS}.gold_channel_roas").collect()[0]
check("total revenue ($)", tot.rev, 92_091, tol=0.5)
check("total spend ($)", tot.spend, 53_200, tol=0.5)
check("blended ROAS", round(float(tot.rev) / float(tot.spend), 2), 1.73, tol=0.001)

# Channel ROAS as computed by sql/analysis_queries.sql Query 2 (credit goes to the campaign that recorded
# the purchase). attribution.py rebuilds full click journeys instead, which is why the README's last-touch
# figures differ by a cent or two for Email (4.24) and Paid Search (2.43).
expected_roas = {"Email": 4.22, "Referral": 3.58, "Paid Search": 2.44, "Instagram": 0.51}
for r in spark.table(f"{NS}.gold_channel_roas").collect():
    check(f"campaign-level ROAS: {r.channel}", r.roas, expected_roas[r.channel], tol=0.001)

buyers = spark.sql(f"SELECT COUNT(*) FROM {NS}.gold_customer_features WHERE purchased = 1").collect()[0][0]
check("purchasing customers", buyers, 1_686)

result = pd.DataFrame(checks)
display(result)
failed = result[result.status == "FAIL"]
assert failed.empty, f"Reconciliation failed:\n{failed}"
print(f"All {len(result)} reconciliation checks passed. Databricks matches the original analysis.")
