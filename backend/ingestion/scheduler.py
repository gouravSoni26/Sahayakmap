import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler # pyright: ignore[reportMissingImports]
from apscheduler.triggers.interval import IntervalTrigger # pyright: ignore[reportMissingImports]
from config import settings

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def start_scheduler():
    if settings.simulation_mode:
        logger.info("Simulation mode — ingestion scheduler NOT started")
        return

    from ingestion.cwc_gauge import fetch_gauge_readings
    from ingestion.open_meteo import fetch_weather_forecasts
    from ingestion.synthetic_social import generate_social_reports
    from ingestion.synthetic_reports import generate_district_reports
    from intelligence.briefing import generate_situation_brief
    from intelligence.alerts import run_alert_checks

    _scheduler.add_job(fetch_gauge_readings, IntervalTrigger(minutes=15), id="gauges", replace_existing=True)
    _scheduler.add_job(fetch_weather_forecasts, IntervalTrigger(minutes=30), id="weather", replace_existing=True)
    _scheduler.add_job(generate_social_reports, IntervalTrigger(minutes=10), id="social", replace_existing=True)
    _scheduler.add_job(generate_district_reports, IntervalTrigger(hours=2), id="district_reports", replace_existing=True)
    _scheduler.add_job(run_alert_checks, IntervalTrigger(minutes=5), id="alerts", replace_existing=True)
    _scheduler.add_job(
        generate_situation_brief,
        IntervalTrigger(minutes=settings.briefing_interval_min),
        id="briefing",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Ingestion scheduler started with %d jobs", len(_scheduler.get_jobs()))


def get_scheduler_jobs() -> list:
    """Return the list of registered APScheduler jobs (empty if scheduler not started)."""
    return _scheduler.get_jobs()


async def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Ingestion scheduler stopped")
