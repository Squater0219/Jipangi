from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase


class AuthenticationAPITests(APITestCase):
    def setUp(self):
        cache.clear()

    def signup(self, **overrides):
        payload = {
            "username": "사용자",
            "email": "USER@example.com",
            "password": "safe-password-1234",
            **overrides,
        }
        return self.client.post("/api/v1/auth/signup", payload, format="json")

    def test_signup_returns_tokens_and_normalizes_email(self):
        response = self.signup()

        self.assertEqual(response.status_code, 201)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)
        self.assertEqual(response.data["user"]["email"], "user@example.com")
        self.assertEqual(get_user_model().objects.get().email, "user@example.com")

    def test_duplicate_email_returns_conflict_code(self):
        self.signup()

        response = self.signup(email="user@EXAMPLE.com")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "EMAIL_ALREADY_EXISTS")

    def test_login_refresh_logout_and_me(self):
        signup_response = self.signup()
        access_token = signup_response.data["access_token"]
        refresh_token = signup_response.data["refresh_token"]

        login_response = self.client.post(
            "/api/v1/auth/login",
            {"email": "user@example.com", "password": "safe-password-1234"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

        refresh_response = self.client.post(
            "/api/v1/auth/token/refresh",
            {"refresh_token": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotEqual(refresh_response.data["refresh_token"], refresh_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_response = self.client.get("/api/v1/users/me")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["email"], "user@example.com")

        logout_response = self.client.post(
            "/api/v1/auth/logout",
            {"refresh_token": refresh_response.data["refresh_token"]},
            format="json",
        )
        self.assertEqual(logout_response.status_code, 204)

        rejected_refresh = self.client.post(
            "/api/v1/auth/token/refresh",
            {"refresh_token": refresh_response.data["refresh_token"]},
            format="json",
        )
        self.assertEqual(rejected_refresh.status_code, 401)
        self.assertEqual(rejected_refresh.data["error"]["code"], "INVALID_TOKEN")

    def test_login_failure_is_generic(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": "missing@example.com", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "INVALID_CREDENTIALS")

    def test_login_is_rate_limited_by_email_and_ip(self):
        for _ in range(5):
            response = self.client.post(
                "/api/v1/auth/login",
                {"email": "target@example.com", "password": "wrong-password"},
                format="json",
            )
            self.assertEqual(response.status_code, 401)

        limited = self.client.post(
            "/api/v1/auth/login",
            {"email": "target@example.com", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.data["error"]["code"], "TOO_MANY_REQUESTS")
