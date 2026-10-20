from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location
from apps.reviews.models import Review

User = get_user_model()


class ReviewApiTests(APITestCase):
    def setUp(self):
        self.ann = User.objects.create_user("ann", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        cat = Category.objects.create(name="Parks")
        self.loc = Location.objects.create(
            title="L", description="d", category=cat, address="a",
            latitude=1, longitude=1, author=self.ann,
        )
        self.url = f"/api/locations/{self.loc.id}/reviews/"

    def test_guest_can_list_but_not_create(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, {"rating": 5}).status_code, 403)

    def test_create_review_and_rating_bounds(self):
        self.client.force_login(self.bob)
        for bad in (0, 6):
            self.assertEqual(self.client.post(self.url, {"rating": bad}).status_code, 400)
        resp = self.client.post(self.url, {"rating": 4, "comment": "nice"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["author"], self.bob.id)

    def test_duplicate_review_returns_400(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(self.url, {"rating": 4}).status_code, 201)
        resp = self.client.post(self.url, {"rating": 5})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_review_on_missing_location_404(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post("/api/locations/999/reviews/", {"rating": 4}).status_code, 404)

    def test_only_author_edits_review(self):
        review = Review.objects.create(location=self.loc, author=self.bob, rating=3)
        url = f"/api/reviews/{review.id}/"
        self.client.force_login(self.ann)
        self.assertEqual(self.client.patch(url, {"rating": 1}).status_code, 403)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.patch(url, {"rating": 5}).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_vote_once_per_user(self):
        review = Review.objects.create(location=self.loc, author=self.bob, rating=3)
        url = f"/api/reviews/{review.id}/vote/"
        self.assertEqual(self.client.post(url, {"value": 1}).status_code, 403)
        self.client.force_login(self.ann)
        resp = self.client.post(url, {"value": 1})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual((resp.data["likes"], resp.data["dislikes"]), (1, 0))
        self.assertEqual(self.client.post(url, {"value": -1}).status_code, 400)
        self.assertEqual(self.client.post(url, {"value": 5}).status_code, 400)
        self.assertEqual(review.votes.count(), 1)
