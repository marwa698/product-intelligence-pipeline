-- analysis_queries.sql : the analytical questions and how they are answered (Owner: Member 2)
USE products_db;
-- Q0: which two snapshot dates are being compared?
SELECT MAX(snapshot_date) AS latest_date,
(SELECT MAX(snapshot_date) FROM price_history
WHERE snapshot_date < (SELECT MAX(snapshot_date) FROM price_history)) AS previous_date
FROM price_history;
-- Q1: which products changed price? (view uses LAG())
SELECT * FROM v_price_changes ORDER BY snapshot_date DESC, ABS(diff) DESC;
-- Q2: which products are new in the latest snapshot?
SELECT * FROM v_new_products;
-- Q3: which products disappeared since the previous snapshot?
SELECT * FROM v_removed_products;
-- Q4: which products moved to a different category?
SELECT * FROM v_category_changes;
-- Q5: how do web prices compare with our internal catalogue? (latest snapshot)
SELECT p.product_name,
ph.price AS web_price,
ic.internal_price,
ROUND(ph.price - ic.internal_price, 2) AS price_gap
FROM products p
JOIN price_history ph ON ph.product_id = p.product_id
AND ph.snapshot_date = (SELECT MAX(snapshot_date) FROM price_history)
JOIN internal_catalog ic ON LOWER(ic.product_name) = LOWER(p.product_name)
ORDER BY ABS(ph.price - ic.internal_price) DESC;
-- Q6: category overview for the dashboard
SELECT * FROM v_category_stats ORDER BY avg_price DESC;