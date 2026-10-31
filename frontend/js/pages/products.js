import { apiFetch, toast, esc } from "../api.js";
import { openModal, closeModal } from "../api.js";

let _page = 1, _search = "", _products = [], _taxes = [];

async function fetchProducts() {
  return apiFetch(`/products?search=${encodeURIComponent(_search)}&page=${_page}&size=20`);
}

async function fetchTaxes() {
  return apiFetch("/taxes?page=1&size=100");
}

export async function renderProducts() {
  const content = document.getElementById("page-content");
  _taxes = (await fetchTaxes().catch(() => ({ items: [] }))).items;

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Products</h1>
        <p>Manage your product catalog and variants</p>
      </div>
      <button class="btn btn-primary" id="add-product-btn">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        Add Product
      </button>
    </div>

    <div class="toolbar">
      <div class="toolbar-search">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>
        <input class="form-control" type="search" id="product-search" placeholder="Search products…" value="${esc(_search)}" />
      </div>
    </div>

    <div id="products-table-wrap">
      <div class="loading-overlay"><div class="spinner"></div></div>
    </div>

    <!-- Product Modal -->
    <div class="modal-backdrop" id="product-modal">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title" id="product-modal-title">Add Product</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('product-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <form id="product-form" novalidate>
            <input type="hidden" id="p-id" />
            <div class="form-group">
              <label class="form-label">Name <span class="required">*</span></label>
              <input class="form-control" type="text" name="name" id="p-name" required />
              <p class="form-error" id="p-name-err"></p>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Type</label>
                <select class="form-control" name="type" id="p-type">
                  <option value="service">Service</option>
                  <option value="product">Product</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Tax</label>
                <select class="form-control" name="tax_id" id="p-tax">
                  <option value="">— None —</option>
                  ${_taxes.map(t => `<option value="${t.id}">${esc(t.name)} (${t.rate}%)</option>`).join("")}
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Sales Price <span class="required">*</span></label>
                <input class="form-control" type="number" step="0.01" min="0" name="sales_price" id="p-sales-price" />
                <p class="form-error" id="p-price-err"></p>
              </div>
              <div class="form-group">
                <label class="form-label">Cost Price</label>
                <input class="form-control" type="number" step="0.01" min="0" name="cost_price" id="p-cost-price" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Notes</label>
              <textarea class="form-control" name="notes" id="p-notes" rows="2" placeholder="Internal notes…"></textarea>
            </div>
          </form>

          <!-- Variants -->
          <div id="variants-section" style="display:none;margin-top:8px">
            <hr class="divider"/>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
              <span style="font-weight:700;font-size:14px">Variants</span>
              <button class="btn btn-sm btn-secondary" id="add-variant-btn">+ Add Variant</button>
            </div>
            <div id="variants-list"></div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('product-modal'))">Cancel</button>
          <button class="btn btn-primary" id="save-product-btn">
            <span class="btn-text">Save</span>
          </button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("product-search").addEventListener("input", debounce(async (e) => {
    _search = e.target.value;
    _page = 1;
    await refreshTable();
  }, 350));

  document.getElementById("add-product-btn").addEventListener("click", () => openProductModal(null));
  document.getElementById("save-product-btn").addEventListener("click", saveProduct);

  document.getElementById("add-variant-btn")?.addEventListener("click", addVariantRow);

  await refreshTable();
}

function openProductModal(product) {
  document.getElementById("product-modal-title").textContent = product ? "Edit Product" : "Add Product";
  document.getElementById("p-id").value = product?.id ?? "";
  document.getElementById("p-name").value = product?.name ?? "";
  document.getElementById("p-type").value = product?.type ?? "service";
  document.getElementById("p-tax").value = product?.tax_id ?? "";
  document.getElementById("p-sales-price").value = product?.sales_price ?? "";
  document.getElementById("p-cost-price").value = product?.cost_price ?? "";
  document.getElementById("p-notes").value = product?.notes ?? "";

  const variantsSection = document.getElementById("variants-section");
  const variantsList = document.getElementById("variants-list");

  if (product) {
    variantsSection.style.display = "";
    variantsList.innerHTML = "";
    (product.variants || []).forEach(v => addVariantRow(v));
  } else {
    variantsSection.style.display = "";
    variantsList.innerHTML = "";
  }

  openModal("product-modal");
}

