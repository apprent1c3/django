from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ROOT_URLCONF="admin_views.urls")
class AdminBreadcrumbsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="super",
            password="secret",
            email="super@example.com",
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_breadcrumbs_absent(self):
        response = self.client.get(reverse("admin:index"))
        self.assertNotContains(response, '<nav aria-label="Breadcrumbs">')

    def test_breadcrumbs_present(self):
        """

        Tests if the breadcrumbs navigation is present in the admin pages.

        This test case checks the presence of breadcrumbs in two scenarios:
        - when adding a new user
        - when viewing the application list for the 'auth' app

        The test ensures that the HTML elements for breadcrumbs are correctly rendered.

        """
        response = self.client.get(reverse("admin:auth_user_add"))
        self.assertContains(response, '<nav aria-label="Breadcrumbs">')
        response = self.client.get(
            reverse("admin:app_list", kwargs={"app_label": "auth"})
        )
        self.assertContains(response, '<nav aria-label="Breadcrumbs">')
