import sys
from etl.clean import validate_raw, run_cleaning
from etl.dedup import run_dedup
from etl.load import run_load

if __name__ == "__main__":
    raw_path = sys.argv[1]
    validate_raw(raw_path)
    clean_path, rejected_path = run_cleaning(raw_path)
    dedup_path = run_dedup(clean_path)
    print(f"Loaded {run_load(dedup_path)} rows")
