# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot_app", "0004_place_average_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="price",
            field=models.IntegerField(
                blank=True, help_text="Сумма чека в тенге (KZT) (опционально)", null=True),
        ),
    ]
