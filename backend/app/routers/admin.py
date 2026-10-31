from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import User
from backend.app.schemas import StaffCreateRequest, UserResponse
from backend.app.security import get_password_hash
from backend.app.deps import require_roles

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


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


@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: str = None,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin"))
):
    """
    Admin-only endpoint to list all platform users with optional role filtering.
    """
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.created_at.desc()).all()
