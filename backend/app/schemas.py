import re
from decimal import Decimal
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Password Validation Rule ---
def validate_password(v: str) -> str:
    if len(v) <= 8:
        raise ValueError("Password must be more than 8 characters")
    if len(v) > 64:
        raise ValueError("Password must be at most 64 characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Needs an uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Needs a lowercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("Needs a number")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Needs a special character")
    return v


# --- Auth & User Schemas ---
class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str
    company: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password(v)


class StaffCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password(v)


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    company: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: UserResponse


# --- Product & Variant Schemas ---
class ProductVariantBase(BaseModel):
    attribute: str
    value: str
    extra_price: Decimal = Decimal("0.00")


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantResponse(ProductVariantBase):
    id: int
    product_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    name: str
    type: str = "service"
    sales_price: Decimal = Decimal("0.00")
    cost_price: Decimal = Decimal("0.00")
    notes: Optional[str] = None
    is_active: bool = True


class ProductCreate(ProductBase):
    variants: Optional[List[ProductVariantCreate]] = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    variants: List[ProductVariantResponse] = []

    class Config:
        from_attributes = True


# --- Plan Schemas ---
class PlanBase(BaseModel):
    name: str
    price: Decimal
    billing_period: str  # daily, weekly, monthly, yearly
    min_quantity: int = 1
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    auto_close: bool = False
    allow_early_close: bool = True
    allow_pause: bool = True
    allow_renew: bool = True
    is_active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanResponse(PlanBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Tax Schemas ---
class TaxBase(BaseModel):
    name: str
    rate: Decimal
    type: str = "percent"
    is_active: bool = True


class TaxCreate(TaxBase):
    pass


class TaxResponse(TaxBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Discount Schemas ---
class DiscountBase(BaseModel):
    code: str
    name: str
    discount_type: str  # fixed, percent
    value: Decimal
    min_purchase: Decimal = Decimal("0.00")
    min_qty: int = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    usage_limit: Optional[int] = None
    applies_to: str = "subscription"
    product_id: Optional[int] = None
    is_active: bool = True


class DiscountCreate(DiscountBase):
    pass


class DiscountResponse(DiscountBase):
    id: int
    used_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Quotation Template Schemas ---
class QuotationTemplateLineBase(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class QuotationTemplateLineCreate(QuotationTemplateLineBase):
    pass


class QuotationTemplateLineResponse(QuotationTemplateLineBase):
    id: int
    template_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class QuotationTemplateBase(BaseModel):
    name: str
    validity_days: int = 30
    plan_id: Optional[int] = None


class QuotationTemplateCreate(QuotationTemplateBase):
    lines: List[QuotationTemplateLineCreate] = []


class QuotationTemplateResponse(QuotationTemplateBase):
    id: int
    created_at: datetime
    lines: List[QuotationTemplateLineResponse] = []

    class Config:
        from_attributes = True


# --- Subscription Schemas ---
class SubscriptionLineBase(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    qty: int = 1
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0.00")
    amount: Decimal


class SubscriptionLineCreate(SubscriptionLineBase):
    pass


class SubscriptionLineResponse(SubscriptionLineBase):
    id: int
    subscription_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SubscriptionBase(BaseModel):
    customer_id: int
    plan_id: int
    start_date: date
    expiry_date: Optional[date] = None
    payment_terms: str = "Immediate"


class SubscriptionCreate(SubscriptionBase):
    lines: List[SubscriptionLineCreate] = []


class SubscriptionResponse(SubscriptionBase):
    id: int
    subscription_number: str
    status: str
    next_invoice_date: Optional[date] = None
    created_at: datetime
    lines: List[SubscriptionLineResponse] = []

    class Config:
        from_attributes = True


# --- Invoice Schemas ---
class InvoiceLineResponse(BaseModel):
    id: int
    invoice_id: int
    product_id: int
    qty: int
    price: Decimal
    tax_rate: Decimal
    amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    subscription_id: Optional[int] = None
    customer_id: int
    status: str
    issue_date: date
    due_date: date
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    created_at: datetime
    lines: List[InvoiceLineResponse] = []

    class Config:
        from_attributes = True


# --- Payment Schemas ---
class PaymentCreate(BaseModel):
    invoice_id: int
    method: str = "bank_transfer"
    amount: Decimal
    note: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    method: str
    amount: Decimal
    payment_date: datetime
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
