from rest_framework.test import APITestCase

from .models import User


class AuthFlowTests(APITestCase):
    """Covers the refresh-token cookie migration (BACKLOG.md item G,
    WEAKNESS_AUDIT.md §1.3) — the exact class of regression a JSON-body-only test wouldn't
    catch, since it needs a real request/response cycle to see cookies.
    """

    def _register(self, email="auth-test@example.com", password="TestPass123!"):
        return self.client.post(
            "/api/v1/auth/register", {"email": email, "password": password}, format="json"
        )

    def test_register_returns_token_but_not_refresh_token_in_body(self):
        response = self._register()

        self.assertEqual(response.status_code, 201)
        self.assertIn("token", response.data)
        self.assertNotIn("refreshToken", response.data)

    def test_register_sets_httponly_refresh_cookie(self):
        response = self._register()

        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/v1/auth")

    def test_refresh_without_cookie_is_unauthorized(self):
        response = self.client.post("/api/v1/auth/refresh")

        self.assertEqual(response.status_code, 401)

    def test_refresh_with_cookie_from_login_issues_new_access_token(self):
        self._register(email="refresh-test@example.com")
        login = self.client.post(
            "/api/v1/auth/login",
            {"email": "refresh-test@example.com", "password": "TestPass123!"},
            format="json",
        )
        self.client.cookies["refresh_token"] = login.cookies["refresh_token"].value

        refresh = self.client.post("/api/v1/auth/refresh")

        self.assertEqual(refresh.status_code, 200)
        self.assertIn("token", refresh.data)
        self.assertNotIn("refreshToken", refresh.data)

    def test_logout_clears_the_refresh_cookie(self):
        self._register(email="logout-test@example.com")

        response = self.client.post("/api/v1/auth/logout")

        cookie = response.cookies["refresh_token"]
        self.assertEqual(cookie.value, "")
        self.assertEqual(int(cookie["max-age"]), 0)


class PermissionDefaultTests(APITestCase):
    """Covers §1.1 — confirms the secure-by-default permission posture (dotnet's gateway had
    the opposite bug: auth configured but never enforced) actually holds for this monolith's
    authenticated-by-default views.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="perm-test@example.com", password="x")

    def test_observations_requires_auth(self):
        response = self.client.get("/api/v1/observations")
        self.assertEqual(response.status_code, 401)

    def test_notifications_requires_auth(self):
        response = self.client.get("/api/v1/notifications")
        self.assertEqual(response.status_code, 401)

    def test_billing_me_requires_auth(self):
        response = self.client.get("/api/v1/billing/me")
        self.assertEqual(response.status_code, 401)

    def test_species_catalog_is_public(self):
        response = self.client.get("/api/v1/species")
        self.assertEqual(response.status_code, 200)
