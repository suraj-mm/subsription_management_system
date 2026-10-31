import { apiFetch, toast, esc, fmtMoney, fmtDate } from "../api.js";
import { getUser } from "../app.js";
import { openModal, closeModal } from "../api.js";

let _page = 1, _statusFilter = "", _overdueOnly = false, _subscriptionId = null;

function invBadge(inv) {
  const isOverdue = inv.status === "Confirmed" && inv.due_date && new Date(inv.due_date) < new Date();
  if (isOverdue) return `<span class="badge badge-overdue">Overdue</span>`;
  const map = { Draft:"badge-draft", Confirmed:"badge-confirmed-inv", Paid:"badge-paid", Cancelled:"badge-cancelled" };
  return `<span class="badge ${map[inv.status] || "badge-draft"}">${esc(inv.status)}</span>`;
}

export async function renderInvoices() {
  const hashQuery = window.location.hash.split("?")[1] || "";
  const urlParams = new URLSearchParams(hashQuery);
  _subscriptionId = urlParams.get("subscription_id") || null;
  _overdueOnly = urlParams.get("overdue") === "1";

  const content = document.getElementById("page-content");
  const user = getUser();
  const isAdmin = user?.role === "admin";

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Invoices</h1>
        <p>${_subscriptionId ? "Filtered by subscription" : _overdueOnly ? "Overdue invoices" : "All invoices"}</p>
      </div>
      <div style="display:flex;gap:8px">
        ${isAdmin ? `<button class="btn btn-secondary" id="generate-btn">Generate Now</button>` : ""}
        <button class="btn btn-secondary" id="bulk-confirm-btn" style="display:none">Confirm Selected</button>
      </div>
    </div>

    <div class="toolbar">
      <div class="toolbar-search">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>
        <input class="form-control" type="search" id="inv-search" placeholder="Search invoice number…" />
      </div>
      <div class="toolbar-filters">
        <select class="form-control" id="inv-status-filter" style="width:160px">
          <option value="">All Statuses</option>
          <option value="Draft">Draft</option>
          <option value="Confirmed">Confirmed</option>
          <option value="Paid">Paid</option>
          <option value="Cancelled">Cancelled</option>
        </select>
        <label class="form-check" style="white-space:nowrap">
          <input type="checkbox" id="overdue-filter" ${_overdueOnly ? "checked" : ""} />
          Overdue only
        </label>
      </div>
    </div>

    <div id="invoices-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>

    <!-- Generate modal -->
    <div class="modal-backdrop" id="generate-modal">
      <div class="modal" style="max-width:400px">
        <div class="modal-header">
          <span class="modal-title">Generate Invoices</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('generate-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <p style="font-size:14px;margin-bottom:16px">Run the billing engine now. Invoices will be created for all active subscriptions due today or earlier.</p>
          <div class="form-group">
            <label class="form-label">Billing Date</label>
            <input class="form-control" type="date" id="gen-date" value="${new Date().toISOString().split("T")[0]}" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('generate-modal'))">Cancel</button>
          <button class="btn btn-primary" id="gen-confirm-btn"><span class="btn-text">Run Billing</span></button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("inv-status-filter")?.addEventListener("change", async (e) => { _statusFilter = e.target.value; _page = 1; await refreshTable(); });
  document.getElementById("overdue-filter")?.addEventListener("change", async (e) => { _overdueOnly = e.target.checked; _page = 1; await refreshTable(); });
  document.getElementById("inv-search")?.addEventListener("input", debounce(async () => { _page = 1; await refreshTable(); }, 350));

  if (isAdmin) {
    document.getElementById("generate-btn")?.addEventListener("click", () => openModal("generate-modal"));
    document.getElementById("gen-confirm-btn")?.addEventListener("click", async () => {
      const btn = document.getElementById("gen-confirm-btn");
      btn.disabled = true; btn.querySelector(".btn-text").textContent = "Running…";
      try {
        const date = document.getElementById("gen-date").value;
        const result = await apiFetch(`/invoices/generate?billing_date=${date}`, { method: "POST" });
        toast(`Generated ${result.generated ?? 0} invoice(s)`, "success");
        closeModal("generate-modal");
        await refreshTable();
      } catch (e) { toast(e.message, "error"); }
      finally { btn.disabled = false; btn.querySelector(".btn-text").textContent = "Run Billing"; }
    });
  }

  await refreshTable();
}

