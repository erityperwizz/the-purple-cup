# Databricks notebook source
# MAGIC %md
# MAGIC # The Purple Cup on Databricks | 04 Logistic regression: what predicts a purchase?
# MAGIC **Simulated / synthetic data. Portfolio project by Erica Mathias.**
# MAGIC
# MAGIC **Business question:** controlling for everything else, does the channel that *first* brought a customer in
# MAGIC change how likely they are to ever buy? And does region matter?
# MAGIC
# MAGIC **Model:** logistic regression, because the outcome is yes/no (purchased or not).
# MAGIC
# MAGIC `purchased ~ first_channel + n_clicks + region`
# MAGIC
# MAGIC - Reference levels: **Instagram** for channel (the biggest budget line) and **West** for region (the largest region).
# MAGIC - Each coefficient is reported as an **odds ratio** with a 95% confidence interval and a p-value.
# MAGIC
# MAGIC **Hypotheses tested for each term**
# MAGIC - H0: the term has no effect on the odds of purchasing (odds ratio = 1).
# MAGIC - H1: it does (odds ratio differs from 1). Significance level: 0.05.

# COMMAND ----------

# MAGIC %pip install statsmodels --quiet

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "purple_cup")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
NS = f"{CATALOG}.{SCHEMA}"

# COMMAND ----------

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# Spark does the heavy lifting upstream; the modeling table is one row per customer.
df = spark.table(f"{NS}.gold_customer_features").toPandas()

# Two customers never clicked, so they have no first channel. They cannot enter this model.
model_df = df.dropna(subset=["first_channel"]).copy()
model_df["n_clicks"] = model_df["n_clicks"].astype(float)
print(f"Customers: {len(df):,} | in model: {len(model_df):,} | base purchase rate: {model_df.purchased.mean():.1%}")

# COMMAND ----------

formula = ("purchased ~ C(first_channel, Treatment(reference='Instagram'))"
           " + n_clicks"
           " + C(region, Treatment(reference='West'))")
fit = smf.logit(formula, data=model_df).fit(disp=False)
print(fit.summary())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Odds ratios, plain-English version

# COMMAND ----------

def clean(term: str) -> str:
    return (term.replace("C(first_channel, Treatment(reference='Instagram'))[T.", "first channel: ")
                .replace("C(region, Treatment(reference='West'))[T.", "region: ")
                .replace("]", ""))

ci = fit.conf_int()
res = pd.DataFrame({
    "term": [clean(t) for t in fit.params.index],
    "coef_log_odds": fit.params.values,
    "odds_ratio": np.exp(fit.params.values),
    "or_ci_low": np.exp(ci[0].values),
    "or_ci_high": np.exp(ci[1].values),
    "p_value": fit.pvalues.values,
})
res["significant_at_05"] = res["p_value"] < 0.05
res = res[res["term"] != "Intercept"].reset_index(drop=True)

stats = pd.DataFrame([{
    "n_obs": int(fit.nobs),
    "pseudo_r2_mcfadden": fit.prsquared,
    "llr_p_value": fit.llr_pvalue,
    "aic": fit.aic,
}])

display(res.round(4))
display(stats.round(4))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save results to gold
# MAGIC Saving the coefficients as a table means a dashboard (or a reviewer) can read the model output with SQL.

# COMMAND ----------

spark.createDataFrame(res).write.format("delta").mode("overwrite").option("overwriteSchema", True) \
     .saveAsTable(f"{NS}.gold_regression_odds_ratios")
spark.createDataFrame(stats).write.format("delta").mode("overwrite").option("overwriteSchema", True) \
     .saveAsTable(f"{NS}.gold_regression_fit")

for _, r in res.iterrows():
    direction = "higher" if r.odds_ratio > 1 else "lower"
    sig = "significant" if r.significant_at_05 else "NOT significant"
    print(f"{r.term:<28} OR={r.odds_ratio:.2f} [{r.or_ci_low:.2f}, {r.or_ci_high:.2f}]  "
          f"p={r.p_value:.4f}  ({sig}; {direction} odds)")
