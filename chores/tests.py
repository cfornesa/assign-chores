from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


class HomePageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alex",
            email="alex@example.com",
            password="safe-test-password",
            first_name="Alex",
            last_name="Member",
        )

    def test_home_page_requires_authentication(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('home')}",
        )

    def test_authenticated_user_can_see_identity_and_sign_out(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assign Chores")
        self.assertContains(response, "Alex Member")
        self.assertContains(response, "alex@example.com")
        self.assertContains(response, f'action="{reverse("logout")}"')

        logout_response = self.client.post(reverse("logout"))

        self.assertRedirects(logout_response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_can_sign_in_with_django_auth_view(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "alex",
                "password": "safe-test-password",
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_accepts_a_replit_preview_origin(self):
        csrf_client = Client(enforce_csrf_checks=True)
        login_page = csrf_client.get(reverse("login"))
        csrf_token = login_page.cookies["csrftoken"].value

        response = csrf_client.post(
            reverse("login"),
            {
                "username": "alex",
                "password": "safe-test-password",
                "csrfmiddlewaretoken": csrf_token,
            },
            HTTP_ORIGIN="https://preview.replit.dev",
        )

        self.assertRedirects(response, reverse("home"))