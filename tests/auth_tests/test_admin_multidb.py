from unittest import mock

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import path, reverse


class Router:
    target_db = None

    def db_for_read(self, model, **hints):
        return self.target_db

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        return True


site = admin.AdminSite(name="test_adminsite")
site.register(User, admin_class=UserAdmin)

urlpatterns = [
    path("admin/", site.urls),
]


@override_settings(ROOT_URLCONF=__name__, DATABASE_ROUTERS=["%s.Router" % __name__])
class MultiDatabaseTests(TestCase):
    databases = {"default", "other"}
    READ_ONLY_METHODS = {"get", "options", "head", "trace"}

    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class, creating a superuser for each database.

        This method is a class method and is intended to be used as a setup method for testing purposes.
        It creates a dictionary of superusers, where each key is a database and the corresponding value is a superuser object.
        The superusers are created with the username 'admin', password 'something', and email 'test@test.org'.
        The method ensures that a superuser is created for each database in the class's databases attribute.

        """
        cls.superusers = {}
        for db in cls.databases:
            Router.target_db = db
            cls.superusers[db] = User.objects.create_superuser(
                username="admin",
                password="something",
                email="test@test.org",
            )

    def tearDown(self):
        # Reset the routers' state between each test.
        Router.target_db = None

    @mock.patch("django.contrib.auth.admin.transaction")
    def test_add_view(self, mock):
        """

        Tests the add view functionality in the admin site for various databases.

        This test ensures that the add view for creating a new user is successful and that 
        the transaction is properly handled using themocked atomic function from Django's 
        transaction module. It checks the view's response status code and verifies that 
        the transaction is started using the correct database connection.

        The test uses the client to simulate a POST request to the add view with valid user 
        credentials and checks for a successful redirect (302 status code). It also 
        verifies that the atomic function is called with the correct database connection 
        for each test database.

        """
        for db in self.databases:
            with self.subTest(db_connection=db):
                Router.target_db = db
                self.client.force_login(self.superusers[db])
                response = self.client.post(
                    reverse("test_adminsite:auth_user_add"),
                    {
                        "username": "some_user",
                        "password1": "helloworld",
                        "password2": "helloworld",
                    },
                )
                self.assertEqual(response.status_code, 302)
                mock.atomic.assert_called_with(using=db)

    @mock.patch("django.contrib.auth.admin.transaction")
    def test_read_only_methods_add_view(self, mock):
        for db in self.databases:
            for method in self.READ_ONLY_METHODS:
                with self.subTest(db_connection=db, method=method):
                    mock.mock_reset()
                    Router.target_db = db
                    self.client.force_login(self.superusers[db])
                    response = getattr(self.client, method)(
                        reverse("test_adminsite:auth_user_add")
                    )
                    self.assertEqual(response.status_code, 200)
                    mock.atomic.assert_not_called()
