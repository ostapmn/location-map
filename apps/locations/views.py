from django.core.cache import cache
from django.db.models import ProtectedError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .cache import LIST_TTL, list_cache_key
from .export import export_response, locations_dataframe
from .filters import LocationFilter
from .models import Category, Location, LocationView
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin
from .serializers import CategorySerializer, LocationSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Category has locations and cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )


VIEW_TTL = 60 * 60  # one counted view per viewer per hour


def record_view(request, location):
    """Count a view unless this user/IP already viewed the location within the last hour."""
    viewer = f"u{request.user.id}" if request.user.is_authenticated else f"ip{request.META.get('REMOTE_ADDR')}"
    if cache.add(f"view:{location.pk}:{viewer}", 1, VIEW_TTL):
        LocationView.objects.create(location=location)
        return True
    return False


class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]
    filterset_class = LocationFilter

    def get_queryset(self):
        return (
            Location.objects.select_related("author", "category")
            .with_stats()
            .order_by("-created_at", "-id")
        )

    def list(self, request, *args, **kwargs):
        key = list_cache_key(request.get_full_path())
        data = cache.get(key)
        if data is None:
            data = super().list(request, *args, **kwargs).data
            cache.set(key, data, LIST_TTL)
        return Response(data)

    @extend_schema(
        parameters=[OpenApiParameter("format", str, enum=["json", "csv"], default="json")],
        responses={200: OpenApiTypes.BINARY},
    )
    @action(detail=False, methods=["get"])
    def export(self, request):
        """Export all locations matching the list filters (no pagination) as JSON or CSV."""
        fmt = request.query_params.get("format", "json").lower()
        if fmt not in ("json", "csv"):
            return Response({"format": ["Must be 'json' or 'csv'."]}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.filter_queryset(self.get_queryset())
        return export_response(locations_dataframe(queryset), fmt)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if record_view(request, instance):
            instance = self.get_object()  # refresh views_7d / popularity
        return Response(self.get_serializer(instance).data)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

    def perform_update(self, serializer):
        serializer.save()
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)
