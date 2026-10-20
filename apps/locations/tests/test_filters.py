from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location, LocationView
from apps.reviews.models import Review

User = get_user_model()


class FilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ann = User.objects.create_user("ann", password="x")
        cls.bob = User.objects.create_user("bob", password="x")
        cls.parks = Category.objects.create(name="Parks")
        cls.cafes = Category.objects.create(name="Cafes")
        cls.park = cls.make("Central Park", "green and quiet", cls.parks, cls.ann)
        cls.cafe = cls.make("Blue Cafe", "great coffee in the park", cls.cafes, cls.bob)
        cls.bar = cls.make("Old Bar", "cocktails", cls.cafes, cls.ann)
        Review.objects.create(location=cls.park, author=cls.ann, rating=5)
        Review.objects.create(location=cls.park, author=cls.bob, rating=4)
        Review.objects.create(location=cls.cafe, author=cls.ann, rating=2)
        for _ in range(3):
            LocationView.objects.create(location=cls.bar)

    @staticmethod
    def make(title, description, category, author):
        return Location.objects.create(
            title=title, description=description, category=category, address="a",
            latitude=1, longitude=1, author=author,
        )

    def titles(self, query=""):
        resp = self.client.get(f"/api/locations/?{query}")
        self.assertEqual(resp.status_code, 200, resp.data)
        return [r["title"] for r in resp.data["results"]]

    def test_search_title_and_description(self):
        self.assertCountEqual(self.titles("search=park"), ["Central Park", "Blue Cafe"])
        self.assertEqual(self.titles("search=COCKTAIL"), ["Old Bar"])

    def test_filter_category_and_author(self):
        self.assertCountEqual(self.titles(f"category={self.cafes.id}"), ["Blue Cafe", "Old Bar"])
        self.assertCountEqual(self.titles(f"author={self.ann.id}"), ["Central Park", "Old Bar"])
        self.assertEqual(self.titles(f"author={self.ann.id}&category={self.cafes.id}"), ["Old Bar"])

    def test_filter_rating(self):
        self.assertEqual(self.titles("min_rating=4"), ["Central Park"])
        self.assertEqual(self.titles("max_rating=3"), ["Blue Cafe"])
        self.assertEqual(len(self.titles("min_rating=2&max_rating=5")), 2)

    def test_ordering(self):
        self.assertEqual(self.titles("ordering=-created_at"), ["Old Bar", "Blue Cafe", "Central Park"])
        self.assertEqual(self.titles("ordering=created_at"), ["Central Park", "Blue Cafe", "Old Bar"])
        # NULL rating (Old Bar) sorts last in both directions
        self.assertEqual(self.titles("ordering=-avg_rating"), ["Central Park", "Blue Cafe", "Old Bar"])
        self.assertEqual(self.titles("ordering=avg_rating"), ["Blue Cafe", "Central Park", "Old Bar"])
        # Central Park: 4.5*2+2=11, Blue Cafe: 2*2+1=5, Old Bar: 3*0.1=0.3
        self.assertEqual(self.titles("ordering=-popularity"), ["Central Park", "Blue Cafe", "Old Bar"])
        self.assertEqual(self.titles("ordering=popularity"), ["Old Bar", "Blue Cafe", "Central Park"])

    def test_invalid_params_return_400(self):
        self.assertEqual(self.client.get("/api/locations/?ordering=title").status_code, 400)
        self.assertEqual(self.client.get("/api/locations/?min_rating=abc").status_code, 400)

    def test_pagination(self):
        for i in range(12):
            self.make(f"Extra {i}", "x", self.parks, self.ann)
        page1 = self.client.get("/api/locations/").data
        self.assertEqual((page1["count"], len(page1["results"])), (15, 10))
        self.assertIsNotNone(page1["next"])
        page2 = self.client.get("/api/locations/?page=2").data
        self.assertEqual(len(page2["results"]), 5)
        ids = [r["id"] for r in page1["results"] + page2["results"]]
        self.assertEqual(len(set(ids)), 15)
