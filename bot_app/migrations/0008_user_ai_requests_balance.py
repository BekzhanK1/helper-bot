# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot_app', '0007_guidecategory_and_update_guide'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='ai_requests_balance',
            field=models.IntegerField(
                default=10, help_text='Количество доступных запросов к AI-помощнику'),
        ),
    ]
