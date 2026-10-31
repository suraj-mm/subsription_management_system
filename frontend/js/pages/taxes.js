import { apiFetch, toast, esc } from "../api.js";
import { openModal, closeModal } from "../api.js";

let _page = 1, _taxes = [];

export async function renderTaxes() {
  const content = document.getElementById("page-content");
  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Taxes</h1>
        <p>Tax rates applied to products and invoice lines</p>
      </div>
      <button class="btn btn-primary" id="add-tax-btn">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        Add Tax
      </button>
    </div>
    <div id="taxes-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>

    <div class="modal-backdrop" id="tax-modal">
      <div class="modal" style="max-width:420px">
        <div class="modal-header">
          <span class="modal-title" id="tax-modal-title">Add Tax</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('tax-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <form id="tax-form" novalidate>
            <input type="hidden" id="tax-id" />
            <div class="form-group">
              <label class="form-label">Name <span class="required">*</span></label>
              <input class="form-control" type="text" id="tax-name" name="name" placeholder="e.g. GST 18%" />
              <p class="form-error" id="tax-name-err"></p>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Rate <span class="required">*</span></label>
                <input class="form-control" type="number" step="0.01" min="0" max="100" id="tax-rate" name="rate" />
                <p class="form-error" id="tax-rate-err"></p>
              </div>
              <div class="form-group">
                <label class="form-label">Type</label>
                <select class="form-control" id="tax-type" name="type">
                  <option value="percent">Percent (%)</option>
                  <option value="fixed">Fixed (₹)</option>
                </select>
              </div>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('tax-modal'))">Cancel</button>
          <button class="btn btn-primary" id="save-tax-btn"><span class="btn-text">Save</span></button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("add-tax-btn").addEventListener("click", () => openTaxModal(null));
  document.getElementById("save-tax-btn").addEventListener("click", saveTax);
  await refreshTable();
}

function openTaxModal(tax) {
  document.getElementById("tax-modal-title").textContent = tax ? "Edit Tax" : "Add Tax";
  document.getElementById("tax-id").value = tax?.id ?? "";
  document.getElementById("tax-name").value = tax?.name ?? "";
  document.getElementById("tax-rate").value = tax?.rate ?? "";
  document.getElementById("tax-type").value = tax?.type ?? "percent";
  openModal("tax-modal");
}

async function saveTax() {
  const btn = document.getElementById("save-tax-btn");
  const id = document.getElementById("tax-id").value;
  const name = document.getElementById("tax-name").value.trim();
  const rate = parseFloat(document.getElementById("tax-rate").value);

  document.getElementById("tax-name-err").classList.remove("visible");
  document.getElementById("tax-rate-err").classList.remove("visible");

  if (!name) { document.getElementById("tax-name-err").textContent = "Name required"; document.getElementById("tax-name-err").classList.add("visible"); return; }
  if (isNaN(rate) || rate < 0 || rate > 100) { document.getElementById("tax-rate-err").textContent = "Rate must be 0–100"; document.getElementById("tax-rate-err").classList.add("visible"); return; }

  const body = { name, rate, type: document.getElementById("tax-type").value };
  btn.disabled = true;
  try {
    if (id) {
      await apiFetch(`/taxes/${id}`, { method: "PATCH", body });
      toast("Tax updated", "success");
    } else {
      await apiFetch("/taxes", { method: "POST", body });
      toast("Tax created", "success");
    }
    closeModal("tax-modal");
    await refreshTable();
  } catch (e) { toast(e.message, "error"); }
  finally { btn.disabled = false; }
}

async function refreshTable() {
  const wrap = document.getElementById("taxes-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await apiFetch(`/taxes?page=${_page}&size=50`);
    _taxes = data.items;
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No taxes yet</div><p>Add tax rates to apply to products.</p></div>`;
      return;
    }
    const rows = data.items.map(t => `
      <tr>
        <td><span style="font-weight:600">${esc(t.name)}</span></td>
        <td>${t.rate}${t.type === "percent" ? "%" : " ₹"}</td>
        <td><span class="badge badge-${t.type === "percent" ? "confirmed" : "quotation"}">${esc(t.type)}</span></td>
        <td><span class="badge badge-${t.is_active ? "active" : "closed"}">${t.is_active ? "Active" : "Inactive"}</span></td>
        <td class="col-actions">
          <button class="btn btn-xs btn-secondary edit-btn" data-id="${t.id}">Edit</button>
          <button class="btn btn-xs ${t.is_active ? "btn-danger" : "btn-ghost"} toggle-btn" data-id="${t.id}" data-active="${t.is_active}">${t.is_active ? "Deactivate" : "Activate"}</button>
        </td>
      </tr>`).join("");
    wrap.innerHTML = `<div class="table-wrapper"><table><thead><tr><th>Name</th><th>Rate</th><th>Type</th><th>Status</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;

    wrap.querySelectorAll(".edit-btn").forEach(btn => btn.addEventListener("click", () => {
      const t = _taxes.find(x => x.id == btn.dataset.id);
      if (t) openTaxModal(t);
    }));
    wrap.querySelectorAll(".toggle-btn").forEach(btn => btn.addEventListener("click", async () => {
      const isActive = btn.dataset.active === "true";
      try {
        await apiFetch(`/taxes/${btn.dataset.id}`, { method: "PATCH", body: { is_active: !isActive } });
        toast(isActive ? "Tax deactivated" : "Tax activated", "success");
        await refreshTable();
      } catch (e) { toast(e.message, "error"); }
    }));
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}
