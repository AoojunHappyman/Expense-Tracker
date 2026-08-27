# Expense Tracker (Flask + MySQL)

เว็บบันทึกรายรับ-รายจ่าย พร้อมกราฟสรุป (Chart.js)

## โครงสร้างโปรเจกต์

```
expense-tracker/
├── app.py                 # Flask backend + REST API
├── schema.sql              # SQL สร้างฐานข้อมูลและตาราง
├── requirements.txt         # Python dependencies
├── .env.example             # ตัวอย่างไฟล์ config (คัดลอกเป็น .env)
├── templates/
│   └── index.html          # หน้าเว็บหลัก
└── static/
    ├── css/style.css       # ดีไซน์ (โทนเดียวกับเว็บเรซูเม่)
    └── js/script.js        # เรียก API, วาดกราฟ, CRUD
```

## วิธีติดตั้งและรัน

### 1. ติดตั้ง MySQL และสร้างฐานข้อมูล

เปิด MySQL แล้วรันไฟล์ `schema.sql`:

```bash
mysql -u root -p < schema.sql
```

คำสั่งนี้จะสร้างฐานข้อมูลชื่อ `expense_tracker`, ตาราง `transactions`,
และใส่ข้อมูลตัวอย่างให้ 7 รายการ (ลบทิ้งได้ถ้าไม่ต้องการ ดูท้ายไฟล์ schema.sql)

### 2. ตั้งค่า environment variables

```bash
cp .env.example .env
```

แล้วเปิดไฟล์ `.env` แก้ `DB_PASSWORD` ให้ตรงกับรหัสผ่าน MySQL ของคุณ

### 3. ติดตั้ง Python packages

แนะนำให้สร้าง virtual environment ก่อน:

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 4. รันเซิร์ฟเวอร์

```bash
python app.py
```

เปิดเบราว์เซอร์ไปที่ **http://localhost:5000**

## API Endpoints

| Method | Endpoint                     | คำอธิบาย                          |
|--------|-------------------------------|-------------------------------------|
| GET    | `/api/transactions`           | ดึงรายการทั้งหมด (filter ได้: `?category=&start=&end=`) |
| POST   | `/api/transactions`           | เพิ่มรายการใหม่                      |
| PUT    | `/api/transactions/<id>`      | แก้ไขรายการ                         |
| DELETE | `/api/transactions/<id>`      | ลบรายการ                           |
| GET    | `/api/summary`                | สรุปยอดรวม + ข้อมูลสำหรับกราฟ         |


## หมายเหตุด้านความปลอดภัย

โค้ดนี้เป็นเวอร์ชันสำหรับโปรเจกต์/portfolio ยังไม่มีระบบ login และ input validation
แบบเข้มงวด หากจะ deploy ใช้งานจริงควรเพิ่ม authentication, CSRF protection,
และ rate limiting ก่อน
