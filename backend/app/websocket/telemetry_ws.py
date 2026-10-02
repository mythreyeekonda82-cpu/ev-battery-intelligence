import os

from pathlib import Path

from fastapi import FastAPI

from fastapi.middleware.cors import (
    CORSMiddleware
)

from fastapi.responses import FileResponse

from .database import (
    Base,
    engine
)

from .routers import (
    auth,
    vehicles,
    telemetry,
    alerts,
    analytics
)

from .websocket.telemetry_ws import (
    router as ws_router
)


Base.metadata.create_all(
    bind=engine
)


app = FastAPI(

    title="EV Battery Intelligence",

    version="1.0.0",

    description=(
        "EV Battery Monitoring, "
        "Predictive Intelligence and "
        "Protection Platform"
    )
)


app.add_middleware(

    CORSMiddleware,

    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000"
    ).split(","),

    allow_methods=["*"],

    allow_headers=["*"],

    allow_credentials=True
)


app.include_router(
    auth.router
)

app.include_router(
    vehicles.router
)

app.include_router(
    telemetry.router
)

app.include_router(
    alerts.router
)

app.include_router(
    analytics.router
)

app.include_router(
    ws_router
)


@app.get("/api/config")
def config():

    return {

        "demo_mode":
            os.getenv(
                "DEMO_MODE",
                "true"
            ).lower() == "true",

        "maps":
            bool(
                os.getenv(
                    "GOOGLE_MAPS_API_KEY"
                )
            )
    }


@app.get("/api/health")
def health():

    return {

        "status": "online",

        "service":
            "EV Battery Intelligence",

        "message":
            "EV battery monitoring API is running."
    }


FRONTEND = (
    Path(__file__)
    .resolve()
    .parents[2]
    / "frontend"
)


@app.get("/")
def index():

    return FileResponse(
        FRONTEND / "index.html"
    )