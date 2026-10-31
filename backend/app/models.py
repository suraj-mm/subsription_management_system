import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Numeric, Text,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


# 1. Users Table (Admin, Staff, Customer)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="customer")  # "admin", "staff", "customer"
    is_active = Column(Boolean, default=True, nullable=False)

    # Customer profile fields
    company = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    tax_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="customer")
    invoices = relationship("Invoice", back_populates="customer")


# 2. Products Table
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(50), default="service", nullable=False)  # service, consumable, storable
    sales_price = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    cost_price = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    subscription_lines = relationship("SubscriptionLine", back_populates="product")
    invoice_lines = relationship("InvoiceLine", back_populates="product")


# 3. Product Variants Table
class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    attribute = Column(String(100), nullable=False)  # e.g., "Brand", "Edition"
    value = Column(String(100), nullable=False)      # e.g., "Odoo", "Enterprise"
    extra_price = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)  # e.g., 560.00

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="variants")


# 4. Plans Table
class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    price = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    billing_period = Column(String(50), nullable=False)  # "daily", "weekly", "monthly", "yearly"
    min_quantity = Column(Integer, default=1, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Business rule flags
    auto_close = Column(Boolean, default=False, nullable=False)
    allow_early_close = Column(Boolean, default=True, nullable=False)
    allow_pause = Column(Boolean, default=True, nullable=False)
    allow_renew = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")
    quotation_templates = relationship("QuotationTemplate", back_populates="plan")


# 5. Taxes Table
class Tax(Base):
    __tablename__ = "taxes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # e.g., "GST 18%", "VAT 5%"
    rate = Column(Numeric(5, 2), nullable=False)  # e.g., 18.00
    type = Column(String(50), default="percent", nullable=False)  # "percent", "fixed"
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


# 6. Discounts Table
class Discount(Base):
    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    discount_type = Column(String(50), nullable=False)  # "fixed", "percent"
    value = Column(Numeric(12, 2), nullable=False)
    min_purchase = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    min_qty = Column(Integer, default=0, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0, nullable=False)
    applies_to = Column(String(50), default="subscription", nullable=False)  # "product", "subscription"
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    product = relationship("Product")


# 7. Quotation Templates Table
class QuotationTemplate(Base):
    __tablename__ = "quotation_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    validity_days = Column(Integer, default=30, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    plan = relationship("Plan", back_populates="quotation_templates")
    lines = relationship("QuotationTemplateLine", back_populates="template", cascade="all, delete-orphan")


# 8. Quotation Template Lines Table
class QuotationTemplateLine(Base):
    __tablename__ = "quotation_template_lines"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("quotation_templates.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    template = relationship("QuotationTemplate", back_populates="lines")
    product = relationship("Product")
    variant = relationship("ProductVariant")


# 9. Subscriptions Table
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    subscription_number = Column(String(100), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    start_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    payment_terms = Column(String(50), default="Immediate", nullable=False)  # "Immediate", "15 days", "30 days"
    status = Column(String(50), default="Draft", nullable=False, index=True)  # "Draft", "Quotation", "Confirmed", "Active", "Paused", "Closed"
    next_invoice_date = Column(Date, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Composite Index for sub-2s query requirement: subscriptions(status, customer_id, next_invoice_date)
    __table_args__ = (
        Index("ix_sub_status_cust_nextinv", "status", "customer_id", "next_invoice_date"),
    )

    # Relationships
    customer = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    lines = relationship("SubscriptionLine", back_populates="subscription", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="subscription")


# 10. Subscription Lines Table
class SubscriptionLine(Base):
    __tablename__ = "subscription_lines"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    qty = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    subscription = relationship("Subscription", back_populates="lines")
    product = relationship("Product", back_populates="subscription_lines")
    variant = relationship("ProductVariant")


# 11. Invoices Table
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(100), unique=True, index=True, nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(50), default="Draft", nullable=False, index=True)  # "Draft", "Confirmed", "Paid", "Cancelled"
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    subtotal = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    tax_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    amount_paid = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Rules:
    # 1. No double billing: UniqueConstraint(subscription_id, period_start)
    # 2. Indexes for sub-2s query requirement: invoices(status, due_date, customer_id)
    __table_args__ = (
        UniqueConstraint("subscription_id", "period_start", name="uq_invoice_subscription_period"),
        Index("ix_inv_status_due_cust", "status", "due_date", "customer_id"),
    )

    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")
    customer = relationship("User", back_populates="invoices")
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


# 12. Invoice Lines Table
class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    qty = Column(Integer, default=1, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="lines")
    product = relationship("Product", back_populates="invoice_lines")


# 13. Payments Table
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False)
    method = Column(String(50), default="bank_transfer", nullable=False)  # "bank_transfer", "card", "cash", "upi"
    amount = Column(Numeric(12, 2), nullable=False)
    payment_date = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Index for sub-2s query: payments(invoice_id)
    __table_args__ = (
        Index("ix_payments_invoice_id", "invoice_id"),
    )

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
