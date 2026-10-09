# Databricks notebook source
# MAGIC %md
# MAGIC # The Purple Cup on Databricks | 02 Silver: types, data quality, constraints
# MAGIC **Simulated / synthetic data. Portfolio project by Erica Mathias.**
# MAGIC
# MAGIC Silver is where raw strings become trustworthy, typed tables. Three things happen here:
# MAGIC 1. **Cast** every column to its real type and **de-duplicate** on the primary key.
# MAGIC 2. Run **data quality checks** (primary keys, foreign keys, allowed values, business rules) and log every result to a table.
# MAGIC 3. Add **Delta CHECK constraints**, so any future write that breaks a rule is rejected by the table itself.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "purple_cup")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
NS = f"{CATALOG}.{SCHEMA}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: cast and de-duplicate

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window


def dedupe(df, key):
    """Keep one row per primary key (the most recently ingested one)."""
    w = Window.partitionBy(key).orderBy(F.col("_ingested_at").desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


products = dedupe(spark.table(f"{NS}.bronze_products"), "product_id").select(
    F.col("product_id").cast("int"),
    F.trim("sku").alias("sku"),
    F.trim("name").alias("name"),
    F.trim("category").alias("category"),
    F.col("price").cast("decimal(10,2)"),
)

customers = dedupe(spark.table(f"{NS}.bronze_customers"), "customer_id").select(
    F.col("customer_id").cast("int"),
    F.to_date("signup_date").alias("signup_date"),
    F.trim("region").alias("region"),
)

campaigns = dedupe(spark.table(f"{NS}.bronze_campaigns"), "campaign_id").select(
    F.col("campaign_id").cast("int"),
    F.trim("name").alias("name"),
    F.trim("channel").alias("channel"),
    F.to_date("start_date").alias("start_date"),
    F.to_date("end_date").alias("end_date"),
    F.col("spend").cast("decimal(12,2)"),
    F.col("impressions").cast("bigint"),
)

events = dedupe(spark.table(f"{NS}.bronze_events"), "event_id").select(
    F.col("event_id").cast("bigint"),
    F.col("customer_id").cast("int"),
    F.col("campaign_id").cast("int"),
    F.col("product_id").cast("int"),          # empty string -> NULL for clicks and carts
    F.lower(F.trim("event_type")).alias("event_type"),
    F.to_timestamp("timestamp").alias("event_ts"),
    F.col("revenue").cast("decimal(12,2)"),
)

for name, df in [("products", products), ("customers", customers),
                 ("campaigns", campaigns), ("events", events)]:
    df.write.format("delta").mode("overwrite").option("overwriteSchema", True) \
      .saveAsTable(f"{NS}.silver_{name}")
    print(f"silver_{name:<10} {spark.table(f'{NS}.silver_{name}').count():>7,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: data quality checks
# MAGIC Each check is a SQL query that counts **violating rows**. A passing check returns 0.
# MAGIC The results are saved to `silver_dq_results`, so there is a permanent record of what was checked and when.

# COMMAND ----------

CHECKS = [
    # (check name, category, SQL that counts violations)
    ("events.event_id is unique", "primary key",
     f"SELECT COUNT(*) - COUNT(DISTINCT event_id) FROM {NS}.silver_events"),
    ("customers.customer_id is unique", "primary key",
     f"SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM {NS}.silver_customers"),
    ("no NULL keys or timestamps in events", "completeness",
     f"SELECT COUNT(*) FROM {NS}.silver_events WHERE event_id IS NULL OR customer_id IS NULL "
     f"OR campaign_id IS NULL OR event_ts IS NULL"),
    ("every event has a known customer", "foreign key",
     f"SELECT COUNT(*) FROM {NS}.silver_events e LEFT ANTI JOIN {NS}.silver_customers c USING (customer_id)"),
    ("every event has a known campaign", "foreign key",
     f"SELECT COUNT(*) FROM {NS}.silver_events e LEFT ANTI JOIN {NS}.silver_campaigns c USING (campaign_id)"),
    ("every purchased product exists", "foreign key",
     f"SELECT COUNT(*) FROM {NS}.silver_events e LEFT ANTI JOIN {NS}.silver_products p USING (product_id) "
     f"WHERE e.product_id IS NOT NULL"),
    ("event_type is click / add_to_cart / purchase", "allowed values",
     f"SELECT COUNT(*) FROM {NS}.silver_events WHERE event_type NOT IN ('click','add_to_cart','purchase')"),
    ("purchases have a product and positive revenue", "business rule",
     f"SELECT COUNT(*) FROM {NS}.silver_events WHERE event_type = 'purchase' "
     f"AND (product_id IS NULL OR revenue <= 0)"),
    ("non-purchases carry no product and no revenue", "business rule",
     f"SELECT COUNT(*) FROM {NS}.silver_events WHERE event_type <> 'purchase' "
     f"AND (product_id IS NOT NULL OR revenue <> 0)"),
    ("revenue is a whole multiple of the product price", "business rule",
     f"SELECT COUNT(*) FROM {NS}.silver_events e JOIN {NS}.silver_products p USING (product_id) "
     f"WHERE e.revenue % p.price <> 0"),
    ("events fall inside their campaign's dates", "business rule",
     f"SELECT COUNT(*) FROM {NS}.silver_events e JOIN {NS}.silver_campaigns c USING (campaign_id) "
     f"WHERE CAST(e.event_ts AS DATE) NOT BETWEEN c.start_date AND c.end_date"),
    ("campaign spend and impressions are positive", "business rule",
     f"SELECT COUNT(*) FROM {NS}.silver_campaigns WHERE spend <= 0 OR impressions <= 0"),
]

from datetime import datetime, timezone

run_at = datetime.now(timezone.utc)
results = []
for name, category, sql in CHECKS:
    violations = spark.sql(sql).collect()[0][0]
    results.append((run_at, name, category, int(violations), "PASS" if violations == 0 else "FAIL"))

dq = spark.createDataFrame(
    results, "run_at timestamp, check_name string, category string, violations long, status string")
dq.write.format("delta").mode("append").saveAsTable(f"{NS}.silver_dq_results")
display(dq)

failed = [r for r in results if r[4] == "FAIL"]
assert not failed, f"{len(failed)} data quality check(s) failed: {[r[1] for r in failed]}"
print(f"All {len(results)} data quality checks passed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Delta CHECK constraints
# MAGIC The checks above test today's data. Constraints protect **tomorrow's** data: once added, Delta rejects any
# MAGIC insert or update that violates them. Adding a constraint also re-validates every existing row.

# COMMAND ----------

CONSTRAINTS = {
    "silver_events": {
        "valid_event_type": "event_type IN ('click','add_to_cart','purchase')",
        "non_negative_revenue": "revenue >= 0",
        "purchase_has_product": "event_type <> 'purchase' OR product_id IS NOT NULL",
    },
    "silver_campaigns": {
        "positive_spend": "spend > 0",
        "valid_dates": "end_date >= start_date",
    },
    "silver_products": {
        "positive_price": "price > 0",
    },
}

for table, rules in CONSTRAINTS.items():
    for cname, expr in rules.items():
        spark.sql(f"ALTER TABLE {NS}.{table} DROP CONSTRAINT IF EXISTS {cname}")
        spark.sql(f"ALTER TABLE {NS}.{table} ADD CONSTRAINT {cname} CHECK ({expr})")
        print(f"{table}: {cname}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Prove a constraint works
# MAGIC Try to insert a purchase with negative revenue. Delta should refuse it.

# COMMAND ----------

try:
    spark.sql(f"""INSERT INTO {NS}.silver_events VALUES
                  (999999999, 1, 1, 1, 'purchase', current_timestamp(), -5.00)""")
    raise RuntimeError("Constraint did not fire")
except Exception as e:
    if "Constraint did not fire" in str(e):
        raise
    print("Rejected as expected:", str(e).splitlines()[0][:160])
