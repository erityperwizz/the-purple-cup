# Databricks notebook source
# MAGIC %md
# MAGIC # The Purple Cup on Databricks | 01 Bronze: raw ingest
# MAGIC **Simulated / synthetic data. Portfolio project by Erica Mathias.**
# MAGIC
# MAGIC This pipeline follows the **medallion architecture**:
# MAGIC
# MAGIC | Layer | What it holds | Notebook |
# MAGIC | --- | --- | --- |
# MAGIC | Bronze | Raw data exactly as it arrived, every column a string, plus ingest metadata | 01 |
# MAGIC | Silver | Typed, validated, de-duplicated tables with data quality checks and Delta constraints | 02 |
# MAGIC | Gold | Star schema and business-ready marts (funnel, ROAS, monthly revenue, customer features) | 03 |
# MAGIC | Analysis | Logistic regression on purchase likelihood | 04 |
# MAGIC | Reconciliation | Gold numbers must match the original SQLite/pandas analysis | 05 |
# MAGIC
# MAGIC This notebook copies the four CSV exports from the repo into a **Unity Catalog volume** (the landing zone),
# MAGIC then loads each one into a bronze **Delta table** without changing any values.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "purple_cup")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.landing")
LANDING = f"/Volumes/{CATALOG}/{SCHEMA}/landing"
print("Landing zone:", LANDING)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: land the raw files
# MAGIC The CSVs live in the repo's `databricks/data/` folder (this notebook runs from a Git folder).
# MAGIC Copying them into a volume mirrors how a real pipeline receives files from an upstream system.

# COMMAND ----------

import os
import shutil

TABLES = ["products", "customers", "campaigns", "events"]
repo_data_dir = os.path.join(os.getcwd(), "data")

for t in TABLES:
    src = os.path.join(repo_data_dir, f"{t}.csv")
    dst = f"{LANDING}/{t}.csv"
    shutil.copyfile(src, dst)
    print(f"landed {t}.csv  ({os.path.getsize(dst):,} bytes)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: load bronze Delta tables
# MAGIC Bronze keeps everything as **strings** on purpose. If an upstream system sends a bad value, bronze still
# MAGIC captures it, and the problem gets caught (and explained) in silver instead of crashing the load.
# MAGIC Two metadata columns record where and when each row came from, which is what makes a pipeline auditable.

# COMMAND ----------

from pyspark.sql import functions as F

for t in TABLES:
    df = (
        spark.read.option("header", True)
        .option("inferSchema", False)
        .csv(f"{LANDING}/{t}.csv")
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_ingested_at", F.current_timestamp())
    )
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", True)
       .saveAsTable(f"{CATALOG}.{SCHEMA}.bronze_{t}"))
    print(f"bronze_{t:<10} {df.count():>7,} rows")

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}"))
