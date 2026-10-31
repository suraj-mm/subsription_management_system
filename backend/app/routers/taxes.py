from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Tax, User
from backend.app.schemas import TaxCreate, TaxUpdate, TaxResponse, PaginatedResponse
from backend.app.deps import get_current_user, require_roles

router = APIRouter(prefix="/taxes", tags=["Tax Rules"])


@router.get("", response_model=PaginatedResponse[TaxResponse])
def list_taxes(
    search: Optional[str] = Query(None, description="Search tax name"),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists tax rules with pagination. Accessible to all authenticated users."""
    query = db.query(Tax)
    if is_active is not None:
        query = query.filter(Tax.is_active == is_active)
    if search:
        query = query.filter(Tax.name.ilike(f"%{search.strip()}%"))

    total = query.count()
    items = query.order_by(Tax.rate.asc()).offset((page - 1) * size).limit(size).all()
    pages = ceil(total / size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("", response_model=TaxResponse, status_code=status.HTTP_201_CREATED)
def create_tax(
    req: TaxCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Creates a named tax rule (e.g. GST 18%)."""
    tax = Tax(
        name=req.name.strip(),
        rate=req.rate,
        type=req.type.lower(),
        is_active=req.is_active
    )
    db.add(tax)
    db.commit()
    db.refresh(tax)
    return tax


@router.get("/{id}", response_model=TaxResponse)
def get_tax(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches single tax rule."""
    tax = db.query(Tax).filter(Tax.id == id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax rule not found")
    return tax


@router.put("/{id}", response_model=TaxResponse)
def update_tax(
    id: int,
    req: TaxUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Updates tax parameters."""
    tax = db.query(Tax).filter(Tax.id == id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax rule not found")

    if req.name is not None:
        tax.name = req.name.strip()
    if req.rate is not None:
        tax.rate = req.rate
    if req.type is not None:
        tax.type = req.type.lower()
    if req.is_active is not None:
        tax.is_active = req.is_active

    db.commit()
    db.refresh(tax)
    return tax


@router.delete("/{id}")
def delete_tax(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """
    Admin-only: Soft-deactivates the tax rule instead of deleting
    to preserve audit trails and prevent foreign key violations.
    """
    tax = db.query(Tax).filter(Tax.id == id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax rule not found")

    tax.is_active = False
    db.commit()
    return {"message": f"Tax rule '{tax.name}' deactivated successfully"}
