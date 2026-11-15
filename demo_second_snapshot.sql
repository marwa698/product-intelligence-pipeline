-- demo_second_snapshot.sql : DEMO ONLY. Run on your LOCAL database, never on shared data.
USE products_db;

SET @d1 := (SELECT MAX(snapshot_date) FROM price_history);
SET @d2 := DATE_ADD(@d1, INTERVAL 1 DAY);

-- Day 2 = copy of day 1, except:
--  * products 1-5 are missing            -> 5 removed products
--  * every product with id divisible by 50 is +25% -> price changes
--  * product 7 moves to 'Demo Category'  -> 1 category change
INSERT INTO price_history
  (product_id, price, currency, rating, availability, category, scraped_at, snapshot_date)
SELECT product_id,
       CASE WHEN product_id % 50 = 0 THEN ROUND(price * 1.25, 2) ELSE price END,
       currency, rating, availability,
       CASE WHEN product_id = 7 THEN 'Demo Category' ELSE category END,
       TIMESTAMP(@d2, '10:00:00'), @d2
FROM price_history
WHERE snapshot_date = @d1
  AND product_id NOT IN (1, 2, 3, 4, 5);

UPDATE products SET is_active = FALSE WHERE product_id IN (1, 2, 3, 4, 5);

-- 3 brand-new products
INSERT INTO products (product_url, product_name, category, first_seen, last_seen, is_active)
VALUES
('http://demo/new1', 'Demo New Book 1', 'Fiction', @d2, @d2, TRUE),
('http://demo/new2', 'Demo New Book 2', 'Poetry',  @d2, @d2, TRUE),
('http://demo/new3', 'Demo New Book 3', 'Travel',  @d2, @d2, TRUE);

INSERT INTO price_history
  (product_id, price, currency, rating, availability, category, scraped_at, snapshot_date)
SELECT product_id, 19.99, 'GBP', 4, 'In stock', category, TIMESTAMP(@d2, '10:00:00'), @d2
FROM products
WHERE product_url LIKE 'http://demo/new%';