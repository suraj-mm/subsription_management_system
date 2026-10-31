import { apiFetch, toast, esc, fmtDate } from "../api.js";
import { openModal, closeModal } from "../api.js";

let _page = 1, _plans = [];

async function fetchPlans() {
  return apiFetch(`/plans?page=${_page}&size=20`);
}

export async function renderPlans() {
  const content = document.getElementById("page-content");
  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Plans</h1>
        <p>Subscription billing plans and pricing</p>
      </div>
      <button class="btn btn-primary" id="add-plan-btn">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        Add Plan
      </button>
    </div>

    <div id="plans-table-wrap">
      <div class="loading-overlay"><div class="spinner"></div></div>
    </div>

    <!-- Plan Modal -->
    <div class="modal-backdrop" id="plan-modal">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title" id="plan-modal-title">Add Plan</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('plan-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <form id="plan-form" novalidate>
            <input type="hidden" id="plan-id" />
            <div class="form-group">
              <label class="form-label">Plan Name <span class="required">*</span></label>
              <input class="form-control" type="text" id="plan-name" name="name" required />
              <p class="form-error" id="plan-name-err"></p>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Price <span class="required">*</span></label>
                <input class="form-control" type="number" step="0.01" min="0" id="plan-price" name="price" />
                <p class="form-error" id="plan-price-err"></p>
              </div>
              <div class="form-group">
                <label class="form-label">Billing Period <span class="required">*</span></label>
                <select class="form-control" id="plan-period" name="billing_period">
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                  <option value="weekly">Weekly</option>
                  <option value="daily">Daily</option>
                </select>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Minimum Quantity</label>
              <input class="form-control" type="number" min="1" id="plan-minqty" name="min_quantity" value="1" />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Start Date</label>
                <input class="form-control" type="date" id="plan-start" name="start_date" />
              </div>
              <div class="form-group">
                <label class="form-label">End Date</label>
                <input class="form-control" type="date" id="plan-end" name="end_date" />
                <p class="form-error" id="plan-end-err"></p>
              </div>
            </div>
            <div style="background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius);padding:14px;margin-top:4px">
              <div style="font-size:12.5px;font-weight:700;margin-bottom:10px;color:var(--color-text-muted)">PLAN FEATURES</div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <label class="form-check"><input type="checkbox" id="plan-autoclose" name="auto_close" /> Auto-close on expiry</label>
                <label class="form-check"><input type="checkbox" id="plan-earlyclose" name="allow_early_close" /> Allow early close</label>
                <label class="form-check"><input type="checkbox" id="plan-pause" name="allow_pause" /> Allow pause</label>
                <label class="form-check"><input type="checkbox" id="plan-renew" name="allow_renew" /> Allow renewal</label>
              </div>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('plan-modal'))">Cancel</button>
          <button class="btn btn-primary" id="save-plan-btn"><span class="btn-text">Save</span></button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("add-plan-btn").addEventListener("click", () => openPlanModal(null));
  document.getElementById("save-plan-btn").addEventListener("click", savePlan);

  await refreshTable();
}

function openPlanModal(plan) {
  document.getElementById("plan-modal-title").textContent = plan ? "Edit Plan" : "Add Plan";
  document.getElementById("plan-id").value = plan?.id ?? "";
  document.getElementById("plan-name").value = plan?.name ?? "";
  document.getElementById("plan-price").value = plan?.price ?? "";
  document.getElementById("plan-period").value = plan?.billing_period ?? "monthly";
  document.getElementById("plan-minqty").value = plan?.min_quantity ?? 1;
  document.getElementById("plan-start").value = plan?.start_date ?? "";
  document.getElementById("plan-end").value = plan?.end_date ?? "";
  document.getElementById("plan-autoclose").checked = plan?.auto_close ?? false;
  document.getElementById("plan-earlyclose").checked = plan?.allow_early_close ?? false;
  document.getElementById("plan-pause").checked = plan?.allow_pause ?? true;
  document.getElementById("plan-renew").checked = plan?.allow_renew ?? true;
  openModal("plan-modal");
}

