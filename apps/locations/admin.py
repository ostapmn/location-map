from django.contrib import admin

from .models import Category, Location

admin.site.register(Category)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "author", "is_deleted"]

    def get_queryset(self, request):
        return Location.all_objects.all()
