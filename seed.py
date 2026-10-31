"""
Brightloop Demo & Benchmark Data Seeder
Odoo Hackathon Kochi

Populates the platform with realistic ERP data covering every PDF scenario:
- 3 Roles: Administrator, Staff, and 6 Enterprise Customers
- Multi-tier Taxes (18% GST, 1% Kerala Flood Cess, Inactive 5% Tax)
- Products with variants (+₹560 Odoo Connector)
- All 4 billing cycles (daily, weekly, monthly, yearly) + Auto-close plan
- Discount states: Active, Expired, and Exhausted (limit reached)
- Complete subscription lifecycle: Draft, Quotation, Confirmed, Active, Paused, Closed
- Full invoice spectrum: Draft, Confirmed, Paid, Cancelled, and Overdue (with payments via card, upi, bank)
- Two active subscriptions due TODAY for real-time live demo billing trigger
- Optional --bulk flag: Generates 3,000 subscriptions & 10,000 invoices for sub-second latency verification.
"""

import sys
import argparse
import datetime
import random

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from backend.app.database import engine, Base, SessionLocal
from backend.app.config import settings
from backend.app.security import get_password_hash
from backend.app.models import (
    User, Tax, Product, ProductVariant, Plan, Discount,
    QuotationTemplate, QuotationTemplateLine,
    Subscription, SubscriptionLine,
    Invoice, InvoiceLine, Payment
)
from backend.app.services.pricing_service import (
    calculate_unit_price, calculate_line_amounts, format_sequence_number, quantize_money
)
from backend.app.services.subscription_service import compute_subscription_totals


def clean_database():
    """Wipes all platform tables and recreates clean schema."""
    print("🧹 Cleaning database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Fresh schema initialized.")


