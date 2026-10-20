from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.locations.models import Location
from apps.locations.permissions import IsOwnerOrAdmin

from .models import Review, ReviewVote
from .serializers import ReviewSerializer, VoteSerializer


def reviews_with_votes():
    return Review.objects.select_related("author").annotate(
        likes=Count("votes", filter=Q(votes__value=ReviewVote.LIKE)),
        dislikes=Count("votes", filter=Q(votes__value=ReviewVote.DISLIKE)),
    ).order_by("-created_at", "-id")


class LocationReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """GET/POST /locations/{location_pk}/reviews/"""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_location(self):
        return get_object_or_404(Location, pk=self.kwargs["location_pk"])

    def get_queryset(self):
        return reviews_with_votes().filter(location_id=self.kwargs["location_pk"])

    def perform_create(self, serializer):
        location = self.get_location()
        # The unique constraint is the source of truth: a check-then-insert would race under concurrent requests.
        try:
            with transaction.atomic():
                serializer.save(location=location, author=self.request.user)
        except IntegrityError:
            raise ValidationError({"detail": "You have already reviewed this location."})


class ReviewViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]

    def get_queryset(self):
        return reviews_with_votes()

    @extend_schema(request=VoteSerializer, responses={200: ReviewSerializer})
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def vote(self, request, pk=None):
        review = self.get_object()
        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                ReviewVote.objects.create(
                    review=review, user=request.user, value=serializer.validated_data["value"]
                )
        except IntegrityError:
            return Response(
                {"detail": "You have already voted on this review."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ReviewSerializer(self.get_object()).data)
