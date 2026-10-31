import { apiFetch, fmtMoney, fmtDate, toast, getToken, esc } from "../api.js";
import { getUser } from "../app.js";

let _sseSource = null;
let _refreshTimeout = null;

async function loadDashboard() {
  const [summary, overdueData, trendData] = await Promise.all([
    apiFetch("/dashboard/summary"),
    apiFetch("/dashboard/overdue?page=1&size=10"),
    apiFetch("/dashboard/revenue-trend"),
  ]);
  return { summary, overdueData, trendData };
}

export async function renderDashboard() {
  const content = document.getElementById("page-content");
  content.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;

  let data;
  try {
    data = await loadDashboard();
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><p>Failed to load dashboard: ${esc(e.message)}</p></div>`;
    return;
  }

  render(content, data);
  setupSSE(content);
}

function render(content, { summary, overdueData, trendData }) {
  const s = summary;
  const trend = trendData.trend || [];
  const maxRevenue = Math.max(...trend.map(t => Number(t.revenue || 0)), 1);

  const barsHtml = trend.map(t => {
    const h = Math.round((Number(t.revenue || 0) / maxRevenue) * 100);
    return `
      <div class="chart-bar-group">
        <div class="chart-bar" style="height:${h}%" title="${esc(t.month)}: ${fmtMoney(t.revenue)}"></div>
        <div class="chart-bar-label">${esc(t.month ? t.month.slice(5) : "")}</div>
      </div>`;
  }).join("");

  const overdueRows = (overdueData.items || []).map(inv => `
    <tr onclick="window.location.hash='#/invoices/${inv.id}'">
      <td><span class="font-mono" style="font-size:12.5px">${esc(inv.invoice_number)}</span></td>
      <td>${esc(inv.customer_name || "—")}</td>
      <td>${fmtDate(inv.due_date)}</td>
      <td class="text-right" style="color:var(--color-danger);font-weight:700">${fmtMoney(inv.outstanding_balance)}</td>
    </tr>
  `).join("") || `<tr><td colspan="4" class="text-center text-muted" style="padding:32px">No overdue invoices 🎉</td></tr>`;

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Dashboard</h1>
        <p>Live subscription and billing overview</p>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <span class="live-dot"></span>
        <span id="live-status" style="font-size:12.5px;color:var(--color-text-muted)">Live</span>
        <button class="btn btn-secondary btn-sm" id="refresh-btn">Refresh</button>
      </div>
    </div>

    <!-- KPIs -->
    <div class="kpi-grid">
      <div class="kpi-card kpi-blue">
        <div class="kpi-label">Active Subscriptions</div>
        <div class="kpi-value">${s.active_subscriptions ?? 0}</div>
        <div class="kpi-sub">Currently running</div>
      </div>
      <div class="kpi-card kpi-green">
        <div class="kpi-label">Monthly Recurring Revenue</div>
        <div class="kpi-value">${fmtMoney(s.mrr)}</div>
        <div class="kpi-sub">Normalized MRR</div>
      </div>
      <div class="kpi-card kpi-red">
        <div class="kpi-label">Overdue Invoices</div>
        <div class="kpi-value">${s.overdue_invoices ?? 0}</div>
        <div class="kpi-sub">${fmtMoney(s.overdue_amount)} outstanding</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Revenue This Month</div>
        <div class="kpi-value">${fmtMoney(s.revenue_this_month)}</div>
        <div class="kpi-sub">Paid invoices</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Customers</div>
        <div class="kpi-value">${s.total_customers ?? 0}</div>
        <div class="kpi-sub">Registered accounts</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Pending Revenue</div>
        <div class="kpi-value">${fmtMoney(s.total_outstanding)}</div>
        <div class="kpi-sub">Confirmed, unpaid</div>
      </div>
    </div>

    <!-- Revenue Trend -->
    <div class="card mb-4" style="margin-bottom:24px">
      <div class="card-header">
        <span class="card-title">Revenue Trend (12 months)</span>
      </div>
      <div class="card-body">
        <div class="chart-wrapper">
          <div class="chart-bars" id="trend-chart">
            ${trend.length ? barsHtml : '<p class="text-muted text-sm" style="padding:16px">No revenue data yet</p>'}
          </div>
        </div>
      </div>
    </div>

    <!-- Overdue Table -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">Overdue Invoices</span>
        <a class="btn btn-sm btn-secondary" href="#/invoices?overdue=1">View all</a>
      </div>
      <div class="table-wrapper" style="border:none;border-radius:0 0 12px 12px">
        <table>
          <thead>
            <tr>
              <th>Invoice</th><th>Customer</th><th>Due Date</th><th class="text-right">Outstanding</th>
            </tr>
          </thead>
          <tbody id="overdue-tbody">${overdueRows}</tbody>
        </table>
      </div>
    </div>
  `;

  document.getElementById("refresh-btn")?.addEventListener("click", async () => {
    try {
      const d = await loadDashboard();
      render(content, d);
      setupSSE(content);
      toast("Dashboard refreshed", "success");
    } catch (e) {
      toast("Refresh failed: " + e.message, "error");
    }
  });
}

function setupSSE(content) {
  if (_sseSource) { _sseSource.close(); _sseSource = null; }

  const token = getToken();
  if (!token) return;

  try {
    _sseSource = new EventSource(`/dashboard/stream?token=${encodeURIComponent(token)}`);

    _sseSource.onopen = () => {
      const el = document.getElementById("live-status");
      if (el) el.textContent = "Live";
    };

    _sseSource.onmessage = (evt) => {
      if (_refreshTimeout) clearTimeout(_refreshTimeout);
      _refreshTimeout = setTimeout(async () => {
        try {
          const d = await loadDashboard();
          render(content, d);
          setupSSE(content);
        } catch {}
      }, 500);
    };

    _sseSource.onerror = () => {
      const el = document.getElementById("live-status");
      if (el) el.textContent = "Reconnecting…";
    };
  } catch {}
}

// Cleanup when navigating away
window.addEventListener("hashchange", () => {
  if (_sseSource) { _sseSource.close(); _sseSource = null; }
  if (_refreshTimeout) clearTimeout(_refreshTimeout);
});
