/* ==========================================
   Expense Tracker - Frontend Logic
========================================== */

const form = document.getElementById("transactionForm");
const tableBody = document.getElementById("transactionBody");
const emptyState = document.getElementById("emptyState");
const dateInput = document.getElementById("date");

let editingId = null;   // ถ้าไม่ null แปลว่ากำลังแก้ไขรายการนี้อยู่
let categoryChart = null;
let monthlyChart = null;

// ตั้งค่าวันที่เริ่มต้นเป็นวันนี้
dateInput.valueAsDate = new Date();

const fmtMoney = (n) =>
    "฿" + Number(n).toLocaleString("th-TH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* ==========================================
   โหลดข้อมูลทั้งหมด (รายการ + สรุป)
========================================== */

async function loadAll() {
    await Promise.all([loadTransactions(), loadSummary(),loadInsights()]);
}

async function loadTransactions() {
    tableBody.innerHTML = Array(3).fill(
        `<tr><td colspan="6"><div class="skeleton" style="height:20px;">.</div></td></tr>`
    ).join("");

    const res = await fetch("/api/transactions");
    const data = await res.json();
    renderTable(data);
}

async function loadSummary() {
    const res = await fetch("/api/summary");
    const data = await res.json();
    renderTotals(data.totals);
    renderCategoryChart(data.by_category);
    renderMonthlyChart(data.by_month);
}

/* ==========================================
   Render: การ์ดสรุปยอด
========================================== */

function renderTotals(totals) {
    document.getElementById("totalIncome").textContent = fmtMoney(totals.income);
    document.getElementById("totalExpense").textContent = fmtMoney(totals.expense);
    document.getElementById("totalBalance").textContent = fmtMoney(totals.balance);
}

/* ==========================================
   Render: ตารางรายการ
========================================== */

function renderTable(transactions) {
    tableBody.innerHTML = "";

    if (transactions.length === 0) {
        emptyState.style.display = "block";
        return;
    }
    emptyState.style.display = "none";

    for (const t of transactions) {
        const tr = document.createElement("tr");
        tr.className = t.type === "income" ? "income-row" : "expense-row";

        tr.innerHTML = `
            <td>${t.date}</td>
            <td><span class="badge ${t.type}">${t.type === "income" ? "รายรับ" : "รายจ่าย"}</span></td>
            <td>${escapeHtml(t.category)}</td>
            <td>${escapeHtml(t.note || "-")}</td>
            <td class="amount-cell">${t.type === "income" ? "+" : "-"}${fmtMoney(t.amount)}</td>
            <td>
                <button class="icon-btn edit" data-id="${t.id}" title="แก้ไข"><i class="fa-solid fa-pen"></i></button>
                <button class="icon-btn delete" data-id="${t.id}" title="ลบ"><i class="fa-solid fa-trash"></i></button>
            </td>
        `;
        tableBody.appendChild(tr);
    }

    // ผูก event ให้ปุ่มแก้ไข/ลบทุกแถว
    tableBody.querySelectorAll(".edit").forEach((btn) =>
        btn.addEventListener("click", () => startEdit(btn.dataset.id, transactions))
    );
    tableBody.querySelectorAll(".delete").forEach((btn) =>
        btn.addEventListener("click", () => deleteTransaction(btn.dataset.id))
    );
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

/* ==========================================
   Render: กราฟ (Chart.js)
========================================== */

function renderCategoryChart(byCategory) {
    const ctx = document.getElementById("categoryChart");
    const labels = byCategory.map((c) => c.category);
    const values = byCategory.map((c) => c.total);

    const palette = ["#2563eb", "#7c3aed", "#f87171", "#facc15", "#22c55e", "#06b6d4", "#f97316", "#ec4899"];

    if (categoryChart) categoryChart.destroy();
    categoryChart = new Chart(ctx, {
        type: "pie",
        data: {
            labels: labels.length ? labels : ["ยังไม่มีข้อมูล"],
            datasets: [{
                data: values.length ? values : [1],
                backgroundColor: palette,
                borderWidth: 2,
                borderColor: "#ffffff",
            }],
        },
        options: {
            plugins: {
                legend: { position: "bottom", labels: { font: { family: "Consolas" } } },
            },
        },
    });
}

function renderMonthlyChart(byMonth) {
    const ctx = document.getElementById("monthlyChart");

    if (monthlyChart) monthlyChart.destroy();
    monthlyChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: byMonth.labels.length ? byMonth.labels : ["-"],
            datasets: [
                {
                    label: "รายรับ",
                    data: byMonth.income.length ? byMonth.income : [0],
                    backgroundColor: "#22c55e",
                    borderRadius: 6,
                },
                {
                    label: "รายจ่าย",
                    data: byMonth.expense.length ? byMonth.expense : [0],
                    backgroundColor: "#f87171",
                    borderRadius: 6,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: "bottom", labels: { font: { family: "Consolas" } } },
            },
            scales: {
                y: { beginAtZero: true },
            },
        },
    });
}

/* ==========================================
   ฟอร์ม: เพิ่ม / แก้ไขรายการ
========================================== */

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
        type: document.getElementById("type").value,
        amount: document.getElementById("amount").value,
        category: document.getElementById("category").value.trim(),
        date: document.getElementById("date").value,
        note: document.getElementById("note").value.trim(),
    };

    const url = editingId ? `/api/transactions/${editingId}` : "/api/transactions";
    const method = editingId ? "PUT" : "POST";

    const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    if (!res.ok) {
        const err = await res.json();
        showToast(err.error || "เกิดข้อผิดพลาด");
        return;
    }

    resetForm();
    await loadAll();
});

