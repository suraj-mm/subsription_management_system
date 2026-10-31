import { apiFetch, toast, esc, fmtMoney, fmtDate } from "../api.js";
import { openModal, closeModal } from "../api.js";
import { getUser, navigate } from "../app.js";

let _page = 1, _statusFilter = "", _customerId = null;

function subBadge(status) {
  const map = { Draft:"badge-draft", Quotation:"badge-quotation", Confirmed:"badge-confirmed", Active:"badge-active", Paused:"badge-paused", Closed:"badge-closed" };
  return `<span class="badge ${map[status] || "badge-draft"}">${esc(status)}</span>`;
}

export async function renderSubscriptions({ params } = {}) {
  const hashQuery = window.location.hash.split("?")[1] || "";
  const urlParams = new URLSearchParams(hashQuery);
  _customerId = urlParams.get("customer_id") || null;

  const content = document.getElementById("page-content");
  const user = getUser();
  const isStaffOrAdmin = user?.role === "admin" || user?.role === "staff";

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Subscriptions</h1>
        <p>${_customerId ? "Filtered by customer" : "All subscription records"}</p>
      </div>
      ${isStaffOrAdmin ? `<button class="btn btn-primary" id="new-sub-btn">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        New Subscription
      </button>` : ""}
    </div>

    <div class="toolbar">
      <div class="toolbar-search">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>
        <input class="form-control" type="search" id="sub-search" placeholder="Search by number…" />
      </div>
      <div class="toolbar-filters">
        <select class="form-control" id="status-filter" style="width:160px">
          <option value="">All Statuses</option>
          <option value="Draft">Draft</option>
          <option value="Quotation">Quotation</option>
          <option value="Confirmed">Confirmed</option>
          <option value="Active">Active</option>
          <option value="Paused">Paused</option>
          <option value="Closed">Closed</option>
        </select>
      </div>
    </div>

    <div id="subs-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>

    <!-- New Sub Modal -->
    <div class="modal-backdrop" id="new-sub-modal">
      <div class="modal" style="max-width:680px">
        <div class="modal-header">
          <span class="modal-title">New Subscription</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('new-sub-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="tabs" id="new-sub-tabs">
            <button class="tab-btn active" data-tab="blank">Blank</button>
            <button class="tab-btn" data-tab="template">From Template</button>
          </div>
          <div id="tab-blank"></div>
          <div id="tab-template" style="display:none"></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('new-sub-modal'))">Cancel</button>
          <button class="btn btn-primary" id="create-sub-btn"><span class="btn-text">Create Subscription</span></button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("status-filter")?.addEventListener("change", async (e) => { _statusFilter = e.target.value; _page = 1; await refreshTable(); });
  document.getElementById("sub-search")?.addEventListener("input", debounce(async (e) => { _page = 1; await refreshTable(e.target.value); }, 350));

  if (isStaffOrAdmin) {
    document.getElementById("new-sub-btn")?.addEventListener("click", () => openNewSubModal());
    document.getElementById("create-sub-btn")?.addEventListener("click", createSubscription);
    document.getElementById("new-sub-tabs")?.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab-btn");
      if (!btn) return;
      document.querySelectorAll("#new-sub-tabs .tab-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-blank").style.display = btn.dataset.tab === "blank" ? "" : "none";
      document.getElementById("tab-template").style.display = btn.dataset.tab === "template" ? "" : "none";
    });
  }

  await refreshTable();
}

let _plans = [], _products = [], _templates = [], _customers = [];

async function openNewSubModal() {
  [_plans, _products, _templates, _customers] = await Promise.all([
    apiFetch("/plans?page=1&size=100").then(d => d.items).catch(() => []),
    apiFetch("/products?page=1&size=200").then(d => d.items).catch(() => []),
    apiFetch("/quotation-templates?page=1&size=100").then(d => d.items).catch(() => []),
    apiFetch("/customers?page=1&size=200").then(d => d.items).catch(() => []),
  ]);

  renderBlankTab();
  renderTemplateTab();
  openModal("new-sub-modal");
}

function customerOptions() {
  return _customers.map(c => `<option value="${c.id}">${esc(c.name)} — ${esc(c.email)}</option>`).join("");
}

function productOptions() {
  return _products.map(p => `<option value="${p.id}">${esc(p.name)} — ₹${Number(p.sales_price).toFixed(2)}</option>`).join("");
}

