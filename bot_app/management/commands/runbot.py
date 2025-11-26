import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def setup_django() -> None:
    """
    Ensure Django is initialised when the command is executed
    outside the usual manage.py entrypoint.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django  # pylint: disable=import-outside-toplevel

    if not settings.configured:
        django.setup()


class Command(BaseCommand):
    help = "Run the City Guide Telegram bot."

    def handle(self, *args, **options):
        setup_django()
        token = settings.BOT_TOKEN
        if not token:
            raise CommandError(
                "BOT_TOKEN is not set in environment or settings.")

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )

        asyncio.run(self._run_polling(token))

    async def _run_polling(self, token: str) -> None:
        from bot_app.handlers import get_bot_router  # import after setup

        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher()
        dp.include_router(get_bot_router())

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
