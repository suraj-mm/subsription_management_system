import { apiFetch, toast, esc } from "../api.js";
import { openModal, closeModal } from "../api.js";

let _page = 1, _templates = [], _products = [], _plans = [];

export async function renderQuotationTemplates() {
  const content = document.getElementById("page-content");
  content.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;

  const [productsData, plansData] = await Promise.all([
    apiFetch("/products?page=1&size=200").catch(() => ({ items: [] })),
    apiFetch("/plans?page=1&size=100").catch(() => ({ items: [] })),
  ]);
  _products = productsData.items;
  _plans = plansData.items;

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Quotation Templates</h1>
        <p>Reusable templates for fast subscription creation</p>
      </div>
      <button class="btn btn-primary" id="add-template-btn">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        New Template
      </button>
    </div>
    <div id="templates-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>

    <div class="modal-backdrop" id="template-modal">
      <div class="modal" style="max-width:640px">
        <div class="modal-header">
          <span class="modal-title" id="template-modal-title">New Template</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('template-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <form id="template-form" novalidate>
            <input type="hidden" id="t-id" />
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Template Name <span class="required">*</span></label>
                <input class="form-control" type="text" id="t-name" name="name" placeholder="e.g. Basic Monthly" />
                <p class="form-error" id="t-name-err"></p>
              </div>
              <div class="form-group">
                <label class="form-label">Default Plan <span class="required">*</span></label>
                <select class="form-control" id="t-plan" name="plan_id">
                  <option value="">— Select plan —</option>
                  ${_plans.map(p => `<option value="${p.id}">${esc(p.name)} (${p.billing_period})</option>`).join("")}
                </select>
                <p class="form-error" id="t-plan-err"></p>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Quote Valid For (days)</label>
                <input class="form-control" type="number" min="1" id="t-validity" name="validity_days" value="30" />
              </div>
              <div class="form-group">
                <label class="form-label">Default Payment Terms</label>
                <input class="form-control" type="text" id="t-terms" name="payment_terms" placeholder="e.g. Net 30" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Notes</label>
              <textarea class="form-control" id="t-notes" name="notes" rows="2"></textarea>
            </div>
          </form>

          <hr class="divider" />
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
            <span style="font-weight:700;font-size:14px">Line Items</span>
            <button class="btn btn-sm btn-secondary" id="add-line-btn">+ Add Line</button>
          </div>
          <p class="form-error" id="t-lines-err"></p>
          <div class="line-items">
            <div class="line-items-header">
              <span>Product</span><span>Variant</span><span>Qty</span><span>Notes</span><span></span>
            </div>
            <div id="template-lines"></div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('template-modal'))">Cancel</button>
          <button class="btn btn-primary" id="save-template-btn"><span class="btn-text">Save Template</span></button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("add-template-btn").addEventListener("click", () => openTemplateModal(null));
  document.getElementById("save-template-btn").addEventListener("click", saveTemplate);
  document.getElementById("add-line-btn").addEventListener("click", () => addTemplateLine(null));

  await refreshTable();
}

function openTemplateModal(t) {
  document.getElementById("template-modal-title").textContent = t ? "Edit Template" : "New Template";
  document.getElementById("t-id").value = t?.id ?? "";
  document.getElementById("t-name").value = t?.name ?? "";
  document.getElementById("t-plan").value = t?.plan_id ?? "";
  document.getElementById("t-validity").value = t?.validity_days ?? 30;
  document.getElementById("t-terms").value = t?.payment_terms ?? "";
  document.getElementById("t-notes").value = t?.notes ?? "";
  document.getElementById("template-lines").innerHTML = "";
  (t?.lines || []).forEach(l => addTemplateLine(l));
  openModal("template-modal");
}

