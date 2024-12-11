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
        """

        Tests that the breadcrumbs navigation is absent from the admin index page.

        This test ensures that the admin index page does not contain the breadcrumbs
        navigation element, which is typically used to provide a trail of links
        representing the current location within the site's hierarchy.

        """
        response = self.client.get(reverse("admin:index"))
        self.assertNotContains(response, '<nav aria-label="Breadcrumbs">')

    def test_breadcrumbs_present(self):
        """
        Tests that breadcrumbs are present in the admin interface.

        Verifies that the breadcrumbs navigation element is included in the HTML response
        for key admin pages, including the user add page and app list page. This ensures
        that users can easily navigate the admin interface and understand their current
        location within the site's hierarchy.
        """
        response = self.client.get(reverse("admin:auth_user_add"))
        self.assertContains(response, '<nav aria-label="Breadcrumbs">')
        response = self.client.get(
            reverse("admin:app_list", kwargs={"app_label": "auth"})
        )
        self.assertContains(response, '<nav aria-label="Breadcrumbs">')
