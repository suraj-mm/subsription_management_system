import re
from decimal import Decimal
from typing import Optional, List, Generic, TypeVar, Any
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


T = TypeVar("T")


# --- Reusable Password Validation Rule ---
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


# --- Generic Pagination Response ---
class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


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


# --- Tax Schemas ---
class TaxBase(BaseModel):
    name: str
    rate: Decimal
    type: str = "percent"  # percent, fixed
    is_active: bool = True


class TaxCreate(TaxBase):
    pass


class TaxUpdate(BaseModel):
    name: Optional[str] = None
    rate: Optional[Decimal] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None


class TaxResponse(TaxBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Product Variant Schemas ---
class ProductVariantBase(BaseModel):
    attribute: str
    value: str
    extra_price: Decimal = Decimal("0.00")


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(BaseModel):
    attribute: Optional[str] = None
    value: Optional[str] = None
    extra_price: Optional[Decimal] = None


class ProductVariantResponse(ProductVariantBase):
    id: int
    product_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Product Schemas ---
class ProductBase(BaseModel):
    name: str
    type: str = "service"
    sales_price: Decimal = Decimal("0.00")
    cost_price: Decimal = Decimal("0.00")
    notes: Optional[str] = None
    tax_id: Optional[int] = None
    is_active: bool = True


class ProductCreate(ProductBase):
    variants: Optional[List[ProductVariantCreate]] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    sales_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    notes: Optional[str] = None
    tax_id: Optional[int] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    variants: List[ProductVariantResponse] = []
    tax: Optional[TaxResponse] = None

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

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValueError("end_date must be strictly after start_date")
        return self


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[Decimal] = None
    billing_period: Optional[str] = None
    min_quantity: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    auto_close: Optional[bool] = None
    allow_early_close: Optional[bool] = None
    allow_pause: Optional[bool] = None
    allow_renew: Optional[bool] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValueError("end_date must be strictly after start_date")
        return self


class PlanResponse(PlanBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Discount Schemas ---
class DiscountBase(BaseModel):
    code: Optional[str] = None
    name: str
    discount_type: str  # fixed, percent
    value: Decimal
    min_purchase: Decimal = Decimal("0.00")
    min_qty: int = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    usage_limit: Optional[int] = None  # null means unlimited
    applies_to: str = "subscription"   # product, subscription
    product_id: Optional[int] = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_discount_rules(self):
        if self.value <= Decimal("0.00"):
            raise ValueError("Discount value must be strictly greater than 0")
        if self.discount_type == "percent" and self.value > Decimal("100.00"):
            raise ValueError("Percentage discount value cannot exceed 100%")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        if self.applies_to == "product" and not self.product_id:
            raise ValueError("product_id is required when applies_to is 'product'")
        return self


class DiscountCreate(DiscountBase):
    pass


class DiscountUpdate(BaseModel):
    name: Optional[str] = None
    discount_type: Optional[str] = None
    value: Optional[Decimal] = None
    min_purchase: Optional[Decimal] = None
    min_qty: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    usage_limit: Optional[int] = None
    applies_to: Optional[str] = None
    product_id: Optional[int] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_discount_rules(self):
        if self.value is not None and self.value <= Decimal("0.00"):
            raise ValueError("Discount value must be strictly greater than 0")
        if self.discount_type == "percent" and self.value is not None and self.value > Decimal("100.00"):
            raise ValueError("Percentage discount value cannot exceed 100%")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


class DiscountResponse(DiscountBase):
    id: int
    used_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Quotation Template Schemas ---
class QuotationTemplateLineCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class QuotationTemplateLineResponse(BaseModel):
    id: int
    template_id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    created_at: datetime
    product: Optional[ProductResponse] = None
    variant: Optional[ProductVariantResponse] = None

    class Config:
        from_attributes = True


class QuotationTemplateCreate(BaseModel):
    name: str
    validity_days: int = 30
    plan_id: Optional[int] = None
    lines: List[QuotationTemplateLineCreate] = []


class QuotationTemplateUpdate(BaseModel):
    name: Optional[str] = None
    validity_days: Optional[int] = None
    plan_id: Optional[int] = None
    lines: Optional[List[QuotationTemplateLineCreate]] = None


class QuotationTemplateResponse(BaseModel):
    id: int
    name: str
    validity_days: int
    plan_id: Optional[int] = None
    created_at: datetime
    lines: List[QuotationTemplateLineResponse] = []
    plan: Optional[PlanResponse] = None

    class Config:
        from_attributes = True


# --- Subscription Schemas ---
class SubscriptionLineInput(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    qty: int = 1


class SubscriptionLineResponse(BaseModel):
    id: int
    subscription_id: int
    product_id: int
    variant_id: Optional[int] = None
    qty: int
    unit_price: Decimal
    tax_rate: Decimal
    amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class SubscriptionCreate(BaseModel):
    customer_id: int
    plan_id: int
    start_date: date
    expiry_date: Optional[date] = None
    payment_terms: str = "Immediate"
    discount_id: Optional[int] = None
    lines: List[SubscriptionLineInput] = []


class SubscriptionFromTemplateRequest(BaseModel):
    customer_id: int
    template_id: Optional[int] = None
    start_date: Optional[date] = None
    payment_terms: str = "Immediate"
    discount_id: Optional[int] = None


class SubscriptionUpdate(BaseModel):
    payment_terms: Optional[str] = None
    expiry_date: Optional[date] = None
    discount_id: Optional[int] = None
    lines: Optional[List[SubscriptionLineInput]] = None


class SubscriptionResponse(BaseModel):
    id: int
    subscription_number: str
    customer_id: int
    plan_id: int
    template_id: Optional[int] = None
    discount_id: Optional[int] = None
    start_date: date
    expiry_date: Optional[date] = None
    payment_terms: str
    status: str
    next_invoice_date: Optional[date] = None
    quotation_valid_until: Optional[date] = None
    created_at: datetime
    subtotal: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    lines: List[SubscriptionLineResponse] = []
    plan: Optional[PlanResponse] = None
    customer: Optional[UserResponse] = None
    discount: Optional[DiscountResponse] = None

    class Config:
        from_attributes = True


# --- Invoice Schemas ---
class InvoiceLineResponse(BaseModel):
    id: int
    invoice_id: int
    product_id: int
    qty: int
    price: Decimal
    discount_amount: Decimal = Decimal("0.00")
    tax_rate: Decimal = Decimal("0.00")
    amount: Decimal
    created_at: datetime
    product: Optional[ProductResponse] = None

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
    outstanding_balance: Decimal = Decimal("0.00")
    sent_at: Optional[datetime] = None
    created_at: datetime
    lines: List[InvoiceLineResponse] = []
    customer: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class InvoiceGenerateRequest(BaseModel):
    auto_confirm: bool = False
    billing_date: Optional[date] = None


class InvoiceBulkConfirmRequest(BaseModel):
    invoice_ids: List[int]


# --- Payment Schemas ---
class PaymentCreate(BaseModel):
    invoice_id: int
    method: str = "Bank Transfer"  # Cash, Bank Transfer, UPI, Card, Cheque
    amount: Decimal
    payment_date: Optional[datetime] = None
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


# --- Dashboard Schemas ---
class DashboardSummaryResponse(BaseModel):
    active_subscriptions: int
    revenue_collected: Decimal
    outstanding_amount: Decimal
    overdue_amount: Decimal
    overdue_invoices_count: int
    mrr: Decimal


class RevenueTrendItem(BaseModel):
    month: str
    revenue: Decimal
