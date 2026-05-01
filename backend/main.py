import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api import health, map_data, flood_map, alerts, briefing, assets, districts, scenarios
from ingestion.scheduler import start_scheduler, stop_scheduler, get_scheduler_jobs

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SahayakMap API...")
    await start_scheduler()
    if not settings.simulation_mode:
        jobs = get_scheduler_jobs()
        if not jobs:
            raise RuntimeError("Scheduler has no jobs registered. Check ingestion setup.")
        logger.info("Scheduler running with %d jobs: %s", len(jobs), [j.id for j in jobs])
    yield
    logger.info("Shutting down SahayakMap API...")
    await stop_scheduler()


app = FastAPI(
    title="SahayakMap API",
    description="Real-time flood intelligence for the Mahanadi Basin",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(map_data.router, prefix="/api", tags=["map"])
app.include_router(flood_map.router, prefix="/api", tags=["map"])
app.include_router(alerts.router, prefix="/api", tags=["alerts"])
app.include_router(briefing.router, prefix="/api", tags=["briefing"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(districts.router, prefix="/api", tags=["districts"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