function renderBlankTab() {
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("tab-blank").innerHTML = `
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Customer <span class="required">*</span></label>
        <select class="form-control" id="ns-customer"><option value="">— Select customer —</option>${customerOptions()}</select>
        <p class="form-error" id="ns-customer-err"></p>
      </div>
      <div class="form-group">
        <label class="form-label">Plan <span class="required">*</span></label>
        <select class="form-control" id="ns-plan"><option value="">— Select plan —</option>${_plans.map(p=>`<option value="${p.id}">${esc(p.name)} (${p.billing_period} — ₹${Number(p.price).toFixed(2)})</option>`).join("")}</select>
        <p class="form-error" id="ns-plan-err"></p>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Start Date <span class="required">*</span></label>
        <input class="form-control" type="date" id="ns-start" value="${today}" />
      </div>
      <div class="form-group">
        <label class="form-label">Expiry Date</label>
        <input class="form-control" type="date" id="ns-expiry" />
        <p class="form-hint">Defaults to 12 months from start</p>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Payment Terms</label>
      <input class="form-control" type="text" id="ns-terms" placeholder="e.g. Net 30" />
    </div>
    <hr class="divider"/>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <span style="font-weight:700;font-size:14px">Line Items <span class="required">*</span></span>
      <button class="btn btn-sm btn-secondary" id="ns-add-line">+ Add Line</button>
    </div>
    <p class="form-error" id="ns-lines-err"></p>
    <div class="line-items">
      <div class="line-items-header"><span>Product</span><span>Variant</span><span>Qty</span><span>Unit Price</span><span></span></div>
      <div id="ns-lines"></div>
    </div>
  `;
  document.getElementById("ns-add-line")?.addEventListener("click", addBlankLine);
  addBlankLine();
}

function addBlankLine() {
  const container = document.getElementById("ns-lines");
  const row = document.createElement("div");
  row.className = "line-item-row";
  row.innerHTML = `
    <select class="form-control" name="bl_product" style="font-size:13px"><option value="">— Product —</option>${productOptions()}</select>
    <select class="form-control" name="bl_variant" style="font-size:13px"><option value="">— None —</option></select>
    <input class="form-control" type="number" name="bl_qty" min="1" value="1" />
    <span class="form-control" style="background:var(--color-bg);cursor:default" id="bl-price-${Date.now()}">—</span>
    <button class="line-remove-btn" type="button"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg></button>
  `;
  const pSel = row.querySelector("[name=bl_product]");
  const vSel = row.querySelector("[name=bl_variant]");
  pSel.addEventListener("change", () => {
    const p = _products.find(x => x.id == pSel.value);
    vSel.innerHTML = `<option value="">— None —</option>` + (p?.variants||[]).map(v=>`<option value="${v.id}">${esc(v.attribute)}: ${esc(v.value)} (+₹${v.extra_price})</option>`).join("");
  });
  row.querySelector(".line-remove-btn").onclick = () => row.remove();
  container.appendChild(row);
}

function renderTemplateTab() {
  document.getElementById("tab-template").innerHTML = `
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Customer <span class="required">*</span></label>
        <select class="form-control" id="ft-customer"><option value="">— Select customer —</option>${customerOptions()}</select>
        <p class="form-error" id="ft-customer-err"></p>
      </div>
      <div class="form-group">
        <label class="form-label">Template <span class="required">*</span></label>
        <select class="form-control" id="ft-template"><option value="">— Select template —</option>${_templates.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join("")}</select>
        <p class="form-error" id="ft-template-err"></p>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Start Date</label>
        <input class="form-control" type="date" id="ft-start" value="${new Date().toISOString().split("T")[0]}" />
      </div>
      <div class="form-group">
        <label class="form-label">Payment Terms</label>
        <input class="form-control" type="text" id="ft-terms" placeholder="e.g. Net 30" />
      </div>
    </div>
  `;
}

