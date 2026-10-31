import { apiFetch, toast, esc, fmtDate } from "../api.js";
import { openModal, closeModal } from "../api.js";

let _page = 1, _discounts = [], _products = [];

export async function renderDiscounts() {
  const content = document.getElementById("page-content");
  _products = (await apiFetch("/products?page=1&size=200").catch(() => ({ items: [] }))).items;

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Discounts</h1>
        <p>Promotional discounts applied automatically on billing</p>
      </div>
      <button class="btn btn-primary" id="add-discount-btn">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        Add Discount
      </button>
    </div>
    <div id="discounts-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>

    <div class="modal-backdrop" id="discount-modal">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title" id="discount-modal-title">Add Discount</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('discount-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <form id="discount-form" novalidate>
            <input type="hidden" id="d-id" />
            <div class="form-group">
              <label class="form-label">Discount Name <span class="required">*</span></label>
              <input class="form-control" type="text" id="d-name" name="name" placeholder="e.g. Summer 20% Off" />
              <p class="form-error" id="d-name-err"></p>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Discount Type</label>
                <select class="form-control" id="d-type" name="discount_type">
                  <option value="percent">Percent (%)</option>
                  <option value="fixed">Fixed (₹)</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Value <span class="required">*</span></label>
                <input class="form-control" type="number" step="0.01" min="0.01" id="d-value" name="value" />
                <p class="form-error" id="d-value-err"></p>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Applies To</label>
              <select class="form-control" id="d-applies" name="applies_to">
                <option value="subscription">Entire Subscription</option>
                <option value="product">Specific Product</option>
              </select>
            </div>
            <div class="form-group" id="d-product-group" style="display:none">
              <label class="form-label">Product <span class="required">*</span></label>
              <select class="form-control" id="d-product" name="product_id">
                <option value="">— Select product —</option>
                ${_products.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}
              </select>
              <p class="form-error" id="d-product-err"></p>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Start Date</label>
                <input class="form-control" type="date" id="d-start" name="start_date" />
              </div>
              <div class="form-group">
                <label class="form-label">End Date</label>
                <input class="form-control" type="date" id="d-end" name="end_date" />
                <p class="form-error" id="d-end-err"></p>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Usage Limit</label>
              <input class="form-control" type="number" min="1" id="d-limit" name="usage_limit" placeholder="Unlimited if blank" />
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('discount-modal'))">Cancel</button>
          <button class="btn btn-primary" id="save-discount-btn"><span class="btn-text">Save</span></button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("add-discount-btn").addEventListener("click", () => openDiscountModal(null));
  document.getElementById("save-discount-btn").addEventListener("click", saveDiscount);

  document.getElementById("d-applies").addEventListener("change", (e) => {
    document.getElementById("d-product-group").style.display = e.target.value === "product" ? "" : "none";
  });

  await refreshTable();
}

function openDiscountModal(d) {
  document.getElementById("discount-modal-title").textContent = d ? "Edit Discount" : "Add Discount";
  document.getElementById("d-id").value = d?.id ?? "";
  document.getElementById("d-name").value = d?.name ?? "";
  document.getElementById("d-type").value = d?.discount_type ?? "percent";
  document.getElementById("d-value").value = d?.value ?? "";
  document.getElementById("d-applies").value = d?.applies_to ?? "subscription";
  document.getElementById("d-product").value = d?.product_id ?? "";
  document.getElementById("d-start").value = d?.start_date ?? "";
  document.getElementById("d-end").value = d?.end_date ?? "";
  document.getElementById("d-limit").value = d?.usage_limit ?? "";
  document.getElementById("d-product-group").style.display = (d?.applies_to === "product") ? "" : "none";
  openModal("discount-modal");
}

