# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot_app", "0005_review_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="guide",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="guides",
                to="bot_app.category",
            ),
        ),
    ]
