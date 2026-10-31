import datetime
from decimal import Decimal
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Payment, Invoice, User
from backend.app.schemas import PaymentCreate, PaymentResponse, PaginatedResponse
from backend.app.deps import get_current_user, require_roles
from backend.app.services.pricing_service import quantize_money
from backend.app.services.event_bus import event_bus

router = APIRouter(prefix="/payments", tags=["Payments & Ledger"])


@router.get("", response_model=PaginatedResponse[PaymentResponse])
def list_payments(
    invoice_id: Optional[int] = Query(None, description="Filter by invoice ID"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists payments with pagination.
    Role-Scoped: Customers only view payments associated with their own invoices.
    """
    query = db.query(Payment).join(Invoice, Payment.invoice_id == Invoice.id)

    if current_user.role == "customer":
        query = query.filter(Invoice.customer_id == current_user.id)
    if invoice_id:
        query = query.filter(Payment.invoice_id == invoice_id)

    total = query.count()
    items = (
        query.order_by(Payment.payment_date.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    pages = ceil(total / size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def record_payment(
    req: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin: Records a payment against a Confirmed invoice.
    Enforces:
    1. Invoice status must be 'Confirmed'.
    2. Payment amount must be strictly greater than 0.
    3. Payment amount cannot exceed outstanding balance.
    4. Automatically marks invoice as 'Paid' when balance reaches zero.
    """
    inv = db.query(Invoice).filter(Invoice.id == req.invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if inv.status == "Paid":
        raise HTTPException(status_code=400, detail="Invoice is already fully Paid.")
    if inv.status != "Confirmed":
        raise HTTPException(status_code=400, detail=f"Cannot record payment on '{inv.status}' invoice. Invoice must be Confirmed.")

    payment_amt = quantize_money(req.amount)
    if payment_amt <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Payment amount must be greater than 0.")

    balance = quantize_money(inv.total_amount - inv.amount_paid)
    if payment_amt > balance:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount (₹{payment_amt}) exceeds remaining balance of ₹{balance}."
        )

    # 1. Create Payment record
    pay = Payment(
        invoice_id=inv.id,
        method=req.method.strip(),
        amount=payment_amt,
        payment_date=req.payment_date or datetime.datetime.utcnow(),
        note=req.note.strip() if req.note else None
    )
    db.add(pay)

    # 2. Update Invoice Paid Amount
    inv.amount_paid = quantize_money(inv.amount_paid + payment_amt)
    if inv.amount_paid >= inv.total_amount:
        inv.status = "Paid"

    db.commit()
    db.refresh(pay)
    db.refresh(inv)

    # 3. Publish real-time event to SSE clients
    event_bus.publish("payment.recorded", {
        "payment_id": pay.id,
        "invoice_id": inv.id,
        "amount": str(pay.amount),
        "method": pay.method,
        "invoice_status": inv.status
    })

    if inv.status == "Paid":
        event_bus.publish("invoice.paid", {
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number
        })

    return pay
