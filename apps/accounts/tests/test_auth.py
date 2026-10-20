import re

from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APIClient, APITestCase

User = get_user_model()
PASSWORD = "Str0ng-pass-123"


class AuthTests(APITestCase):
    def test_register_logs_in_and_rejects_duplicate_email(self):
        data = {"username": "ann", "email": "ann@example.com", "password": PASSWORD}
        resp = self.client.post("/api/auth/register/", data)
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("password", resp.data)
        self.assertIn("sessionid", resp.cookies)
        resp = self.client.post("/api/auth/register/", {**data, "username": "ann2"})
        self.assertEqual(resp.status_code, 400)

    def test_weak_password_rejected(self):
        resp = self.client.post(
            "/api/auth/register/", {"username": "bob", "email": "b@example.com", "password": "123"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_login_and_logout(self):
        User.objects.create_user("ann", "ann@example.com", PASSWORD)
        bad = self.client.post("/api/auth/login/", {"username": "ann", "password": "x"})
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post("/api/auth/login/", {"username": "ann", "password": PASSWORD})
        self.assertEqual(ok.status_code, 200)
        self.assertIn("sessionid", ok.cookies)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        # session is gone: logout requires authentication
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 403)

    def test_csrf_enforced_for_logged_in_session(self):
        User.objects.create_user("ann", "ann@example.com", PASSWORD)
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        resp = client.post(
            "/api/auth/login/", {"username": "ann", "password": PASSWORD}, HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(client.post("/api/auth/logout/").status_code, 403)

    def test_password_reset_flow(self):
        user = User.objects.create_user("ann", "ann@example.com", PASSWORD)
        resp = self.client.post("/api/auth/password-reset/", {"email": "nobody@example.com"})
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(len(mail.outbox), 0)

        resp = self.client.post("/api/auth/password-reset/", {"email": "ann@example.com"})
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        uid = re.search(r"uid: (\S+)", body).group(1)
        token = re.search(r"token: (\S+)", body).group(1)

        bad = self.client.post(
            "/api/auth/password-reset/confirm/", {"uid": uid, "token": "bad", "new_password": "New-pass-4567"}
        )
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post(
            "/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "New-pass-4567"}
        )
        self.assertEqual(ok.status_code, 204)
        user.refresh_from_db()
        self.assertTrue(user.check_password("New-pass-4567"))
        # token is single-use
        again = self.client.post(
            "/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "Other-pass-789"}
        )
        self.assertEqual(again.status_code, 400)