let _selectedIds = new Set();

async function refreshTable(search = "") {
  const wrap = document.getElementById("invoices-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  _selectedIds.clear();

  try {
    let url = `/invoices?page=${_page}&size=20`;
    if (_statusFilter) url += `&status=${encodeURIComponent(_statusFilter)}`;
    if (_overdueOnly) url += `&overdue_only=true`;
    if (_subscriptionId) url += `&subscription_id=${_subscriptionId}`;
    const q = document.getElementById("inv-search")?.value.trim();
    if (q) url += `&search=${encodeURIComponent(q)}`;

    const data = await apiFetch(url);
    const user = getUser();
    const isAdmin = user?.role === "admin";

    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No invoices found</div><p>Invoices are generated automatically when subscriptions become due.</p></div>`;
      return;
    }

    const rows = data.items.map(inv => `
      <tr>
        ${isAdmin ? `<td><input type="checkbox" class="inv-check" data-id="${inv.id}" ${inv.status !== "Draft" ? "disabled" : ""} /></td>` : ""}
        <td onclick="window.location.hash='#/invoices/${inv.id}'" style="cursor:pointer"><span class="font-mono" style="font-size:12.5px">${esc(inv.invoice_number)}</span></td>
        <td>${esc(inv.customer_name || "—")}</td>
        <td>${invBadge(inv)}</td>
        <td>${fmtDate(inv.due_date)}</td>
        <td class="text-right font-bold">${fmtMoney(inv.total_amount)}</td>
        <td class="text-right" style="${inv.outstanding_balance > 0 ? "color:var(--color-danger)" : "color:var(--color-success)"}">${fmtMoney(inv.outstanding_balance)}</td>
        <td class="col-actions">
          <a class="btn btn-xs btn-secondary" href="#/invoices/${inv.id}">View</a>
        </td>
      </tr>`).join("");

    wrap.innerHTML = `
      <div class="table-wrapper">
        <table>
          <thead><tr>
            ${isAdmin ? "<th><input type='checkbox' id='select-all-inv' /></th>" : ""}
            <th>Invoice</th><th>Customer</th><th>Status</th><th>Due Date</th>
            <th class="text-right">Total</th><th class="text-right">Outstanding</th><th></th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <div class="pagination">
          <span class="pagination-info">${data.total} invoices</span>
          <button class="pagination-btn" id="prev-btn" ${data.page<=1?"disabled":""}>← Prev</button>
          <span style="font-size:13px;padding:0 4px">Page ${data.page} of ${data.pages}</span>
          <button class="pagination-btn" id="next-btn" ${data.page>=data.pages?"disabled":""}>Next →</button>
        </div>
      </div>`;

    if (isAdmin) {
      document.getElementById("select-all-inv")?.addEventListener("change", (e) => {
        wrap.querySelectorAll(".inv-check:not(:disabled)").forEach(cb => {
          cb.checked = e.target.checked;
          if (e.target.checked) _selectedIds.add(parseInt(cb.dataset.id));
          else _selectedIds.delete(parseInt(cb.dataset.id));
        });
        document.getElementById("bulk-confirm-btn").style.display = _selectedIds.size ? "" : "none";
      });

      wrap.querySelectorAll(".inv-check").forEach(cb => {
        cb.addEventListener("change", () => {
          if (cb.checked) _selectedIds.add(parseInt(cb.dataset.id));
          else _selectedIds.delete(parseInt(cb.dataset.id));
          document.getElementById("bulk-confirm-btn").style.display = _selectedIds.size ? "" : "none";
        });
      });

      document.getElementById("bulk-confirm-btn")?.addEventListener("click", async () => {
        try {
          await apiFetch("/invoices/confirm-bulk", { method: "POST", body: { invoice_ids: [..._selectedIds] } });
          toast("Selected invoices confirmed", "success");
          await refreshTable();
        } catch (e) { toast(e.message, "error"); }
      });
    }

    wrap.querySelector("#prev-btn")?.addEventListener("click", async () => { _page--; await refreshTable(); });
    wrap.querySelector("#next-btn")?.addEventListener("click", async () => { _page++; await refreshTable(); });
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}

function debounce(fn, ms) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