def seed_primary_data(db: Session):
    today = datetime.date.today()
    print("🌱 Seeding Brightloop primary data...")

    existing_admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL.lower()).first()
    if existing_admin:
        print("  -> Primary seed data already detected. Skipping duplicate base creation.")
        return

    # 1. Users & Roles
    print("  -> Creating platform accounts...")
    admin = User(
        email=settings.ADMIN_EMAIL.lower(),
        name=settings.ADMIN_NAME,
        hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
        role="admin",
        is_active=True
    )
    db.add(admin)

    staff = User(
        email="staff@brightloop.com",
        name="Sarah Jenkins (Billing Ops)",
        hashed_password=get_password_hash("Staff@12345"),
        role="staff",
        is_active=True
    )
    db.add(staff)

    customers_data = [
        ("Acme Corporation", "alex@acme.com", "+91 98450 11223", "42 Industrial Park, Kochi", "GSTIN32AAACA1234A1Z1"),
        ("Globex Logistics", "rachel@globex.in", "+91 98450 22334", "15 Infopark Expressway, Kakkanad", "GSTIN32BBBCB2345B2Z2"),
        ("Nexus Technologies", "arjun@nexustech.io", "+91 98450 33445", "88 Cyber City, Bangalore", "GSTIN29CCCC2345C3Z3"),
        ("Stark Industries", "tony@stark.org", "+91 98450 44556", "10880 Malibu Point, CA", "GSTIN27DDDD3456D4Z4"),
        ("Wayne Enterprises", "bruce@waynecorp.com", "+91 98450 55667", "1007 Mountain Drive, Gotham", "GSTIN27EEEE4567E5Z5"),
        ("Apollo Health Services", "maya@apollohealth.in", "+91 98450 66778", "12 Marine Drive, Kochi", "GSTIN32FFFF5678F6Z6"),
    ]

    customers = []
    for name, email, phone, addr, tax_no in customers_data:
        c = User(
            email=email.lower(),
            name=name,
            hashed_password=get_password_hash("Customer@12345"),
            role="customer",
            is_active=True,
            company=name,
            phone=phone,
            address=addr,
            tax_id=tax_no
        )
        db.add(c)
        customers.append(c)

    db.commit()
    for c in customers:
        db.refresh(c)
    db.refresh(admin)
    db.refresh(staff)

    # 2. Taxes
    print("  -> Creating taxes...")
    tax_gst = Tax(name="GST 18%", rate=Decimal("18.00"), type="percent", is_active=True)
    tax_cess = Tax(name="Kerala Flood Cess 1%", rate=Decimal("1.00"), type="percent", is_active=True)
    tax_inactive = Tax(name="Legacy Service Tax 5%", rate=Decimal("5.00"), type="percent", is_active=False)
    db.add_all([tax_gst, tax_cess, tax_inactive])
    db.commit()
    db.refresh(tax_gst)

    # 3. Products & Variants
    print("  -> Creating products and variants...")
    p1 = Product(name="Enterprise ERP Suite", type="service", sales_price=Decimal("15000.00"), cost_price=Decimal("7500.00"), tax_id=tax_gst.id, is_active=True)
    p2 = Product(name="Dedicated Cloud Server", type="product", sales_price=Decimal("5000.00"), cost_price=Decimal("2800.00"), tax_id=tax_gst.id, is_active=True)
    p3 = Product(name="24/7 Priority SLA Support", type="service", sales_price=Decimal("3500.00"), cost_price=Decimal("1000.00"), tax_id=tax_gst.id, is_active=True)
    p4 = Product(name="SSL & Zero-Trust Shield", type="service", sales_price=Decimal("1200.00"), cost_price=Decimal("350.00"), tax_id=tax_gst.id, is_active=True)
    db.add_all([p1, p2, p3, p4])
    db.commit()
    for p in [p1, p2, p3, p4]:
        db.refresh(p)

    # Required Odoo Variant: +₹560
    v1_odoo = ProductVariant(product_id=p1.id, attribute="Integration", value="Odoo Sync Engine", extra_price=Decimal("560.00"))
    v1_sap = ProductVariant(product_id=p1.id, attribute="Integration", value="SAP NetWeaver", extra_price=Decimal("1500.00"))
    v2_ram = ProductVariant(product_id=p2.id, attribute="RAM Tier", value="64GB ECC High-RAM", extra_price=Decimal("2000.00"))
    db.add_all([v1_odoo, v1_sap, v2_ram])
    db.commit()
    db.refresh(v1_odoo)
    db.refresh(v2_ram)

    # 4. Plans (all 4 billing periods + auto-close)
    print("  -> Creating subscription plans...")
    plan_monthly = Plan(
        name="Monthly Professional",
        billing_period="monthly",
        price=Decimal("15000.00"),
        min_quantity=1,
        allow_pause=True,
        allow_renew=True,
        allow_early_close=True,
        auto_close=False,
        is_active=True
    )
    plan_yearly = Plan(
        name="Annual Enterprise VIP",
        billing_period="yearly",
        price=Decimal("150000.00"),
        min_quantity=1,
        allow_pause=True,
        allow_renew=True,
        allow_early_close=True,
        auto_close=False,
        is_active=True
    )
    plan_weekly = Plan(
        name="Weekly Sprint Care",
        billing_period="weekly",
        price=Decimal("3500.00"),
        min_quantity=1,
        allow_pause=True,
        allow_renew=True,
        allow_early_close=True,
        auto_close=False,
        is_active=True
    )
    plan_daily = Plan(
        name="Daily Compute Burst",
        billing_period="daily",
        price=Decimal("600.00"),
        min_quantity=1,
        allow_pause=True,
        allow_renew=True,
        allow_early_close=True,
        auto_close=False,
        is_active=True
    )
    plan_autoclose = Plan(
        name="Fixed Pilot (Auto-Close)",
        billing_period="monthly",
        price=Decimal("6000.00"),
        min_quantity=1,
        allow_pause=False,
        allow_renew=False,
        allow_early_close=False,
        auto_close=True,
        is_active=True
    )
    db.add_all([plan_monthly, plan_yearly, plan_weekly, plan_daily, plan_autoclose])
    db.commit()
    for pl in [plan_monthly, plan_yearly, plan_weekly, plan_daily, plan_autoclose]:
        db.refresh(pl)

    # 5. Discounts (Active, Expired, Exhausted)
    print("  -> Creating discounts...")
    d_active = Discount(
        code="EARLY10",
        name="Early Adopter 10%",
        discount_type="percent",
        value=Decimal("10.00"),
        applies_to="subscription",
        start_date=today - datetime.timedelta(days=60),
        end_date=today + datetime.timedelta(days=90),
        usage_limit=100,
        used_count=12,
        is_active=True
    )
    d_expired = Discount(
        code="LAUNCH25",
        name="Launch Promo 25% (Expired)",
        discount_type="percent",
        value=Decimal("25.00"),
        applies_to="subscription",
        start_date=today - datetime.timedelta(days=90),
        end_date=today - datetime.timedelta(days=15),
        usage_limit=50,
        used_count=8,
        is_active=True
    )
    d_exhausted = Discount(
        code="VIP2000",
        name="VIP Voucher ₹2000 (Exhausted)",
        discount_type="fixed",
        value=Decimal("2000.00"),
        applies_to="subscription",
        start_date=today - datetime.timedelta(days=30),
        end_date=today + datetime.timedelta(days=30),
        usage_limit=2,
        used_count=2,  # Limit reached!
        is_active=True
    )
    db.add_all([d_active, d_expired, d_exhausted])
    db.commit()
    db.refresh(d_active)

    # 6. Quotation Templates
    print("  -> Creating quotation templates...")
    tpl = QuotationTemplate(
        name="Standard ERP Onboarding",
        validity_days=30,
        plan_id=plan_monthly.id
    )
    db.add(tpl)
    db.flush()
    tpl_line1 = QuotationTemplateLine(template_id=tpl.id, product_id=p1.id, variant_id=v1_odoo.id, quantity=1)
    tpl_line2 = QuotationTemplateLine(template_id=tpl.id, product_id=p3.id, variant_id=None, quantity=1)
    db.add_all([tpl_line1, tpl_line2])
    db.commit()
    db.refresh(tpl)

    # 7. Subscriptions across all lifecycle states
    print("  -> Creating subscriptions...")

    # Helper to construct lines
    def build_sub_lines(sub_id, lines_spec):
        for prod, var, qty in lines_spec:
            unit_price = calculate_unit_price(prod, var)
            subtotal, tax_rate, tax_amount, total = calculate_line_amounts(qty, unit_price, prod.tax)
            s_line = SubscriptionLine(
                subscription_id=sub_id,
                product_id=prod.id,
                variant_id=var.id if var else None,
                qty=qty,
                unit_price=unit_price,
                tax_rate=tax_rate,
                amount=total
            )
            db.add(s_line)

    # Sub 1: Draft
    s_draft = Subscription(
        subscription_number="TEMP",
        customer_id=customers[0].id,
        plan_id=plan_monthly.id,
        start_date=today,
        expiry_date=today + datetime.timedelta(days=365),
        status="Draft",
        payment_terms="Net 15"
    )
    db.add(s_draft)
    db.flush()
    s_draft.subscription_number = format_sequence_number("SUB", s_draft.id)
    build_sub_lines(s_draft.id, [(p1, v1_odoo, 1), (p2, None, 1)])

    # Sub 2: Quotation
    s_quote = Subscription(
        subscription_number="TEMP",
        customer_id=customers[1].id,
        plan_id=plan_monthly.id,
        start_date=today,
        expiry_date=today + datetime.timedelta(days=365),
        status="Quotation",
        quotation_valid_until=today + datetime.timedelta(days=20),
        template_id=tpl.id,
        payment_terms="Net 30"
    )
    db.add(s_quote)
    db.flush()
    s_quote.subscription_number = format_sequence_number("SUB", s_quote.id)
    build_sub_lines(s_quote.id, [(p1, v1_odoo, 1), (p3, None, 1)])

    # Sub 3: Confirmed
    s_conf = Subscription(
        subscription_number="TEMP",
        customer_id=customers[2].id,
        plan_id=plan_monthly.id,
        start_date=today,
        expiry_date=today + datetime.timedelta(days=365),
        status="Confirmed",
        payment_terms="Net 30"
    )
    db.add(s_conf)
    db.flush()
    s_conf.subscription_number = format_sequence_number("SUB", s_conf.id)
    build_sub_lines(s_conf.id, [(p1, None, 1)])

    # Sub 4: Active (DUE TODAY! Will be billed when clicking "Run Billing" in demo)
    s_active1 = Subscription(
        subscription_number="TEMP",
        customer_id=customers[3].id,
        plan_id=plan_monthly.id,
        start_date=today - datetime.timedelta(days=30),
        expiry_date=today + datetime.timedelta(days=335),
        next_invoice_date=today,  # DUE TODAY
        status="Active",
        payment_terms="Immediate",
        discount_id=d_active.id
    )
    db.add(s_active1)
    db.flush()
    s_active1.subscription_number = format_sequence_number("SUB", s_active1.id)
    build_sub_lines(s_active1.id, [(p1, v1_odoo, 1), (p3, None, 1)])

    # Sub 5: Active (DUE TODAY! Second subscription due today for demo run)
    s_active2 = Subscription(
        subscription_number="TEMP",
        customer_id=customers[4].id,
        plan_id=plan_yearly.id,
        start_date=today - datetime.timedelta(days=365),
        expiry_date=today + datetime.timedelta(days=365),
        next_invoice_date=today,  # DUE TODAY
        status="Active",
        payment_terms="Net 30"
    )
    db.add(s_active2)
    db.flush()
    s_active2.subscription_number = format_sequence_number("SUB", s_active2.id)
    build_sub_lines(s_active2.id, [(p1, v1_odoo, 2)])

    # Sub 6: Active (Already billed, next invoice next month)
    s_active_billed = Subscription(
        subscription_number="TEMP",
        customer_id=customers[0].id,
        plan_id=plan_monthly.id,
        start_date=today - datetime.timedelta(days=60),
        expiry_date=today + datetime.timedelta(days=305),
        next_invoice_date=today + datetime.timedelta(days=30),
        status="Active",
        payment_terms="Net 15"
    )
    db.add(s_active_billed)
    db.flush()
    s_active_billed.subscription_number = format_sequence_number("SUB", s_active_billed.id)
    build_sub_lines(s_active_billed.id, [(p1, v1_odoo, 1), (p4, None, 2)])

    # Sub 7: Paused
    s_paused = Subscription(
        subscription_number="TEMP",
        customer_id=customers[1].id,
        plan_id=plan_monthly.id,
        start_date=today - datetime.timedelta(days=45),
        expiry_date=today + datetime.timedelta(days=320),
        next_invoice_date=today + datetime.timedelta(days=15),
        status="Paused",
        payment_terms="Net 15"
    )
    db.add(s_paused)
    db.flush()
    s_paused.subscription_number = format_sequence_number("SUB", s_paused.id)
    build_sub_lines(s_paused.id, [(p2, v2_ram, 1)])

    # Sub 8: Closed (Expired auto-close plan)
    s_closed = Subscription(
        subscription_number="TEMP",
        customer_id=customers[5].id,
        plan_id=plan_autoclose.id,
        start_date=today - datetime.timedelta(days=60),
        expiry_date=today - datetime.timedelta(days=5),
        status="Closed",
        payment_terms="Due on Receipt"
    )
    db.add(s_closed)
    db.flush()
    s_closed.subscription_number = format_sequence_number("SUB", s_closed.id)
    build_sub_lines(s_closed.id, [(p1, None, 1)])

    db.commit()

    # 8. Invoices covering all statuses (Paid, Confirmed, Overdue, Draft, Cancelled)
    print("  -> Creating invoices and payments...")

    # Helper to insert an invoice
    def create_invoice(sub, customer, status, p_start, p_end, due_date, discount=None):
        sub_totals = compute_subscription_totals(sub)
        subtotal = sub_totals["subtotal"]
        tax_amount = sub_totals["tax_amount"]
        discount_amount = Decimal("0.00")
        if discount:
            if discount.discount_type == "percent":
                discount_amount = quantize_money(subtotal * (discount.value / Decimal("100.00")))
            else:
                discount_amount = quantize_money(min(subtotal, discount.value))

        taxable = max(Decimal("0.00"), subtotal - discount_amount)
        if subtotal > 0:
            tax_amount = quantize_money(tax_amount * (taxable / subtotal))
        total_amount = taxable + tax_amount

        inv = Invoice(
            invoice_number="TEMP",
            subscription_id=sub.id,
            customer_id=customer.id,
            status=status,
            issue_date=p_start or today,
            period_start=p_start,
            period_end=p_end,
            due_date=due_date,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total_amount=total_amount,
            amount_paid=Decimal("0.00"),
            sent_at=today - datetime.timedelta(days=20) if status in ["Confirmed", "Paid"] else None
        )
        db.add(inv)
        db.flush()
        inv.invoice_number = format_sequence_number("INV", inv.id)

        # Copy lines
        for s_line in sub.lines:
            inv_line = InvoiceLine(
                invoice_id=inv.id,
                product_id=s_line.product_id,
                qty=s_line.qty,
                price=s_line.unit_price,
                tax_rate=s_line.tax_rate,
                discount_amount=Decimal("0.00"),
                amount=s_line.amount
            )
            db.add(inv_line)
        return inv

    # Invoice 1: Paid (Historical paid invoice with 2 payment records)
    inv1 = create_invoice(
        s_active_billed, customers[0], "Paid",
        p_start=today - datetime.timedelta(days=90),
        p_end=today - datetime.timedelta(days=61),
        due_date=today - datetime.timedelta(days=75)
    )
    p_half = quantize_money(inv1.total_amount / Decimal("2.00"))
    p_rest = inv1.total_amount - p_half
    pay1 = Payment(invoice_id=inv1.id, amount=p_half, method="card", note="TXN-CARD-98412", payment_date=datetime.datetime.utcnow() - datetime.timedelta(days=80))
    pay2 = Payment(invoice_id=inv1.id, amount=p_rest, method="upi", note="UPI/8849102910@okaxis", payment_date=datetime.datetime.utcnow() - datetime.timedelta(days=78))
    inv1.amount_paid = inv1.total_amount
    db.add_all([pay1, pay2])

    # Invoice 2: Confirmed with Partial Payment (Partially Paid)
    inv2 = create_invoice(
        s_active1, customers[3], "Confirmed",
        p_start=today - datetime.timedelta(days=60),
        p_end=today - datetime.timedelta(days=31),
        due_date=today + datetime.timedelta(days=10)
    )
    part_amount = Decimal("10000.00")
    pay_part = Payment(invoice_id=inv2.id, amount=part_amount, method="bank_transfer", note="NEFT/HDFC/0019283", payment_date=datetime.datetime.utcnow() - datetime.timedelta(days=5))
    inv2.amount_paid = part_amount
    db.add(pay_part)

    # Invoice 3: OVERDUE! (Confirmed, due date in the past, zero paid -> will show in red!)
    inv3 = create_invoice(
        s_conf, customers[2], "Confirmed",
        p_start=today - datetime.timedelta(days=45),
        p_end=today - datetime.timedelta(days=16),
        due_date=today - datetime.timedelta(days=14)  # Overdue by 14 days!
    )

    # Invoice 4: Draft invoice
    inv4 = create_invoice(
        s_active2, customers[4], "Draft",
        p_start=today - datetime.timedelta(days=30),
        p_end=today - datetime.timedelta(days=1),
        due_date=today + datetime.timedelta(days=15)
    )

    # Invoice 5: Cancelled invoice
    inv5 = create_invoice(
        s_closed, customers[5], "Cancelled",
        p_start=today - datetime.timedelta(days=60),
        p_end=today - datetime.timedelta(days=31),
        due_date=today - datetime.timedelta(days=45)
    )

    db.commit()
    print("✅ Primary seed completed successfully!")


