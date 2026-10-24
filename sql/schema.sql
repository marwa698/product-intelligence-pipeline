-- =====================================================
-- schema.sql : Web-to-Warehouse Product Intelligence Pipeline
-- Database : MySQL 8.0+
-- Owner : Member 2 (Gany Mohamed)
-- =====================================================

CREATE DATABASE IF NOT EXISTS products_db
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE products_db;

-- 1) Staging: today's incoming data (emptied on every run)
DROP TABLE IF EXISTS stg_products;
CREATE TABLE stg_products (
    product_name VARCHAR(500),
    category VARCHAR(100),
    price DECIMAL(10,2),
    currency VARCHAR(3),
    rating INT,
    availability VARCHAR(50),
    product_url VARCHAR(500),
    scraped_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) Products: one row per product (current state)
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_url VARCHAR(500) NOT NULL UNIQUE,
    product_name VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    first_seen DATE NOT NULL,
    last_seen DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_products_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) Price history: one row per product per day (snapshot)
CREATE TABLE IF NOT EXISTS price_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'GBP',
    rating INT,
    availability VARCHAR(50),
    category VARCHAR(100),
    scraped_at DATETIME NOT NULL,
    snapshot_date DATE NOT NULL,
    UNIQUE KEY uq_product_day (product_id, snapshot_date), -- same product cannot appear twice on the same day
    INDEX idx_history_snapshot (snapshot_date),
    CONSTRAINT fk_history_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_price CHECK (price > 0),
    CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4) Internal catalog: the company's own list, used for comparison
CREATE TABLE IF NOT EXISTS internal_catalog (
    catalog_id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    internal_price DECIMAL(10,2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5) Quality log: results of data-quality checks
CREATE TABLE IF NOT EXISTS etl_quality_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    run_date DATE,
    check_name VARCHAR(100),
    status VARCHAR(10),        -- 'PASS' or 'FAIL'
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;