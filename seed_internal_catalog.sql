-- =====================================================
-- seed_internal_catalog.sql : company's internal catalogue
-- Owner: Member 2 (Jana Mohamed) - MySQL 8.0+
-- Names match the website exactly so the JOIN in Q5 works.
-- =====================================================

USE products_db;

TRUNCATE TABLE internal_catalog;  -- so the script can be re-run safely

INSERT INTO internal_catalog (product_name, category, internal_price) VALUES
-- 10 books that exist on the website (prices differ a little from the web price)
('A Light in the Attic', 'Poetry', 49.99),
('Tipping the Velvet', 'Historical Fiction', 52.00),
('Soumission', 'Fiction', 48.50),
('Sharp Objects', 'Mystery', 45.00),
('Sapiens: A Brief History of Humankind', 'History', 55.00),
('The Requiem Red', 'Young Adult', 21.50),
('The Dirty Little Secrets of Getting Your Dream Job', 'Business', 35.00),
('The Coming Woman: A Novel Based on the Life of the Infamous Feminist, Victoria Woodhull', 'Default', 16.99),
('The Boys in the Boat: Nine Americans and Their Epic Quest for Gold at the 1936 Berlin Olympics', 'Default', 24.00),
('The Black Maria', 'Poetry', 50.00),
-- 5 books NOT on the website (for testing unmatched products)
('Our Own Internal Book', 'Fiction', 30.00),
('Company Handbook Vol. 1', 'Business', 18.00),
('Internal Poetry Collection', 'Poetry', 25.50),
('Warehouse Mystery Stories', 'Mystery', 27.00),
('Introduction to Our Catalogue', 'Default', 12.00);