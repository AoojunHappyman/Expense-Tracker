"""
Expense Tracker - Flask + MySQL backend
=========================================
REST API สำหรับบันทึกรายรับ-รายจ่าย พร้อม endpoint สรุปข้อมูลสำหรับกราฟ (Chart.js)
"""

import os
from datetime import date
from decimal import Decimal, InvalidOperation

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, g, redirect, url_for

load_dotenv()

app = Flask(__name__)

from production import configure_runtime
configure_runtime(app)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "connection_timeout": 10,
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "expense_tracker"),
}


if os.getenv("DB_SSL_CA"):
    DB_CONFIG.update(
        ssl_ca=os.environ["DB_SSL_CA"],
        ssl_verify_cert=True,
        ssl_verify_identity=True,
        use_pure=True,
    )
if app.config['PRODUCTION'] and DB_CONFIG['host'] not in ('localhost', '127.0.0.1') and not os.getenv('DB_SSL_CA'):
    raise RuntimeError('Remote production database requires DB_SSL_CA for verified TLS')


def get_db_connection():
    """เปิดการเชื่อมต่อ MySQL ใหม่ทุกครั้งที่เรียกใช้ (เหมาะกับแอปขนาดเล็ก)"""
    return mysql.connector.connect(**DB_CONFIG)


from auth import init_auth
from account_migration import register_commands

init_auth(app, lambda: get_db_connection())
register_commands(app, lambda: get_db_connection())


def validate_transaction(data):
    """ตรวจและจัดรูปแบบข้อมูลให้ตรงกับ schema ก่อนเขียนฐานข้อมูล"""
    if not isinstance(data, dict):
        raise ValueError("กรุณาส่งข้อมูลเป็น JSON object")

    missing = [key for key in ("type", "amount", "category", "date") if key not in data]
    if missing:
        raise ValueError(f"ข้อมูลไม่ครบ: {', '.join(missing)}")
    if data["type"] not in ("income", "expense"):
        raise ValueError("type ต้องเป็น income หรือ expense เท่านั้น")

    raw_amount = data["amount"]
    try:
        if isinstance(raw_amount, bool) or not isinstance(raw_amount, (str, int, float)):
            raise ValueError
        amount = Decimal(str(raw_amount))
        if not amount.is_finite() or not Decimal("0") < amount <= Decimal("99999999.99"):
            raise ValueError
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValueError("amount ต้องมากกว่า 0 ไม่เกิน 99999999.99 และมีทศนิยมไม่เกิน 2 ตำแหน่ง") from None

    category = data["category"]
    if not isinstance(category, str) or not category.strip() or len(category.strip()) > 50:
        raise ValueError("category ต้องเป็นข้อความที่ไม่ว่างและยาวไม่เกิน 50 ตัวอักษร")
    note = data.get("note", "")
    if not isinstance(note, str) or len(note.strip()) > 255:
        raise ValueError("note ต้องเป็นข้อความยาวไม่เกิน 255 ตัวอักษร")

    raw_date = data["date"]
    try:
        if not isinstance(raw_date, str):
            raise ValueError
        parsed_date = date.fromisoformat(raw_date)
        if parsed_date.isoformat() != raw_date or parsed_date.year < 1000:
            raise ValueError
    except ValueError:
        raise ValueError("date ต้องเป็นวันที่ที่มีอยู่จริง รูปแบบ YYYY-MM-DD ปี 1000–9999") from None

    return (data["type"], amount, category.strip(), note.strip(), parsed_date)


# ==========================================
# หน้าเว็บหลัก
# ==========================================

@app.route("/")
def index():
    if not g.user:
        return redirect(url_for("login"))
    return render_template("index.html")


# ==========================================
# API: รายการธุรกรรมทั้งหมด (GET, POST)
# ==========================================

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    """ดึงรายการทั้งหมด รองรับ filter ผ่าน query string: ?category=...&start=...&end=..."""
    category = request.args.get("category")
    start = request.args.get("start")
    end = request.args.get("end")

    query = "SELECT id, type, amount, category, note, date FROM transactions WHERE user_id = %s"
    params = [g.user["id"]]

    if category:
        query += " AND category = %s"
        params.append(category)
    if start:
        query += " AND date >= %s"
        params.append(start)
    if end:
        query += " AND date <= %s"
        params.append(end)

    query += " ORDER BY date DESC, id DESC"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # แปลง Decimal และ date ให้เป็นชนิดที่ JSON ใช้ได้
    for row in rows:
        row["amount"] = float(row["amount"])
        row["date"] = row["date"].isoformat()

    return jsonify(rows)


@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    """เพิ่มรายการใหม่"""
    try:
        values = validate_transaction(request.get_json(silent=True))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO transactions (type, amount, category, note, date, user_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (*values, g.user["id"]),
        )
        new_id = cursor.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return jsonify({"id": new_id, "message": "เพิ่มรายการสำเร็จ"}), 201


# ==========================================
# API: แก้ไข / ลบรายการเดียว (PUT, DELETE)
# ==========================================

@app.route("/api/transactions/<int:transaction_id>", methods=["PUT"])
def update_transaction(transaction_id):
    try:
        values = validate_transaction(request.get_json(silent=True))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # ล็อกรายการระหว่างตรวจและแก้ไข แยกกรณีไม่พบออกจากค่าเดิมที่ไม่เปลี่ยน
        cursor.execute("SELECT id FROM transactions WHERE id = %s AND user_id = %s FOR UPDATE", (transaction_id, g.user["id"]))
        if cursor.fetchone() is None:
            conn.rollback()
            return jsonify({"error": "ไม่พบรายการนี้"}), 404
        cursor.execute(
            """UPDATE transactions
               SET type = %s, amount = %s, category = %s, note = %s, date = %s
               WHERE id = %s AND user_id = %s""",
            (*values, transaction_id, g.user["id"]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return jsonify({"message": "แก้ไขรายการสำเร็จ"})


@app.route("/api/transactions/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = %s AND user_id = %s", (transaction_id, g.user["id"]))
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()

    if affected == 0:
        return jsonify({"error": "ไม่พบรายการนี้"}), 404
    return jsonify({"message": "ลบรายการสำเร็จ"})


# ==========================================
# API: สรุปข้อมูลสำหรับกราฟ
# ==========================================

@app.get("/api/dashboard")
def get_dashboard():
    from dashboard import build_dashboard, validate_filters
    filters = dict(month=request.args.get('month', ''),
                   category=request.args.get('category', ''), kind=request.args.get('type', ''))
    try:
        validate_filters(**filters)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, type, amount, category, note, date FROM transactions "
            "WHERE user_id = %s ORDER BY date DESC, id DESC",
            (g.user['id'],),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return jsonify(build_dashboard(rows, **filters))


@app.route("/api/summary")
def get_summary():
    response = get_dashboard()
    if isinstance(response, tuple):
        return response
    return jsonify(response.get_json()['summary'])


@app.route("/api/insights")
def get_insights():
    response = get_dashboard()
    if isinstance(response, tuple):
        return response
    return jsonify(response.get_json()['insights'])


if __name__ == "__main__":
    app.run(debug=False, port=5000)