async function createSubscription() {
  const btn = document.getElementById("create-sub-btn");
  const activeTab = document.querySelector("#new-sub-tabs .tab-btn.active")?.dataset.tab;
  btn.disabled = true;
  btn.querySelector(".btn-text").textContent = "Creating…";

  try {
    if (activeTab === "template") {
      const customer_id = document.getElementById("ft-customer").value;
      const template_id = document.getElementById("ft-template").value;
      let valid = true;
      if (!customer_id) { document.getElementById("ft-customer-err").textContent = "Required"; document.getElementById("ft-customer-err").classList.add("visible"); valid = false; }
      if (!template_id) { document.getElementById("ft-template-err").textContent = "Required"; document.getElementById("ft-template-err").classList.add("visible"); valid = false; }
      if (!valid) return;

      const body = {
        customer_id: parseInt(customer_id),
        template_id: parseInt(template_id),
        start_date: document.getElementById("ft-start").value || null,
        payment_terms: document.getElementById("ft-terms").value.trim() || null,
      };
      const sub = await apiFetch("/subscriptions/from-template", { method: "POST", body });
      toast("Subscription created from template", "success");
      closeModal("new-sub-modal");
      navigate(`/subscriptions/${sub.id}`);
    } else {
      // Blank
      const customer_id = document.getElementById("ns-customer").value;
      const plan_id = document.getElementById("ns-plan").value;
      let valid = true;
      if (!customer_id) { document.getElementById("ns-customer-err").textContent = "Required"; document.getElementById("ns-customer-err").classList.add("visible"); valid = false; }
      if (!plan_id) { document.getElementById("ns-plan-err").textContent = "Required"; document.getElementById("ns-plan-err").classList.add("visible"); valid = false; }

      const lineRows = document.querySelectorAll("#ns-lines .line-item-row");
      const lines = [];
      lineRows.forEach(row => {
        const product_id = row.querySelector("[name=bl_product]").value;
        const variant_id = row.querySelector("[name=bl_variant]").value;
        const qty = parseInt(row.querySelector("[name=bl_qty]").value) || 1;
        if (product_id) lines.push({ product_id: parseInt(product_id), variant_id: variant_id ? parseInt(variant_id) : null, qty });
      });
      if (!lines.length) { document.getElementById("ns-lines-err").textContent = "Add at least one line"; document.getElementById("ns-lines-err").classList.add("visible"); valid = false; }
      if (!valid) return;

      const body = {
        customer_id: parseInt(customer_id),
        plan_id: parseInt(plan_id),
        start_date: document.getElementById("ns-start").value,
        expiry_date: document.getElementById("ns-expiry").value || null,
        payment_terms: document.getElementById("ns-terms").value.trim() || null,
        lines,
      };
      const sub = await apiFetch("/subscriptions", { method: "POST", body });
      toast("Subscription created", "success");
      closeModal("new-sub-modal");
      navigate(`/subscriptions/${sub.id}`);
    }
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.querySelector(".btn-text").textContent = "Create Subscription";
  }
}

let _searchVal = "";
async function refreshTable(search = _searchVal) {
  _searchVal = search;
  const wrap = document.getElementById("subs-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    let url = `/subscriptions?page=${_page}&size=20`;
    if (_statusFilter) url += `&status=${encodeURIComponent(_statusFilter)}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (_customerId) url += `&customer_id=${_customerId}`;
    const data = await apiFetch(url);
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No subscriptions found</div><p>Try adjusting your filters.</p></div>`;
      return;
    }
    const rows = data.items.map(s => `
      <tr onclick="window.location.hash='#/subscriptions/${s.id}'" style="cursor:pointer">
        <td><span class="font-mono" style="font-size:12.5px">${esc(s.subscription_number)}</span></td>
        <td>${esc(s.customer?.name || "—")}</td>
        <td>${esc(s.plan?.name || "—")}</td>
        <td>${subBadge(s.status)}</td>
        <td>${fmtDate(s.start_date)}</td>
        <td>${fmtDate(s.expiry_date)}</td>
        <td class="text-right font-bold">${fmtMoney(s.total_amount)}</td>
      </tr>`).join("");
    wrap.innerHTML = `
      <div class="table-wrapper">
        <table><thead><tr><th>Number</th><th>Customer</th><th>Plan</th><th>Status</th><th>Start</th><th>Expiry</th><th class="text-right">Total</th></tr></thead>
        <tbody>${rows}</tbody></table>
        <div class="pagination">
          <span class="pagination-info">${data.total} subscriptions</span>
          <button class="pagination-btn" id="prev-btn" ${data.page<=1?"disabled":""}>← Prev</button>
          <span style="font-size:13px;padding:0 4px">Page ${data.page} of ${data.pages}</span>
          <button class="pagination-btn" id="next-btn" ${data.page>=data.pages?"disabled":""}>Next →</button>
        </div>
      </div>`;
    wrap.querySelector("#prev-btn")?.addEventListener("click", async () => { _page--; await refreshTable(); });
    wrap.querySelector("#next-btn")?.addEventListener("click", async () => { _page++; await refreshTable(); });
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}

function debounce(fn, ms) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
