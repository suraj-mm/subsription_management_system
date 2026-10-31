from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, Optional
from backend.app.models import Product, ProductVariant, Tax

TWO_PLACES = Decimal("0.01")


def quantize_money(amount: Decimal) -> Decimal:
    """Consistently rounds monetary amounts to 2 decimal places using standard ROUND_HALF_UP."""
    return Decimal(str(amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_unit_price(product: Product, variant: Optional[ProductVariant] = None) -> Decimal:
    """
    Computes effective sales price: base sales_price + variant extra_price.
    E.g., base product 1000.00 + Odoo variant 560.00 = 1560.00.
    """
    base = Decimal(str(product.sales_price)) if product.sales_price is not None else Decimal("0.00")
    extra = Decimal(str(variant.extra_price)) if variant and variant.extra_price is not None else Decimal("0.00")
    return quantize_money(base + extra)


def calculate_line_amounts(
    qty: int,
    unit_price: Decimal,
    tax: Optional[Tax] = None,
    tax_rate_override: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Calculates line subtotal, tax amount, and total amount.
    Returns: (subtotal, tax_rate, tax_amount, total_amount)
    """
    q = Decimal(str(qty))
    price = quantize_money(Decimal(str(unit_price)))
    subtotal = quantize_money(q * price)

    if tax_rate_override is not None:
        effective_rate = Decimal(str(tax_rate_override))
    elif tax is not None:
        effective_rate = Decimal(str(tax.rate))
    else:
        effective_rate = Decimal("0.00")

    effective_rate = quantize_money(effective_rate)

    # If tax type is fixed vs percent:
    if tax and tax.type == "fixed":
        tax_amount = quantize_money(effective_rate * q)
    else:
        tax_amount = quantize_money(subtotal * (effective_rate / Decimal("100.00")))

    total = quantize_money(subtotal + tax_amount)
    return subtotal, effective_rate, tax_amount, total


def format_sequence_number(prefix: str, entity_id: int) -> str:
    """
    Generates standardized readable identifiers:
    E.g., format_sequence_number("SUB", 42) -> 'SUB-00042'
    format_sequence_number("INV", 7) -> 'INV-00007'
    """
    return f"{prefix}-{entity_id:05d}"