async function savePlan() {
  const btn = document.getElementById("save-plan-btn");
  const id = document.getElementById("plan-id").value;
  const name = document.getElementById("plan-name").value.trim();
  const price = parseFloat(document.getElementById("plan-price").value);
  const end_date = document.getElementById("plan-end").value;
  const start_date = document.getElementById("plan-start").value;

  document.getElementById("plan-name-err").textContent = "";
  document.getElementById("plan-price-err").textContent = "";
  document.getElementById("plan-end-err").textContent = "";

  if (!name) { document.getElementById("plan-name-err").textContent = "Name required"; document.getElementById("plan-name-err").classList.add("visible"); return; }
  if (isNaN(price) || price < 0) { document.getElementById("plan-price-err").textContent = "Valid price required"; document.getElementById("plan-price-err").classList.add("visible"); return; }
  if (start_date && end_date && end_date <= start_date) {
    document.getElementById("plan-end-err").textContent = "End date must be after start date";
    document.getElementById("plan-end-err").classList.add("visible"); return;
  }

  const body = {
    name,
    price,
    billing_period: document.getElementById("plan-period").value,
    min_quantity: parseInt(document.getElementById("plan-minqty").value) || 1,
    start_date: start_date || null,
    end_date: end_date || null,
    auto_close: document.getElementById("plan-autoclose").checked,
    allow_early_close: document.getElementById("plan-earlyclose").checked,
    allow_pause: document.getElementById("plan-pause").checked,
    allow_renew: document.getElementById("plan-renew").checked,
  };

  btn.disabled = true;
  try {
    if (id) {
      await apiFetch(`/plans/${id}`, { method: "PATCH", body });
      toast("Plan updated", "success");
    } else {
      await apiFetch("/plans", { method: "POST", body });
      toast("Plan created", "success");
    }
    closeModal("plan-modal");
    await refreshTable();
  } catch (e) {
    toast(e.message, "error");
  } finally { btn.disabled = false; }
}

async function refreshTable() {
  const wrap = document.getElementById("plans-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await fetchPlans();
    _plans = data.items;
    renderTable(wrap, data);
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}

function renderTable(wrap, data) {
  if (!data.items.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No plans yet</div><p>Create your first subscription plan.</p></div>`;
    return;
  }

  const flags = p => [
    p.auto_close ? "Auto-close" : null,
    p.allow_early_close ? "Early-close" : null,
    p.allow_pause ? "Pause" : null,
    p.allow_renew ? "Renew" : null,
  ].filter(Boolean).map(f => `<span class="badge badge-confirmed" style="margin:1px">${f}</span>`).join("");

  const rows = data.items.map(p => `
    <tr data-id="${p.id}">
      <td><span style="font-weight:600">${esc(p.name)}</span></td>
      <td>₹${Number(p.price).toFixed(2)}</td>
      <td><span class="badge badge-active">${esc(p.billing_period)}</span></td>
      <td>${p.min_quantity}</td>
      <td>${flags(p)}</td>
      <td>${fmtDate(p.start_date)} — ${fmtDate(p.end_date)}</td>
      <td class="col-actions">
        <button class="btn btn-xs btn-secondary edit-btn" data-id="${p.id}">Edit</button>
      </td>
    </tr>
  `).join("");

  wrap.innerHTML = `
    <div class="table-wrapper">
      <table>
        <thead><tr><th>Name</th><th>Price</th><th>Period</th><th>Min Qty</th><th>Features</th><th>Availability</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="pagination">
        <span class="pagination-info">${data.total} plans</span>
        <button class="pagination-btn" id="prev-btn" ${data.page<=1?"disabled":""}>← Prev</button>
        <span style="font-size:13px;padding:0 4px">Page ${data.page} of ${data.pages}</span>
        <button class="pagination-btn" id="next-btn" ${data.page>=data.pages?"disabled":""}>Next →</button>
      </div>
    </div>
  `;

  wrap.querySelectorAll(".edit-btn").forEach(btn => btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const plan = _plans.find(p => p.id == btn.dataset.id);
    if (plan) openPlanModal(plan);
  }));

  wrap.querySelector("#prev-btn")?.addEventListener("click", async () => { _page--; await refreshTable(); });
  wrap.querySelector("#next-btn")?.addEventListener("click", async () => { _page++; await refreshTable(); });
}
