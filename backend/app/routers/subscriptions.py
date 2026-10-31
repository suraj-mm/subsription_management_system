import datetime
from math import ceil
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.models import (
    Subscription, SubscriptionLine, Product, ProductVariant,
    Plan, QuotationTemplate, User
)
from backend.app.schemas import (
    SubscriptionCreate, SubscriptionFromTemplateRequest, SubscriptionUpdate,
    SubscriptionResponse, SubscriptionLineResponse, PaginatedResponse
)
from backend.app.deps import get_current_user, require_roles
from backend.app.routers.plans import is_plan_available
from backend.app.services.pricing_service import (
    calculate_unit_price, calculate_line_amounts, format_sequence_number, quantize_money
)
from backend.app.services.subscription_service import (
    transition_subscription, renew_subscription, compute_subscription_totals,
    add_billing_period
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions Management"])


def serialize_subscription(sub: Subscription) -> SubscriptionResponse:
    """Computes real-time totals and formats the subscription response."""
    totals = compute_subscription_totals(sub)
    resp = SubscriptionResponse.model_validate(sub)
    resp.subtotal = totals["subtotal"]
    resp.tax_amount = totals["tax_amount"]
    resp.total_amount = totals["total_amount"]
    return resp


@router.get("", response_model=PaginatedResponse[SubscriptionResponse])
def list_subscriptions(
    status: Optional[str] = Query(None, description="Draft, Quotation, Confirmed, Active, Paused, Closed"),
    customer_id: Optional[int] = Query(None, description="Filter by customer (Staff/Admin only)"),
    search: Optional[str] = Query(None, description="Search subscription number"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists subscriptions with pagination and status filters.
    Strict Role-Scoping:
    - Customer role CAN ONLY SEE THEIR OWN subscriptions.
    - Staff/Admin can view all or filter by customer_id.
    """
    query = db.query(Subscription)

    if current_user.role == "customer":
        query = query.filter(Subscription.customer_id == current_user.id)
    elif customer_id:
        query = query.filter(Subscription.customer_id == customer_id)

    if status:
        query = query.filter(Subscription.status == status)
    if search:
        query = query.filter(Subscription.subscription_number.ilike(f"%{search.strip()}%"))

    total = query.count()
    subs = (
        query.order_by(Subscription.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    pages = ceil(total / size) if total > 0 else 1

    items = [serialize_subscription(s) for s in subs]
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    req: SubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin: Creates a new subscription in 'Draft' status.
    Snapshots product pricing and tax rates into line items.
    Validates minimum quantity against the selected plan.
    """
    customer = db.query(User).filter(User.id == req.customer_id).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Customer not found")

    plan = db.query(Plan).filter(Plan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=400, detail="Plan not found")

    today = datetime.date.today()
    if not is_plan_available(plan, today):
        raise HTTPException(status_code=400, detail="Plan is not currently available for subscriptions")

    if not req.lines:
        raise HTTPException(status_code=400, detail="Subscription must contain at least one line item")

    # Validate min_quantity across lines
    total_qty = sum(line.qty for line in req.lines)
    if total_qty < plan.min_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Total quantity ({total_qty}) does not meet the plan's minimum requirement of {plan.min_quantity}"
        )

    # Expiry defaults to 12 months after start_date if not provided
    expiry = req.expiry_date
    if not expiry:
        expiry = req.start_date + datetime.timedelta(days=365)

    sub = Subscription(
        subscription_number="TEMP",
        customer_id=req.customer_id,
        plan_id=req.plan_id,
        start_date=req.start_date,
        expiry_date=expiry,
        payment_terms=req.payment_terms,
        discount_id=req.discount_id,
        status="Draft"
    )
    db.add(sub)
    db.flush()

    sub.subscription_number = format_sequence_number("SUB", sub.id)

    # Snapshot lines
    for line in req.lines:
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if not product or not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product {line.product_id} is inactive or not found")

        variant = None
        if line.variant_id:
            variant = db.query(ProductVariant).filter(
                ProductVariant.id == line.variant_id,
                ProductVariant.product_id == line.product_id
            ).first()
            if not variant:
                raise HTTPException(status_code=400, detail=f"Variant {line.variant_id} does not belong to product {line.product_id}")

        unit_price = calculate_unit_price(product, variant)
        subtotal, tax_rate, tax_amount, total = calculate_line_amounts(line.qty, unit_price, product.tax)

        sub_line = SubscriptionLine(
            subscription_id=sub.id,
            product_id=line.product_id,
            variant_id=line.variant_id,
            qty=line.qty,
            unit_price=unit_price,
            tax_rate=tax_rate,
            amount=total
        )
        db.add(sub_line)

    db.commit()
    db.refresh(sub)
    return serialize_subscription(sub)


@router.post("/from-template/{template_id}", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription_from_template(
    template_id: int,
    req: SubscriptionFromTemplateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin: Copies quotation template lines into a new subscription.
    Sets status = 'Quotation' and quotation_valid_until = today + validity_days.
    Snapshots current pricing.
    """
    template = db.query(QuotationTemplate).filter(QuotationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Quotation template not found")

    if not template.plan_id:
        raise HTTPException(status_code=400, detail="Quotation template has no assigned plan")

    plan = template.plan
    today = datetime.date.today()
    if not is_plan_available(plan, today):
        raise HTTPException(status_code=400, detail="Plan assigned to template is currently unavailable")

    customer = db.query(User).filter(User.id == req.customer_id).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Customer not found")

    start = req.start_date or today
    expiry = start + datetime.timedelta(days=365)
    valid_until = today + datetime.timedelta(days=template.validity_days)

    sub = Subscription(
        subscription_number="TEMP",
        customer_id=req.customer_id,
        plan_id=template.plan_id,
        template_id=template.id,
        start_date=start,
        expiry_date=expiry,
        payment_terms=req.payment_terms,
        discount_id=req.discount_id,
        status="Quotation",
        quotation_valid_until=valid_until
    )
    db.add(sub)
    db.flush()

    sub.subscription_number = format_sequence_number("SUB", sub.id)

    # Snapshot lines from template
    for t_line in template.lines:
        product = db.query(Product).filter(Product.id == t_line.product_id).first()
        variant = db.query(ProductVariant).filter(ProductVariant.id == t_line.variant_id).first() if t_line.variant_id else None

        unit_price = calculate_unit_price(product, variant)
        subtotal, tax_rate, tax_amount, total = calculate_line_amounts(t_line.quantity, unit_price, product.tax)

        sub_line = SubscriptionLine(
            subscription_id=sub.id,
            product_id=t_line.product_id,
            variant_id=t_line.variant_id,
            qty=t_line.quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
            amount=total
        )
        db.add(sub_line)

    db.commit()
    db.refresh(sub)
    return serialize_subscription(sub)


@router.get("/{id}", response_model=SubscriptionResponse)
def get_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches full subscription details with computed financial breakdown.
    A customer requesting another user's subscription receives a 404.
    """
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == "customer" and sub.customer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return serialize_subscription(sub)


# --- Lifecycle Status Actions ---

@router.post("/{id}/confirm", response_model=SubscriptionResponse)
def confirm_subscription(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin only: Transitions subscription from 'Quotation' to 'Confirmed'.
    Blocks transition if quotation_valid_until has passed.
    """
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updated = transition_subscription(sub, "Confirmed", db, user)
    return serialize_subscription(updated)


@router.post("/{id}/activate", response_model=SubscriptionResponse)
def activate_subscription(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin only: Transitions subscription from 'Confirmed' to 'Active'.
    Sets next_invoice_date = start_date for Billing Engine handoff.
    """
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updated = transition_subscription(sub, "Active", db, user)
    return serialize_subscription(updated)


@router.post("/{id}/pause", response_model=SubscriptionResponse)
def pause_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Pauses an active subscription.
    Allowed by Staff/Admin OR owning customer if plan.allow_pause is True.
    """
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == "customer" and sub.customer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updated = transition_subscription(sub, "Paused", db, current_user)
    return serialize_subscription(updated)


@router.post("/{id}/resume", response_model=SubscriptionResponse)
def resume_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resumes a paused subscription back to Active.
    Adjusts next_invoice_date forward to prevent retroactive back-billing.
    """
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == "customer" and sub.customer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updated = transition_subscription(sub, "Active", db, current_user)
    return serialize_subscription(updated)


@router.post("/{id}/close", response_model=SubscriptionResponse)
def close_subscription(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Closes a subscription.
    Enforces plan.allow_early_close if closed prior to expiry_date.
    """
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == "customer" and sub.customer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updated = transition_subscription(sub, "Closed", db, current_user)
    return serialize_subscription(updated)


@router.post("/{id}/renew", response_model=SubscriptionResponse)
def renew_subscription_endpoint(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extends subscription expiry date by one billing cycle.
    Enforces plan.allow_renew.
    """
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == "customer" and sub.customer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updated = renew_subscription(sub, db, current_user)
    return serialize_subscription(updated)
