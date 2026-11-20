import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


# ============================================================
# IMPORTS
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .database import init_db, SessionLocal
from .models import Telemetry
from .services.protection_alerts import record_protection_alerts
from .seed_demo_users import create_demo_users, create_fleet
from .simulator.engine import get_simulation_engine


# ============================================================
# EXISTING ROUTERS
# ============================================================

from .routers.auth import router as auth_router
from .routers.vehicles import router as vehicles_router
from .routers.telemetry import router as telemetry_router
from .routers.analytics import router as analytics_router
from .routers.alerts import router as alerts_router
from .routers.settings import router as settings_router
from .routers.notifications import router as notifications_router
from .routers.reports import router as reports_router

from .routers.battery_intelligence import (
    router as battery_intelligence_router
)

from .routers.advanced_intelligence import (
    router as advanced_intelligence_router
)

from .routers.battery_intelligence_plus import (
    router as battery_intelligence_plus_router
)

from .routers.voltiq_assistant import (
    router as voltiq_assistant_router
)


# ============================================================
# PATHS AND SETTINGS
# ============================================================

FRONTEND_DIR = BASE_DIR / "frontend"

SIMULATOR_SNAPSHOT_INTERVAL_SECONDS = 300

simulator_snapshot_task = None


# ============================================================
# SAVE SIMULATOR TELEMETRY
# ============================================================

def save_simulator_telemetry_snapshot():

    engine = get_simulation_engine()
    db = SessionLocal()

    saved_count = 0
    snapshots = []

    try:

        for battery_id in list(engine.batteries.keys()):

            battery = engine.get_battery(battery_id)

            if battery is None:
                continue

            snapshots.append(battery)

            record = Telemetry(
                battery_id=battery_id,
                voltage=battery["voltage"],
                current=battery["current"],
                temperature=battery["temperature"],
                soc=battery["soc"],
                soh=battery["soh"],
                cycles=battery["cycle_count"],
                power_kw=battery["power_kw"],
            )

            db.add(record)
            saved_count += 1

        db.commit()

        record_snapshot_alerts(db, snapshots)

        return saved_count

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


# ============================================================
# RESTORE SIMULATOR STATE
# Resume each battery from its last stored reading so history
# stays continuous across restarts.
# ============================================================

def restore_simulator_state(db):

    engine = get_simulation_engine()
    restored = 0

    for battery_id in list(engine.batteries.keys()):

        latest = (
            db.query(Telemetry)
            .filter(Telemetry.battery_id == battery_id)
            .order_by(Telemetry.timestamp.desc())
            .first()
        )

        if engine.restore_state(battery_id, latest):
            restored += 1

    print(f"[Simulator] Restored {restored} batteries from telemetry.")


# ============================================================
# PROTECTION ALERTS
# Runs the protection analyses on each fresh snapshot and saves
# actionable findings as alerts. A failure here must never stop
# telemetry from being saved, so errors are logged and rolled back.
# ============================================================

def record_snapshot_alerts(db, snapshots):

    since = datetime.utcnow() - timedelta(hours=24)

    try:

        added = 0

        for battery in snapshots:

            battery_id = battery["battery_id"]

            history = (
                db.query(Telemetry)
                .filter(
                    Telemetry.battery_id == battery_id,
                    Telemetry.timestamp >= since,
                )
                .order_by(Telemetry.timestamp.asc())
                .all()
            )

            added += record_protection_alerts(db, battery, history)

        db.commit()

        if added:
            print(f"[Alerts] Recorded {added} protection alert(s).")

    except Exception as error:

        db.rollback()
        print("[Alerts] Protection alert check failed:", error)


# ============================================================
# BACKGROUND SNAPSHOT WORKER
# ============================================================

async def simulator_telemetry_worker():

    while True:

        try:

            saved_count = await asyncio.to_thread(
                save_simulator_telemetry_snapshot
            )

            print(
                f"[Telemetry] Saved {saved_count} "
                "simulator battery readings."
            )

        except Exception as error:

            print(
                "[Telemetry] Simulator snapshot failed:",
                error
            )

        await asyncio.sleep(
            SIMULATOR_SNAPSHOT_INTERVAL_SECONDS
        )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="EV Battery Intelligence Platform",
    description=(
        "EV battery monitoring, fleet intelligence, "
        "battery health analytics, telemetry and alerts, "
        "predictive battery intelligence, maintenance, "
        "additional battery safety intelligence, "
        "AI battery assistant and GPS charging station support."
    ),
    version="1.3.0",
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
async def startup_event():

    global simulator_snapshot_task

    init_db()

    db = SessionLocal()

    try:

        create_demo_users(db)
        create_fleet(db)
        restore_simulator_state(db)

    finally:

        db.close()

    simulator_snapshot_task = asyncio.create_task(
        simulator_telemetry_worker()
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():

    global simulator_snapshot_task

    if simulator_snapshot_task is not None:

        simulator_snapshot_task.cancel()

        try:
            await simulator_snapshot_task

        except asyncio.CancelledError:
            pass

        simulator_snapshot_task = None


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
        "version": "1.3.0",
    }


# ============================================================
# REGISTER EXISTING API ROUTERS
# ============================================================

app.include_router(auth_router)
app.include_router(vehicles_router)
app.include_router(telemetry_router)
app.include_router(analytics_router)
app.include_router(alerts_router)
app.include_router(settings_router)
app.include_router(notifications_router)
app.include_router(reports_router)
app.include_router(battery_intelligence_router)

app.include_router(advanced_intelligence_router)
app.include_router(battery_intelligence_plus_router)
app.include_router(voltiq_assistant_router)


# ============================================================
# FRONTEND FILES
# no-cache makes browsers revalidate on each load (cheap, uses the
# ETag), so a frontend update is picked up without a hard refresh.
# ============================================================

def frontend_file(name):

    return FileResponse(
        FRONTEND_DIR / name,
        headers={"Cache-Control": "no-cache"},
    )


# ============================================================
# FRONTEND HOME
# ============================================================

@app.get("/")
def home():

    return frontend_file("index.html")


# ============================================================
# MAIN FRONTEND FILES
# ============================================================

@app.get("/app.js")
def javascript():

    return frontend_file("app.js")


@app.get("/styles.css")
def stylesheet():

    return frontend_file("styles.css")


# ============================================================
# BATTERY INTELLIGENCE FRONTEND FILES
# ============================================================

@app.get("/battery-intelligence.js")
def battery_intelligence():

    return frontend_file("battery-intelligence.js")


@app.get("/battery-intelligence-api.js")
def battery_intelligence_api():

    return frontend_file("battery-intelligence-api.js")


# ============================================================
# ADVANCED INTELLIGENCE FRONTEND FILES
# ============================================================

@app.get("/advanced-intelligence.js")
def advanced_intelligence_javascript():

    return frontend_file("advanced-intelligence.js")


@app.get("/advanced-intelligence.css")
def advanced_intelligence_stylesheet():

    return frontend_file("advanced-intelligence.css")


@app.get("/battery-protection-intelligence.js")
def battery_protection_intelligence_javascript():

    return frontend_file("battery-protection-intelligence.js")


# ============================================================
# VOLTIQ ASSISTANT FRONTEND FILES
# ============================================================

@app.get("/voltiq-assistant.js")
def voltiq_assistant_javascript():

    return frontend_file("voltiq-assistant.js")


@app.get("/voltiq-assistant.css")
def voltiq_assistant_stylesheet():

    return frontend_file("voltiq-assistant.css")