import { apiFetch, toast, esc, fmtMoney, fmtDate, fmtDatetime } from "../api.js";
import { getUser, navigate } from "../app.js";
import { openModal, closeModal } from "../api.js";

function invBadge(inv) {
  const isOverdue = inv.status === "Confirmed" && inv.due_date && new Date(inv.due_date) < new Date();
  if (isOverdue) return `<span class="badge badge-overdue">Overdue</span>`;
  const map = { Draft:"badge-draft", Confirmed:"badge-confirmed-inv", Paid:"badge-paid", Cancelled:"badge-cancelled" };
  return `<span class="badge ${map[inv.status] || "badge-draft"}">${esc(inv.status)}</span>`;
}

export async function renderInvoiceDetail({ params }) {
  const id = params?.id;
  if (!id) { navigate("/invoices"); return; }

  const content = document.getElementById("page-content");
  content.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;

  let inv;
  try {
    inv = await apiFetch(`/invoices/${id}`);
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><p>Invoice not found or access denied.</p></div>`;
    return;
  }

  const user = getUser();
  const isAdmin = user?.role === "admin";
  const isStaff = user?.role === "staff";

  const outstanding = Number(inv.outstanding_balance ?? 0);
  const canConfirm = (isAdmin || isStaff) && inv.status === "Draft";
  const canCancel = (isAdmin || isStaff) && ["Draft","Confirmed"].includes(inv.status);
  const canPay = outstanding > 0 && inv.status === "Confirmed";
  const canSend = (isAdmin || isStaff) && inv.status === "Confirmed";
  const canPrint = true;

  // Line items
  const lineRows = (inv.lines || []).map(l => `
    <tr>
      <td>${esc(l.product_name || l.description || "—")}</td>
      <td class="text-right">${l.qty}</td>
      <td class="text-right">${fmtMoney(l.unit_price)}</td>
      <td class="text-right">${l.tax_rate ? `${l.tax_rate}%` : "—"}</td>
      <td class="text-right">${l.discount_amount > 0 ? `-${fmtMoney(l.discount_amount)}` : "—"}</td>
      <td class="text-right font-bold">${fmtMoney(l.total)}</td>
    </tr>`).join("") || `<tr><td colspan="6" class="text-center text-muted">No line items</td></tr>`;

  // Payments
  const paymentRows = (inv.payments || []).map(p => `
    <tr>
      <td>${fmtDatetime(p.paid_at)}</td>
      <td>${esc(p.method || "—")}</td>
      <td class="text-right font-bold" style="color:var(--color-success)">${fmtMoney(p.amount)}</td>
      <td>${esc(p.reference || "—")}</td>
    </tr>`).join("") || `<tr><td colspan="4" class="text-center text-muted" style="padding:16px">No payments recorded</td></tr>`;

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1 style="font-size:18px">${esc(inv.invoice_number)}</h1>
        <p>Invoice Detail</p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        ${invBadge(inv)}
        ${canConfirm ? `<button class="btn btn-primary btn-sm" id="confirm-btn">Confirm</button>` : ""}
        ${canSend ? `<button class="btn btn-secondary btn-sm" id="send-btn">Send to Customer</button>` : ""}
        ${canPay ? `<button class="btn btn-primary btn-sm" id="pay-btn">Record Payment</button>` : ""}
        ${canCancel ? `<button class="btn btn-danger btn-sm" id="cancel-btn">Cancel</button>` : ""}
        ${canPrint ? `<button class="btn btn-ghost btn-sm" id="print-btn">🖨 Print</button>` : ""}
        <a class="btn btn-secondary btn-sm" href="#/invoices">← Back</a>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
      <div class="card">
        <div class="card-header"><span class="card-title">Invoice Info</span></div>
        <div class="card-body">
          <div class="detail-grid">
            <div class="detail-field"><label>Customer</label><span>${esc(inv.customer_name || "—")}</span></div>
            <div class="detail-field"><label>Subscription</label><span>${esc(inv.subscription?.subscription_number || "—")}</span></div>
            <div class="detail-field"><label>Issue Date</label><span>${fmtDate(inv.created_at)}</span></div>
            <div class="detail-field"><label>Due Date</label><span style="${inv.status==="Confirmed"&&inv.due_date&&new Date(inv.due_date)<new Date()?"color:var(--color-danger);font-weight:700":""}"> ${fmtDate(inv.due_date)}</span></div>
            <div class="detail-field"><label>Period</label><span>${fmtDate(inv.period_start)} → ${fmtDate(inv.period_end)}</span></div>
            <div class="detail-field"><label>Sent At</label><span>${inv.sent_at ? fmtDatetime(inv.sent_at) : "Not sent"}</span></div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Amount Summary</span></div>
        <div class="card-body">
          <div class="detail-grid">
            <div class="detail-field"><label>Subtotal</label><span>${fmtMoney(inv.subtotal)}</span></div>
            <div class="detail-field"><label>Tax</label><span>${fmtMoney(inv.tax_amount)}</span></div>
            <div class="detail-field"><label>Discount</label><span>${fmtMoney(inv.discount_amount)}</span></div>
            <div class="detail-field"><label>Total</label><span style="font-size:18px;font-weight:800;color:var(--color-primary)">${fmtMoney(inv.total_amount)}</span></div>
            <div class="detail-field"><label>Amount Paid</label><span style="color:var(--color-success);font-weight:700">${fmtMoney(inv.amount_paid)}</span></div>
            <div class="detail-field"><label>Outstanding</label><span style="color:${outstanding>0?"var(--color-danger)":"var(--color-success)"};font-weight:700">${fmtMoney(outstanding)}</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Lines -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><span class="card-title">Line Items</span></div>
      <div class="table-wrapper" style="border:none;border-radius:0 0 12px 12px">
        <table><thead><tr><th>Description</th><th class="text-right">Qty</th><th class="text-right">Unit Price</th><th class="text-right">Tax</th><th class="text-right">Discount</th><th class="text-right">Total</th></tr></thead>
        <tbody>${lineRows}</tbody></table>
      </div>
    </div>

    <!-- Payments -->
    <div class="card">
      <div class="card-header"><span class="card-title">Payment History</span></div>
      <div class="table-wrapper" style="border:none;border-radius:0 0 12px 12px">
        <table><thead><tr><th>Date</th><th>Method</th><th class="text-right">Amount</th><th>Reference</th></tr></thead>
        <tbody>${paymentRows}</tbody></table>
      </div>
    </div>

    <!-- Payment Modal -->
    <div class="modal-backdrop" id="payment-modal">
      <div class="modal" style="max-width:420px">
        <div class="modal-header">
          <span class="modal-title">Record Payment</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('payment-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="alert alert-info mb-3">Outstanding balance: <strong>${fmtMoney(outstanding)}</strong></div>
          <form id="payment-form" novalidate>
            <div class="form-group">
              <label class="form-label">Amount <span class="required">*</span></label>
              <input class="form-control" type="number" step="0.01" min="0.01" max="${outstanding}" id="pay-amount" value="${outstanding}" />
              <p class="form-error" id="pay-amount-err"></p>
            </div>
            <div class="form-group">
              <label class="form-label">Payment Method <span class="required">*</span></label>
              <select class="form-control" id="pay-method">
                <option value="bank_transfer">Bank Transfer</option>
                <option value="cash">Cash</option>
                <option value="card">Card</option>
                <option value="upi">UPI</option>
                <option value="cheque">Cheque</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Reference / Transaction ID</label>
              <input class="form-control" type="text" id="pay-ref" placeholder="Optional" />
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('payment-modal'))">Cancel</button>
          <button class="btn btn-primary" id="confirm-payment-btn"><span class="btn-text">Record Payment</span></button>
        </div>
      </div>
    </div>
  `;

  // Button handlers
  document.getElementById("confirm-btn")?.addEventListener("click", async () => {
    try {
      await apiFetch(`/invoices/${id}/confirm`, { method: "POST" });
      toast("Invoice confirmed", "success");
      await renderInvoiceDetail({ params });
    } catch (e) { toast(e.message, "error"); }
  });

  document.getElementById("cancel-btn")?.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to cancel this invoice?")) return;
    try {
      await apiFetch(`/invoices/${id}/cancel`, { method: "POST" });
      toast("Invoice cancelled", "success");
      await renderInvoiceDetail({ params });
    } catch (e) { toast(e.message, "error"); }
  });

  document.getElementById("send-btn")?.addEventListener("click", async () => {
    try {
      await apiFetch(`/invoices/${id}/send`, { method: "POST" });
      toast("Invoice sent to customer", "success");
      await renderInvoiceDetail({ params });
    } catch (e) { toast(e.message, "error"); }
  });

  document.getElementById("print-btn")?.addEventListener("click", async () => {
    try {
      const html = await apiFetch(`/invoices/${id}/print`);
      const w = window.open("", "_blank");
      w.document.write(html);
      w.document.close();
      w.print();
    } catch (e) { toast(e.message, "error"); }
  });

  document.getElementById("pay-btn")?.addEventListener("click", () => openModal("payment-modal"));

  document.getElementById("confirm-payment-btn")?.addEventListener("click", async () => {
    const btn = document.getElementById("confirm-payment-btn");
    const amount = parseFloat(document.getElementById("pay-amount").value);
    const amountErr = document.getElementById("pay-amount-err");
    amountErr.classList.remove("visible");

    if (!amount || amount <= 0) { amountErr.textContent = "Amount must be > 0"; amountErr.classList.add("visible"); return; }
    if (amount > outstanding) { amountErr.textContent = `Cannot exceed outstanding (${fmtMoney(outstanding)})`; amountErr.classList.add("visible"); return; }

    btn.disabled = true;
    try {
      await apiFetch("/payments", {
        method: "POST",
        body: {
          invoice_id: parseInt(id),
          amount,
          method: document.getElementById("pay-method").value,
          reference: document.getElementById("pay-ref").value.trim() || null,
        }
      });
      toast("Payment recorded", "success");
      closeModal("payment-modal");
      await renderInvoiceDetail({ params });
    } catch (e) { toast(e.message, "error"); }
    finally { btn.disabled = false; }
  });
}
