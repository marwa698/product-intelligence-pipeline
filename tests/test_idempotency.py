import pandas as pd
from sqlalchemy import text
from etl.db import get_engine
from etl.load import load_all


def _count(conn, table):
    return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def _sample():
    ts = pd.Timestamp("2026-10-14 10:00:00")
    rows = [
        ("Book A", "Poetry", 50.00, "GBP", 3, "In stock", "http://t/1", ts),
        ("Book B", "Travel", 20.00, "GBP", 4, "In stock", "http://t/2", ts),
    ]
    cols = ["product_name", "category", "price", "currency", "rating",
            "availability", "product_url", "scraped_at"]
    return pd.DataFrame(rows, columns=cols)


def test_load_is_idempotent():
    engine = get_engine()
    with engine.begin() as c:
        c.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        c.execute(text("TRUNCATE TABLE price_history"))
        c.execute(text("TRUNCATE TABLE products"))
        c.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    df = _sample()
    load_all(df, engine)
    with engine.connect() as c:
        first = (_count(c, "products"), _count(c, "price_history"))
    load_all(df, engine)
    with engine.connect() as c:
        second = (_count(c, "products"), _count(c, "price_history"))
    assert first == second == (2, 2)
