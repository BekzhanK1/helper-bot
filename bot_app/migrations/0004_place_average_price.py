# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot_app", "0003_alter_category_options_alter_city_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="place",
            name="average_price",
            field=models.IntegerField(
                blank=True, default=0, help_text="Средний чек в тенге (KZT)", null=True),
        ),
    ]
