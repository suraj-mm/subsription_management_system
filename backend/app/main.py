import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.models import User
from backend.app.security import get_password_hash
from backend.app.routers import auth, admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brightloop")


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

    yield
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

# Mount Routers
app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for monitors, load balancers, and hackathon judges."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
