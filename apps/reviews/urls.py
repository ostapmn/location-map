from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import LocationReviewViewSet, ReviewViewSet

router = DefaultRouter()
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path(
        "locations/<int:location_pk>/reviews/",
        LocationReviewViewSet.as_view({"get": "list", "post": "create"}),
        name="location-reviews",
    ),
] + router.urls
