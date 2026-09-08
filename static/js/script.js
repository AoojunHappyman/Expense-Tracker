/* ==========================================
   Expense Tracker - Frontend Logic
========================================== */

const form = document.getElementById("transactionForm");
const tableBody = document.getElementById("transactionBody");
const emptyState = document.getElementById("emptyState");
const dateInput = document.getElementById("date");

const submitBtn = document.getElementById("submitBtn");
const cancelEditBtn = document.getElementById("cancelEdit");
const confirmModal = document.getElementById("confirmModal");
const cancelDeleteBtn = document.getElementById("cancelDelete");
const confirmDeleteBtn = document.getElementById("confirmDelete");
let isSaving = false;
let isDeleting = false;
let pendingDeleteId = null;
let deleteTrigger = null;

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
    tableBody.innerHTML = Array(3).fill(
        `<tr><td colspan="6"><div class="skeleton" style="height:20px;">.</div></td></tr>`
    ).join("");
    const res = await apiFetch("/api/dashboard");
    if (!res.ok) throw new Error("Unable to load dashboard");
    const data = await res.json();
    renderTable(data.transactions);
    renderTotals(data.summary.totals);
    renderCategoryChart(data.summary.by_category);
    renderMonthlyChart(data.summary.by_month);
    renderInsights(data.insights);
}

/* ==========================================
   Render: การ์ดสรุปยอด
========================================== */



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

    const palette = ["#96b96c", "#e3bc7a", "#c88878", "#6c998c", "#b6bb9e", "#8c9dad", "#aaa0b5", "#d5d9b6"];

    if (categoryChart) categoryChart.destroy();
    categoryChart = new Chart(ctx, {
        type: "pie",
        data: {
            labels: labels.length ? labels : ["ยังไม่มีข้อมูล"],
            datasets: [{
                data: values.length ? values : [1],
                backgroundColor: palette,
                borderWidth: 2,
                borderColor: getComputedStyle(document.body).getPropertyValue("--surface").trim(),
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom", labels: { color: getComputedStyle(document.body).getPropertyValue("--text").trim(), usePointStyle: true, pointStyle: "circle", boxWidth: 8, boxHeight: 8, padding: 18, font: { family: "Arial, Noto Sans Thai, sans-serif", size: 12 } } },
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
                    backgroundColor: "#96b96c",
                    borderRadius: 6,
                },
                {
                    label: "รายจ่าย",
                    data: byMonth.expense.length ? byMonth.expense : [0],
                    backgroundColor: "#c88878",
                    borderRadius: 6,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom", labels: { color: getComputedStyle(document.body).getPropertyValue("--text").trim(), usePointStyle: true, pointStyle: "circle", boxWidth: 8, boxHeight: 8, padding: 18, font: { family: "Arial, Noto Sans Thai, sans-serif", size: 12 } } },
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
    if (isSaving || isDeleting || pendingDeleteId !== null) return;

    const payload = {
        type: document.getElementById("type").value,
        amount: document.getElementById("amount").value,
        category: document.getElementById("category").value.trim(),
        date: document.getElementById("date").value,
        note: document.getElementById("note").value.trim(),
    };

    const url = editingId ? `/api/transactions/${editingId}` : "/api/transactions";
    const method = editingId ? "PUT" : "POST";

    isSaving = true;
    setFormBusy(true);
    submitBtn.textContent = "กำลังบันทึก...";
    try {
        const res = await apiFetch(url, {
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showToast(err.error || "บันทึกไม่สำเร็จ", "error");
            return;
        }
        resetForm();
        try {
            await loadAll();
        } catch {
            showToast("บันทึกแล้ว แต่โหลดข้อมูลใหม่ไม่สำเร็จ กรุณารีเฟรชหน้า", "error");
        }
    } catch {
        showToast("ไม่สามารถยืนยันผลการบันทึกได้ กรุณารีเฟรชตรวจรายการก่อนลองใหม่", "error");
    } finally {
        isSaving = false;
        setFormBusy(false);
        submitBtn.innerHTML = '<i class="fa-solid fa-check"></i> ' +
            (editingId !== null ? "บันทึกการแก้ไข" : "บันทึกรายการ");
    }
});

function setFormBusy(busy) {
    Array.from(form.elements).forEach((element) => { element.disabled = busy; });
}

cancelEditBtn.addEventListener("click", () => {
    if (isSaving || isDeleting) return;
    resetForm();
    document.getElementById("type").focus();
});

function startEdit(id, transactions) {
    if (isSaving || isDeleting || pendingDeleteId !== null) return;
    cancelEditBtn.hidden = false;
    document.getElementById("formTitle").textContent = "แก้ไขรายการ";
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
    cancelEditBtn.hidden = true;
    document.getElementById("formTitle").textContent = "เพิ่มรายการ";
    form.reset();
    dateInput.valueAsDate = new Date();
    document.getElementById("submitBtn").innerHTML = '<i class="fa-solid fa-check"></i> บันทึกรายการ';
}

/* ==========================================
   ลบรายการ
========================================== */

function deleteTransaction(id) {
    if (isSaving || isDeleting || pendingDeleteId !== null) return;
    pendingDeleteId = id;
    deleteTrigger = document.activeElement;
    confirmModal.classList.add("show");
    cancelDeleteBtn.focus();
}

function closeDeleteModal() {
    if (isDeleting) return;
    confirmModal.classList.remove("show");
    pendingDeleteId = null;
    if (deleteTrigger?.isConnected) deleteTrigger.focus();
    else submitBtn.focus();
    deleteTrigger = null;
}

cancelDeleteBtn.addEventListener("click", closeDeleteModal);
confirmModal.addEventListener("click", (event) => {
    if (event.target === confirmModal) closeDeleteModal();
});
confirmModal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        event.preventDefault();
        closeDeleteModal();
    }
    if (event.key === "Tab") {
        event.preventDefault();
        if (!isDeleting) {
            (document.activeElement === cancelDeleteBtn ? confirmDeleteBtn : cancelDeleteBtn).focus();
        }
    }
});

confirmDeleteBtn.addEventListener("click", async () => {
    if (pendingDeleteId === null || isDeleting || isSaving) return;
    const id = pendingDeleteId;
    let deleted = false;
    isDeleting = true;
    setFormBusy(true);
    cancelDeleteBtn.disabled = true;
    confirmDeleteBtn.disabled = true;
    confirmDeleteBtn.textContent = "กำลังลบ...";
    try {
        const res = await apiFetch(`/api/transactions/${id}`, { method: "DELETE" });
        if (!res.ok) {
            showToast("ลบไม่สำเร็จ", "error");
            return;
        }
        deleted = true;
        if (String(editingId) === String(id)) resetForm();
        try {
            await loadAll();
        } catch {
            showToast("ลบแล้ว แต่โหลดข้อมูลใหม่ไม่สำเร็จ กรุณารีเฟรชหน้า", "error");
        }
    } catch {
        showToast("ไม่สามารถยืนยันผลการลบได้ กรุณารีเฟรชตรวจรายการ", "error");
    } finally {
        isDeleting = false;
        setFormBusy(false);
        cancelDeleteBtn.disabled = false;
        confirmDeleteBtn.disabled = false;
        confirmDeleteBtn.textContent = "ลบรายการ";
        if (deleted) closeDeleteModal();
        else cancelDeleteBtn.focus();
    }
});

/* ==========================================
   Dark Mode (เหมือนกับเว็บเรซูเม่)
========================================== */

const darkModeBtn = document.getElementById("darkMode");

darkModeBtn.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    const isDark = document.body.classList.contains("dark");
    localStorage.setItem("darkMode", isDark ? "on" : "off");
    applyChartTheme();
});