def seed_bulk_benchmark_data(db: Session, target_subs=3000, target_invoices=10000):
    """
    Creates 3,000 subscriptions and 10,000 invoices for database stress testing.
    Uses bulk batch inserts for maximum speed and memory efficiency.
    """
    print(f"\n🚀 Launching Bulk Performance Seeder: {target_subs:,} subscriptions & {target_invoices:,} invoices...")
    today = datetime.date.today()

    # Query existing dependencies
    customers = db.query(User).filter(User.role == "customer").all()
    plans = db.query(Plan).all()
    products = db.query(Product).all()

    if not customers or not plans or not products:
        print("❌ Please run primary seed before running bulk seed.")
        return

    # Add 100 benchmark customers if needed
    current_cust_count = len(customers)
    if current_cust_count < 100:
        print(f"  -> Generating extra customers to reach 100+...")
        new_customers = []
        cust_pwd_hash = get_password_hash("Customer@12345")
        for i in range(current_cust_count + 1, 105):
            c = User(
                email=f"client_{i}@enterprise{i}.com",
                name=f"Enterprise Corp {i}",
                hashed_password=cust_pwd_hash,
                role="customer",
                is_active=True,
                company=f"Enterprise Corp {i}",
                phone=f"+91 98000 {i:05d}"
            )
            new_customers.append(c)
        db.bulk_save_objects(new_customers)
        db.commit()
        customers = db.query(User).filter(User.role == "customer").all()

    # Generate 3,000 subscriptions
    print(f"  -> Bulk generating {target_subs:,} subscriptions...")
    statuses = ["Draft", "Quotation", "Confirmed", "Active", "Paused", "Closed"]
    sub_objects = []
    sub_lines_batch = []

    # Get max current ID
    max_sub = db.query(Subscription).order_by(Subscription.id.desc()).first()
    start_sub_id = (max_sub.id if max_sub else 0) + 1

    for i in range(target_subs):
        sid = start_sub_id + i
        cust = random.choice(customers)
        plan = random.choice(plans)
        status = random.choice(statuses)
        start_d = today - datetime.timedelta(days=random.randint(10, 365))
        exp_d = start_d + datetime.timedelta(days=365)
        next_d = today + datetime.timedelta(days=random.randint(5, 30)) if status == "Active" else None

        sub = Subscription(
            id=sid,
            subscription_number=f"SUB-B{sid:07d}",
            customer_id=cust.id,
            plan_id=plan.id,
            status=status,
            start_date=start_d,
            expiry_date=exp_d,
            next_invoice_date=next_d,
            payment_terms="Net 30"
        )
        sub_objects.append(sub)

        # 1-2 lines per subscription
        p = random.choice(products)
        sub_lines_batch.append(
            SubscriptionLine(
                subscription_id=sid,
                product_id=p.id,
                qty=random.randint(1, 5),
                unit_price=p.sales_price,
                tax_rate=Decimal("18.00"),
                amount=quantize_money(p.sales_price * Decimal("1.18"))
            )
        )

    # Fast bulk insert
    db.bulk_save_objects(sub_objects)
    db.bulk_save_objects(sub_lines_batch)
    db.commit()
    print(f"  ✅ {target_subs:,} subscriptions indexed.")

    # Generate 10,000 invoices with guaranteed unique (subscription_id, period_start)
    print(f"  -> Bulk generating {target_invoices:,} invoices...")
    max_inv = db.query(Invoice).order_by(Invoice.id.desc()).first()
    start_inv_id = (max_inv.id if max_inv else 0) + 1

    inv_statuses = ["Paid", "Confirmed", "Draft", "Cancelled"]
    inv_objects = []
    inv_lines_batch = []

    inv_count = 0
    cycle = 0
    while inv_count < target_invoices:
        for s_idx in range(target_subs):
            if inv_count >= target_invoices:
                break
            sid = start_sub_id + s_idx
            iid = start_inv_id + inv_count
            cust = customers[s_idx % len(customers)]
            status = random.choice(inv_statuses)

            # Each cycle for this subscription is offset by 30 days — guaranteeing unique (sub_id, period_start)
            p_start = today - datetime.timedelta(days=(cycle + 1) * 30)
            p_end = p_start + datetime.timedelta(days=29)
            due = p_end + datetime.timedelta(days=15)

            base_amt = Decimal(random.randint(2000, 25000))
            tax = quantize_money(base_amt * Decimal("0.18"))
            total = base_amt + tax
            paid = total if status == "Paid" else (Decimal("0.00") if status != "Confirmed" else Decimal(random.choice([0, 500, 1000])))

            inv = Invoice(
                id=iid,
                invoice_number=f"INV-B{iid:07d}",
                subscription_id=sid,
                customer_id=cust.id,
                status=status,
                issue_date=p_start,
                period_start=p_start,
                period_end=p_end,
                due_date=due,
                subtotal=base_amt,
                tax_amount=tax,
                discount_amount=Decimal("0.00"),
                total_amount=total,
                amount_paid=paid,
                sent_at=p_end if status in ["Confirmed", "Paid"] else None
            )
            inv_objects.append(inv)

            inv_lines_batch.append(
                InvoiceLine(
                    invoice_id=iid,
                    product_id=products[0].id,
                    qty=1,
                    price=base_amt,
                    tax_rate=Decimal("18.00"),
                    discount_amount=Decimal("0.00"),
                    amount=total
                )
            )
            inv_count += 1
        cycle += 1

    db.bulk_save_objects(inv_objects)
    db.bulk_save_objects(inv_lines_batch)
    db.commit()
    print(f"  ✅ {target_invoices:,} invoices committed and indexed.")
    print("🚀 Bulk Performance Seeder Complete!\n")


