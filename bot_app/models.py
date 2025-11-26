from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class City(models.Model):
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "City"
        verbose_name_plural = "Cities"


class User(models.Model):
    class Role(models.TextChoices):
        TOURIST = "tourist", "Турист"
        STUDENT = "student", "Студент"
        LOCAL = "local", "Местный"

    class Status(models.TextChoices):
        NOVICE = "novice", "Novice"
        EXPERT = "expert", "Expert"
        LEGEND = "legend", "Legend"

    telegram_id = models.BigIntegerField(primary_key=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    city = models.ForeignKey(
        City, on_delete=models.SET_NULL, null=True, related_name="users")
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.TOURIST)
    balance_requests = models.IntegerField(default=5)
    reputation_points = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NOVICE)

    def __str__(self) -> str:
        base = self.full_name or self.username or str(self.telegram_id)
        return f"{base} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Bot user"
        verbose_name_plural = "Bot users"


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"


class Place(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255)
    city = models.ForeignKey(
        City, on_delete=models.CASCADE, related_name="places")
    # {"lat": float, "lon": float}
    location = models.JSONField(default=dict, blank=True, null=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="places", blank=True, null=True)  # made optional
    google_place_id = models.CharField(
        max_length=255, unique=True, blank=True, null=True)
    avg_rating = models.FloatField(default=0.0)
    review_count = models.IntegerField(default=0)
    ai_summary = models.TextField(blank=True)
    is_pinned = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Place"
        verbose_name_plural = "Places"


class Review(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reviews")
    place = models.ForeignKey(
        Place, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING)
    is_verified_by_ai = models.BooleanField(default=False)
    photo_ids = models.JSONField(default=list)

    def __str__(self) -> str:
        return f"Review {self.pk} for {self.place}"

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"


class Guide(models.Model):
    topic = models.CharField(max_length=200)
    city = models.ForeignKey(
        City, on_delete=models.CASCADE, related_name="guides")
    content = models.TextField()

    def __str__(self) -> str:
        return f"{self.topic} ({self.city})"

    class Meta:
        verbose_name = "Guide"
        verbose_name_plural = "Guides"
