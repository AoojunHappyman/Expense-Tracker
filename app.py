"""
Expense Tracker - Flask + MySQL backend
=========================================
REST API สำหรับบันทึกรายรับ-รายจ่าย พร้อม endpoint สรุปข้อมูลสำหรับกราฟ (Chart.js)
"""

import os
from datetime import date

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "expense_tracker"),
}


def get_db_connection():
    """เปิดการเชื่อมต่อ MySQL ใหม่ทุกครั้งที่เรียกใช้ (เหมาะกับแอปขนาดเล็ก)"""
    return mysql.connector.connect(**DB_CONFIG)


# ==========================================
# หน้าเว็บหลัก
# ==========================================

@app.route("/")
def index():
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

    query = "SELECT id, type, amount, category, note, date FROM transactions WHERE 1=1"
    params = []

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
    data = request.get_json(force=True)

    required = ["type", "amount", "category", "date"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"ข้อมูลไม่ครบ: {', '.join(missing)}"}), 400

    if data["type"] not in ("income", "expense"):
        return jsonify({"error": "type ต้องเป็น income หรือ expense เท่านั้น"}), 400

    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount ต้องเป็นตัวเลขที่มากกว่า 0"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO transactions (type, amount, category, note, date)
           VALUES (%s, %s, %s, %s, %s)""",
        (
            data["type"],
            amount,
            data["category"],
            data.get("note", ""),
            data["date"],
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify({"id": new_id, "message": "เพิ่มรายการสำเร็จ"}), 201


# ==========================================
# API: แก้ไข / ลบรายการเดียว (PUT, DELETE)
# ==========================================

@app.route("/api/transactions/<int:transaction_id>", methods=["PUT"])
def update_transaction(transaction_id):
    data = request.get_json(force=True)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE transactions
           SET type = %s, amount = %s, category = %s, note = %s, date = %s
           WHERE id = %s""",
        (
            data["type"],
            float(data["amount"]),
            data["category"],
            data.get("note", ""),
            data["date"],
            transaction_id,
        ),
    )
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()

    if affected == 0:
        return jsonify({"error": "ไม่พบรายการนี้"}), 404
    return jsonify({"message": "แก้ไขรายการสำเร็จ"})


@app.route("/api/transactions/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = %s", (transaction_id,))
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

@app.route("/api/summary")
def get_summary():
    """
    ส่งข้อมูลสรุป 3 ก้อน:
    - totals: ยอดรวมรายรับ/รายจ่าย/คงเหลือ
    - by_category: ยอดรายจ่ายแยกตามหมวดหมู่ (สำหรับ pie chart)
    - by_month: ยอดรายรับ-รายจ่ายแยกตามเดือน (สำหรับ bar/line chart)
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ยอดรวม
    cursor.execute(
        """SELECT type, COALESCE(SUM(amount), 0) AS total
           FROM transactions GROUP BY type"""
    )
    totals_raw = {row["type"]: float(row["total"]) for row in cursor.fetchall()}
    income = totals_raw.get("income", 0)
    expense = totals_raw.get("expense", 0)

    # แยกตามหมวดหมู่ (เฉพาะรายจ่าย)
    cursor.execute(
        """SELECT category, SUM(amount) AS total
           FROM transactions
           WHERE type = 'expense'
           GROUP BY category
           ORDER BY total DESC"""
    )
    by_category = [
        {"category": row["category"], "total": float(row["total"])}
        for row in cursor.fetchall()
    ]

    # แยกตามเดือน
    cursor.execute(
        """SELECT DATE_FORMAT(date, '%Y-%m') AS month,
                  type,
                  SUM(amount) AS total
           FROM transactions
           GROUP BY month, type
           ORDER BY month ASC"""
    )
    monthly_raw = cursor.fetchall()
    cursor.close()
    conn.close()

    months = sorted({row["month"] for row in monthly_raw})
    by_month = {"labels": months, "income": [], "expense": []}
    for m in months:
        inc = next((r["total"] for r in monthly_raw if r["month"] == m and r["type"] == "income"), 0)
        exp = next((r["total"] for r in monthly_raw if r["month"] == m and r["type"] == "expense"), 0)
        by_month["income"].append(float(inc))
        by_month["expense"].append(float(exp))

    return jsonify(
        {
            "totals": {
                "income": income,
                "expense": expense,
                "balance": income - expense,
            },
            "by_category": by_category,
            "by_month": by_month,
        }
    )

@app.route("/api/insights")
def get_insights():
    """
    วิเคราะห์ข้อมูลรายจ่าย:
    - top_categories: หมวดหมู่ใช้จ่ายสูงสุด 3 อันดับ
    - busiest_day: วันในสัปดาห์ที่ใช้จ่ายรวมเยอะที่สุด
    - day_breakdown: ยอดรวมแยกตามวันในสัปดาห์ (ทั้ง 7 วัน)
    - month_comparison: เทียบยอดรายจ่ายเดือนนี้กับเดือนก่อน
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # หมวดหมู่ใช้จ่ายสูงสุด 3 อันดับ
    cursor.execute(
        """SELECT category, SUM(amount) AS total, COUNT(*) AS count
           FROM transactions
           WHERE type = 'expense'
           GROUP BY category
           ORDER BY total DESC
           LIMIT 3"""
    )
    top_categories = [
        {"category": r["category"], "total": float(r["total"]), "count": r["count"]}
        for r in cursor.fetchall()
    ]

    # ดึงรายจ่ายทั้งหมดมาคำนวณวันในสัปดาห์ (ทำใน Python เพื่อได้ชื่อวันภาษาไทย)
    cursor.execute("SELECT date, amount FROM transactions WHERE type = 'expense'")
    expense_rows = cursor.fetchall()

    thai_days = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
    day_totals = [0.0] * 7
    for r in expense_rows:
        day_totals[r["date"].weekday()] += float(r["amount"])

    day_breakdown = [{"day": thai_days[i], "total": day_totals[i]} for i in range(7)]

    busiest_day = None
    if any(day_totals):
        idx = max(range(7), key=lambda i: day_totals[i])
        busiest_day = {"day": thai_days[idx], "total": day_totals[idx]}

    # เทียบเดือนนี้กับเดือนก่อน
    cursor.execute(
        """SELECT DATE_FORMAT(date, '%Y-%m') AS month, SUM(amount) AS total
           FROM transactions
           WHERE type = 'expense'
           GROUP BY month
           ORDER BY month DESC
           LIMIT 2"""
    )
    months = cursor.fetchall()
    cursor.close()
    conn.close()

    month_comparison = None
    if len(months) == 2:
        current, previous = float(months[0]["total"]), float(months[1]["total"])
        pct_change = ((current - previous) / previous * 100) if previous else 0
        month_comparison = {
            "current_month": months[0]["month"],
            "current_total": current,
            "previous_total": previous,
            "pct_change": round(pct_change, 1),
        }

    return jsonify(
        {
            "top_categories": top_categories,
            "busiest_day": busiest_day,
            "day_breakdown": day_breakdown,
            "month_comparison": month_comparison,
        }
    )
if __name__ == "__main__":
    app.run(debug=True, port=5000)
