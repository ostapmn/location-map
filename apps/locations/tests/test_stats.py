from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location, LocationView
from apps.reviews.models import Review

User = get_user_model()


class StatsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.ann = User.objects.create_user("ann", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        cat = Category.objects.create(name="Parks")
        self.loc = Location.objects.create(
            title="L", description="d", category=cat, address="a",
            latitude=1, longitude=1, author=self.ann,
        )
        self.url = f"/api/locations/{self.loc.id}/"

    def test_no_reviews_means_null_rating_and_zero_popularity(self):
        data = self.client.get("/api/locations/").data["results"][0]
        self.assertIsNone(data["avg_rating"])
        self.assertEqual(data["reviews_count"], 0)
        self.assertEqual(data["popularity"], 0)

    def test_rating_and_popularity_computed(self):
        Review.objects.create(location=self.loc, author=self.ann, rating=5)
        Review.objects.create(location=self.loc, author=self.bob, rating=2)
        data = self.client.get("/api/locations/").data["results"][0]
        self.assertEqual(data["avg_rating"], 3.5)
        self.assertEqual(data["reviews_count"], 2)
        # 3.5*2 + 2 + 0*0.1
        self.assertAlmostEqual(data["popularity"], 9.0)

    def test_detail_counts_one_view_per_viewer_per_hour(self):
        self.assertEqual(self.client.get(self.url).data["views_7d"], 1)
        self.assertEqual(self.client.get(self.url).data["views_7d"], 1)
        self.assertEqual(LocationView.objects.count(), 1)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.url).data["views_7d"], 2)
        self.client.get(self.url)
        self.assertEqual(LocationView.objects.count(), 2)

    def test_view_counted_again_after_ttl(self):
        self.client.get(self.url)
        cache.clear()  # simulates the 1h key expiring
        self.client.get(self.url)
        self.assertEqual(LocationView.objects.count(), 2)

    def test_only_last_7_days_counted(self):
        LocationView.objects.create(location=self.loc)
        old = LocationView.objects.create(location=self.loc)
        LocationView.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=8))
        data = self.client.get("/api/locations/").data["results"][0]
        self.assertEqual(data["views_7d"], 1)

    def test_list_does_not_count_views(self):
        self.client.get("/api/locations/")
        self.assertEqual(LocationView.objects.count(), 0)

    def test_stats_not_multiplied_by_joins(self):
        for i in range(3):
            LocationView.objects.create(location=self.loc)
        Review.objects.create(location=self.loc, author=self.ann, rating=4)
        Review.objects.create(location=self.loc, author=self.bob, rating=2)
        data = self.client.get("/api/locations/").data["results"][0]
        self.assertEqual((data["reviews_count"], data["views_7d"], data["avg_rating"]), (2, 3, 3.0))

    def test_create_response_includes_stats(self):
        self.client.force_login(self.ann)
        resp = self.client.post("/api/locations/", {
            "title": "N", "description": "d", "category": self.loc.category_id,
            "address": "a", "latitude": "1", "longitude": "1",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["reviews_count"], 0)
