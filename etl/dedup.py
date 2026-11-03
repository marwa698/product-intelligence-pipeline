import pandas as pd
from datetime import date
from rapidfuzz import fuzz, process
from etl.db import get_engine

STG_COLUMNS = ["product_name", "category", "price", "currency",
               "rating", "availability", "product_url", "scraped_at"]


def remove_exact_duplicates(df):
    """Same product_url twice: keep the last one."""
    before = len(df)
    df = df.drop_duplicates(subset="product_url", keep="last")
    print(f"Removed {before - len(df)} exact duplicates")
    return df


def find_fuzzy_duplicates(df, threshold=90):
    """Find similar names with different URLs. Flag them, never delete."""
    df = df.reset_index(drop=True)
    names = df["product_name"].str.lower().str.strip().tolist()
    pairs = []
    for i, name in enumerate(names):
        matches = process.extract(name, names, scorer=fuzz.ratio,
                                  score_cutoff=threshold, limit=5)
        for _, score, j in matches:
            if i > j:  # skip self-match and mirrored pairs
                pairs.append({
                    "name_1": df.iloc[i]["product_name"],
                    "name_2": df.iloc[j]["product_name"],
                    "similarity": score,
                })
    return pd.DataFrame(pairs, columns=["name_1", "name_2", "similarity"])


def save_possible_duplicates(df):
    pairs = find_fuzzy_duplicates(df)
    pairs.to_csv(f"data/processed/possible_duplicates_{date.today()}.csv", index=False)


def compare_with_catalog(df, engine):
    """Add in_internal_catalog and internal_price. These go to the report only, not to the DB."""
    catalog = pd.read_sql("SELECT product_name, internal_price FROM internal_catalog", engine)
    df = df.copy()
    df["_key"] = df["product_name"].str.lower().str.strip()
    catalog["_key"] = catalog["product_name"].str.lower().str.strip()
    catalog = catalog.drop_duplicates(subset="_key")
    merged = df.merge(catalog[["_key", "internal_price"]], on="_key",
                      how="left", indicator=True)
    merged["in_internal_catalog"] = merged["_merge"] == "both"
    return merged.drop(columns=["_key", "_merge"])


def run_dedup(clean_path):
    """Handoff function for Airflow. Returns the path of dedup_DATE.csv."""
    df = pd.read_csv(clean_path, parse_dates=["scraped_at"])
    df = remove_exact_duplicates(df)
    save_possible_duplicates(df)
    matched = compare_with_catalog(df, get_engine())
    matched.to_csv(f"data/processed/catalog_match_{date.today()}.csv", index=False)
    out = f"data/processed/dedup_{date.today()}.csv"
    df[STG_COLUMNS].to_csv(out, index=False)
    return out