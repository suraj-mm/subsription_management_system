import datetime
from decimal import Decimal
from typing import Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models import Subscription, Plan, User
from backend.app.services.pricing_service import quantize_money
from backend.app.services.event_bus import event_bus

# Official State Machine Transition Matrix
ALLOWED_TRANSITIONS = {
    "Draft": {"Quotation"},
    "Quotation": {"Confirmed", "Draft"},
    "Confirmed": {"Active"},
    "Active": {"Paused", "Closed"},
    "Paused": {"Active", "Closed"},
    "Closed": set(),
}


def compute_subscription_totals(sub: Subscription) -> Dict[str, Decimal]:
    """
    Computes total subtotal, tax amount, and grand total from the subscription's lines.
    """
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")

    for line in sub.lines:
        line_subtotal = quantize_money(line.unit_price * line.qty)
        subtotal += line_subtotal
        tax_amount = quantize_money(line_subtotal * (line.tax_rate / Decimal("100.00")))
        tax_total += tax_amount

    total_amount = quantize_money(subtotal + tax_total)
    return {
        "subtotal": quantize_money(subtotal),
        "tax_amount": quantize_money(tax_total),
        "total_amount": total_amount
    }


def add_billing_period(base_date: datetime.date, period: str) -> datetime.date:
    """Calculates next date increment based on billing frequency."""
    p = period.lower()
    if p == "daily":
        return base_date + datetime.timedelta(days=1)
    elif p == "weekly":
        return base_date + datetime.timedelta(weeks=1)
    elif p == "monthly":
        # Approximate 30 days or next month
        return base_date + datetime.timedelta(days=30)
    elif p == "yearly":
        return base_date + datetime.timedelta(days=365)
    return base_date + datetime.timedelta(days=30)


def transition_subscription(
    sub: Subscription,
    target_status: str,
    db: Session,
    user: User,
    today: datetime.date = None
) -> Subscription:
    """
    Validates and executes a subscription lifecycle transition.
    Enforces the ALLOWED state machine and plan-level capability flags.
    """
    if today is None:
        today = datetime.date.today()

    current_status = sub.status
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition from '{current_status}' to '{target_status}'. Allowed transitions: {list(allowed)}"
        )

    plan = sub.plan
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is missing associated plan configuration"
        )

    # 1. Quotation -> Confirmed: Validate quote expiration
    if current_status == "Quotation" and target_status == "Confirmed":
        if sub.quotation_valid_until and today > sub.quotation_valid_until:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quotation has expired on {sub.quotation_valid_until}. Confirmation blocked."
            )

    # 2. Confirmed -> Active: Hand-off to Billing Engine
    elif current_status == "Confirmed" and target_status == "Active":
        # Hand-off to billing: set next_invoice_date = start_date
        sub.next_invoice_date = sub.start_date

    # 3. Active -> Paused: Enforce plan flag
    elif current_status == "Active" and target_status == "Paused":
        if not plan.allow_pause:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This subscription plan does not allow pausing."
            )

    # 4. Paused -> Active (Resume): Avoid retroactive back-billing
    elif current_status == "Paused" and target_status == "Active":
        # Shift next_invoice_date forward if it fell behind during pause
        if sub.next_invoice_date and sub.next_invoice_date < today:
            sub.next_invoice_date = today

    # 5. Early Close enforcement: Closing before expiry_date
    elif target_status == "Closed":
        if sub.expiry_date and today < sub.expiry_date:
            if not plan.allow_early_close:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This subscription plan does not allow early cancellation."
                )

    sub.status = target_status
    db.commit()
    db.refresh(sub)

    # Publish real-time status change to SSE event bus
    event_bus.publish("subscription.status", {
        "subscription_id": sub.id,
        "subscription_number": sub.subscription_number,
        "customer_id": sub.customer_id,
        "previous_status": current_status,
        "new_status": target_status
    })

    return sub


def renew_subscription(sub: Subscription, db: Session, user: User, today: datetime.date = None) -> Subscription:
    """
    Renews an active or paused subscription by one billing period.
    Enforces plan.allow_renew.
    """
    if today is None:
        today = datetime.date.today()

    plan = sub.plan
    if not plan or not plan.allow_renew:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This subscription plan does not allow renewal."
        )

    if sub.status not in ["Active", "Paused"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot renew subscription in '{sub.status}' status. Only Active or Paused subscriptions can be renewed."
        )

    base_date = sub.expiry_date if sub.expiry_date and sub.expiry_date > today else today
    sub.expiry_date = add_billing_period(base_date, plan.billing_period)
    db.commit()
    db.refresh(sub)
    return sub


def auto_close_expired_subscriptions(db: Session, today: datetime.date = None) -> int:
    """
    Closes Active subscriptions whose expiry_date has passed, where plan.auto_close is true.
    Scheduled via APScheduler.
    """
    if today is None:
        today = datetime.date.today()

    expired_subs = (
        db.query(Subscription)
        .join(Plan, Subscription.plan_id == Plan.id)
        .filter(
            Subscription.status == "Active",
            Subscription.expiry_date.isnot(None),
            Subscription.expiry_date < today,
            Plan.auto_close == True
        )
        .all()
    )

    closed_count = 0
    for s in expired_subs:
        s.status = "Closed"
        closed_count += 1

    if closed_count > 0:
        db.commit()

    return closed_count
