from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


# popularity = avg_rating * 2 + reviews_count + views_7d * 0.1
RATING_WEIGHT = 2.0
REVIEWS_WEIGHT = 1.0
VIEWS_WEIGHT = 0.1
VIEWS_WINDOW = timedelta(days=7)


class LocationQuerySet(models.QuerySet):
    def with_stats(self):
        """Compute rating, review count, weekly views and popularity on the fly."""
        recent_views = (
            LocationView.objects.filter(
                location=OuterRef("pk"), created_at__gte=timezone.now() - VIEWS_WINDOW
            )
            .values("location")
            .annotate(c=Count("pk"))
            .values("c")
        )
        return self.annotate(
            avg_rating=Avg("reviews__rating"),
            reviews_count=Count("reviews"),
            views_7d=Coalesce(Subquery(recent_views), 0),
        ).annotate(
            popularity=ExpressionWrapper(
                Coalesce(F("avg_rating"), 0.0) * RATING_WEIGHT
                + F("reviews_count") * REVIEWS_WEIGHT
                + F("views_7d") * VIEWS_WEIGHT,
                output_field=FloatField(),
            )
        )


class LocationManager(models.Manager.from_queryset(LocationQuerySet)):
    """Default manager: hides soft-deleted locations."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Location(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="locations")
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = LocationManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])


class LocationView(models.Model):
    """One counted view of a location (at most one per viewer per hour)."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="views")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
