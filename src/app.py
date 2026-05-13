from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.handlers import build_router
from config import get_settings
from db.database import Database
from db.repositories import EmbeddingRepository, MessageRepository, SummaryRepository, TrackedChatRepository
from db.schema import init_schema
from jobs.scheduler import SummaryScheduler
from logging_setup import setup_logging
from services.analytics_service import AnalyticsService
from services.llm_service import LLMService
from services.memory_service import MemoryService

logger = logging.getLogger(__name__)


async def build_runtime() -> tuple[Dispatcher, Bot, SummaryScheduler, Database]:
    settings = get_settings()

    db = Database(settings.database_url)
    await db.connect()
    await init_schema(db)

    message_repo = MessageRepository(db)
    embedding_repo = EmbeddingRepository(db)
    summary_repo = SummaryRepository(db)
    tracked_chat_repo = TrackedChatRepository(db)

    llm_service = LLMService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        embedding_model=settings.openai_embedding_model,
    )
    memory_service = MemoryService(message_repo, embedding_repo, llm_service)
    analytics_service = AnalyticsService(message_repo, summary_repo, llm_service)

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    router = build_router(
        llm_service=llm_service,
        memory_service=memory_service,
        analytics_service=analytics_service,
        tracked_chat_repo=tracked_chat_repo,
        admin_ids=settings.admin_id_set,
        bot_username=settings.bot_username,
        max_user_message_chars=settings.max_user_message_chars,
        max_embedding_chars=settings.max_embedding_chars,
    )
    dp.include_router(router)

    scheduler = SummaryScheduler(
        analytics_service=analytics_service,
        tracked_chat_repo=tracked_chat_repo,
        hour_utc=settings.summary_hour_utc,
        minute_utc=settings.summary_minute_utc,
        weekly_day_of_week=settings.weekly_day_of_week,
        timezone=settings.tz,
    )

    return dp, bot, scheduler, db


async def run_polling(dp: Dispatcher, bot: Bot, scheduler: SummaryScheduler) -> None:
    settings = get_settings()
    scheduler.start()
    try:
        await dp.start_polling(bot, allowed_updates=settings.polling_updates)
    finally:
        scheduler.shutdown()


async def run_webhook(dp: Dispatcher, bot: Bot, scheduler: SummaryScheduler) -> None:
    settings = get_settings()

    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    full_webhook_url = f"{settings.webhook_base_url.rstrip('/')}{settings.webhook_path}"
    await bot.set_webhook(full_webhook_url)

    scheduler.start()
    try:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)
        await site.start()
        logger.info("Webhook started on %s:%s", settings.webhook_host, settings.webhook_port)
        while True:
            await asyncio.sleep(3600)
    finally:
        scheduler.shutdown()
        await bot.delete_webhook(drop_pending_updates=False)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    dp, bot, scheduler, db = await build_runtime()

    try:
        if settings.use_webhook:
            await run_webhook(dp, bot, scheduler)
        else:
            await run_polling(dp, bot, scheduler)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
