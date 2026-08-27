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
    await Promise.all([loadTransactions(), loadSummary()]);
}

async function loadTransactions() {
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
        alert(err.error || "เกิดข้อผิดพลาด");
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
        alert("ลบไม่สำเร็จ");
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
    darkModeBtn.textContent = isDark ? "☀️" : "🌙";
    localStorage.setItem("darkMode", isDark ? "on" : "off");
});

if (localStorage.getItem("darkMode") === "on") {
    document.body.classList.add("dark");
    darkModeBtn.textContent = "☀️";
}

/* ==========================================
   เริ่มโหลดข้อมูลตอนเปิดหน้า
========================================== */

loadAll();
