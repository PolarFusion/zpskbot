from __future__ import annotations

from datetime import datetime, timezone

from apscheduler.schedulers import SchedulerNotRunningError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from db.repositories import TrackedChatRepository
from services.analytics_service import AnalyticsService


class SummaryScheduler:
    def __init__(
        self,
        analytics_service: AnalyticsService,
        tracked_chat_repo: TrackedChatRepository,
        hour_utc: int,
        minute_utc: int,
        weekly_day_of_week: str,
        timezone: str,
    ) -> None:
        self.analytics_service = analytics_service
        self.tracked_chat_repo = tracked_chat_repo
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.hour_utc = hour_utc
        self.minute_utc = minute_utc
        self.weekly_day_of_week = weekly_day_of_week

    def start(self) -> None:
        self.scheduler.add_job(
            self._run_daily,
            trigger=CronTrigger(hour=self.hour_utc, minute=self.minute_utc),
            id="daily_summary",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_weekly,
            trigger=CronTrigger(day_of_week=self.weekly_day_of_week, hour=self.hour_utc, minute=self.minute_utc),
            id="weekly_summary",
            replace_existing=True,
        )
        self.scheduler.start()

    async def _run_daily(self) -> None:
        target_date = datetime.now(timezone.utc).date()
        for chat_id in await self.tracked_chat_repo.list_tracked_chat_ids():
            await self.analytics_service.build_daily_summary(chat_id, target_date)

    async def _run_weekly(self) -> None:
        for chat_id in await self.tracked_chat_repo.list_tracked_chat_ids():
            await self.analytics_service.build_weekly_summary(chat_id)

    def shutdown(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
        except SchedulerNotRunningError:
            pass
