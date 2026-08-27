-- ==========================================
-- Expense Tracker Database Schema
-- ==========================================

CREATE DATABASE IF NOT EXISTS expense_tracker
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE expense_tracker;

CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type ENUM('income', 'expense') NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    category VARCHAR(50) NOT NULL,
    note VARCHAR(255) DEFAULT '',
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตัวอย่างข้อมูล (ลบทิ้งได้ถ้าไม่ต้องการ)
INSERT INTO transactions (type, amount, category, note, date) VALUES
    ('income',  15000.00, 'เงินเดือน/ค่าขนม', 'เงินจากที่บ้าน',      '2026-08-01'),
    ('expense',   250.00, 'อาหาร',            'ข้าวกลางวัน',         '2026-08-02'),
    ('expense',   120.00, 'เดินทาง',           'ค่ารถไฟฟ้า',          '2026-08-03'),
    ('expense',   890.00, 'ช้อปปิ้ง',           'เสื้อยืด',             '2026-08-05'),
    ('expense',   300.00, 'อาหาร',            'อาหารเย็นกับเพื่อน',    '2026-08-07'),
    ('income',    2000.00, 'รายได้พิเศษ',       'รับจ้างติวหนังสือ',    '2026-08-10'),
    ('expense',   450.00, 'บันเทิง',           'ดูหนัง',              '2026-08-12');