function addTemplateLine(line = null) {
  const container = document.getElementById("template-lines");
  const row = document.createElement("div");
  row.className = "line-item-row";
  row.style.gridTemplateColumns = "3fr 1.5fr 1fr 1.5fr auto";
  row.innerHTML = `
    <select class="form-control" name="tl_product" style="font-size:13px">
      <option value="">— Product —</option>
      ${_products.map(p => `<option value="${p.id}" ${p.id == line?.product_id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}
    </select>
    <select class="form-control" name="tl_variant" style="font-size:13px">
      <option value="">— None —</option>
    </select>
    <input class="form-control" type="number" name="tl_qty" min="1" value="${line?.quantity ?? 1}" placeholder="Qty" />
    <input class="form-control" type="text" name="tl_notes" placeholder="Notes" value="${esc(line?.notes || "")}" />
    <button class="line-remove-btn" type="button">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
    </button>
  `;

  // Populate variants when product changes
  const productSel = row.querySelector("[name=tl_product]");
  const variantSel = row.querySelector("[name=tl_variant]");

  function updateVariants(selectedVariantId) {
    const product = _products.find(p => p.id == productSel.value);
    variantSel.innerHTML = `<option value="">— None —</option>` +
      (product?.variants || []).map(v =>
        `<option value="${v.id}" ${v.id == selectedVariantId ? "selected" : ""}>${esc(v.attribute)}: ${esc(v.value)} (+₹${v.extra_price})</option>`
      ).join("");
  }

  productSel.addEventListener("change", () => updateVariants(null));
  if (line?.product_id) updateVariants(line?.variant_id);

  row.querySelector(".line-remove-btn").onclick = () => row.remove();
  container.appendChild(row);
}

async function saveTemplate() {
  const btn = document.getElementById("save-template-btn");
  const id = document.getElementById("t-id").value;
  const name = document.getElementById("t-name").value.trim();
  const plan_id = document.getElementById("t-plan").value;

  let valid = true;
  document.getElementById("t-name-err").classList.remove("visible");
  document.getElementById("t-plan-err").classList.remove("visible");
  document.getElementById("t-lines-err").classList.remove("visible");

  if (!name) { document.getElementById("t-name-err").textContent = "Name required"; document.getElementById("t-name-err").classList.add("visible"); valid = false; }
  if (!plan_id) { document.getElementById("t-plan-err").textContent = "Plan required"; document.getElementById("t-plan-err").classList.add("visible"); valid = false; }

  const lineRows = document.querySelectorAll("#template-lines .line-item-row");
  const lines = [];
  lineRows.forEach(row => {
    const product_id = row.querySelector("[name=tl_product]").value;
    const variant_id = row.querySelector("[name=tl_variant]").value;
    const quantity = parseInt(row.querySelector("[name=tl_qty]").value) || 1;
    const notes = row.querySelector("[name=tl_notes]").value.trim();
    if (product_id) lines.push({ product_id: parseInt(product_id), variant_id: variant_id ? parseInt(variant_id) : null, quantity, notes: notes || null });
  });

  if (!lines.length) {
    document.getElementById("t-lines-err").textContent = "Add at least one line item";
    document.getElementById("t-lines-err").classList.add("visible"); valid = false;
  }
  if (!valid) return;

  const body = {
    name, plan_id: parseInt(plan_id),
    validity_days: parseInt(document.getElementById("t-validity").value) || 30,
    payment_terms: document.getElementById("t-terms").value.trim() || null,
    notes: document.getElementById("t-notes").value.trim() || null,
    lines,
  };

  btn.disabled = true;
  try {
    if (id) {
      await apiFetch(`/quotation-templates/${id}`, { method: "PATCH", body });
      toast("Template updated", "success");
    } else {
      await apiFetch("/quotation-templates", { method: "POST", body });
      toast("Template created", "success");
    }
    closeModal("template-modal");
    await refreshTable();
  } catch (e) { toast(e.message, "error"); }
  finally { btn.disabled = false; }
}

async function refreshTable() {
  const wrap = document.getElementById("templates-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await apiFetch(`/quotation-templates?page=${_page}&size=20`);
    _templates = data.items;
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No templates yet</div><p>Create templates to speed up subscription creation.</p></div>`;
      return;
    }
    const rows = data.items.map(t => `
      <tr>
        <td><span style="font-weight:600">${esc(t.name)}</span></td>
        <td>${esc(t.plan?.name ?? "—")}</td>
        <td>${t.validity_days} days</td>
        <td>${t.lines?.length ?? 0} lines</td>
        <td class="col-actions">
          <button class="btn btn-xs btn-secondary edit-btn" data-id="${t.id}">Edit</button>
        </td>
      </tr>`).join("");
    wrap.innerHTML = `<div class="table-wrapper"><table><thead><tr><th>Name</th><th>Default Plan</th><th>Quote Valid</th><th>Lines</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
    wrap.querySelectorAll(".edit-btn").forEach(btn => btn.addEventListener("click", () => {
      const t = _templates.find(x => x.id == btn.dataset.id);
      if (t) openTemplateModal(t);
    }));
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}
