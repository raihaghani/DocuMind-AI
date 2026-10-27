from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from workspace.models import Workspace


class AuthenticationTests(TestCase):
    def test_registration_creates_user_and_workspace(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "alice",
                "email": "alice@example.com",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
            },
        )
        self.assertRedirects(response, reverse("workspace:dashboard"))
        user = User.objects.get(username="alice")
        self.assertTrue(Workspace.objects.filter(owner=user).exists())

    def test_registration_rejects_duplicate_username(self):
        User.objects.create_user("bob", "bob@example.com", "Str0ngPass!23")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "bob",
                "email": "other@example.com",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already taken")

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "charlie",
                "email": "c@example.com",
                "password1": "123",
                "password2": "123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="charlie").exists())

    def test_login_and_logout(self):
        User.objects.create_user("dave", "d@example.com", "Str0ngPass!23")
        login = self.client.post(
            reverse("accounts:login"),
            {"username": "dave", "password": "Str0ngPass!23"},
        )
        self.assertRedirects(login, reverse("workspace:dashboard"))

        # Logout must be a POST.
        get_logout = self.client.get(reverse("accounts:logout"))
        self.assertEqual(get_logout.status_code, 405)
        logout = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(logout, reverse("accounts:login"))

    def test_invalid_login_shows_error(self):
        User.objects.create_user("erin", "e@example.com", "Str0ngPass!23")
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "erin", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")

    def test_protected_pages_require_login(self):
        protected = [
            reverse("workspace:dashboard"),
            reverse("documents:list"),
            reverse("documents:upload"),
            reverse("ai_assistant:ask"),
            reverse("ai_assistant:history"),
            reverse("accounts:account"),
        ]
        for url in protected:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response.url)