def print_access_summary():
    """Prints clear table of credentials for judges and reviewers."""
    print("\n" + "=" * 80)
    print(" 🌟 BRIGHTLOOP SUBSCRIPTION MANAGEMENT — DEMO ACCOUNTS 🌟")
    print("=" * 80)
    print(f"{'Role':<12} | {'Email':<28} | {'Password':<16} | {'Description'}")
    print("-" * 80)
    print(f"{'admin':<12} | {'admin@brightloop.com':<28} | {'Admin@12345':<16} | Full platform administrator")
    print(f"{'staff':<12} | {'staff@brightloop.com':<28} | {'Staff@12345':<16} | Billing & subscription ops")
    print(f"{'customer':<12} | {'alex@acme.com':<28} | {'Customer@12345':<16} | Acme Corp (Active Sub + Paid Inv)")
    print(f"{'customer':<12} | {'rachel@globex.in':<28} | {'Customer@12345':<16} | Globex (Quotation + Paused)")
    print(f"{'customer':<12} | {'arjun@nexustech.io':<28} | {'Customer@12345':<16} | Nexus (OVERDUE Invoice)")
    print(f"{'customer':<12} | {'tony@stark.org':<28} | {'Customer@12345':<16} | Stark (Active DUE TODAY for demo)")
    print(f"{'customer':<12} | {'bruce@waynecorp.com':<28} | {'Customer@12345':<16} | Wayne (Active DUE TODAY for demo)")
    print(f"{'customer':<12} | {'maya@apollohealth.in':<28} | {'Customer@12345':<16} | Apollo (Closed Sub + Cancelled)")
    print("=" * 80)
    print(" 🎯 LIVE DEMO STEP: Log in as admin, go to Invoices, click 'Generate Now'.")
    print("    Tony Stark and Bruce Wayne's active subscriptions due today will instantly")
    print("    generate 2 brand new Draft invoices with live SSE notification!")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Brightloop Database Seeder")
    parser.add_argument("--reset", action="store_true", help="Wipes all tables and recreates fresh schema")
    parser.add_argument("--bulk", action="store_true", help="Generates 3,000 subscriptions and 10,000 invoices for benchmarking")
    args = parser.parse_args()

    if args.reset:
        clean_database()

    db = SessionLocal()
    try:
        seed_primary_data(db)
        if args.bulk:
            seed_bulk_benchmark_data(db)
        print_access_summary()
    finally:
        db.close()


if __name__ == "__main__":
    main()
