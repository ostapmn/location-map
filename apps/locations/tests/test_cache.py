from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location

User = get_user_model()
LIST = "/api/locations/"


class ListCacheTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.ann = User.objects.create_user("ann", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        self.cat = Category.objects.create(name="Parks")
        self.loc = Location.objects.create(
            title="L", description="d", category=self.cat, address="a",
            latitude=1, longitude=1, author=self.ann,
        )
        self.payload = {
            "title": "New", "description": "d", "category": self.cat.id,
            "address": "a", "latitude": "1", "longitude": "1",
        }

    def count(self):
        return self.client.get(LIST).data["count"]

    def test_second_request_served_from_cache_without_queries(self):
        self.client.get(LIST)
        with self.assertNumQueries(0):
            resp = self.client.get(LIST)
        self.assertEqual(resp.data["count"], 1)

    def test_each_query_string_cached_separately(self):
        self.assertEqual(self.client.get(LIST + "?search=zzz").data["count"], 0)
        self.assertEqual(self.client.get(LIST + "?search=L").data["count"], 1)
        self.assertEqual(self.client.get(LIST + "?search=zzz").data["count"], 0)

    def test_invalidated_on_create(self):
        self.assertEqual(self.count(), 1)
        self.client.force_login(self.ann)
        self.assertEqual(self.client.post(LIST, self.payload).status_code, 201)
        self.assertEqual(self.count(), 2)

    def test_invalidated_on_update(self):
        self.client.get(LIST)
        self.client.force_login(self.ann)
        self.client.patch(f"{LIST}{self.loc.id}/", {"title": "Renamed"})
        self.assertEqual(self.client.get(LIST).data["results"][0]["title"], "Renamed")

    def test_invalidated_on_soft_delete(self):
        self.assertEqual(self.count(), 1)
        self.client.force_login(self.ann)
        self.assertEqual(self.client.delete(f"{LIST}{self.loc.id}/").status_code, 204)
        self.assertEqual(self.count(), 0)

    def test_invalidated_on_new_review(self):
        self.assertIsNone(self.client.get(LIST).data["results"][0]["avg_rating"])
        self.client.force_login(self.bob)
        resp = self.client.post(f"{LIST}{self.loc.id}/reviews/", {"rating": 4})
        self.assertEqual(resp.status_code, 201)
        data = self.client.get(LIST).data["results"][0]
        self.assertEqual((data["avg_rating"], data["reviews_count"]), (4.0, 1))

    def test_invalidated_on_review_update_and_delete(self):
        self.client.force_login(self.bob)
        review_id = self.client.post(f"{LIST}{self.loc.id}/reviews/", {"rating": 4}).data["id"]
        self.assertEqual(self.client.get(LIST).data["results"][0]["avg_rating"], 4.0)
        self.client.patch(f"/api/reviews/{review_id}/", {"rating": 1})
        self.assertEqual(self.client.get(LIST).data["results"][0]["avg_rating"], 1.0)
        self.client.delete(f"/api/reviews/{review_id}/")
        self.assertIsNone(self.client.get(LIST).data["results"][0]["avg_rating"])

    def test_detail_view_does_not_invalidate_list(self):
        self.client.get(LIST)
        self.client.get(f"{LIST}{self.loc.id}/")
        with self.assertNumQueries(0):
            self.client.get(LIST)
