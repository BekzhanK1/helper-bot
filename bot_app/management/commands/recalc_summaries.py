import asyncio

from django.core.management.base import BaseCommand

from bot_app.models import Place
from bot_app.services.ai_service import update_place_summary


class Command(BaseCommand):
    help = "Recalculate AI summaries for all places."

    def handle(self, *args, **options):
        place_ids = list(Place.objects.values_list("id", flat=True))

        async def recalc():
            for place_id in place_ids:
                await update_place_summary(place_id)
                self.stdout.write(f"Updated place #{place_id}")

        asyncio.run(recalc())
        self.stdout.write(self.style.SUCCESS("AI summaries recalculated."))

