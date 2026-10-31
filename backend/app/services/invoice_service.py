import datetime
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import logging

from backend.app.models import (
    Subscription, Invoice, InvoiceLine, Discount, Tax, User
)
from backend.app.services.pricing_service import (
    quantize_money, format_sequence_number
)
from backend.app.services.event_bus import event_bus

logger = logging.getLogger("brightloop.billing")


def advance_billing_period(base_date: datetime.date, period: str) -> Tuple[datetime.date, datetime.date]:
    """
    Computes period_end and next_period_start using calendar-aware relativedelta.
    E.g., monthly: 2026-01-31 -> period_end=2026-02-27, next_start=2026-02-28.
    """
    p = period.lower()
    if p == "daily":
        delta = relativedelta(days=1)
    elif p == "weekly":
        delta = relativedelta(weeks=1)
    elif p == "monthly":
        delta = relativedelta(months=1)
    elif p == "yearly":
        delta = relativedelta(years=1)
    else:
        delta = relativedelta(months=1)

    period_end = base_date + delta - relativedelta(days=1)
    next_start = base_date + delta
    return period_end, next_start


def calculate_due_date(issue_date: datetime.date, payment_terms: str) -> datetime.date:
    """Calculates due date based on payment terms (Immediate, 15 days, 30 days)."""
    terms = (payment_terms or "Immediate").lower()
    if "15" in terms:
        return issue_date + datetime.timedelta(days=15)
    elif "30" in terms:
        return issue_date + datetime.timedelta(days=30)
    return issue_date


def try_claim_discount_usage(db: Session, discount_id: int) -> bool:
    """
    Atomically increments used_count if usage_limit is null or used_count < usage_limit.
    Guarantees no race condition or limit overrun during concurrent batch billing.
    """
    sql = text("""
        UPDATE discounts
        SET used_count = used_count + 1
        WHERE id = :id AND (usage_limit IS NULL OR used_count < usage_limit)
    """)
    result = db.execute(sql, {"id": discount_id})
    return result.rowcount > 0


def find_best_product_discount(
    db: Session,
    product_id: int,
    qty: int,
    subtotal: Decimal,
    today: datetime.date
) -> Optional[Tuple[Discount, Decimal]]:
    """
    Finds active product-level discounts and picks the one yielding the greatest saving.
    Returns: (discount, saving_amount) or None
    """
    discounts = db.query(Discount).filter(
        Discount.applies_to == "product",
        Discount.product_id == product_id,
        Discount.is_active == True
    ).all()

    best_saving = Decimal("0.00")
    best_discount = None

    for d in discounts:
        if d.start_date and today < d.start_date:
            continue
        if d.end_date and today > d.end_date:
            continue
        if d.usage_limit is not None and d.used_count >= d.usage_limit:
            continue
        if qty < d.min_qty:
            continue
        if subtotal < d.min_purchase:
            continue

        if d.discount_type == "percent":
            saving = quantize_money(subtotal * (d.value / Decimal("100.00")))
        else:
            saving = min(quantize_money(d.value), subtotal)

        if saving > best_saving:
            best_saving = saving
            best_discount = d

    if best_discount:
        return best_discount, best_saving
    return None


