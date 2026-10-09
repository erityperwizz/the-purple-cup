# The Purple Cup on Databricks

**Simulated / synthetic data. Portfolio project by Erica Mathias.**

This folder rebuilds The Purple Cup's analysis layer as a **medallion pipeline on Databricks**
(Unity Catalog, Delta Lake, Spark SQL, PySpark), adds a **logistic regression**, and proves the
migration with a **reconciliation** step.

| Notebook | Layer | What it does |
| --- | --- | --- |
| `01_bronze_ingest` | Bronze | Lands the CSV exports in a Unity Catalog volume and loads raw Delta tables (all strings, plus `_source_file` and `_ingested_at`). |
| `02_silver_quality` | Silver | Casts types, de-duplicates on primary keys, runs 12 data quality checks logged to `silver_dq_results`, and adds Delta CHECK constraints. |
| `03_gold_marts` | Gold | Builds a star schema (`gold_fact_events` plus customer, product, campaign and date dimensions) and marts for the funnel, channel ROAS, monthly revenue, and customer features. |
| `04_purchase_regression` | Analysis | Logistic regression `purchased ~ first_channel + n_clicks + region`, reported as odds ratios with 95% CIs and p-values, saved to gold. |
| `05_reconcile` | QA | Confirms no rows were lost and that gold matches the original SQLite/pandas numbers (revenue, spend, ROAS, funnel, buyers). |
| `00_run_all` | | Runs all five in order. |

## Run it (Databricks Free Edition)

1. **Workspace > Create > Git folder**, paste `https://github.com/erityperwizz/the-purple-cup`.
2. Open `databricks/00_run_all` and click **Run all** (serverless compute).
3. Tables land in `workspace.purple_cup`. Browse them in **Catalog**.

To refresh the CSVs after regenerating the synthetic data: `python databricks/export_to_csv.py`.
