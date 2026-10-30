import pandas as pd
from sqlalchemy import text
from etl.db import get_engine

STG_COLUMNS = ["product_name", "category", "price", "currency",
               "rating", "availability", "product_url", "scraped_at"]

# New product -> inserted. Existing product -> updated (first_seen never changes).
UPSERT_PRODUCTS = """
INSERT INTO products (product_url, product_name, category, first_seen, last_seen, is_active)
SELECT s.product_url, s.product_name, s.category,
       DATE(s.scraped_at), DATE(s.scraped_at), TRUE
FROM stg_products s
ON DUPLICATE KEY UPDATE
    product_name = VALUES(product_name),
    category     = VALUES(category),
    last_seen    = GREATEST(last_seen, VALUES(last_seen)),
    is_active    = TRUE
"""

# One snapshot per product per day. The UNIQUE key makes a re-run do nothing.
INSERT_HISTORY = """
INSERT INTO price_history
    (product_id, price, currency, rating, availability, category, scraped_at, snapshot_date)
SELECT p.product_id, s.price, s.currency, s.rating, s.availability, s.category,
       s.scraped_at, DATE(s.scraped_at)
FROM stg_products s
JOIN products p ON p.product_url = s.product_url
ON DUPLICATE KEY UPDATE history_id = history_id
"""

# Products missing from today's scrape are marked inactive.
MARK_INACTIVE = """
UPDATE products SET is_active = FALSE
WHERE product_url NOT IN (SELECT product_url FROM stg_products)
"""


def load_to_staging(df, engine):
    """Empty the staging table, then fill it with today's file."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE stg_products"))
    # Never use if_exists="replace": it would destroy Jenny's table design.
    df[STG_COLUMNS].to_sql("stg_products", engine, if_exists="append",
                           index=False, method="multi", chunksize=500)


def load_all(df, engine):
    """Staging, then upsert + history + inactive in ONE transaction."""
    load_to_staging(df, engine)
    with engine.begin() as conn:
        conn.execute(text(UPSERT_PRODUCTS))
        conn.execute(text(INSERT_HISTORY))
        conn.execute(text(MARK_INACTIVE))


def run_load(dedup_path):
    """Handoff function for Airflow. Returns the number of rows loaded."""
    df = pd.read_csv(dedup_path, parse_dates=["scraped_at"])
    if len(df) == 0:
        raise ValueError("Dedup file is empty: refusing to load "
                         "(it would mark ALL products inactive)")
    load_all(df, get_engine())
    return len(df)