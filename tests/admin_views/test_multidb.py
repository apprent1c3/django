from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import path, reverse

from .models import Book


class Router:
    target_db = None

    def db_for_read(self, model, **hints):
        return self.target_db

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        return True


site = admin.AdminSite(name="test_adminsite")
site.register(Book)


def book(request, book_id):
    """
    .\"\"\" 
    Retrieves the title of a book by its ID and returns it as an HTTP response.

    :param request: The incoming HTTP request.
    :param book_id: The unique identifier of the book to retrieve.

    :return: An HttpResponse containing the title of the book.

    """
    b = Book.objects.get(id=book_id)
    return HttpResponse(b.title)


urlpatterns = [
    path("admin/", site.urls),
    path("books/<book_id>/", book),
]


@override_settings(ROOT_URLCONF=__name__, DATABASE_ROUTERS=["%s.Router" % __name__])
class MultiDatabaseTests(TestCase):
    databases = {"default", "other"}
    READ_ONLY_METHODS = {"get", "options", "head", "trace"}

    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class.

        This method creates a superuser and a test book in each database, storing their
        identifiers in class attributes for later use in tests. The superuser is created
        with a specific username, password, and email, while the test book is created
        with a generic name. The method ensures that test data is properly isolated
        across different databases by using a router to target each database
        individually.

        Attributes set by this method:
            superusers (dict): A dictionary mapping database names to superuser objects.
            test_book_ids (dict): A dictionary mapping database names to test book IDs.

        """
        cls.superusers = {}
        cls.test_book_ids = {}
        for db in cls.databases:
            Router.target_db = db
            cls.superusers[db] = User.objects.create_superuser(
                username="admin",
                password="something",
                email="test@test.org",
            )
            b = Book(name="Test Book")
            b.save(using=db)
            cls.test_book_ids[db] = b.id

    def tearDown(self):
        # Reset the routers' state between each test.
        Router.target_db = None

    @mock.patch("django.contrib.admin.options.transaction")
    def test_add_view(self, mock):
        """

        Tests the add view functionality in the admin interface.

        This test checks that the add view correctly handles the addition of a new book
        and redirects to the changelist view after a successful addition. It also verifies
        that the addition operation is wrapped in a database transaction.

        The test covers the adding of a book through the admin interface, ensuring that
        the operation is executed within a transaction on the correct database, and that
        the user is redirected to the changelist view after the operation is complete.

        The test is performed for each database configured in the test setup.

        """
        for db in self.databases:
            with self.subTest(db=db):
                mock.mock_reset()
                Router.target_db = db
                self.client.force_login(self.superusers[db])
                response = self.client.post(
                    reverse("test_adminsite:admin_views_book_add"),
                    {"name": "Foobar: 5th edition"},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.url, reverse("test_adminsite:admin_views_book_changelist")
                )
                mock.atomic.assert_called_with(using=db)

    @mock.patch("django.contrib.admin.options.transaction")
    def test_read_only_methods_add_view(self, mock):
        """

        Tests that read-only methods in the admin add view do not trigger transactions.

        This test checks that the specified read-only HTTP methods do not initiate a transaction
        when accessing the admin add view for a particular database. It iterates over multiple
        databases and methods, verifying that each combination results in a successful response
        (status code 200) without invoking a transaction.

        The methods tested are those defined in the `READ_ONLY_METHODS` list, which typically
        includes HTTP methods such as GET, HEAD, and OPTIONS. The test is performed for each
        database in the `databases` list, with the client logged in as a superuser for the
        respective database.

        """
        for db in self.databases:
            for method in self.READ_ONLY_METHODS:
                with self.subTest(db=db, method=method):
                    mock.mock_reset()
                    Router.target_db = db
                    self.client.force_login(self.superusers[db])
                    response = getattr(self.client, method)(
                        reverse("test_adminsite:admin_views_book_add"),
                    )
                    self.assertEqual(response.status_code, 200)
                    mock.atomic.assert_not_called()

    @mock.patch("django.contrib.admin.options.transaction")
    def test_change_view(self, mock):
        """

        Tests the change view for the Book model in the admin interface.

        This test case iterates over multiple databases, simulating a change operation for a book instance in each database.
        It verifies that the change operation is successful, redirects to the changelist view, and checks that a database transaction
        is properly handled using atomic blocks. The test also ensures that the transaction is executed on the correct database.

        """
        for db in self.databases:
            with self.subTest(db=db):
                mock.mock_reset()
                Router.target_db = db
                self.client.force_login(self.superusers[db])
                response = self.client.post(
                    reverse(
                        "test_adminsite:admin_views_book_change",
                        args=[self.test_book_ids[db]],
                    ),
                    {"name": "Test Book 2: Test more"},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.url, reverse("test_adminsite:admin_views_book_changelist")
                )
                mock.atomic.assert_called_with(using=db)

    @mock.patch("django.contrib.admin.options.transaction")
    def test_read_only_methods_change_view(self, mock):
        """

        Tests that read-only methods in the change view do not initiate database transactions.

        This test checks that the specified read-only methods, when used to access a book's change view, 
        return a successful response (200 status code) without attempting to write to the database.
        The test is run for each database and read-only method, with the user logged in as a superuser.

        """
        for db in self.databases:
            for method in self.READ_ONLY_METHODS:
                with self.subTest(db=db, method=method):
                    mock.mock_reset()
                    Router.target_db = db
                    self.client.force_login(self.superusers[db])
                    response = getattr(self.client, method)(
                        reverse(
                            "test_adminsite:admin_views_book_change",
                            args=[self.test_book_ids[db]],
                        ),
                        data={"name": "Test Book 2: Test more"},
                    )
                    self.assertEqual(response.status_code, 200)
                    mock.atomic.assert_not_called()

    @mock.patch("django.contrib.admin.options.transaction")
    def test_delete_view(self, mock):
        """

        Tests the delete view in the admin interface.

        Verifies that when a user attempts to delete a book, the deletion is wrapped in a database transaction,
        and after successful deletion, the user is redirected to the book changelist page.

        The test is run for each configured database, ensuring the deletion process works consistently across different databases.

        """
        for db in self.databases:
            with self.subTest(db=db):
                mock.mock_reset()
                Router.target_db = db
                self.client.force_login(self.superusers[db])
                response = self.client.post(
                    reverse(
                        "test_adminsite:admin_views_book_delete",
                        args=[self.test_book_ids[db]],
                    ),
                    {"post": "yes"},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.url, reverse("test_adminsite:admin_views_book_changelist")
                )
                mock.atomic.assert_called_with(using=db)

    @mock.patch("django.contrib.admin.options.transaction")
    def test_read_only_methods_delete_view(self, mock):
        for db in self.databases:
            for method in self.READ_ONLY_METHODS:
                with self.subTest(db=db, method=method):
                    mock.mock_reset()
                    Router.target_db = db
                    self.client.force_login(self.superusers[db])
                    response = getattr(self.client, method)(
                        reverse(
                            "test_adminsite:admin_views_book_delete",
                            args=[self.test_book_ids[db]],
                        )
                    )
                    self.assertEqual(response.status_code, 200)
                    mock.atomic.assert_not_called()


class ViewOnSiteRouter:
    def db_for_read(self, model, instance=None, **hints):
        if model._meta.app_label in {"auth", "sessions", "contenttypes"}:
            return "default"
        return "other"

    def db_for_write(self, model, **hints):
        """
        Determines the database to use for writing data for a given model.

        This method is used to route database operations to the appropriate database.
        It checks the app label of the model and returns 'default' for models from the
        'auth', 'sessions', and 'contenttypes' apps, and 'other' for all other models.

        :param model: The model for which to determine the write database
        :param hints: Additional hints used to determine the database
        :returns: The name of the database to use for writing data

        """
        if model._meta.app_label in {"auth", "sessions", "contenttypes"}:
            return "default"
        return "other"

    def allow_relation(self, obj1, obj2, **hints):
        return obj1._state.db in {"default", "other"} and obj2._state.db in {
            "default",
            "other",
        }

    def allow_migrate(self, db, app_label, **hints):
        return True


@override_settings(ROOT_URLCONF=__name__, DATABASE_ROUTERS=[ViewOnSiteRouter()])
class ViewOnSiteTests(TestCase):
    databases = {"default", "other"}

    def test_contenttype_in_separate_db(self):
        """

        Test that content type in a separate database is handled correctly when accessing the 'view on site' shortcut in the admin interface.

        This test covers the following scenarios:
            * Creation of a new book in a separate database
            * Deletion of all existing content types in the separate database
            * Login as a superuser
            * Accessing the 'view on site' shortcut URL for the book
            * Verifying the redirect status code and URL pattern

        The test ensures that the 'view on site' shortcut in the admin interface correctly handles content types located in a separate database.

        """
        ContentType.objects.using("other").all().delete()
        book = Book.objects.using("other").create(name="other book")
        user = User.objects.create_superuser(
            username="super", password="secret", email="super@example.com"
        )

        book_type = ContentType.objects.get(app_label="admin_views", model="book")

        self.client.force_login(user)

        shortcut_url = reverse("admin:view_on_site", args=(book_type.pk, book.id))
        response = self.client.get(shortcut_url, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertRegex(
            response.url, f"http://(testserver|example.com)/books/{book.id}/"
        )