function startEdit(id, transactions) {
    const t = transactions.find((x) => String(x.id) === String(id));
    if (!t) return;

    editingId = t.id;
    document.getElementById("type").value = t.type;
    document.getElementById("amount").value = t.amount;
    document.getElementById("category").value = t.category;
    document.getElementById("date").value = t.date;
    document.getElementById("note").value = t.note || "";

    document.getElementById("submitBtn").innerHTML = '<i class="fa-solid fa-check"></i> บันทึกการแก้ไข';
    form.scrollIntoView({ behavior: "smooth" });
}

function resetForm() {
    editingId = null;
    form.reset();
    dateInput.valueAsDate = new Date();
    document.getElementById("submitBtn").innerHTML = '<i class="fa-solid fa-check"></i> บันทึกรายการ';
}

/* ==========================================
   ลบรายการ
========================================== */

async function deleteTransaction(id) {
    if (!confirm("ยืนยันลบรายการนี้?")) return;

    const res = await fetch(`/api/transactions/${id}`, { method: "DELETE" });
    if (!res.ok) {
        showToast("ลบไม่สำเร็จ");
        return;
    }
    await loadAll();
}

/* ==========================================
   Dark Mode (เหมือนกับเว็บเรซูเม่)
========================================== */

const darkModeBtn = document.getElementById("darkMode");

darkModeBtn.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    const isDark = document.body.classList.contains("dark");
    localStorage.setItem("darkMode", isDark ? "on" : "off");
});

if (localStorage.getItem("darkMode") === "on") {
    document.body.classList.add("dark");
}

/* ==========================================
   เริ่มโหลดข้อมูลตอนเปิดหน้า
========================================== */

loadAll();

function showToast(message, type = "success") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fa-solid ${type === "success" ? "fa-circle-check" : "fa-circle-exclamation"}"></i>
        <span>${message}</span>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("hide");
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function renderTotals(totals) {
    animateValue("totalIncome", totals.income);
    animateValue("totalExpense", totals.expense);
    animateValue("totalBalance", totals.balance);
}

function animateValue(elId, endValue) {
    const el = document.getElementById(elId);
    const startValue = parseFloat(el.dataset.raw || 0);
    const duration = 600;
    const startTime = performance.now();

    function step(now) {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out
        const current = startValue + (endValue - startValue) * eased;
        el.textContent = fmtMoney(current);
        if (progress < 1) requestAnimationFrame(step);
    }
    el.dataset.raw = endValue;
    requestAnimationFrame(step);
}

async function loadInsights() {
    const res = await fetch("/api/insights");
    const data = await res.json();
    renderInsights(data);
}

function renderInsights(data) {
    const container = document.getElementById("insightContent");
    const items = [];

    // หมวดหมู่ใช้จ่ายสูงสุด 3 อันดับ
    if (data.top_categories.length) {
        const rankHtml = data.top_categories
            .map((c, i) => `<li><span><span class="rank-num">${i + 1}.</span>${escapeHtml(c.category)}</span><b>${fmtMoney(c.total)}</b></li>`)
            .join("");
        items.push(`
            <div class="insight-item">
                <i class="fa-solid fa-ranking-star"></i>
                <div>
                    <p class="insight-title">หมวดหมู่ใช้จ่ายสูงสุด</p>
                    <ul class="rank-list">${rankHtml}</ul>
                </div>
            </div>
        `);
    }

    // วันในสัปดาห์ที่ใช้จ่ายเยอะสุด
    if (data.busiest_day) {
        items.push(`
            <div class="insight-item">
                <i class="fa-solid fa-calendar-day"></i>
                <div>
                    <p class="insight-title">วันที่ใช้จ่ายเยอะที่สุด</p>
                    <p class="insight-detail">วัน<b>${data.busiest_day.day}</b> ใช้จ่ายรวม <b>${fmtMoney(data.busiest_day.total)}</b></p>
                </div>
            </div>
        `);
    }

    // เทียบเดือนนี้กับเดือนก่อน
    if (data.month_comparison) {
        const mc = data.month_comparison;
        const isUp = mc.pct_change > 0;
        const trendClass = isUp ? "trend-up" : "trend-down";
        const trendIcon = isUp ? "fa-arrow-trend-up" : "fa-arrow-trend-down";
        items.push(`
            <div class="insight-item">
                <i class="fa-solid fa-chart-line"></i>
                <div>
                    <p class="insight-title">เทียบกับเดือนก่อน</p>
                    <p class="insight-detail">
                        ใช้จ่ายเดือนนี้ <b>${fmtMoney(mc.current_total)}</b>
                        <span class="${trendClass}"><i class="fa-solid ${trendIcon}"></i> ${Math.abs(mc.pct_change)}%</span>
                        เทียบกับเดือนก่อน
                    </p>
                </div>
            </div>
        `);
    }

    container.innerHTML = items.length
        ? `<div class="insight-grid">${items.join("")}</div>`
        : `<p class="empty-state">ยังมีข้อมูลไม่พอสำหรับวิเคราะห์</p>`;
}