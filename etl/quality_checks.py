"""
etl/quality_checks.py  -  Member 3: Data Quality Checks
=======================================================
Every check returns a tuple:  (check_name, status, details)   with status in PASS / WARN / FAIL.

    1. row_count        clean rows >= 90% of raw rows
    2. null_pct         0% NULL in price and product_url
    3. negative_prices  no price <= 0
    4. rating_range     rating between 1 and 5 (NULL is allowed)
    5. duplicates       no repeated product_url
    6. rejected_ratio   rejected rows: < 5% PASS, 5% to < 10% WARN, 10% or more FAIL

Handoff function (name fixed by the Data Contract - do not rename):
    run_quality_checks(raw_path, clean_path, rejected_path) -> list of results
    -> writes logs/quality_YYYY-MM-DD.log
    -> tries to write the etl_quality_log table (MySQL); never crashes if the DB is not ready
    -> raises an Exception if ANY check is FAIL (so Airflow marks the task as failed)
"""
from datetime import date
from pathlib import Path

import pandas as pd


# --------------------------------------------------------------------------- #
# The checks
# --------------------------------------------------------------------------- #
def check_row_count(raw_count, clean_count, min_ratio=0.9):
    ratio = clean_count / raw_count if raw_count else 0
    status = "PASS" if ratio >= min_ratio else "FAIL"
    return ("row_count", status,
            f"raw={raw_count}, clean={clean_count}, ratio={ratio:.2%}")


def check_null_pct(df):
    n = len(df)
    price_pct = df["price"].isna().sum() / n if n else 0.0
    url_pct = df["product_url"].isna().sum() / n if n else 0.0
    ok = (price_pct == 0 and url_pct == 0)
    return ("null_pct", "PASS" if ok else "FAIL",
            f"price_null={price_pct:.2%}, url_null={url_pct:.2%}")


def check_no_negative_prices(df):
    prices = pd.to_numeric(df["price"], errors="coerce")
    bad = int((prices <= 0).sum())
    return ("negative_prices", "PASS" if bad == 0 else "FAIL", f"{bad} bad rows")


def check_rating_range(df):
    ratings = pd.to_numeric(df["rating"], errors="coerce").dropna()
    bad = int((~ratings.between(1, 5)).sum())
    return ("rating_range", "PASS" if bad == 0 else "FAIL",
            f"{bad} ratings outside 1-5")


def check_no_duplicates(df):
    dup = int(df["product_url"].duplicated().sum())
    return ("duplicates", "PASS" if dup == 0 else "FAIL",
            f"{dup} duplicated product_url")


def check_rejected_ratio(clean_count, rejected_count):
    total = clean_count + rejected_count
    ratio = rejected_count / total if total else 0
    if ratio < 0.05:
        status = "PASS"
    elif ratio < 0.10:
        status = "WARN"
    else:
        status = "FAIL"
    return ("rejected_ratio", status,
            f"rejected={rejected_count}, total={total}, ratio={ratio:.2%}")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _read_csv_safe(path):
    """A rejected file with no rows still has a header, but a totally empty file would crash read_csv."""
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_log_file(results):
    Path("logs").mkdir(parents=True, exist_ok=True)
    log_path = f"logs/quality_{date.today().isoformat()}.log"
    with open(log_path, "w", encoding="utf-8") as f:
        for name, status, details in results:
            f.write(f"{status}\t{name}\t{details}\n")
    return log_path


def _write_log_table(results):
    """Writes to etl_quality_log (MySQL). If db.py / the table is not ready yet, only prints a message."""
    try:
        from sqlalchemy import text
        from etl.db import get_engine

        with get_engine().begin() as conn:
            for name, status, details in results:
                conn.execute(
                    text("INSERT INTO etl_quality_log (run_date, check_name, status, details) "
                         "VALUES (:d, :n, :s, :t)"),
                    {"d": date.today(), "n": name, "s": status, "t": details},
                )
    except Exception as e:
        print(f"Could not write quality results to DB: {e}")


# --------------------------------------------------------------------------- #
# Handoff function (used by Member 5 / Airflow)
# --------------------------------------------------------------------------- #
def run_quality_checks(raw_path, clean_path, rejected_path):
    raw = pd.read_json(raw_path, dtype=False, convert_dates=False)
    clean_df = _read_csv_safe(clean_path)
    rejected = _read_csv_safe(rejected_path)

    results = [
        check_row_count(len(raw), len(clean_df)),
        check_null_pct(clean_df),
        check_no_negative_prices(clean_df),
        check_rating_range(clean_df),
        check_no_duplicates(clean_df),
        check_rejected_ratio(len(clean_df), len(rejected)),
    ]

    # 1) log file   2) MySQL table   3) fail the pipeline if any FAIL
    _write_log_file(results)
    _write_log_table(results)

    failed = [r for r in results if r[1] == "FAIL"]
    if failed:
        raise Exception(f"Data quality failed: {failed}")

    return results