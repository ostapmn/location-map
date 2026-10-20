import csv
import io
import json

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location
from apps.reviews.models import Review

User = get_user_model()
URL = "/api/locations/export/"


class ExportTests(APITestCase):
    def setUp(self):
        self.ann = User.objects.create_user("ann", password="x")
        self.parks = Category.objects.create(name="Parks")
        self.cafes = Category.objects.create(name="Cafes")
        self.park = self.make("Central Park", self.parks)
        self.cafe = self.make("Кафе Блакитне", self.cafes)
        Review.objects.create(location=self.park, author=self.ann, rating=5)

    def make(self, title, category):
        return Location.objects.create(
            title=title, description="d", category=category, address="a",
            latitude="50.45", longitude="30.52", author=self.ann,
        )

    def test_json_default_and_headers(self):
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp["Content-Type"])
        self.assertIn("locations.json", resp["Content-Disposition"])
        rows = json.loads(resp.content)
        self.assertEqual(len(rows), 2)
        park = next(r for r in rows if r["title"] == "Central Park")
        self.assertEqual((park["category"], park["author"], park["avg_rating"]), ("Parks", "ann", 5.0))
        self.assertEqual(park["latitude"], 50.45)

    def test_csv(self):
        resp = self.client.get(URL + "?format=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertIn("locations.csv", resp["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(resp.content.decode("utf-8"))))
        self.assertEqual(len(rows), 2)
        self.assertIn("Кафе Блакитне", [r["title"] for r in rows])
        self.assertEqual(list(rows[0].keys())[:3], ["id", "title", "description"])

    def test_applies_list_filters_without_pagination(self):
        for i in range(12):
            self.make(f"Extra {i}", self.parks)
        self.assertEqual(len(json.loads(self.client.get(URL).content)), 14)  # > page size
        rows = json.loads(self.client.get(URL + f"?category={self.cafes.id}").content)
        self.assertEqual([r["title"] for r in rows], ["Кафе Блакитне"])
        rows = json.loads(self.client.get(URL + "?min_rating=4").content)
        self.assertEqual([r["title"] for r in rows], ["Central Park"])

    def test_ordering_applies(self):
        rows = json.loads(self.client.get(URL + "?ordering=created_at").content)
        self.assertEqual(rows[0]["title"], "Central Park")

    def test_soft_deleted_excluded(self):
        self.cafe.delete()
        self.assertEqual(len(json.loads(self.client.get(URL).content)), 1)

    def test_empty_result(self):
        resp = self.client.get(URL + "?search=nothing&format=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode().strip().split(",")[0], "id")
        self.assertEqual(json.loads(self.client.get(URL + "?search=nothing").content), [])

    def test_bad_format_and_bad_filter(self):
        self.assertEqual(self.client.get(URL + "?format=xml").status_code, 400)
        self.assertEqual(self.client.get(URL + "?min_rating=abc").status_code, 400)

    def test_csv_formula_injection_escaped(self):
        self.make("=HYPERLINK(1)", self.parks)
        body = self.client.get(URL + "?format=csv").content.decode()
        self.assertIn("'=HYPERLINK(1)", body)