def run_billing(db: Session, today: Optional[datetime.date] = None, auto_confirm: bool = False) -> List[Invoice]:
    """
    Billing Engine Core:
    1. Selects Active subscriptions where next_invoice_date <= today and period_start within expiry_date.
    2. Runs catch-up loop per subscription: generates invoices for all due periods until next_invoice_date > today.
    3. Guarantees no duplicate billing via DB-level UniqueConstraint(subscription_id, period_start) inside savepoints.
    4. Evaluates best product and subscription discounts without stacking.
    5. Advances next_invoice_date.
    """
    if today is None:
        today = datetime.date.today()

    active_subs = (
        db.query(Subscription)
        .filter(
            Subscription.status == "Active",
            Subscription.next_invoice_date.isnot(None),
            Subscription.next_invoice_date <= today
        )
        .all()
    )

    generated_invoices = []

    for sub in active_subs:
        plan = sub.plan
        if not plan:
            continue

        # Catch-up loop: run periods until next_invoice_date > today
        while sub.next_invoice_date and sub.next_invoice_date <= today:
            period_start = sub.next_invoice_date

            # If subscription has expired prior to this period start, stop catch-up
            if sub.expiry_date and period_start > sub.expiry_date:
                break

            period_end, next_period_start = advance_billing_period(period_start, plan.billing_period)
            due_date = calculate_due_date(today, sub.payment_terms)

            # Transaction savepoint per invoice to enforce 'no duplicates' gracefully
            sp = db.begin_nested()
            try:
                # 1. Initialize Invoice
                invoice = Invoice(
                    invoice_number="TEMP",
                    subscription_id=sub.id,
                    customer_id=sub.customer_id,
                    status="Confirmed" if auto_confirm else "Draft",
                    issue_date=today,
                    due_date=due_date,
                    period_start=period_start,
                    period_end=period_end,
                    subtotal=Decimal("0.00"),
                    discount_amount=Decimal("0.00"),
                    tax_amount=Decimal("0.00"),
                    total_amount=Decimal("0.00"),
                    amount_paid=Decimal("0.00")
                )
                db.add(invoice)
                db.flush()

                # Generate clean sequence number: INV-YEAR-ID (e.g. INV-2026-00001)
                invoice.invoice_number = f"INV-{today.year}-{invoice.id:05d}"

                # Calculate lines & discounts
                inv_subtotal = Decimal("0.00")
                inv_discount = Decimal("0.00")
                inv_tax = Decimal("0.00")

                # Evaluate potential subscription-level discount
                sub_discount = None
                sub_discount_saving = Decimal("0.00")
                if sub.discount_id:
                    d = db.query(Discount).filter(Discount.id == sub.discount_id, Discount.is_active == True).first()
                    if d:
                        is_valid = True
                        if d.start_date and today < d.start_date: is_valid = False
                        if d.end_date and today > d.end_date: is_valid = False
                        if d.usage_limit is not None and d.used_count >= d.usage_limit: is_valid = False
                        if is_valid:
                            sub_discount = d

                # First pass: compute pre-discount line amounts and match product discounts
                line_data = []
                total_pre_discount = Decimal("0.00")

                for s_line in sub.lines:
                    line_sub = quantize_money(s_line.unit_price * s_line.qty)
                    total_pre_discount += line_sub

                    prod_disc_res = find_best_product_discount(db, s_line.product_id, s_line.qty, line_sub, today)
                    line_data.append({
                        "sub_line": s_line,
                        "line_sub": line_sub,
                        "prod_disc": prod_disc_res
                    })

                # Check subscription discount threshold against total pre-discount
                if sub_discount:
                    if total_pre_discount >= sub_discount.min_purchase:
                        if sub_discount.discount_type == "percent":
                            sub_discount_saving = quantize_money(total_pre_discount * (sub_discount.value / Decimal("100.00")))
                        else:
                            sub_discount_saving = min(quantize_money(sub_discount.value), total_pre_discount)
                    else:
                        sub_discount = None

                # Second pass: apply discounts (best saving per line without stacking)
                claimed_discounts = set()

                for item in line_data:
                    s_line = item["sub_line"]
                    line_sub = item["line_sub"]
                    prod_disc_info = item["prod_disc"]

                    best_line_disc_amount = Decimal("0.00")
                    chosen_disc_id = None

                    # Product discount saving
                    prod_saving = prod_disc_info[1] if prod_disc_info else Decimal("0.00")

                    # Pro-rata share of subscription discount
                    sub_pro_rata = Decimal("0.00")
                    if sub_discount and total_pre_discount > Decimal("0.00"):
                        sub_pro_rata = quantize_money(sub_discount_saving * (line_sub / total_pre_discount))

                    # Non-stacking: pick the best saving
                    if prod_saving >= sub_pro_rata and prod_saving > Decimal("0.00"):
                        best_line_disc_amount = min(prod_saving, line_sub)
                        chosen_disc_id = prod_disc_info[0].id
                    elif sub_pro_rata > Decimal("0.00"):
                        best_line_disc_amount = min(sub_pro_rata, line_sub)
                        chosen_disc_id = sub_discount.id

                    # Attempt usage claiming if not already claimed in this run
                    if chosen_disc_id and chosen_disc_id not in claimed_discounts:
                        if try_claim_discount_usage(db, chosen_disc_id):
                            claimed_discounts.add(chosen_disc_id)
                        else:
                            # Limit was reached -> discount revoked
                            best_line_disc_amount = Decimal("0.00")

                    taxable_line_amount = max(Decimal("0.00"), line_sub - best_line_disc_amount)
                    line_tax_amount = quantize_money(taxable_line_amount * (s_line.tax_rate / Decimal("100.00")))
                    line_final_amount = quantize_money(taxable_line_amount + line_tax_amount)

                    # Create Invoice Line
                    inv_line = InvoiceLine(
                        invoice_id=invoice.id,
                        product_id=s_line.product_id,
                        qty=s_line.qty,
                        price=s_line.unit_price,
                        discount_amount=best_line_disc_amount,
                        tax_rate=s_line.tax_rate,
                        amount=line_final_amount
                    )
                    db.add(inv_line)

                    inv_subtotal += line_sub
                    inv_discount += best_line_disc_amount
                    inv_tax += line_tax_amount

                # Set invoice totals
                invoice.subtotal = inv_subtotal
                invoice.discount_amount = inv_discount
                invoice.tax_amount = inv_tax
                invoice.total_amount = quantize_money(inv_subtotal - inv_discount + inv_tax)

                # Advance next_invoice_date on the subscription
                sub.next_invoice_date = next_period_start

                db.flush()
                sp.commit()
                generated_invoices.append(invoice)

                # Broadcast real-time SSE event
                event_bus.publish("invoice.created", {
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "customer_id": invoice.customer_id,
                    "total_amount": str(invoice.total_amount),
                    "status": invoice.status
                })

            except IntegrityError:
                # Duplicate period constraint triggered -> skip duplicate quietly
                sp.rollback()
                logger.info("Skipped duplicate billing for subscription %d period %s", sub.id, period_start)
                sub.next_invoice_date = next_period_start
                break

    if generated_invoices:
        db.commit()

    return generated_invoices
