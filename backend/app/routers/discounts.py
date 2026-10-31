import re
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Discount, Product, User
from backend.app.schemas import (
    DiscountCreate, DiscountUpdate, DiscountResponse, PaginatedResponse
)
from backend.app.deps import get_current_user, require_roles

router = APIRouter(prefix="/discounts", tags=["Discounts & Promotions"])


@router.get("", response_model=PaginatedResponse[DiscountResponse])
def list_discounts(
    search: Optional[str] = Query(None, description="Search discount code or name"),
    applies_to: Optional[str] = Query(None, description="product or subscription"),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists discount codes with pagination and filters."""
    query = db.query(Discount)
    if is_active is not None:
        query = query.filter(Discount.is_active == is_active)
    if applies_to:
        query = query.filter(Discount.applies_to == applies_to.lower())
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(Discount.code.ilike(s) | Discount.name.ilike(s))

    total = query.count()
    items = query.order_by(Discount.created_at.desc()).offset((page - 1) * size).limit(size).all()
    pages = ceil(total / size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("", response_model=DiscountResponse, status_code=status.HTTP_201_CREATED)
def create_discount(
    req: DiscountCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """
    Admin-only: Creates a discount coupon.
    Enforces percentage bounds (<=100), value > 0, date validity, and product binding.
    """
    if req.code and req.code.strip():
        code = req.code.strip().upper()
    else:
        clean = re.sub(r'[^A-Z0-9]', '', req.name.upper())[:8]
        code = f"{clean or 'DISC'}-{int(datetime.datetime.utcnow().timestamp()) % 10000:04d}"

    existing = db.query(Discount).filter(Discount.code == code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Discount code '{code}' already exists")

    if req.applies_to == "product" and req.product_id:
        product = db.query(Product).filter(Product.id == req.product_id).first()
        if not product:
            raise HTTPException(status_code=400, detail="Specified product_id does not exist")

    discount = Discount(
        code=code,
        name=req.name.strip(),
        discount_type=req.discount_type.lower(),
        value=req.value,
        min_purchase=req.min_purchase,
        min_qty=req.min_qty,
        start_date=req.start_date,
        end_date=req.end_date,
        usage_limit=req.usage_limit,
        used_count=0,
        applies_to=req.applies_to.lower(),
        product_id=req.product_id if req.applies_to == "product" else None,
        is_active=req.is_active
    )
    db.add(discount)
    db.commit()
    db.refresh(discount)
    return discount


@router.get("/{id}", response_model=DiscountResponse)
def get_discount(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches single discount rule details."""
    discount = db.query(Discount).filter(Discount.id == id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    return discount


@router.put("/{id}", response_model=DiscountResponse)
def update_discount(
    id: int,
    req: DiscountUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Updates discount attributes."""
    discount = db.query(Discount).filter(Discount.id == id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")

    if req.name is not None:
        discount.name = req.name.strip()
    if req.discount_type is not None:
        discount.discount_type = req.discount_type.lower()
    if req.value is not None:
        discount.value = req.value
    if req.min_purchase is not None:
        discount.min_purchase = req.min_purchase
    if req.min_qty is not None:
        discount.min_qty = req.min_qty
    if req.start_date is not None:
        discount.start_date = req.start_date
    if req.end_date is not None:
        discount.end_date = req.end_date
    if req.usage_limit is not None:
        discount.usage_limit = req.usage_limit
    if req.applies_to is not None:
        discount.applies_to = req.applies_to.lower()
    if req.product_id is not None:
        discount.product_id = req.product_id
    if req.is_active is not None:
        discount.is_active = req.is_active

    db.commit()
    db.refresh(discount)
    return discount


@router.delete("/{id}")
def delete_discount(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Deactivates discount code to preserve financial audit trail."""
    discount = db.query(Discount).filter(Discount.id == id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")

    discount.is_active = False
    db.commit()
    return {"message": f"Discount code '{discount.code}' deactivated successfully"}
