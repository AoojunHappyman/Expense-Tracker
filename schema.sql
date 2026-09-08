-- ==========================================
-- Expense Tracker Database Schema
-- ==========================================

CREATE DATABASE IF NOT EXISTS expense_tracker
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE expense_tracker;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    recovery_hash CHAR(64) NOT NULL,
    auth_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type ENUM('income', 'expense') NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    category VARCHAR(50) NOT NULL,
    note VARCHAR(255) DEFAULT '',
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INT NOT NULL,
    INDEX idx_transactions_user_date (user_id, date),
    CONSTRAINT fk_transactions_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auth_rate_limits (
    bucket_key CHAR(64) PRIMARY KEY,
    attempts INT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    INDEX idx_rate_expiry (expires_at)
) ENGINE=InnoDB;
