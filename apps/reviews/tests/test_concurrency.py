import threading

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.locations.models import Category, Location
from apps.reviews.models import Review, ReviewVote

User = get_user_model()
THREADS = 6


class ConcurrentRequestTests(TransactionTestCase):
    """Parallel duplicate requests must give exactly one 2xx and 400s for the rest, never a 500."""

    def setUp(self):
        self.ann = User.objects.create_user("ann", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        cat = Category.objects.create(name="Parks")
        self.loc = Location.objects.create(
            title="L", description="d", category=cat, address="a",
            latitude=1, longitude=1, author=self.ann,
        )

    def fire(self, user, method, url, data):
        barrier = threading.Barrier(THREADS)
        statuses = []

        def worker():
            client = APIClient(raise_request_exception=False)
            client.force_login(user)
            barrier.wait()
            try:
                statuses.append(getattr(client, method)(url, data).status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return sorted(statuses)

    def test_parallel_duplicate_reviews(self):
        statuses = self.fire(self.bob, "post", f"/api/locations/{self.loc.id}/reviews/", {"rating": 4})
        self.assertEqual(statuses, [201] + [400] * (THREADS - 1))
        self.assertEqual(Review.objects.filter(author=self.bob).count(), 1)

    def test_parallel_duplicate_votes(self):
        review = Review.objects.create(location=self.loc, author=self.ann, rating=3)
        statuses = self.fire(self.bob, "post", f"/api/reviews/{review.id}/vote/", {"value": 1})
        self.assertEqual(statuses, [200] + [400] * (THREADS - 1))
        self.assertEqual(ReviewVote.objects.filter(review=review).count(), 1)
