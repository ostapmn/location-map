from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location, LocationView

User = get_user_model()


def seed(*args):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


class SeedTests(APITestCase):
    def test_creates_30_locations_and_is_idempotent(self):
        seed()
        self.assertEqual(Location.objects.count(), 30)
        self.assertEqual(Category.objects.count(), 5)
        views = LocationView.objects.count()
        self.assertIn("already exists", seed())
        self.assertEqual((Location.objects.count(), LocationView.objects.count()), (30, views))

    def test_reset_recreates_without_duplicates(self):
        seed()
        seed("--reset")
        self.assertEqual(Location.objects.count(), 30)
        self.assertEqual(User.objects.count(), 5)
        self.assertEqual(Category.objects.count(), 5)

    def test_data_exercises_api(self):
        seed()
        resp = self.client.get("/api/locations/?ordering=-popularity")
        self.assertEqual((resp.status_code, resp.data["count"], len(resp.data["results"])), (200, 30, 10))
        popularity = [r["popularity"] for r in resp.data["results"]]
        self.assertEqual(popularity, sorted(popularity, reverse=True))
        self.assertEqual(self.client.get("/api/locations/export/?format=csv").status_code, 200)
