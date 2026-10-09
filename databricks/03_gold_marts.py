# Databricks notebook source
# MAGIC %md
# MAGIC # The Purple Cup on Databricks | 03 Gold: star schema and business marts
# MAGIC **Simulated / synthetic data. Portfolio project by Erica Mathias.**
# MAGIC
# MAGIC Gold is what analysts and dashboards read. It has two parts:
# MAGIC - A **star schema**: one fact table (`gold_fact_events`) surrounded by dimension tables.
# MAGIC - **Marts**: small, pre-aggregated tables that each answer one business question.
# MAGIC
# MAGIC All of it is written in **Spark SQL**, translated from the original SQLite queries in `sql/analysis_queries.sql`.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "purple_cup")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
spark.sql(f"USE {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Star schema
# MAGIC The fact table is one row per event. It carries foreign keys to every dimension plus a `date_key`,
# MAGIC so a BI tool can slice any measure by customer, campaign, channel, product, or date.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE gold_dim_customer AS
# MAGIC SELECT customer_id, signup_date, region FROM silver_customers;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE gold_dim_product AS
# MAGIC SELECT product_id, sku, name AS product_name, category, price FROM silver_products;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE gold_dim_campaign AS
# MAGIC SELECT campaign_id, name AS campaign_name, channel, start_date, end_date, spend, impressions
# MAGIC FROM silver_campaigns;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE gold_dim_date AS
# MAGIC SELECT CAST(date_format(d, 'yyyyMMdd') AS INT) AS date_key,
# MAGIC        d AS calendar_date,
# MAGIC        date_format(d, 'yyyy-MM') AS year_month,
# MAGIC        date_format(d, 'EEEE')    AS day_of_week,
# MAGIC        weekofyear(d)             AS week_of_year
# MAGIC FROM (SELECT explode(sequence(DATE'2025-01-01', DATE'2025-06-30', INTERVAL 1 DAY)) AS d);
# MAGIC
# MAGIC CREATE OR REPLACE TABLE gold_fact_events AS
# MAGIC SELECT e.event_id,
# MAGIC        e.customer_id,
# MAGIC        e.campaign_id,
# MAGIC        e.product_id,
# MAGIC        CAST(date_format(e.event_ts, 'yyyyMMdd') AS INT) AS date_key,
# MAGIC        e.event_ts,
# MAGIC        e.event_type,
# MAGIC        CASE WHEN e.event_type = 'click'       THEN 1 ELSE 0 END AS is_click,
# MAGIC        CASE WHEN e.event_type = 'add_to_cart' THEN 1 ELSE 0 END AS is_cart,
# MAGIC        CASE WHEN e.event_type = 'purchase'    THEN 1 ELSE 0 END AS is_purchase,
# MAGIC        e.revenue
# MAGIC FROM silver_events e;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Mart 1: the funnel
# MAGIC `LAG()` gives step-over-step conversion; `FIRST_VALUE()` compares every stage back to impressions.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE gold_funnel AS
# MAGIC WITH funnel AS (
# MAGIC   SELECT 'Impressions' AS stage, 1 AS stage_order, (SELECT SUM(impressions) FROM gold_dim_campaign) AS cnt
# MAGIC   UNION ALL SELECT 'Clicks',      2, SUM(is_click)    FROM gold_fact_events
# MAGIC   UNION ALL SELECT 'Add to cart', 3, SUM(is_cart)     FROM gold_fact_events
# MAGIC   UNION ALL SELECT 'Purchase',    4, SUM(is_purchase) FROM gold_fact_events
# MAGIC )
# MAGIC SELECT stage, stage_order, cnt AS count,
# MAGIC        ROUND(100.0 * cnt / LAG(cnt) OVER (ORDER BY stage_order), 2)         AS step_conv_pct,
# MAGIC        ROUND(100.0 * cnt / FIRST_VALUE(cnt) OVER (ORDER BY stage_order), 4) AS pct_of_impressions
# MAGIC FROM funnel;
# MAGIC
# MAGIC SELECT * FROM gold_funnel ORDER BY stage_order;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Mart 2: channel ROAS (campaign-level)
# MAGIC Events and budget are aggregated in **separate CTEs** before joining. Joining first would repeat each
# MAGIC campaign's spend once per event row and overcount it (a join fan-out).

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE gold_channel_roas AS
# MAGIC WITH channel_events AS (
# MAGIC   SELECT c.channel,
# MAGIC          SUM(f.is_click)    AS clicks,
# MAGIC          SUM(f.is_purchase) AS purchases,
# MAGIC          SUM(f.revenue)     AS revenue
# MAGIC   FROM gold_fact_events f JOIN gold_dim_campaign c USING (campaign_id)
# MAGIC   GROUP BY c.channel
# MAGIC ),
# MAGIC channel_budget AS (
# MAGIC   SELECT channel, SUM(spend) AS spend, SUM(impressions) AS impressions
# MAGIC   FROM gold_dim_campaign GROUP BY channel
# MAGIC )
# MAGIC SELECT b.channel, b.impressions, ev.clicks, ev.purchases,
# MAGIC        ROUND(ev.revenue, 2)                                   AS revenue,
# MAGIC        b.spend,
# MAGIC        ROUND(ev.revenue / b.spend, 2)                         AS roas,
# MAGIC        ROUND(100.0 * ev.purchases / ev.clicks, 2)             AS click_to_buy_pct,
# MAGIC        ROUND(100.0 * ev.revenue / SUM(ev.revenue) OVER (), 1) AS pct_of_total_revenue
# MAGIC FROM channel_budget b JOIN channel_events ev USING (channel);
# MAGIC
# MAGIC SELECT * FROM gold_channel_roas ORDER BY roas DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Mart 3: monthly revenue with a running total

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE gold_monthly_revenue AS
# MAGIC WITH monthly AS (
# MAGIC   SELECT d.year_month AS month, SUM(f.is_purchase) AS orders, SUM(f.revenue) AS revenue
# MAGIC   FROM gold_fact_events f JOIN gold_dim_date d USING (date_key)
# MAGIC   WHERE f.is_purchase = 1
# MAGIC   GROUP BY d.year_month
# MAGIC )
# MAGIC SELECT month, orders, ROUND(revenue, 2) AS revenue,
# MAGIC        ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS cumulative_revenue
# MAGIC FROM monthly;
# MAGIC
# MAGIC SELECT * FROM gold_monthly_revenue ORDER BY month;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Mart 4: customer features (feeds the regression in notebook 04)
# MAGIC One row per customer. `ROW_NUMBER()` finds each customer's **first clicked channel**, which is the
# MAGIC discovery channel the attribution analysis cares about.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE gold_customer_features AS
# MAGIC WITH ev AS (
# MAGIC   SELECT f.*, c.channel FROM gold_fact_events f JOIN gold_dim_campaign c USING (campaign_id)
# MAGIC ),
# MAGIC first_touch AS (
# MAGIC   SELECT customer_id, channel AS first_channel
# MAGIC   FROM (SELECT customer_id, channel,
# MAGIC                ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY event_ts, event_id) AS rn
# MAGIC         FROM ev WHERE is_click = 1)
# MAGIC   WHERE rn = 1
# MAGIC ),
# MAGIC activity AS (
# MAGIC   SELECT customer_id,
# MAGIC          SUM(is_click)                                        AS n_clicks,
# MAGIC          COUNT(DISTINCT CASE WHEN is_click = 1 THEN channel END) AS n_channels,
# MAGIC          SUM(is_purchase)                                     AS n_purchases,
# MAGIC          SUM(revenue)                                         AS total_revenue
# MAGIC   FROM ev GROUP BY customer_id
# MAGIC )
# MAGIC SELECT c.customer_id, c.region, c.signup_date, ft.first_channel,
# MAGIC        COALESCE(a.n_clicks, 0)      AS n_clicks,
# MAGIC        COALESCE(a.n_channels, 0)    AS n_channels,
# MAGIC        COALESCE(a.n_purchases, 0)   AS n_purchases,
# MAGIC        COALESCE(a.total_revenue, 0) AS total_revenue,
# MAGIC        CASE WHEN COALESCE(a.n_purchases, 0) > 0 THEN 1 ELSE 0 END AS purchased
# MAGIC FROM gold_dim_customer c
# MAGIC LEFT JOIN activity a    USING (customer_id)
# MAGIC LEFT JOIN first_touch ft USING (customer_id);
# MAGIC
# MAGIC SELECT first_channel, COUNT(*) AS customers, ROUND(AVG(purchased) * 100, 1) AS purchase_rate_pct
# MAGIC FROM gold_customer_features GROUP BY first_channel ORDER BY purchase_rate_pct DESC;
