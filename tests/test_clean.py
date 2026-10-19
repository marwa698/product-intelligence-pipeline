"""Unit tests for Member 3's work.   Run from the repo root:   python -m pytest tests -v"""
import json
from pathlib import Path

import pandas as pd
import pytest

from etl import clean as C
from etl import quality_checks as Q

BASE = "https://books.toscrape.com/catalogue/"


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    """The tests (and the CI) must run WITHOUT a database: never write to etl_quality_log here."""
    monkeypatch.setattr(Q, "_write_log_table", lambda results: None)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)               # run_cleaning writes relative paths (data/..., logs/...)
    return tmp_path


def raw(**over):
    """One valid raw row (Data Contract 7.1); override any field to create a problem."""
    row = {"product_name": "A Light in the Attic", "category": "Poetry", "price": "£51.77",
           "rating": "Three", "availability": "In stock (22 available)",
           "product_url": BASE + "a-light-in-the-attic_1000/index.html",
           "scraped_at": "2026-10-14T10:00:00"}
    row.update(over)
    return row


def cleaned(*rows):
    return C.clean(pd.DataFrame(rows))


def sample_rows(with_bad_rows=False):
    """10 messy-but-valid rows; with_bad_rows adds 4 more (negative price, no url, 'Seven', duplicate url)."""
    def row(name, cat, price, rating, avail, slug, ts="2026-10-14T10:00:00"):
        return {"product_name": name, "category": cat, "price": price, "rating": rating,
                "availability": avail, "product_url": f"{BASE}{slug}/index.html", "scraped_at": ts}

    rows = [
        row("A Light in the Attic", "Poetry", "£51.77", "Three", "In stock (22 available)", "a-light-in-the-attic_1000"),
        row("  Tipping   the Velvet ", "historical fiction", "£53.74", "One", "In stock (20 available)", "tipping-the-velvet_999"),
        row("Soumission", "Fiction", "Â£50.10", "One", "In stock (20 available)", "soumission_998"),
        row("Sharp Objects", "MYSTERY", "£47.82", "Four", "In stock (20 available)", "sharp-objects_997"),
        row("Sapiens: A Brief History of Humankind", "History", "£54.23", "Five", "In stock (20 available)", "sapiens_996"),
        row("The Requiem Red", "Young Adult", "£22.65", "One", "In stock (19 available)", "the-requiem-red_995"),
        row("The Boys in the Boat", "Nonfiction", "£22.60", "Four", "In stock (19 available)", "the-boys-in-the-boat_992"),
        row("The Black Maria", "Poetry", "£52.15", "One", "Out of stock", "the-black-maria_991"),
        row("Starving Hearts", "Women's fiction", "£13.99", "Two", "In stock (19 available)", "starving-hearts_990"),
        row("Libertarianism for Beginners", "Politics", "£51.33", "Two", "In stock (19 available)", "libertarianism_982"),
    ]
    if with_bad_rows:
        rows += [
            row("Negative Price Book", "Poetry", "£-5.00", "Two", "In stock (3 available)", "negative-price_1"),
            row("No Link Book", "Fiction", "£12.00", "Three", "In stock (3 available)", "x"),
            row("Seven Stars Book", "Fiction", "£18.50", "Seven", "In stock (3 available)", "seven-stars_3"),
            row("A Light in the Attic", "Poetry", "£51.77", "Three", "In stock (22 available)",
                "a-light-in-the-attic_1000", "2026-10-14T10:05:00"),
        ]
        rows[11]["product_url"] = None          # the "No Link Book" row has no link
    return rows


def write_sample(path, with_bad_rows=False):
    Path(path).write_text(json.dumps(sample_rows(with_bad_rows), ensure_ascii=False), encoding="utf-8")


# ---------------------------- cleaning rules ---------------------------- #
def test_price_and_currency():
    df = cleaned(raw(), raw(price="Â£50.10"), raw(price="$9.99"), raw(price="€7.50"))
    assert list(df["price"]) == [51.77, 50.10, 9.99, 7.50]
    assert list(df["currency"]) == ["GBP", "GBP", "USD", "EUR"]


def test_negative_price_is_not_turned_into_positive():
    df = cleaned(raw(price="£-5.00"))
    assert df["price"].iloc[0] == -5.0


def test_rating_words_numbers_and_unknown():
    df = cleaned(raw(rating="Three"), raw(rating="Five"), raw(rating="Seven"), raw(rating=4), raw(rating=None))
    assert df["rating"].iloc[0] == 3 and df["rating"].iloc[1] == 5
    assert pd.isna(df["rating"].iloc[2])          # unknown word -> NULL, code does not crash
    assert df["rating"].iloc[3] == 4
    assert pd.isna(df["rating"].iloc[4])


