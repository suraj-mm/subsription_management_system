import { apiFetch, toast, esc } from "../api.js";

let _page = 1, _search = "";

export async function renderCustomers() {
  const content = document.getElementById("page-content");
  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Customers</h1>
        <p>All registered customer accounts</p>
      </div>
    </div>
    <div class="toolbar">
      <div class="toolbar-search">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>
        <input class="form-control" type="search" id="customer-search" placeholder="Search by name or email…" />
      </div>
    </div>
    <div id="customers-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>
  `;

  document.getElementById("customer-search").addEventListener("input", debounce(async (e) => {
    _search = e.target.value;
    _page = 1;
    await refreshTable();
  }, 350));

  await refreshTable();
}

async function refreshTable() {
  const wrap = document.getElementById("customers-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await apiFetch(`/customers?search=${encodeURIComponent(_search)}&page=${_page}&size=25`);
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No customers found</div><p>Customers self-register via the sign-up page.</p></div>`;
      return;
    }
    const rows = data.items.map(c => `
      <tr onclick="window.location.hash='#/subscriptions?customer_id=${c.id}'">
        <td>
          <div style="font-weight:600">${esc(c.name)}</div>
          <div style="font-size:12px;color:var(--color-text-muted)">${esc(c.email)}</div>
        </td>
        <td>${esc(c.company || "—")}</td>
        <td>${esc(c.phone || "—")}</td>
        <td><span class="badge badge-${c.is_active ? "active" : "closed"}">${c.is_active ? "Active" : "Inactive"}</span></td>
        <td class="text-muted text-sm">${new Date(c.created_at).toLocaleDateString("en-IN")}</td>
        <td class="col-actions">
          <a class="btn btn-xs btn-secondary" href="#/subscriptions?customer_id=${c.id}">View Subs</a>
        </td>
      </tr>`).join("");

    wrap.innerHTML = `
      <div class="table-wrapper">
        <table><thead><tr><th>Name / Email</th><th>Company</th><th>Phone</th><th>Status</th><th>Joined</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table>
        <div class="pagination">
          <span class="pagination-info">${data.total} customers</span>
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
