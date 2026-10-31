import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from backend.app.models import (
    Subscription, SubscriptionLine, Invoice, Payment, Plan
)
from backend.app.services.pricing_service import quantize_money


def get_dashboard_summary(
    db: Session,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    plan_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    today: Optional[datetime.date] = None
) -> Dict[str, Any]:
    """
    Computes real-time executive dashboard KPIs via SQL aggregates.
    MRR, Total Collected, Outstanding, and Overdue calculated dynamically.
    """
    if today is None:
        today = datetime.date.today()

    # 1. Active Subscriptions Count
    sub_query = db.query(Subscription).filter(Subscription.status == "Active")
    if plan_id:
        sub_query = sub_query.filter(Subscription.plan_id == plan_id)
    if customer_id:
        sub_query = sub_query.filter(Subscription.customer_id == customer_id)
    active_subscriptions = sub_query.count()

    # 2. Revenue Collected (Payments)
    pay_query = db.query(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
    if customer_id or plan_id:
        pay_query = pay_query.join(Invoice, Payment.invoice_id == Invoice.id)
        if customer_id:
            pay_query = pay_query.filter(Invoice.customer_id == customer_id)
        if plan_id:
            pay_query = pay_query.join(Subscription, Invoice.subscription_id == Subscription.id).filter(Subscription.plan_id == plan_id)

    if start_date:
        pay_query = pay_query.filter(func.date(Payment.payment_date) >= start_date)
    if end_date:
        pay_query = pay_query.filter(func.date(Payment.payment_date) <= end_date)

    revenue_collected = quantize_money(pay_query.scalar() or Decimal("0.00"))

    # 3. Outstanding Balance (Confirmed Invoices: total_amount - amount_paid)
    out_query = db.query(
        func.coalesce(func.sum(Invoice.total_amount - Invoice.amount_paid), Decimal("0.00"))
    ).filter(Invoice.status == "Confirmed")

    if customer_id:
        out_query = out_query.filter(Invoice.customer_id == customer_id)
    if plan_id:
        out_query = out_query.join(Subscription, Invoice.subscription_id == Subscription.id).filter(Subscription.plan_id == plan_id)

    outstanding_amount = quantize_money(out_query.scalar() or Decimal("0.00"))

    # 4. Overdue Balance & Count (Confirmed, due_date < today, amount_paid < total_amount)
    overdue_query = db.query(Invoice).filter(
        Invoice.status == "Confirmed",
        Invoice.due_date < today,
        Invoice.amount_paid < Invoice.total_amount
    )
    if customer_id:
        overdue_query = overdue_query.filter(Invoice.customer_id == customer_id)
    if plan_id:
        overdue_query = overdue_query.join(Subscription, Invoice.subscription_id == Subscription.id).filter(Subscription.plan_id == plan_id)

    overdue_invoices_count = overdue_query.count()

    overdue_sum_query = db.query(
        func.coalesce(func.sum(Invoice.total_amount - Invoice.amount_paid), Decimal("0.00"))
    ).filter(
        Invoice.status == "Confirmed",
        Invoice.due_date < today,
        Invoice.amount_paid < Invoice.total_amount
    )
    if customer_id:
        overdue_sum_query = overdue_sum_query.filter(Invoice.customer_id == customer_id)
    if plan_id:
        overdue_sum_query = overdue_sum_query.join(Subscription, Invoice.subscription_id == Subscription.id).filter(Subscription.plan_id == plan_id)

    overdue_amount = quantize_money(overdue_sum_query.scalar() or Decimal("0.00"))

    # 5. MRR (Monthly Recurring Revenue) Calculation
    # Normalizes active subscriptions' pre-tax revenue to a monthly scale:
    # yearly / 12, weekly * (52 / 12), daily * (365 / 12), monthly * 1
    active_subs = (
        db.query(Subscription)
        .join(Plan, Subscription.plan_id == Plan.id)
        .filter(Subscription.status == "Active")
        .all()
    )

    mrr = Decimal("0.00")
    for s in active_subs:
        # Pre-tax line subtotal
        sub_pretax = sum(l.unit_price * l.qty for l in s.lines)
        if sub_pretax <= Decimal("0.00") and s.plan:
            sub_pretax = s.plan.price

        period = (s.plan.billing_period if s.plan else "monthly").lower()
        if period == "yearly":
            sub_mrr = sub_pretax / Decimal("12.00")
        elif period == "weekly":
            sub_mrr = (sub_pretax * Decimal("52.00")) / Decimal("12.00")
        elif period == "daily":
            sub_mrr = (sub_pretax * Decimal("365.00")) / Decimal("12.00")
        else:  # monthly
            sub_mrr = sub_pretax

        mrr += sub_mrr

    return {
        "active_subscriptions": active_subscriptions,
        "revenue_collected": revenue_collected,
        "outstanding_amount": outstanding_amount,
        "overdue_amount": overdue_amount,
        "overdue_invoices_count": overdue_invoices_count,
        "mrr": quantize_money(mrr)
    }


def get_revenue_trend(db: Session, months: int = 6) -> List[Dict[str, Any]]:
    """
    Generates monthly historical revenue trend data for charts.
    """
    today = datetime.date.today()
    trend = []

    for i in range(months - 1, -1, -1):
        target_date = today - relativedelta(months=i)
        year = target_date.year
        month = target_date.month
        month_label = target_date.strftime("%b %Y")

        month_sum = (
            db.query(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .filter(
                func.strftime("%Y", Payment.payment_date) == str(year),
                func.strftime("%m", Payment.payment_date) == f"{month:02d}"
            )
            .scalar()
        )

        trend.append({
            "month": month_label,
            "revenue": quantize_money(month_sum or Decimal("0.00"))
        })

    return trend
