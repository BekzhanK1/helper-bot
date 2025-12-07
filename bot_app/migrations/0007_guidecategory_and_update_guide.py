# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot_app", "0006_guide_category"),
    ]

    operations = [
        # Создаем модель GuideCategory
        migrations.CreateModel(
            name="GuideCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(unique=True)),
            ],
            options={
                "verbose_name": "Guide Category",
                "verbose_name_plural": "Guide Categories",
            },
        ),
        # Удаляем старое поле category из Guide (которое ссылалось на Category)
        migrations.RemoveField(
            model_name="guide",
            name="category",
        ),
        # Добавляем новое поле category в Guide (которое ссылается на GuideCategory)
        migrations.AddField(
            model_name="guide",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="guides",
                to="bot_app.guidecategory",
            ),
        ),
    ]
