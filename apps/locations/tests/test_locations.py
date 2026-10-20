from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location

User = get_user_model()


class LocationApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="x")
        self.other = User.objects.create_user("other", password="x")
        self.admin = User.objects.create_user("admin", password="x", is_staff=True)
        self.cat = Category.objects.create(name="Parks")
        self.payload = {
            "title": "Central Park", "description": "Big park", "category": self.cat.id,
            "address": "NYC", "latitude": "40.785091", "longitude": "-73.968285",
        }

    def make_location(self):
        return Location.objects.create(
            title="L", description="d", category=self.cat, address="a",
            latitude=1, longitude=1, author=self.owner,
        )

    def test_guest_can_read_but_not_write(self):
        loc = self.make_location()
        self.assertEqual(self.client.get("/api/locations/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/locations/{loc.id}/").status_code, 200)
        self.assertEqual(self.client.post("/api/locations/", self.payload).status_code, 403)

    def test_create_sets_author_ignoring_payload(self):
        self.client.force_login(self.owner)
        resp = self.client.post("/api/locations/", {**self.payload, "author": self.other.id})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["author"], self.owner.id)

    def test_coordinate_validation(self):
        self.client.force_login(self.owner)
        for field, value in [("latitude", "91"), ("latitude", "-91"), ("longitude", "181")]:
            resp = self.client.post("/api/locations/", {**self.payload, field: value})
            self.assertEqual(resp.status_code, 400, (field, value))

    def test_only_owner_or_admin_can_modify(self):
        loc = self.make_location()
        url = f"/api/locations/{loc.id}/"
        self.client.force_login(self.other)
        self.assertEqual(self.client.patch(url, {"title": "X"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.patch(url, {"title": "X"}).status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.patch(url, {"title": "Y"}).status_code, 200)

    def test_soft_delete(self):
        loc = self.make_location()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.delete(f"/api/locations/{loc.id}/").status_code, 204)
        self.assertEqual(self.client.get(f"/api/locations/{loc.id}/").status_code, 404)
        self.assertEqual(self.client.get("/api/locations/").data["count"], 0)
        self.assertTrue(Location.all_objects.get(pk=loc.id).is_deleted)

    def test_categories_admin_only_writes(self):
        self.assertEqual(self.client.get("/api/categories/").status_code, 200)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post("/api/categories/", {"name": "Bars"}).status_code, 403)
        self.client.force_login(self.admin)
        resp = self.client.post("/api/categories/", {"name": "Bars"})
        self.assertEqual(resp.status_code, 201)
        url = f"/api/categories/{resp.data['id']}/"
        self.assertEqual(self.client.patch(url, {"name": "Pubs"}).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_category_with_locations_cannot_be_deleted(self):
        self.make_location()
        self.client.force_login(self.admin)
        resp = self.client.delete(f"/api/categories/{self.cat.id}/")
        self.assertEqual(resp.status_code, 400)
