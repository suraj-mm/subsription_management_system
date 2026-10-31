import { apiFetch, toast, esc, fmtMoney, fmtDate } from "../api.js";
import { getUser, navigate } from "../app.js";

function subBadge(status) {
  const map = { Draft:"badge-draft", Quotation:"badge-quotation", Confirmed:"badge-confirmed", Active:"badge-active", Paused:"badge-paused", Closed:"badge-closed" };
  return `<span class="badge ${map[status] || "badge-draft"}">${esc(status)}</span>`;
}

const STEPS = ["Draft", "Quotation", "Confirmed", "Active", "Paused", "Closed"];

export async function renderSubscriptionDetail({ params }) {
  const id = params?.id;
  if (!id) { navigate("/subscriptions"); return; }

  const content = document.getElementById("page-content");
  content.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;

  let sub;
  try {
    sub = await apiFetch(`/subscriptions/${id}`);
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><p>Not found or access denied.</p></div>`;
    return;
  }

  const user = getUser();
  const isStaff = user?.role === "admin" || user?.role === "staff";
  const plan = sub.plan || {};

  // Stepper
  const displaySteps = ["Draft", "Quotation", "Confirmed", "Active"];
  const stepperHtml = displaySteps.map((s, i) => {
    const isDone = STEPS.indexOf(sub.status) > STEPS.indexOf(s);
    const isCurrent = sub.status === s;
    return `
      <div class="stepper-step ${isDone ? "done" : ""} ${isCurrent ? "current" : ""}">
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <div class="stepper-dot">${isDone ? "✓" : i + 1}</div>
          <div class="stepper-label">${s}</div>
        </div>
        ${i < displaySteps.length - 1 ? '<div class="stepper-connector"></div>' : ""}
      </div>`;
  }).join("");

  // Action buttons
  const actions = [];
  if (isStaff) {
    if (sub.status === "Draft") actions.push(`<button class="btn btn-secondary btn-sm" data-action="quote">Send to Quotation</button>`);
    if (sub.status === "Quotation") actions.push(`<button class="btn btn-secondary btn-sm" data-action="confirm">Confirm</button>`);
    if (sub.status === "Confirmed") actions.push(`<button class="btn btn-primary btn-sm" data-action="activate">Activate</button>`);
  }
  if (sub.status === "Active" && plan.allow_pause) actions.push(`<button class="btn btn-secondary btn-sm" data-action="pause">Pause</button>`);
  if (sub.status === "Paused") actions.push(`<button class="btn btn-primary btn-sm" data-action="resume">Resume</button>`);
  if (sub.status === "Active" && plan.allow_renew) actions.push(`<button class="btn btn-ghost btn-sm" data-action="renew">Renew</button>`);
  if (["Draft","Quotation","Confirmed","Active","Paused"].includes(sub.status)) {
    const canClose = isStaff || (plan.allow_early_close);
    if (canClose) actions.push(`<button class="btn btn-danger btn-sm" data-action="close">Close</button>`);
  }

  // Lines
  const linesHtml = (sub.lines || []).map(l => `
    <tr>
      <td>${esc(l.product?.name || "—")}</td>
      <td>${l.variant ? `${esc(l.variant.attribute)}: ${esc(l.variant.value)}` : "—"}</td>
      <td class="text-right">${l.qty}</td>
      <td class="text-right">${fmtMoney(l.unit_price)}</td>
      <td class="text-right">${l.tax_rate ? `${l.tax_rate}%` : "—"}</td>
      <td class="text-right font-bold">${fmtMoney(l.amount)}</td>
    </tr>`).join("") || `<tr><td colspan="6" class="text-center text-muted">No line items</td></tr>`;

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1 style="font-size:18px">${esc(sub.subscription_number)}</h1>
        <p>Subscription Detail</p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        ${subBadge(sub.status)}
        <a class="btn btn-secondary btn-sm" href="#/subscriptions">← Back</a>
      </div>
    </div>

    <!-- Status Stepper -->
    <div class="card mb-4" style="margin-bottom:20px">
      <div class="card-body">
        <div class="stepper">${stepperHtml}</div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px">
          ${actions.join("")}
        </div>
        ${sub.status === "Paused" ? `<div class="alert alert-warning mt-3">Subscription is paused. Billing is suspended. Resume to continue.</div>` : ""}
        ${sub.status === "Closed" ? `<div class="alert alert-info mt-3">Subscription is closed.</div>` : ""}
        ${sub.quotation_valid_until && sub.status === "Quotation" ? `<div class="alert alert-warning mt-3">Quotation valid until ${fmtDate(sub.quotation_valid_until)}</div>` : ""}
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
      <!-- Details -->
      <div class="card">
        <div class="card-header"><span class="card-title">Subscription Info</span></div>
        <div class="card-body">
          <div class="detail-grid">
            <div class="detail-field"><label>Customer</label><span>${esc(sub.customer?.name || "—")}</span></div>
            <div class="detail-field"><label>Email</label><span>${esc(sub.customer?.email || "—")}</span></div>
            <div class="detail-field"><label>Plan</label><span>${esc(plan.name || "—")}</span></div>
            <div class="detail-field"><label>Billing Period</label><span>${esc(plan.billing_period || "—")}</span></div>
            <div class="detail-field"><label>Start Date</label><span>${fmtDate(sub.start_date)}</span></div>
            <div class="detail-field"><label>Expiry Date</label><span>${fmtDate(sub.expiry_date)}</span></div>
            <div class="detail-field"><label>Payment Terms</label><span>${esc(sub.payment_terms || "—")}</span></div>
            <div class="detail-field"><label>Next Invoice</label><span>${fmtDate(sub.next_invoice_date)}</span></div>
          </div>
        </div>
      </div>

      <!-- Totals -->
      <div class="card">
        <div class="card-header"><span class="card-title">Financial Summary</span></div>
        <div class="card-body">
          <div class="detail-grid">
            <div class="detail-field"><label>Subtotal</label><span>${fmtMoney(sub.subtotal)}</span></div>
            <div class="detail-field"><label>Tax Amount</label><span>${fmtMoney(sub.tax_amount)}</span></div>
            <div class="detail-field" style="grid-column:span 2"><label>Total Amount</label><span style="font-size:20px;font-weight:800;color:var(--color-primary)">${fmtMoney(sub.total_amount)}</span></div>
          </div>
          ${sub.discount ? `<div class="alert alert-success mt-3">Discount applied: <strong>${esc(sub.discount.name)}</strong></div>` : ""}
        </div>
      </div>
    </div>

    <!-- Lines Table -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header"><span class="card-title">Line Items</span></div>
      <div class="table-wrapper" style="border:none;border-radius:0 0 12px 12px">
        <table><thead><tr><th>Product</th><th>Variant</th><th class="text-right">Qty</th><th class="text-right">Unit Price</th><th class="text-right">Tax</th><th class="text-right">Amount</th></tr></thead>
        <tbody>${linesHtml}</tbody>
        <tfoot>
          <tr style="background:var(--color-bg)">
            <td colspan="5" class="text-right" style="font-weight:700;padding:12px 16px">Total</td>
            <td class="text-right font-bold" style="padding:12px 16px;font-size:15px">${fmtMoney(sub.total_amount)}</td>
          </tr>
        </tfoot>
        </table>
      </div>
    </div>

    <!-- Invoices for this subscription -->
    <div class="card">
      <div class="card-header">
        <span class="card-title">Invoices</span>
        <a class="btn btn-sm btn-secondary" href="#/invoices?subscription_id=${sub.id}">View all</a>
      </div>
      <div id="sub-invoices-wrap">
        <div class="loading-overlay"><div class="spinner"></div></div>
      </div>
    </div>
  `;

  // Attach action handlers
  content.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.action;
      btn.disabled = true;
      try {
        const endpoints = {
          quote: `/subscriptions/${id}/quote`,
          confirm: `/subscriptions/${id}/confirm`,
          activate: `/subscriptions/${id}/activate`,
          pause: `/subscriptions/${id}/pause`,
          resume: `/subscriptions/${id}/resume`,
          renew: `/subscriptions/${id}/renew`,
          close: `/subscriptions/${id}/close`,
        };
        await apiFetch(endpoints[action], { method: "POST" });
        toast(`Status updated`, "success");
        await renderSubscriptionDetail({ params });
      } catch (e) {
        toast(e.message, "error");
        btn.disabled = false;
      }
    });
  });

  // Load related invoices
  try {
    const invData = await apiFetch(`/invoices?subscription_id=${id}&page=1&size=10`);
    const invWrap = document.getElementById("sub-invoices-wrap");
    if (!invData.items.length) {
      invWrap.innerHTML = `<div class="empty-state" style="padding:24px"><p>No invoices generated yet.</p></div>`;
    } else {
      const rows = invData.items.map(inv => {
        const isOverdue = inv.status === "Confirmed" && inv.due_date && new Date(inv.due_date) < new Date();
        const badge = isOverdue
          ? `<span class="badge badge-overdue">Overdue</span>`
          : `<span class="badge badge-${inv.status === "Paid" ? "paid" : inv.status === "Confirmed" ? "confirmed-inv" : inv.status === "Cancelled" ? "cancelled" : "draft"}">${esc(inv.status)}</span>`;
        return `<tr onclick="window.location.hash='#/invoices/${inv.id}'" style="cursor:pointer">
          <td><span class="font-mono" style="font-size:12.5px">${esc(inv.invoice_number)}</span></td>
          <td>${badge}</td>
          <td>${fmtDate(inv.due_date)}</td>
          <td class="text-right font-bold">${fmtMoney(inv.total_amount)}</td>
          <td class="text-right" style="color:var(--color-danger)">${fmtMoney(inv.outstanding_balance)}</td>
        </tr>`;
      }).join("");
      invWrap.innerHTML = `<div class="table-wrapper" style="border:none;border-radius:0 0 12px 12px"><table>
        <thead><tr><th>Invoice</th><th>Status</th><th>Due</th><th class="text-right">Total</th><th class="text-right">Outstanding</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
    }
  } catch {}
}
