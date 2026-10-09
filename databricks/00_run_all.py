# Databricks notebook source
# MAGIC %md
# MAGIC # The Purple Cup on Databricks | Run the whole pipeline
# MAGIC **Simulated / synthetic data. Portfolio project by Erica Mathias.**
# MAGIC
# MAGIC Runs bronze, silver, gold, the regression, and reconciliation in order. Any failed data quality
# MAGIC or reconciliation check stops the run.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "purple_cup")
params = {"catalog": dbutils.widgets.get("catalog"), "schema": dbutils.widgets.get("schema")}

for nb in ["01_bronze_ingest", "02_silver_quality", "03_gold_marts",
           "04_purchase_regression", "05_reconcile"]:
    print(f"Running {nb} ...")
    dbutils.notebook.run(f"./{nb}", 1800, params)
    print(f"  done: {nb}")

print("Pipeline complete.")
