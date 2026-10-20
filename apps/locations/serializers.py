from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Category, Location


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class LocationSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)
    avg_rating = serializers.SerializerMethodField()
    reviews_count = serializers.IntegerField(read_only=True)
    views_7d = serializers.IntegerField(read_only=True)
    popularity = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            "id", "title", "description", "category", "address",
            "latitude", "longitude", "author", "author_username",
            "avg_rating", "reviews_count", "views_7d", "popularity",
            "created_at", "updated_at",
        ]
        read_only_fields = ["author", "created_at", "updated_at"]

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_avg_rating(self, obj):
        return None if obj.avg_rating is None else round(obj.avg_rating, 2)

    @extend_schema_field(serializers.FloatField())
    def get_popularity(self, obj):
        return round(obj.popularity, 2)
