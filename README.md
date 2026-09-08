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
และตาราง `users` โดยไม่ใส่ข้อมูลตัวอย่างในบัญชีผู้ใช้

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
| GET    | `/api/insights`               | วิเคราะห์หมวดหมู่ วันในสัปดาห์ และเปรียบเทียบรายจ่ายรายเดือน |

### GET `/api/insights`

วิเคราะห์รายจ่ายทั้งหมด โดยไม่รับตัวกรอง ส่งผลลัพธ์ JSON ดังนี้:

| Field | ข้อมูล |
|-------|--------|
| `top_categories` | หมวดหมู่รายจ่ายสูงสุดไม่เกิน 3 อันดับ แต่ละรายการมี `category`, `total`, `count` |
| `busiest_day` | วันในสัปดาห์ที่มียอดรายจ่ายรวมสูงสุด (`day`, `total`) หรือ `null` เมื่อไม่มีรายจ่าย |
| `day_breakdown` | ยอดรายจ่ายทั้ง 7 วัน เรียงจันทร์ถึงอาทิตย์ แต่ละรายการมี `day`, `total` |
| `month_comparison` | `current_month`, `current_total`, `previous_total`, `pct_change` หรือ `null` เมื่อมีข้อมูลรายจ่ายไม่ถึง 2 เดือน |

ปัจจุบัน `month_comparison` เปรียบเทียบสองเดือนล่าสุดที่มีข้อมูลรายจ่าย
ซึ่งอาจไม่ใช่เดือนปัจจุบันหรือเดือนที่ติดกัน โดย `current_month` อยู่ในรูป `YYYY-MM`
และ `pct_change` เป็นเปอร์เซ็นต์การเปลี่ยนแปลง ปัดทศนิยม 1 ตำแหน่ง
(คืนค่า 0 หากยอดเดือนก่อนเป็น 0)

## ระบบบัญชีและการย้ายข้อมูล

- สมัครที่ `/register` เข้าสู่ระบบที่ `/login` และกู้บัญชีที่ `/recover`
- ชื่อผู้ใช้ใช้ a–z, 0–9, `_`, `-` จำนวน 3–50 ตัว รหัสผ่าน 12–128 ตัว
- รหัสผ่านเก็บเป็น hash; รหัสกู้บัญชีสุ่มแสดงเพียงครั้งเดียวและเก็บเป็น hash
- เก็บรหัสกู้บัญชีก่อนออกจากหน้าสมัคร หากลืมรหัสผ่านและทำรหัสนี้หาย จะกู้ด้วยตนเองไม่ได้
- การกู้บัญชีเปลี่ยนรหัสกู้ใหม่และยกเลิก session เก่าทุกอุปกรณ์
- ทุก API ต้องเข้าสู่ระบบ ข้อมูลรายการ สรุป และ Insight จำกัดเฉพาะเจ้าของบัญชี
- คำขอ POST/PUT/DELETE ต้องมี `X-CSRF-Token` จาก meta tag หรือ `csrf_token` ในฟอร์ม

### อัปเกรดฐานข้อมูลเดิม

สำรองฐานข้อมูลก่อนอัปเกรด จากนั้นรันคำสั่งนี้ (รันซ้ำได้):

```powershell
.\venv\Scripts\python.exe -m flask --app app migrate-accounts
```

รายการเดิมยังอยู่ครบ แต่ยังไม่ผูกบัญชีและจะไม่แสดงให้ผู้ใช้ใหม่เห็น
สมัครบัญชีเจ้าของก่อน แล้วรันบนเครื่องเซิร์ฟเวอร์โดยแทน `your_username` ด้วยชื่อบัญชีนั้น:

```powershell
.\venv\Scripts\python.exe -m flask --app app assign-legacy your_username
```

คำสั่งนี้ย้ายเฉพาะรายการที่ยังไม่มีเจ้าของ ไม่เปลี่ยนรายการของบัญชีอื่น
ไม่มี API ให้ผู้ใช้ทั่วไปอ้างสิทธิ์ข้อมูลเดิม

ตั้ง `SECRET_KEY` เป็นค่าสุ่มยาวและเก็บคงเดิมใน environment ของเซิร์ฟเวอร์
หากไม่ตั้ง ระบบใช้ค่าสุ่มชั่วคราว ซึ่งทำให้ session หลุดเมื่อรีสตาร์ตหรือใช้หลาย worker
ตั้ง `COOKIE_SECURE=1` เมื่อเปิดผ่าน HTTPS

### ทดสอบ

```powershell
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
# Integration tests ต้องมีสิทธิ์สร้าง/ลบฐานข้อมูลทดสอบแยก
$env:RUN_MYSQL_TESTS="1"
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

## หมายเหตุด้านความปลอดภัย

มีระบบบัญชี การตรวจเจ้าของข้อมูล input validation และ CSRF protection แล้ว
มี rate limiting สำหรับ login/register/recover แล้ว
ก่อนเปิดสาธารณะยังต้องตั้ง HTTPS ใช้ production server และระบบสำรองข้อมูล
ระบบกู้บัญชีเวอร์ชันนี้ใช้รหัสกู้แบบครั้งเดียว ไม่ส่งอีเมล

## จำกัดความถี่การใช้งานบัญชี

| หน้า | ต่อ IP | ต่อชื่อผู้ใช้ (รวมทุก IP) |
|------|--------|--------------------------|
| เข้าสู่ระบบ | 30 ครั้ง / 15 นาที | 10 ครั้ง / 15 นาที |
| สมัครสมาชิก | 5 ครั้ง / 1 ชั่วโมง | — |
| กู้บัญชี | 10 ครั้ง / 15 นาที | 5 ครั้ง / 15 นาที |

นับ POST ที่ผ่าน CSRF ทั้งสำเร็จและไม่สำเร็จ ไม่จำกัดการเปิดหน้า GET
เมื่อเกินโควตาจะตอบ HTTP 429 พร้อม `Retry-After` เป็นวินาทีและข้อความภาษาไทย
หน้าต่างเวลาเริ่มจากครั้งแรก การลองซ้ำขณะถูกจำกัดไม่ยืดเวลารอ
บัญชีที่ถูกจำกัดยังใช้งาน session ที่เข้าสู่ระบบไว้ได้

ตัวนับเก็บในตาราง `auth_rate_limits` ของ MySQL ใช้ร่วมกันทุก worker
และไม่หายเมื่อรีสตาร์ต ใช้ `SECRET_KEY` เดียวกันทุก worker เพื่อสร้างคีย์ HMAC
ไม่เก็บ IP หรือชื่อผู้ใช้เป็นข้อความตรงในตารางนี้
รัน `migrate-accounts` เมื่ออัปเกรดเพื่อสร้างตารางเพิ่มเติม
ข้อมูลตัวนับหมดอายุถูกล้างทีละไม่เกิน 100 แถวเมื่อมีการตรวจครั้งถัดไป
หากฐานข้อมูลตัวจำกัดไม่พร้อม ระบบจะตอบ 503 แทนการปล่อยผ่าน

ระบบใช้ `request.remote_addr` และไม่เชื่อ `X-Forwarded-For` โดยตรง
หากนำขึ้น reverse proxy ต้องตั้ง trusted proxy ให้ตรงโครงสร้างจริงก่อนเปิดใช้งาน
มิฉะนั้นผู้ใช้หลัง proxy อาจถูกนับเป็น IP เดียวกัน
