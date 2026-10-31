import asyncio
import datetime
from math import ceil
from typing import Optional, List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import User, Invoice
from backend.app.schemas import (
    DashboardSummaryResponse, RevenueTrendItem, InvoiceResponse, PaginatedResponse
)
from backend.app.deps import get_current_user, require_roles
from backend.app.security import decode_token
from backend.app.services.dashboard_service import get_dashboard_summary, get_revenue_trend
from backend.app.services.event_bus import event_bus
from backend.app.routers.invoices import serialize_invoice

router = APIRouter(prefix="/dashboard", tags=["Executive Dashboard & Real-Time Stream"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_summary(
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    plan_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin only: Retrieves live aggregated financial & subscription KPI metrics.
    MRR, Total Revenue Collected, Total Outstanding, and Overdue totals.
    """
    return get_dashboard_summary(
        db=db,
        start_date=start_date,
        end_date=end_date,
        plan_id=plan_id,
        customer_id=customer_id
    )


@router.get("/overdue", response_model=PaginatedResponse[InvoiceResponse])
def get_overdue_invoices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin only: Lists currently overdue invoices requiring collection follow-ups.
    """
    today = datetime.date.today()
    query = db.query(Invoice).filter(
        Invoice.status == "Confirmed",
        Invoice.due_date < today,
        Invoice.amount_paid < Invoice.total_amount
    )

    total = query.count()
    invs = (
        query.order_by(Invoice.due_date.asc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    pages = ceil(total / size) if total > 0 else 1

    return {
        "items": [serialize_invoice(i) for i in invs],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }


@router.get("/revenue-trend", response_model=List[RevenueTrendItem])
def get_trend(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "staff"))
):
    """
    Staff/Admin only: Monthly historical collected revenue for trend visualizations.
    """
    return get_revenue_trend(db, months=months)


@router.get("/stream")
async def dashboard_realtime_stream(
    token: Optional[str] = Query(None, description="Bearer JWT access token for SSE authorization"),
    db: Session = Depends(get_db)
):
    """
    Real-Time Server-Sent Events (SSE) Stream:
    Since standard EventSource cannot send Authorization headers, accepts JWT via ?token=.
    Pushes instantaneous events:
    - invoice.created
    - invoice.confirmed
    - invoice.paid
    - payment.recorded
    - subscription.status
    Includes 15-second heartbeat comments to keep browser connections alive.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required for live stream")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active or user.role not in ["admin", "staff"]:
        raise HTTPException(status_code=403, detail="Dashboard stream requires staff or admin access")

    async def sse_generator():
        q = event_bus.subscribe()
        try:
            # Initial connection acknowledgement
            yield ": connected\n\n"
            while True:
                try:
                    # Wait for next event or send 15s heartbeat
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(q)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