function addVariantRow(variant = null) {
  const list = document.getElementById("variants-list");
  const row = document.createElement("div");
  row.className = "line-item-row";
  row.style.gridTemplateColumns = "2fr 2fr 1fr auto";
  row.innerHTML = `
    <input class="form-control" type="text" name="v_attr" placeholder="Attribute (e.g. Size)" value="${esc(variant?.attribute || "")}" />
    <input class="form-control" type="text" name="v_val" placeholder="Value (e.g. Large)" value="${esc(variant?.value || "")}" />
    <input class="form-control" type="number" step="0.01" name="v_price" placeholder="Extra ₹" value="${variant?.extra_price ?? ""}" />
    <button class="line-remove-btn" type="button" aria-label="Remove">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
    </button>
  `;
  row.querySelector(".line-remove-btn").onclick = () => row.remove();
  list.appendChild(row);
}

async function saveProduct() {
  const btn = document.getElementById("save-product-btn");
  const id = document.getElementById("p-id").value;
  const name = document.getElementById("p-name").value.trim();
  const sales_price = parseFloat(document.getElementById("p-sales-price").value);

  document.getElementById("p-name-err").textContent = "";
  document.getElementById("p-price-err").textContent = "";

  if (!name) { document.getElementById("p-name-err").textContent = "Name is required"; document.getElementById("p-name-err").classList.add("visible"); return; }
  if (isNaN(sales_price) || sales_price < 0) { document.getElementById("p-price-err").textContent = "Valid price required"; document.getElementById("p-price-err").classList.add("visible"); return; }

  const tax_id = document.getElementById("p-tax").value;
  const body = {
    name,
    type: document.getElementById("p-type").value,
    sales_price,
    cost_price: parseFloat(document.getElementById("p-cost-price").value) || 0,
    notes: document.getElementById("p-notes").value.trim() || null,
    tax_id: tax_id ? parseInt(tax_id) : null,
  };

  // Collect variants
  const variantRows = document.querySelectorAll("#variants-list .line-item-row");
  const variants = [];
  variantRows.forEach(row => {
    const attr = row.querySelector("[name=v_attr]").value.trim();
    const val = row.querySelector("[name=v_val]").value.trim();
    const ep = parseFloat(row.querySelector("[name=v_price]").value) || 0;
    if (attr && val) variants.push({ attribute: attr, value: val, extra_price: ep });
  });
  body.variants = variants;

  btn.disabled = true;
  try {
    if (id) {
      await apiFetch(`/products/${id}`, { method: "PATCH", body });
      toast("Product updated", "success");
    } else {
      await apiFetch("/products", { method: "POST", body });
      toast("Product created", "success");
    }
    closeModal("product-modal");
    await refreshTable();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function refreshTable() {
  const wrap = document.getElementById("products-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await fetchProducts();
    _products = data.items;
    renderTable(wrap, data);
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}

function renderTable(wrap, data) {
  if (!data.items.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No products yet</div><p>Add your first product to get started.</p></div>`;
    return;
  }

  const rows = data.items.map(p => `
    <tr data-id="${p.id}">
      <td><span style="font-weight:600">${esc(p.name)}</span></td>
      <td><span class="badge badge-confirmed">${esc(p.type)}</span></td>
      <td>₹${Number(p.sales_price).toFixed(2)}</td>
      <td>${p.tax ? `${p.tax.name} (${p.tax.rate}%)` : "—"}</td>
      <td>${p.variants?.length ?? 0}</td>
      <td class="col-actions">
        <button class="btn btn-xs btn-secondary edit-btn" data-id="${p.id}">Edit</button>
      </td>
    </tr>
  `).join("");

  wrap.innerHTML = `
    <div class="table-wrapper">
      <table>
        <thead><tr><th>Name</th><th>Type</th><th>Sales Price</th><th>Tax</th><th>Variants</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${paginationHtml(data)}
    </div>
  `;

  wrap.querySelectorAll(".edit-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const product = _products.find(p => p.id == btn.dataset.id);
      if (product) openProductModal(product);
    });
  });

  setupPagination(wrap);
}

function paginationHtml(data) {
  return `
    <div class="pagination">
      <span class="pagination-info">Showing ${data.items.length} of ${data.total} products</span>
      <button class="pagination-btn" id="prev-btn" ${data.page <= 1 ? "disabled" : ""}>← Prev</button>
      <span style="font-size:13px;padding:0 4px">Page ${data.page} of ${data.pages}</span>
      <button class="pagination-btn" id="next-btn" ${data.page >= data.pages ? "disabled" : ""}>Next →</button>
    </div>`;
}

function setupPagination(wrap) {
  wrap.querySelector("#prev-btn")?.addEventListener("click", async () => { _page--; await refreshTable(); });
  wrap.querySelector("#next-btn")?.addEventListener("click", async () => { _page++; await refreshTable(); });
}

function debounce(fn, ms) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
