"""
Export the four Purple Cup tables from SQLite to CSV so they can be loaded
into Databricks. SIMULATED / SYNTHETIC DATA - PORTFOLIO PROJECT.

Run from the repo root:  python databricks/export_to_csv.py
Author: Erica Mathias
"""
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "brewmetrics.db"
OUT = ROOT / "databricks" / "data"
TABLES = ["products", "customers", "campaigns", "events"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as conn:
        for table in TABLES:
            df = pd.read_sql(f"SELECT * FROM {table}", conn)
            # Integer ID columns with blanks (product_id on clicks and carts) come back from
            # pandas as floats ("2.0"). Write them as whole numbers so strict casts accept them.
            for col in df.columns:
                if col.endswith("_id"):
                    df[col] = df[col].astype("Int64")
            df.to_csv(OUT / f"{table}.csv", index=False)
            print(f"{table:<10} {len(df):>7,} rows -> databricks/data/{table}.csv")


if __name__ == "__main__":
    main()