if (localStorage.getItem("darkMode") !== "off") {
    document.body.classList.add("dark");
}

/* ==========================================
   เริ่มโหลดข้อมูลตอนเปิดหน้า
========================================== */

applyChartTheme();
loadAll().catch(() => showToast("โหลดข้อมูลไม่สำเร็จ กรุณารีเฟรชหน้าเพื่อลองใหม่", "error"));

function showToast(message, type = "success") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fa-solid ${type === "success" ? "fa-circle-check" : "fa-circle-exclamation"}"></i>
        <span>${escapeHtml(message)}</span>
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
    const res = await apiFetch("/api/insights");
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
function applyChartTheme() {
    const style = getComputedStyle(document.body);
    const muted = style.getPropertyValue("--muted").trim();
    const line = style.getPropertyValue("--line").trim();
    darkModeBtn.setAttribute("aria-label", document.body.classList.contains("dark") ? "เปลี่ยนเป็นโหมดสว่าง" : "เปลี่ยนเป็นโหมดมืด");
    if (typeof Chart === "undefined") return;
    Chart.defaults.color = muted;
    Chart.defaults.borderColor = line;
    for (const chart of [categoryChart, monthlyChart]) {
        if (!chart) continue;
        chart.options.plugins.legend.labels.color = style.getPropertyValue("--text").trim();
        if (chart === monthlyChart) {
            for (const axis of ["x", "y"]) {
                chart.options.scales[axis].ticks.color = muted;
                chart.options.scales[axis].grid.color = line;
            }
        } else {
            chart.data.datasets[0].borderColor = style.getPropertyValue("--surface").trim();
        }
        chart.update();
    }
}

async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
        },
    });
    if (response.status === 401) {
        window.location.assign("/login");
        throw new Error("Session expired");
    }
    return response;
}
