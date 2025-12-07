from django.contrib import admin

try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    UnfoldModelAdmin = admin.ModelAdmin

from .models import Category, City, Guide, GuideCategory, Place, Review, User


@admin.register(City)
class CityAdmin(UnfoldModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(UnfoldModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(GuideCategory)
class GuideCategoryAdmin(UnfoldModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class UserAdmin(UnfoldModelAdmin):
    list_display = (
        "telegram_id",
        "username",
        "city",
        "role",
        "status",
        "balance_requests",
        "reputation_points",
    )
    list_filter = ("role", "status", "city")
    search_fields = ("telegram_id", "username", "full_name")
    readonly_fields = ("telegram_id",)
    list_editable = ("balance_requests", "reputation_points")
    fields = (
        "telegram_id",
        "username",
        "full_name",
        "city",
        "role",
        "status",
        "balance_requests",
        "reputation_points",
    )


@admin.register(Place)
class PlaceAdmin(UnfoldModelAdmin):
    list_display = ("name", "category", "city", "is_pinned",
                    "avg_rating", "review_count")
    search_fields = ("name",)
    list_filter = ("category", "city", "is_pinned")


@admin.register(Review)
class ReviewAdmin(UnfoldModelAdmin):
    list_display = ("user", "place", "rating", "status")
    list_filter = ("status",)
    list_editable = ("status",)


@admin.register(Guide)
class GuideAdmin(UnfoldModelAdmin):
    list_display = ("topic", "category", "city")
    list_filter = ("category", "city")
    search_fields = ("topic", "city__name", "category__name")
