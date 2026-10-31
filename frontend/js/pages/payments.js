import { apiFetch, toast, esc, fmtMoney, fmtDatetime } from "../api.js";
import { getUser } from "../app.js";

let _page = 1;

export async function renderPayments() {
  const content = document.getElementById("page-content");
  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Payments</h1>
        <p>All recorded payments across invoices</p>
      </div>
    </div>
    <div id="payments-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>
  `;
  await refreshTable();
}

async function refreshTable() {
  const wrap = document.getElementById("payments-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await apiFetch(`/payments?page=${_page}&size=25`);
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No payments yet</div><p>Payments are recorded from invoice detail pages.</p></div>`;
      return;
    }
    const rows = data.items.map(p => `
      <tr onclick="window.location.hash='#/invoices/${p.invoice_id}'" style="cursor:pointer">
        <td><span class="font-mono" style="font-size:12.5px">${esc(p.invoice?.invoice_number || `INV-${p.invoice_id}`)}</span></td>
        <td>${esc(p.customer_name || "—")}</td>
        <td>${fmtDatetime(p.paid_at)}</td>
        <td><span class="badge badge-confirmed">${esc(p.method || "—")}</span></td>
        <td class="text-right font-bold" style="color:var(--color-success)">${fmtMoney(p.amount)}</td>
        <td>${esc(p.reference || "—")}</td>
      </tr>`).join("");
    wrap.innerHTML = `
      <div class="table-wrapper">
        <table><thead><tr><th>Invoice</th><th>Customer</th><th>Date</th><th>Method</th><th class="text-right">Amount</th><th>Reference</th></tr></thead>
        <tbody>${rows}</tbody></table>
        <div class="pagination">
          <span class="pagination-info">${data.total} payments</span>
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
