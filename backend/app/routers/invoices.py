import datetime
import logging
from math import ceil
from typing import Optional, List
from decimal import Decimal

logger = logging.getLogger("brightloop.invoices")
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.models import Invoice, InvoiceLine, User, Payment
from backend.app.schemas import (
    InvoiceResponse, InvoiceLineResponse, InvoiceGenerateRequest,
    InvoiceBulkConfirmRequest, PaginatedResponse
)
from backend.app.deps import get_current_user, require_roles
from backend.app.services.invoice_service import run_billing
from backend.app.services.event_bus import event_bus
from backend.app.routers.auth import send_reset_email  # reuse email infrastructure

router = APIRouter(prefix="/invoices", tags=["Invoices & Billing"])


def serialize_invoice(inv: Invoice) -> InvoiceResponse:
    """Calculates outstanding balance and formats InvoiceResponse."""
    resp = InvoiceResponse.model_validate(inv)
    resp.outstanding_balance = max(Decimal("0.00"), inv.total_amount - inv.amount_paid)
    return resp


@router.get("", response_model=PaginatedResponse[InvoiceResponse])
def list_invoices(
    status: Optional[str] = Query(None, description="Draft, Confirmed, Paid, Cancelled"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    subscription_id: Optional[int] = Query(None, description="Filter by subscription ID"),
    overdue_only: bool = Query(False, description="Filter invoices that are overdue"),
    search: Optional[str] = Query(None, description="Search by invoice number"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists invoices with search, pagination, and status filters.
    Role-Scoped: Customers ONLY ever see their own invoices.
    """
    query = db.query(Invoice)

    if current_user.role == "customer":
        query = query.filter(Invoice.customer_id == current_user.id)
    elif customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    if subscription_id:
        query = query.filter(Invoice.subscription_id == subscription_id)

    if status:
        query = query.filter(Invoice.status == status)

    today = datetime.date.today()
    if overdue_only:
        query = query.filter(
            Invoice.status == "Confirmed",
            Invoice.due_date < today,
            Invoice.amount_paid < Invoice.total_amount
        )

    if search:
        query = query.filter(Invoice.invoice_number.ilike(f"%{search.strip()}%"))

    total = query.count()
    invs = (
        query.order_by(Invoice.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    pages = ceil(total / size) if total > 0 else 1

    items = [serialize_invoice(inv) for inv in invs]
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("/generate", response_model=List[InvoiceResponse])
def trigger_billing_run(
    req: InvoiceGenerateRequest = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin: Manually triggers the billing engine cycle.
    Generates invoices for all active due subscriptions without double-billing.
    """
    billing_date = req.billing_date if req and req.billing_date else datetime.date.today()
    auto_confirm = req.auto_confirm if req else False

    invoices = run_billing(db, today=billing_date, auto_confirm=auto_confirm)
    return [serialize_invoice(inv) for inv in invoices]


@router.post("/confirm-bulk")
def confirm_bulk_invoices(
    req: InvoiceBulkConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """Staff/Admin: Bulk confirms draft invoices for billing day."""
    invoices = db.query(Invoice).filter(
        Invoice.id.in_(req.invoice_ids),
        Invoice.status == "Draft"
    ).all()

    for inv in invoices:
        inv.status = "Confirmed"
        event_bus.publish("invoice.confirmed", {
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "total_amount": str(inv.total_amount)
        })

    db.commit()
    return {"message": f"Successfully confirmed {len(invoices)} invoice(s)"}


@router.get("/{id}", response_model=InvoiceResponse)
def get_invoice(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches invoice details including line items and outstanding balance.
    Customers receive 404 if attempting to view another customer's invoice.
    """
    inv = db.query(Invoice).filter(Invoice.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if current_user.role == "customer" and inv.customer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return serialize_invoice(inv)


@router.post("/{id}/confirm", response_model=InvoiceResponse)
def confirm_invoice(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """Staff/Admin: Transitions invoice from 'Draft' to 'Confirmed'."""
    inv = db.query(Invoice).filter(Invoice.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if inv.status != "Draft":
        raise HTTPException(status_code=400, detail=f"Cannot confirm invoice in '{inv.status}' status. Must be Draft.")

    inv.status = "Confirmed"
    db.commit()
    db.refresh(inv)

    event_bus.publish("invoice.confirmed", {
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "total_amount": str(inv.total_amount)
    })

    return serialize_invoice(inv)


@router.post("/{id}/cancel", response_model=InvoiceResponse)
def cancel_invoice(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin: Cancels an invoice.
    Allowed only from Draft or Confirmed, and only if no payments have been recorded.
    Paid is terminal and cannot be cancelled.
    """
    inv = db.query(Invoice).filter(Invoice.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if inv.status == "Paid":
        raise HTTPException(status_code=400, detail="Cannot cancel a fully Paid invoice.")

    if inv.amount_paid > Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Cannot cancel an invoice with recorded payments.")

    inv.status = "Cancelled"
    db.commit()
    db.refresh(inv)

    event_bus.publish("invoice.cancelled", {
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number
    })

    return serialize_invoice(inv)


@router.post("/{id}/send")
def send_invoice(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin: Dispatches invoice to the customer email with fallback simulation.
    Updates sent_at timestamp.
    """
    inv = db.query(Invoice).filter(Invoice.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    inv.sent_at = datetime.datetime.utcnow()
    db.commit()

    # Log/Print simulation
    logger.info("Invoice %s dispatched to %s (Total: INR %s)", inv.invoice_number, inv.customer.email, inv.total_amount)

    return {
        "message": f"Invoice {inv.invoice_number} sent to {inv.customer.email}",
        "sent_at": inv.sent_at
    }


@router.get("/{id}/print", response_class=HTMLResponse)
def print_invoice(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Renders a print-friendly, cleanly formatted HTML invoice.
    Available to staff/admin or the owning customer.
    """
    inv = db.query(Invoice).filter(Invoice.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if current_user.role == "customer" and inv.customer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    lines_html = ""
    for idx, l in enumerate(inv.lines):
        product_name = l.product.name if l.product else f"Item #{l.product_id}"
        lines_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">{idx + 1}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;"><strong>{product_name}</strong></td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: center;">{l.qty}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: right;">₹{l.price:,.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: right; color: #dc2626;">-₹{l.discount_amount:,.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: right;">{l.tax_rate}%</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: right; font-weight: bold;">₹{l.amount:,.2f}</td>
        </tr>
        """

    balance = max(Decimal("0.00"), inv.total_amount - inv.amount_paid)
    status_color = "#16a34a" if inv.status == "Paid" else ("#f59e0b" if inv.status == "Confirmed" else "#64748b")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Invoice {inv.invoice_number} - Brightloop</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 40px; color: #1e293b; background: #fff; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0d9488; padding-bottom: 20px; }}
            .brand {{ font-size: 26px; font-weight: 800; color: #0d9488; }}
            .badge {{ display: inline-block; padding: 6px 14px; border-radius: 9999px; color: #fff; font-size: 13px; font-weight: bold; background: {status_color}; }}
            .meta-grid {{ display: flex; justify-content: space-between; margin-top: 30px; margin-bottom: 30px; }}
            .meta-col {{ width: 48%; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ background: #f8fafc; padding: 12px 10px; text-align: left; font-size: 13px; border-bottom: 2px solid #cbd5e1; }}
            .totals-box {{ width: 320px; margin-left: auto; margin-top: 25px; }}
            .total-row {{ display: flex; justify-content: space-between; padding: 6px 0; }}
            .grand-total {{ border-top: 2px solid #0d9488; margin-top: 8px; padding-top: 8px; font-size: 18px; font-weight: bold; color: #0d9488; }}
            .actions {{ margin-bottom: 20px; }}
            .btn-print {{ background: #0d9488; color: #fff; border: none; padding: 10px 20px; font-size: 14px; font-weight: bold; border-radius: 6px; cursor: pointer; }}
            @media print {{ .no-print {{ display: none; }} body {{ padding: 0; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="actions no-print">
                <button class="btn-print" onclick="window.print()">🖨️ Print Invoice</button>
            </div>
            <div class="header">
                <div>
                    <div class="brand">Brightloop Technologies</div>
                    <div style="color: #64748b; font-size: 13px;">Enterprise Subscription & Billing Management</div>
                </div>
                <div style="text-align: right;">
                    <div class="badge">{inv.status.upper()}</div>
                    <div style="font-size: 18px; font-weight: bold; margin-top: 8px;">{inv.invoice_number}</div>
                </div>
            </div>

            <div class="meta-grid">
                <div class="meta-col">
                    <div style="font-size: 12px; font-weight: bold; color: #64748b; text-transform: uppercase;">Billed To:</div>
                    <div style="font-size: 16px; font-weight: bold; margin-top: 4px;">{inv.customer.name}</div>
                    <div>{inv.customer.company or ''}</div>
                    <div style="color: #64748b;">{inv.customer.email}</div>
                    <div style="color: #64748b;">{inv.customer.address or ''}</div>
                    <div>Tax ID: {inv.customer.tax_id or 'N/A'}</div>
                </div>
                <div class="meta-col" style="text-align: right;">
                    <div><strong>Issue Date:</strong> {inv.issue_date}</div>
                    <div><strong>Due Date:</strong> {inv.due_date}</div>
                    <div><strong>Period:</strong> {inv.period_start or 'N/A'} to {inv.period_end or 'N/A'}</div>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th style="width: 40px;">#</th>
                        <th>Description</th>
                        <th style="text-align: center; width: 60px;">Qty</th>
                        <th style="text-align: right; width: 100px;">Price</th>
                        <th style="text-align: right; width: 90px;">Discount</th>
                        <th style="text-align: right; width: 70px;">Tax</th>
                        <th style="text-align: right; width: 110px;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {lines_html}
                </tbody>
            </table>

            <div class="totals-box">
                <div class="total-row"><span>Subtotal:</span><span>₹{inv.subtotal:,.2f}</span></div>
                <div class="total-row" style="color: #dc2626;"><span>Discounts:</span><span>-₹{inv.discount_amount:,.2f}</span></div>
                <div class="total-row"><span>Taxes:</span><span>+₹{inv.tax_amount:,.2f}</span></div>
                <div class="total-row grand-total"><span>Total Amount:</span><span>₹{inv.total_amount:,.2f}</span></div>
                <div class="total-row" style="color: #16a34a; font-weight: bold;"><span>Amount Paid:</span><span>₹{inv.amount_paid:,.2f}</span></div>
                <div class="total-row" style="font-size: 16px; font-weight: bold; color: #dc2626; border-top: 1px dashed #cbd5e1; margin-top: 4px; padding-top: 4px;">
                    <span>Balance Due:</span><span>₹{balance:,.2f}</span>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