async function saveDiscount() {
  const btn = document.getElementById("save-discount-btn");
  const id = document.getElementById("d-id").value;
  const name = document.getElementById("d-name").value.trim();
  const value = parseFloat(document.getElementById("d-value").value);
  const applies_to = document.getElementById("d-applies").value;
  const product_id = document.getElementById("d-product").value;
  const end_date = document.getElementById("d-end").value;
  const start_date = document.getElementById("d-start").value;

  let valid = true;
  if (!name) { document.getElementById("d-name-err").textContent = "Name required"; document.getElementById("d-name-err").classList.add("visible"); valid = false; }
  if (!value || value <= 0) { document.getElementById("d-value-err").textContent = "Value must be > 0"; document.getElementById("d-value-err").classList.add("visible"); valid = false; }
  if (applies_to === "product" && !product_id) { document.getElementById("d-product-err").textContent = "Select a product"; document.getElementById("d-product-err").classList.add("visible"); valid = false; }
  if (start_date && end_date && end_date < start_date) { document.getElementById("d-end-err").textContent = "End must be ≥ start"; document.getElementById("d-end-err").classList.add("visible"); valid = false; }
  if (!valid) return;

  const body = {
    name,
    discount_type: document.getElementById("d-type").value,
    value,
    applies_to,
    product_id: applies_to === "product" ? parseInt(product_id) : null,
    start_date: start_date || null,
    end_date: end_date || null,
    usage_limit: document.getElementById("d-limit").value ? parseInt(document.getElementById("d-limit").value) : null,
  };

  btn.disabled = true;
  try {
    if (id) {
      await apiFetch(`/discounts/${id}`, { method: "PATCH", body });
      toast("Discount updated", "success");
    } else {
      await apiFetch("/discounts", { method: "POST", body });
      toast("Discount created", "success");
    }
    closeModal("discount-modal");
    await refreshTable();
  } catch (e) { toast(e.message, "error"); }
  finally { btn.disabled = false; }
}

async function refreshTable() {
  const wrap = document.getElementById("discounts-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await apiFetch(`/discounts?page=${_page}&size=20`);
    _discounts = data.items;
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No discounts yet</div><p>Create promotional discounts to attach to subscriptions.</p></div>`;
      return;
    }
    const rows = data.items.map(d => `
      <tr>
        <td><span style="font-weight:600">${esc(d.name)}</span></td>
        <td>${d.value}${d.discount_type === "percent" ? "%" : " ₹"}</td>
        <td><span class="badge badge-confirmed">${esc(d.applies_to)}</span></td>
        <td>${fmtDate(d.start_date)} — ${fmtDate(d.end_date)}</td>
        <td>${d.usage_limit != null ? `${d.used_count}/${d.usage_limit}` : `${d.used_count} used`}</td>
        <td><span class="badge badge-${d.is_active ? "active" : "closed"}">${d.is_active ? "Active" : "Inactive"}</span></td>
        <td class="col-actions">
          <button class="btn btn-xs btn-secondary edit-btn" data-id="${d.id}">Edit</button>
          <button class="btn btn-xs ${d.is_active ? "btn-danger" : "btn-ghost"} toggle-btn" data-id="${d.id}" data-active="${d.is_active}">${d.is_active ? "Deactivate" : "Activate"}</button>
        </td>
      </tr>`).join("");
    wrap.innerHTML = `
      <div class="table-wrapper">
        <table><thead><tr><th>Name</th><th>Value</th><th>Applies To</th><th>Validity</th><th>Usage</th><th>Status</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table>
      </div>`;
    wrap.querySelectorAll(".edit-btn").forEach(btn => btn.addEventListener("click", () => {
      const d = _discounts.find(x => x.id == btn.dataset.id);
      if (d) openDiscountModal(d);
    }));
    wrap.querySelectorAll(".toggle-btn").forEach(btn => btn.addEventListener("click", async () => {
      const isActive = btn.dataset.active === "true";
      try {
        await apiFetch(`/discounts/${btn.dataset.id}`, { method: "PATCH", body: { is_active: !isActive } });
        toast(isActive ? "Discount deactivated" : "Discount activated", "success");
        await refreshTable();
      } catch (e) { toast(e.message, "error"); }
    }));
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}
