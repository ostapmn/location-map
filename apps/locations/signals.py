from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import invalidate_list_cache
from .models import Location


@receiver([post_save, post_delete], sender=Location)
def invalidate_on_location_change(sender, **kwargs):
    # soft delete goes through save(), so it is covered by post_save
    invalidate_list_cache()


@receiver([post_save, post_delete], sender="reviews.Review")
def invalidate_on_review_change(sender, **kwargs):
    invalidate_list_cache()
