import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User
from backend.app.security import get_password_hash
from backend.app.routers import (
    auth, admin, products, plans, taxes, quotation_templates,
    subscriptions, discounts, invoices, payments, dashboard
)
from backend.app.routers.subscriptions import customers_router
from backend.app.services.subscription_service import auto_close_expired_subscriptions
from backend.app.services.invoice_service import run_billing
from backend.app.services.event_bus import event_bus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brightloop")

# APScheduler instance for background recurring tasks
scheduler = BackgroundScheduler()


def run_auto_close_job():
    """Background task executing daily to close expired subscriptions where plan.auto_close=True."""
    db = SessionLocal()
    try:
        count = auto_close_expired_subscriptions(db)
        if count > 0:
            logger.info("Auto-close job completed: closed %d expired subscription(s)", count)
    except Exception as e:
        logger.error("Error executing auto-close job: %s", e)
    finally:
        db.close()


def run_daily_billing_job():
    """Daily automated recurring billing run."""
    db = SessionLocal()
    try:
        invoices = run_billing(db, today=datetime.date.today())
        if invoices:
            logger.info("Daily recurring billing job generated %d invoice(s)", len(invoices))
    except Exception as e:
        logger.error("Error executing daily recurring billing job: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. Register running asyncio event loop with event bus for thread-safe SSE dispatch
    event_bus.set_loop(asyncio.get_running_loop())

    # 1. Automatically create all 13 database tables on startup
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)

    # 2. Seed initial administrator account if it doesn't exist
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL.lower()).first()
        if not admin_user:
            admin_user = User(
                email=settings.ADMIN_EMAIL.lower(),
                name=settings.ADMIN_NAME,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            logger.info("Seeded initial administrator account: %s", settings.ADMIN_EMAIL)
        else:
            logger.info("Admin account already present: %s", settings.ADMIN_EMAIL)
    finally:
        db.close()

    # 3. Start APScheduler for automated subscription & billing maintenance
    if not scheduler.running:
        scheduler.add_job(
            run_auto_close_job,
            "interval",
            hours=24,
            id="subscription_auto_close",
            replace_existing=True
        )
        scheduler.add_job(
            run_daily_billing_job,
            "interval",
            hours=24,
            id="subscription_billing_run",
            replace_existing=True
        )
        scheduler.start()
        logger.info("APScheduler initialized: daily auto-close and billing jobs registered.")

    yield

    # Shutdown scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")

    logger.info("Shutting down Brightloop API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Unified real-time subscription management backend built for Odoo Hackathon Kochi",
    lifespan=lifespan
)

# CORS Middleware configuration
origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Global exception handler returning clean JSON error payload for unexpected 500s."""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {}
        )
    logger.error("Unhandled server exception on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again or contact support."}
    )

# Mount All System Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(products.router)
app.include_router(plans.router)
app.include_router(taxes.router)
app.include_router(quotation_templates.router)
app.include_router(subscriptions.router)
app.include_router(customers_router)
app.include_router(discounts.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for monitors, load balancers, and hackathon judges."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }


# Static files — MUST be mounted AFTER all API routes
import os
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
_frontend_dir = os.path.abspath(_frontend_dir)
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="static")
