-- test_data.sql : TEST ONLY. Run on your LOCAL database, never on shared data.
USE products_db;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE price_history;
TRUNCATE TABLE products;
SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO products (product_url, product_name, category, first_seen, last_seen, is_active) VALUES
('http://t/1', 'Book A', 'Poetry',  '2026-10-14', '2026-10-15', TRUE),
('http://t/2', 'Book B', 'Travel',  '2026-10-14', '2026-10-15', TRUE),
('http://t/3', 'Book C', 'Fiction', '2026-10-14', '2026-10-14', FALSE),  -- removed
('http://t/4', 'Book D', 'Mystery', '2026-10-14', '2026-10-15', TRUE),
('http://t/5', 'Book E', 'Fiction', '2026-10-15', '2026-10-15', TRUE);   -- new

INSERT INTO price_history (product_id, price, rating, availability, category, scraped_at, snapshot_date) VALUES
-- day 1 : 14 Oct
(1, 50.00, 3, 'In stock', 'Poetry',   '2026-10-14 10:00:00', '2026-10-14'),
(2, 20.00, 4, 'In stock', 'Travel',   '2026-10-14 10:00:00', '2026-10-14'),
(3, 15.00, 2, 'In stock', 'Fiction',  '2026-10-14 10:00:00', '2026-10-14'),
(4, 30.00, 5, 'In stock', 'Mystery',  '2026-10-14 10:00:00', '2026-10-14'),
-- day 2 : 15 Oct
(1, 45.00, 3, 'In stock', 'Poetry',   '2026-10-15 10:00:00', '2026-10-15'),  -- price dropped
(2, 20.00, 4, 'In stock', 'Travel',   '2026-10-15 10:00:00', '2026-10-15'),  -- unchanged
(4, 30.00, 5, 'In stock', 'Thriller', '2026-10-15 10:00:00', '2026-10-15'),  -- category changed
(5, 12.00, 3, 'In stock', 'Fiction',  '2026-10-15 10:00:00', '2026-10-15');  -- new product

SELECT * FROM price_history ORDER BY snapshot_date, product_id;