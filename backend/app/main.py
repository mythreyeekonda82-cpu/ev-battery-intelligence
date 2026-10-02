from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .database import init_db

# Routers
from .routers.auth import router as auth_router
from .routers.vehicles import router as vehicles_router
from .routers.telemetry import router as telemetry_router
from .routers.analytics import router as analytics_router
from .routers.alerts import router as alerts_router
from .routers.settings import router as settings_router
from .routers.notifications import router as notifications_router
from .routers.reports import router as reports_router


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="EV Battery Intelligence Platform",
    description=(
        "EV battery monitoring, fleet intelligence, "
        "battery health analytics, telemetry and alerts."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup_event():
    init_db()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health_check():
    return {
        "success": True,
        "status": "healthy",
        "service": "EV Battery Intelligence Platform",
    }


# ============================================================
# SYSTEM STATUS
# ============================================================

@app.get("/api/status")
def system_status():
    return {
        "success": True,
        "status": "online",
        "service": "EV Battery Intelligence Platform",
        "version": "1.0.0",
    }


# ============================================================
# REGISTER API ROUTERS
# ============================================================

app.include_router(auth_router)
app.include_router(vehicles_router)
app.include_router(telemetry_router)
app.include_router(analytics_router)
app.include_router(alerts_router)
app.include_router(settings_router)
app.include_router(notifications_router)
app.include_router(reports_router)


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app.js")
def javascript():
    return FileResponse(FRONTEND_DIR / "app.js")


@app.get("/styles.css")
def stylesheet():
    return FileResponse(FRONTEND_DIR / "styles.css")