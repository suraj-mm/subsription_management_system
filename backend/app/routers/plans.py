import datetime
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.database import get_db
from backend.app.models import Plan, User
from backend.app.schemas import PlanCreate, PlanUpdate, PlanResponse, PaginatedResponse
from backend.app.deps import get_current_user, require_roles

router = APIRouter(prefix="/plans", tags=["Subscription Plans"])


def is_plan_available(plan: Plan, today: datetime.date = None) -> bool:
    """
    Evaluates whether a plan is currently available for new subscription creation.
    Must be active and inside the validity date window.
    """
    if not plan.is_active:
        return False
    if today is None:
        today = datetime.date.today()
    if plan.start_date and today < plan.start_date:
        return False
    if plan.end_date and today > plan.end_date:
        return False
    return True


@router.get("", response_model=PaginatedResponse[PlanResponse])
def list_plans(
    search: Optional[str] = Query(None, description="Search plan name"),
    billing_period: Optional[str] = Query(None, description="daily, weekly, monthly, yearly"),
    is_active: Optional[bool] = Query(None),
    available_only: bool = Query(False, description="Filter only currently available plans"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists subscription plans with pagination and availability checks."""
    query = db.query(Plan)
    if is_active is not None:
        query = query.filter(Plan.is_active == is_active)
    if billing_period:
        query = query.filter(Plan.billing_period == billing_period.lower())
    if search:
        query = query.filter(Plan.name.ilike(f"%{search.strip()}%"))

    today = datetime.date.today()
    if available_only:
        query = query.filter(Plan.is_active == True)
        # Check start_date <= today or None
        query = query.filter(or_(Plan.start_date.is_(None), Plan.start_date <= today))
        # Check end_date >= today or None
        query = query.filter(or_(Plan.end_date.is_(None), Plan.end_date >= today))

    total = query.count()
    items = query.order_by(Plan.name.asc()).offset((page - 1) * size).limit(size).all()
    pages = ceil(total / size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    req: PlanCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """
    Admin-only: Creates a recurring subscription plan.
    Enforces billing periods and plan lifecycle capability flags.
    """
    valid_periods = {"daily", "weekly", "monthly", "yearly"}
    if req.billing_period.lower() not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid billing period '{req.billing_period}'. Must be one of {valid_periods}"
        )

    plan = Plan(
        name=req.name.strip(),
        price=req.price,
        billing_period=req.billing_period.lower(),
        min_quantity=req.min_quantity,
        start_date=req.start_date,
        end_date=req.end_date,
        auto_close=req.auto_close,
        allow_early_close=req.allow_early_close,
        allow_pause=req.allow_pause,
        allow_renew=req.allow_renew,
        is_active=req.is_active
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/{id}", response_model=PlanResponse)
def get_plan(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches details of a single subscription plan."""
    plan = db.query(Plan).filter(Plan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.put("/{id}", response_model=PlanResponse)
def update_plan(
    id: int,
    req: PlanUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Updates plan settings and business flags."""
    plan = db.query(Plan).filter(Plan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if req.name is not None:
        plan.name = req.name.strip()
    if req.price is not None:
        plan.price = req.price
    if req.billing_period is not None:
        valid_periods = {"daily", "weekly", "monthly", "yearly"}
        if req.billing_period.lower() not in valid_periods:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid billing period '{req.billing_period}'. Must be one of {valid_periods}"
            )
        plan.billing_period = req.billing_period.lower()
    if req.min_quantity is not None:
        plan.min_quantity = req.min_quantity
    if req.start_date is not None:
        plan.start_date = req.start_date
    if req.end_date is not None:
        plan.end_date = req.end_date

    # Validate combined date range if either updated
    if plan.start_date and plan.end_date and plan.end_date <= plan.start_date:
        raise HTTPException(status_code=400, detail="end_date must be strictly after start_date")

    if req.auto_close is not None:
        plan.auto_close = req.auto_close
    if req.allow_early_close is not None:
        plan.allow_early_close = req.allow_early_close
    if req.allow_pause is not None:
        plan.allow_pause = req.allow_pause
    if req.allow_renew is not None:
        plan.allow_renew = req.allow_renew
    if req.is_active is not None:
        plan.is_active = req.is_active

    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{id}")
def delete_plan(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    """Admin-only: Deactivates plan instead of deleting to safeguard existing subscriptions."""
    plan = db.query(Plan).filter(Plan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.is_active = False
    db.commit()
    return {"message": f"Plan '{plan.name}' deactivated successfully"}
