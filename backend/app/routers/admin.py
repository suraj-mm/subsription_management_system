from math import ceil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.models import User
from backend.app.schemas import StaffCreateRequest, UserResponse, PaginatedResponse
from backend.app.security import get_password_hash
from backend.app.deps import require_roles, get_current_user

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


class UserActivateRequest(BaseModel):
    is_active: bool


@router.post("/staff", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    req: StaffCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin"))
):
    """
    Admin-only endpoint to add a new staff member.
    Enforces password complexity.
    Returns 403 if called by customer or staff.
    Returns 409 if email already exists.
    """
    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists"
        )

    staff_user = User(
        email=req.email.lower(),
        name=req.name.strip(),
        hashed_password=get_password_hash(req.password),
        role="staff",
        is_active=True
    )
    db.add(staff_user)
    db.commit()
    db.refresh(staff_user)
    return staff_user


@router.get("/users", response_model=PaginatedResponse[UserResponse])
def list_users(
    role: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin"))
):
    """
    Admin-only: list all platform users with optional role filtering, search, and pagination.
    """
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(User.name.ilike(s), User.email.ilike(s)))
    total = query.count()
    items = query.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size).all()
    pages = ceil(total / size) if total > 0 else 1
    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


@router.patch("/users/{user_id}", response_model=UserResponse)
def toggle_user_active(
    user_id: int,
    req: UserActivateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin"))
):
    """Admin-only: activate or deactivate any user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    user.is_active = req.is_active
    db.commit()
    db.refresh(user)
    return user
