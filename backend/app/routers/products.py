from math import ceil
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.models import Product, ProductVariant, Tax, User
from backend.app.schemas import (
    ProductCreate, ProductUpdate, ProductResponse,
    ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse,
    PaginatedResponse
)
from backend.app.deps import get_current_user, require_roles

router = APIRouter(prefix="/products", tags=["Products & Catalog"])


@router.get("", response_model=PaginatedResponse[ProductResponse])
def list_products(
    search: Optional[str] = Query(None, description="Search by product name or notes"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists catalog products with search, pagination, and active filters.
    Sub-2s response time optimized. Accessible to all authenticated users (Admin, Staff, Customer).
    """
    query = db.query(Product)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(Product.name.ilike(s), Product.notes.ilike(s)))

    total = query.count()
    items = query.order_by(Product.name.asc()).offset((page - 1) * size).limit(size).all()
    pages = ceil(total / size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Create a new product with optional initial variants."""
    if req.tax_id:
        tax = db.query(Tax).filter(Tax.id == req.tax_id).first()
        if not tax:
            raise HTTPException(status_code=400, detail="Specified tax_id does not exist")

    product = Product(
        name=req.name.strip(),
        type=req.type,
        sales_price=req.sales_price,
        cost_price=req.cost_price,
        notes=req.notes.strip() if req.notes else None,
        tax_id=req.tax_id,
        is_active=req.is_active
    )
    db.add(product)
    db.flush()

    if req.variants:
        for v in req.variants:
            variant = ProductVariant(
                product_id=product.id,
                attribute=v.attribute.strip(),
                value=v.value.strip(),
                extra_price=v.extra_price
            )
            db.add(variant)

    db.commit()
    db.refresh(product)
    return product


@router.get("/{id}", response_model=ProductResponse)
def get_product(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches single product details with all configured variants and inherited tax rule."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{id}", response_model=ProductResponse)
def update_product(
    id: int,
    req: ProductUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Updates product attributes."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if req.tax_id is not None:
        if req.tax_id != 0:
            tax = db.query(Tax).filter(Tax.id == req.tax_id).first()
            if not tax:
                raise HTTPException(status_code=400, detail="Specified tax_id does not exist")
            product.tax_id = req.tax_id
        else:
            product.tax_id = None

    if req.name is not None:
        product.name = req.name.strip()
    if req.type is not None:
        product.type = req.type
    if req.sales_price is not None:
        product.sales_price = req.sales_price
    if req.cost_price is not None:
        product.cost_price = req.cost_price
    if req.notes is not None:
        product.notes = req.notes.strip() if req.notes else None
    if req.is_active is not None:
        product.is_active = req.is_active

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{id}")
def delete_product(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Deactivates product to preserve relational data integrity."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False
    db.commit()
    return {"message": f"Product '{product.name}' deactivated successfully"}


# --- Variant Sub-endpoints ---
@router.post("/{id}/variants", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED)
def add_product_variant(
    id: int,
    req: ProductVariantCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Adds a variant (e.g. Brand=Odoo, extra_price=+560) to a product."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant = ProductVariant(
        product_id=product.id,
        attribute=req.attribute.strip(),
        value=req.value.strip(),
        extra_price=req.extra_price
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


@router.put("/{id}/variants/{variant_id}", response_model=ProductVariantResponse)
def update_product_variant(
    id: int,
    variant_id: int,
    req: ProductVariantUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Updates an existing product variant."""
    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id,
        ProductVariant.product_id == id
    ).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Product variant not found")

    if req.attribute is not None:
        variant.attribute = req.attribute.strip()
    if req.value is not None:
        variant.value = req.value.strip()
    if req.extra_price is not None:
        variant.extra_price = req.extra_price

    db.commit()
    db.refresh(variant)
    return variant


@router.delete("/{id}/variants/{variant_id}")
def delete_product_variant(
    id: int,
    variant_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Removes a variant option."""
    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id,
        ProductVariant.product_id == id
    ).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Product variant not found")

    db.delete(variant)
    db.commit()
    return {"message": "Variant deleted successfully"}
