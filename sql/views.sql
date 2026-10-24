-- =====================================================
-- views.sql : analysis views (Owner: Member 2) - MySQL 8.0+
-- Each view compares the LATEST snapshot with the PREVIOUS one.
-- =====================================================

USE products_db;

-- 1) Price changes: LAG() gets the previous day's price of the same product
CREATE OR REPLACE VIEW v_price_changes AS
WITH ordered AS (
    SELECT p.product_id,
           p.product_name,
           ph.snapshot_date,
           ph.price,
           LAG(ph.price) OVER (PARTITION BY ph.product_id ORDER BY ph.snapshot_date) AS old_price
    FROM price_history ph
    JOIN products p ON p.product_id = ph.product_id
)
SELECT product_id,
       product_name,
       snapshot_date,
       old_price,
       price AS new_price,
       ROUND(price - old_price, 2) AS diff,
       ROUND((price - old_price) / NULLIF(old_price, 0) * 100, 1) AS pct_change
FROM ordered
WHERE old_price IS NOT NULL
  AND price <> old_price;

-- 2) New products: first ever snapshot is the latest date (and an earlier snapshot exists)
CREATE OR REPLACE VIEW v_new_products AS
WITH latest AS (
    SELECT MAX(snapshot_date) AS d FROM price_history
),
first_snap AS (
    SELECT product_id, MIN(snapshot_date) AS first_date
    FROM price_history
    GROUP BY product_id
)
SELECT p.product_id, p.product_name, p.category, f.first_date AS first_seen
FROM first_snap f
JOIN products p ON p.product_id = f.product_id
CROSS JOIN latest l
WHERE f.first_date = l.d
  AND EXISTS (SELECT 1 FROM price_history WHERE snapshot_date < l.d);

-- 3) Removed products: present in the previous snapshot, missing from the latest
CREATE OR REPLACE VIEW v_removed_products AS
WITH dates AS (
    SELECT MAX(snapshot_date) AS latest,
           (SELECT MAX(snapshot_date) FROM price_history
            WHERE snapshot_date < (SELECT MAX(snapshot_date) FROM price_history)) AS previous
    FROM price_history
)
SELECT p.product_id,
       p.product_name,
       p.category,
       prev.price AS last_known_price,
       prev.snapshot_date AS last_seen_date
FROM dates d
JOIN price_history prev ON prev.snapshot_date = d.previous
JOIN products p ON p.product_id = prev.product_id
LEFT JOIN price_history cur
       ON cur.product_id = prev.product_id AND cur.snapshot_date = d.latest
WHERE cur.product_id IS NULL;

-- 4) Category changes: LAG() on the category column
CREATE OR REPLACE VIEW v_category_changes AS
WITH ordered AS (
    SELECT p.product_id,
           p.product_name,
           ph.snapshot_date,
           ph.category,
           LAG(ph.category) OVER (PARTITION BY ph.product_id ORDER BY ph.snapshot_date) AS old_category
    FROM price_history ph
    JOIN products p ON p.product_id = ph.product_id
)
SELECT product_id,
       product_name,
       snapshot_date,
       old_category,
       category AS new_category
FROM ordered
WHERE old_category IS NOT NULL
  AND old_category <> category;

-- 5) Category statistics for the latest snapshot (used by the dashboard)
CREATE OR REPLACE VIEW v_category_stats AS
SELECT category,
       ROUND(AVG(price), 2) AS avg_price,
       MIN(price) AS min_price,
       MAX(price) AS max_price,
       COUNT(*) AS products_count
FROM price_history
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM price_history)
GROUP BY category;