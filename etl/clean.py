"""
etl/clean.py  -  Member 3: Cleaning + Validation
================================================
Input : data/raw/products_YYYY-MM-DD.json      (written by Member 1, values exactly as on the site)
Output: data/processed/clean_YYYY-MM-DD.csv    (the 8 Data-Contract columns, in this exact order)
        data/rejected/rejected_YYYY-MM-DD.csv  (raw rows that cannot be used + a reject_reason column)

DECISIONS ON MISSING / BAD VALUES  (copy this block to the README)
------------------------------------------------------------------
* product_url missing            -> REJECTED  (it is the unique key of a product)
* product_name missing           -> REJECTED
* price missing / not a number   -> REJECTED
* price <= 0                     -> REJECTED
* currency cannot be detected    -> REJECTED  (a price without a currency is ambiguous; we do not guess)
* scraped_at missing / invalid   -> REJECTED  (the history table needs the snapshot date)
* rating missing / unknown word  -> kept as NULL (not critical)
* rating a number outside 1..5   -> REJECTED
* category missing               -> "Unknown"
* availability                   -> "In stock" if the text contains "in stock", otherwise "Out of stock"

Handoff functions (names are fixed by the Data Contract - do not rename):
    validate_raw(raw_path)   -> raises an Exception if the raw file has a problem
    run_cleaning(raw_path)   -> (clean_path, rejected_path)
"""
from datetime import date
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["product_name", "category", "price", "rating",
                    "availability", "product_url", "scraped_at"]

# Data Contract 7.2: the clean CSV must have exactly these columns, in this order.
OUTPUT_COLUMNS = ["product_name", "category", "price", "currency", "rating",
                  "availability", "product_url", "scraped_at"]

RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
# "Â£" is what "£" looks like when the scraper forgot response.encoding = "utf-8".
CURRENCY_MAP = {"£": "GBP", "Â£": "GBP", "$": "USD", "€": "EUR"}


# --------------------------------------------------------------------------- #
# Step 1: read + validate (Extract)
# --------------------------------------------------------------------------- #
def load_raw(path, verbose=False):
    # dtype=False / convert_dates=False -> keep every value exactly as scraped (strings);
    # we do the conversions ourselves, in clean().
    df = pd.read_json(path, dtype=False, convert_dates=False)
    if verbose:
        print(df.head())
        df.info()
    return df


def validate_columns(df):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")


# --------------------------------------------------------------------------- #
# Step 2: cleaning (Transform)
# --------------------------------------------------------------------------- #
def _clean_text(s):
    """strip + collapse repeated spaces; empty text becomes missing (NA)."""
    s = s.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    return s.mask(s == "", pd.NA)


def _title_case(text):
    # str.title() turns "Women's Fiction" into "Women'S Fiction", so capitalise word by word.
    if pd.isna(text):
        return text
    return " ".join(w.capitalize() for w in str(text).split(" "))


def _clean_rating(s):
    """'Three' -> 3, '4' -> 4, unknown word ('Seven') -> NULL, number outside 1-5 is kept (rejected later)."""
    words = s.astype("string").str.strip().str.title().map(RATING_MAP)
    nums = pd.to_numeric(s, errors="coerce")
    nums = nums.where(nums % 1 == 0)                  # 3.5 is not a valid rating
    out = pd.to_numeric(words, errors="coerce").fillna(nums)
    return out.astype("Int64")


def clean(df):
    """Returns ONLY the 8 contract columns, in contract order. The index is preserved."""
    df = df.copy()

    # 2.1 spaces and letter case
    df["product_name"] = _clean_text(df["product_name"])
    df["category"] = _clean_text(df["category"]).map(_title_case)
    df["product_url"] = _clean_text(df["product_url"])

    # 2.2 price "£51.77" -> 51.77 + currency "GBP"
    price_txt = df["price"].astype("string")
    df["currency"] = price_txt.str.extract(r"(Â£|£|\$|€)")[0].map(CURRENCY_MAP)
    # keep the minus sign so a negative price is caught instead of silently becoming positive
    df["price"] = pd.to_numeric(price_txt.str.replace(r"[^\d.\-]", "", regex=True),
                                errors="coerce").round(2)

    # 2.3 rating
    df["rating"] = _clean_rating(df["rating"])

    # 2.4 availability: "In stock (22 available)" -> "In stock"
    in_stock = df["availability"].astype("string").str.contains("in stock", case=False, na=False)
    df["availability"] = in_stock.map({True: "In stock", False: "Out of stock"})

    # 2.5 date
    try:
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce", format="ISO8601")
    except (TypeError, ValueError):                   # very old pandas without ISO8601
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")

    # 2.6 missing category -> "Unknown"
    df["category"] = df["category"].fillna("Unknown")

    return df[OUTPUT_COLUMNS]


# --------------------------------------------------------------------------- #
# Step 2.7: valid vs rejected
# --------------------------------------------------------------------------- #
def reject_reasons(df):
    """Text explaining why each row is rejected ('' = row is fine). Works on the output of clean()."""
    checks = {
        "missing product_url": df["product_url"].isna(),
        "missing product_name": df["product_name"].isna(),
        "missing or invalid price": df["price"].isna(),
        "price <= 0": df["price"].notna() & (df["price"] <= 0),
        "missing currency": df["currency"].isna(),
        "rating out of range": df["rating"].notna() & ~df["rating"].between(1, 5),
        "invalid scraped_at": df["scraped_at"].isna(),
    }
    reasons = pd.Series([""] * len(df), index=df.index, dtype="object")
    for name, mask in checks.items():
        mask = mask.fillna(False).astype(bool)
        reasons[mask] = reasons[mask] + name + "; "
    return reasons.str.rstrip("; ")


def split_valid_rejected(df):
    bad = reject_reasons(df) != ""
    return df[~bad].copy(), df[bad].copy()


# --------------------------------------------------------------------------- #
# Handoff functions (used by Member 4 and Member 5 / Airflow)
# --------------------------------------------------------------------------- #
def validate_raw(raw_path):
    """Checks the raw file. Raises an Exception if there is a problem."""
    df = load_raw(raw_path, verbose=True)
    if len(df) == 0:
        raise ValueError("Raw file is empty")
    validate_columns(df)


def run_cleaning(raw_path):
    """Cleans the raw file and returns (clean_path, rejected_path)."""
    raw = load_raw(raw_path)
    if len(raw) == 0:
        raise ValueError("Raw file is empty")
    validate_columns(raw)

    cleaned = clean(raw)
    valid, rejected_clean = split_valid_rejected(cleaned)

    # The rejected file keeps the ORIGINAL scraped values (easier to investigate) + the reason.
    rejected = raw.loc[rejected_clean.index].copy()
    rejected["reject_reason"] = reject_reasons(cleaned).loc[rejected.index]

    today = date.today().isoformat()
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    Path("data/rejected").mkdir(parents=True, exist_ok=True)
    clean_path = f"data/processed/clean_{today}.csv"
    rejected_path = f"data/rejected/rejected_{today}.csv"
    valid[OUTPUT_COLUMNS].to_csv(clean_path, index=False)
    rejected.to_csv(rejected_path, index=False)

    print(f"clean={len(valid)}, rejected={len(rejected)}")
    return clean_path, rejected_path
