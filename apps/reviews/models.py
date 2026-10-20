from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.locations.models import Location


class Review(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["location", "author"], name="unique_review_per_user")
        ]

    def __str__(self):
        return f"{self.author} -> {self.location} ({self.rating})"


class ReviewVote(models.Model):
    LIKE = 1
    DISLIKE = -1

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_votes"
    )
    value = models.SmallIntegerField(choices=[(LIKE, "Like"), (DISLIKE, "Dislike")])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="unique_vote_per_user")
        ]
