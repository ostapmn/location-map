import django_filters as filters
from django.db.models import F, Q

from .models import Location


class NullsLastOrderingFilter(filters.OrderingFilter):
    """Ordering where locations without reviews (NULL rating) always sort last, with a stable tie-break."""

    def filter(self, qs, value):
        if not value:
            return qs
        ordering = []
        for param in value:
            field = super().get_ordering_value(param)
            expr = F(field.lstrip("-"))
            ordering.append(expr.desc(nulls_last=True) if field.startswith("-") else expr.asc(nulls_last=True))
        return qs.order_by(*ordering, "-id")


class LocationFilter(filters.FilterSet):
    search = filters.CharFilter(method="filter_search", label="Search in title and description")
    category = filters.NumberFilter(field_name="category_id")
    author = filters.NumberFilter(field_name="author_id")
    min_rating = filters.NumberFilter(field_name="avg_rating", lookup_expr="gte")
    max_rating = filters.NumberFilter(field_name="avg_rating", lookup_expr="lte")
    ordering = NullsLastOrderingFilter(fields=["created_at", "avg_rating", "popularity"])

    class Meta:
        model = Location
        fields = []

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value))
