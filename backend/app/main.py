import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User
from backend.app.security import get_password_hash
from backend.app.routers import (
    auth, admin, products, plans, taxes, quotation_templates, subscriptions
)
from backend.app.services.subscription_service import auto_close_expired_subscriptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brightloop")

# APScheduler instance for background lifecycle tasks
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


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    # 3. Start APScheduler for automated subscription lifecycle maintenance
    if not scheduler.running:
        scheduler.add_job(
            run_auto_close_job,
            "interval",
            hours=24,
            id="subscription_auto_close",
            replace_existing=True
        )
        scheduler.start()
        logger.info("APScheduler initialized: daily auto-close job registered.")

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

# Mount All Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(products.router)
app.include_router(plans.router)
app.include_router(taxes.router)
app.include_router(quotation_templates.router)
app.include_router(subscriptions.router)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for monitors, load balancers, and hackathon judges."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