def test_availability_is_normalised():
    df = cleaned(raw(availability="In stock (22 available)"), raw(availability="Out of stock"), raw(availability=None))
    assert list(df["availability"]) == ["In stock", "Out of stock", "Out of stock"]


def test_text_cleaning_and_category_case():
    df = cleaned(raw(product_name="  Tipping   the Velvet "), raw(category="  historical   fiction "),
                 raw(category="Women's fiction"), raw(category=None))
    assert df["product_name"].iloc[0] == "Tipping the Velvet"
    assert df["category"].iloc[1] == "Historical Fiction"
    assert df["category"].iloc[2] == "Women's Fiction"     # not "Women'S Fiction"
    assert df["category"].iloc[3] == "Unknown"


def test_output_has_exactly_the_8_contract_columns_in_order():
    assert list(cleaned(raw()).columns) == ["product_name", "category", "price", "currency", "rating",
                                            "availability", "product_url", "scraped_at"]


# ---------------------------- rejected rows ---------------------------- #
def test_bad_rows_are_rejected_with_a_reason():
    df = cleaned(raw(), raw(price="£-5.00"), raw(product_url=None), raw(price="abc"),
                 raw(rating=9), raw(price="51.77"), raw(scraped_at="not a date"))
    valid, rejected = C.split_valid_rejected(df)
    assert len(valid) == 1 and len(rejected) == 6
    reasons = C.reject_reasons(df)
    assert "price <= 0" in reasons.iloc[1]
    assert "missing product_url" in reasons.iloc[2]
    assert "missing or invalid price" in reasons.iloc[3]
    assert "rating out of range" in reasons.iloc[4]
    assert "missing currency" in reasons.iloc[5]
    assert "invalid scraped_at" in reasons.iloc[6]


# ---------------------------- end to end ---------------------------- #
def test_run_cleaning_on_ok_sample(workdir):
    write_sample("raw.json")
    C.validate_raw("raw.json")
    clean_path, rejected_path = C.run_cleaning("raw.json")
    out = pd.read_csv(clean_path)
    assert len(out) == 10 and len(pd.read_csv(rejected_path)) == 0
    assert list(out.columns) == C.OUTPUT_COLUMNS


def test_run_cleaning_on_bad_sample(workdir):
    write_sample("raw.json", with_bad_rows=True)
    clean_path, rejected_path = C.run_cleaning("raw.json")
    assert len(pd.read_csv(clean_path)) == 12          # 10 good + duplicate url + "Seven" (rating NULL is allowed)
    rej = pd.read_csv(rejected_path)
    assert len(rej) == 2 and "reject_reason" in rej.columns


def test_validate_raw_errors(workdir):
    Path("empty.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        C.validate_raw("empty.json")
    Path("nocol.json").write_text(json.dumps([{"product_name": "x"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        C.validate_raw("nocol.json")


# ---------------------------- quality checks ---------------------------- #
def test_quality_all_pass_on_ok_sample(workdir):
    write_sample("raw.json")
    paths = C.run_cleaning("raw.json")
    results = Q.run_quality_checks("raw.json", *paths)
    assert all(status == "PASS" for _, status, _ in results)
    assert Path(f"logs/quality_{pd.Timestamp.today().date()}.log").exists()


def test_quality_fails_on_negative_price_and_raises(workdir):
    write_sample("raw.json")
    clean_path, rejected_path = C.run_cleaning("raw.json")
    df = pd.read_csv(clean_path)
    df.loc[0, "price"] = -1
    df.to_csv(clean_path, index=False)
    with pytest.raises(Exception, match="Data quality failed"):
        Q.run_quality_checks("raw.json", clean_path, rejected_path)


def test_quality_fails_on_bad_sample(workdir):
    write_sample("raw.json", with_bad_rows=True)
    paths = C.run_cleaning("raw.json")
    with pytest.raises(Exception, match="Data quality failed"):
        Q.run_quality_checks("raw.json", *paths)         # duplicate url in the clean file


def test_rejected_ratio_levels():
    assert Q.check_rejected_ratio(98, 2)[1] == "PASS"
    assert Q.check_rejected_ratio(93, 7)[1] == "WARN"
    assert Q.check_rejected_ratio(80, 20)[1] == "FAIL"
    assert Q.check_rejected_ratio(90, 10)[1] == "FAIL"      # exactly 10% -> FAIL (guide: 10% or more)
