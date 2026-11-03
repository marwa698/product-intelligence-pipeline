from fastapi import FastAPI
import pandas as pd
from sqlalchemy import text
from etl.db import get_engine

app = FastAPI(title="Product Intelligence API")
engine = get_engine()


def query(sql, params=None):
    df = pd.read_sql(text(sql), engine, params=params or {})
    df = df.astype(object).where(df.notnull(), None)  # NaN is not valid JSON
    return df.to_dict(orient="records")


@app.get("/products/latest")
def latest(limit: int = 50):
    return query("""
        SELECT p.product_name, p.category, ph.price, ph.rating, ph.availability
        FROM price_history ph JOIN products p USING (product_id)
        WHERE ph.snapshot_date = (SELECT MAX(snapshot_date) FROM price_history)
        LIMIT :limit
    """, {"limit": limit})


@app.get("/products/price-changes")
def price_changes():
    return query("SELECT * FROM v_price_changes")


@app.get("/products/new")
def new_products():
    return query("SELECT * FROM v_new_products")


@app.get("/products/removed")
def removed_products():
    return query("SELECT * FROM v_removed_products")
