from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection, connections
from django.test import TransactionTestCase
from django.test.utils import captured_stdout

from .models import Proxy, UserProxy

update_proxy_permissions = import_module(
    "django.contrib.auth.migrations.0011_update_proxy_permissions"
)


class ProxyModelWithDifferentAppLabelTests(TransactionTestCase):
    available_apps = [
        "auth_tests",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    def setUp(self):
        """
        Create proxy permissions with content_type to the concrete model
        rather than the proxy model (as they were before Django 2.2 and
        migration 11).
        """
        Permission.objects.all().delete()
        self.concrete_content_type = ContentType.objects.get_for_model(UserProxy)
        self.default_permission = Permission.objects.create(
            content_type=self.concrete_content_type,
            codename="add_userproxy",
            name="Can add userproxy",
        )
        self.custom_permission = Permission.objects.create(
            content_type=self.concrete_content_type,
            codename="use_different_app_label",
            name="May use a different app label",
        )

    def test_proxy_model_permissions_contenttype(self):
        proxy_model_content_type = ContentType.objects.get_for_model(
            UserProxy, for_concrete_model=False
        )
        self.assertEqual(
            self.default_permission.content_type, self.concrete_content_type
        )
        self.assertEqual(
            self.custom_permission.content_type, self.concrete_content_type
        )
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        self.default_permission.refresh_from_db()
        self.assertEqual(self.default_permission.content_type, proxy_model_content_type)
        self.custom_permission.refresh_from_db()
        self.assertEqual(self.custom_permission.content_type, proxy_model_content_type)

    def test_user_has_now_proxy_model_permissions(self):
        user = User.objects.create()
        user.user_permissions.add(self.default_permission)
        user.user_permissions.add(self.custom_permission)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertTrue(user.has_perm("auth." + permission.codename))
            self.assertFalse(user.has_perm("auth_tests." + permission.codename))
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        # Reload user to purge the _perm_cache.
        user = User._default_manager.get(pk=user.pk)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertFalse(user.has_perm("auth." + permission.codename))
            self.assertTrue(user.has_perm("auth_tests." + permission.codename))

    def test_migrate_backwards(self):
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
            update_proxy_permissions.revert_proxy_model_permissions(apps, editor)
        self.default_permission.refresh_from_db()
        self.assertEqual(
            self.default_permission.content_type, self.concrete_content_type
        )
        self.custom_permission.refresh_from_db()
        self.assertEqual(
            self.custom_permission.content_type, self.concrete_content_type
        )

    def test_user_keeps_same_permissions_after_migrating_backward(self):
        """

        Tests that a user's permissions remain unchanged after migrating backwards.

        This function checks the user's permissions before and after reverting proxy model
        permissions, ensuring that the user retains the correct permissions. It verifies
        that the user has the assigned default and custom permissions for the 'auth' app
        and does not have them for the 'auth_tests' app, confirming that the migration
        does not affect the user's existing permissions.

        """
        user = User.objects.create()
        user.user_permissions.add(self.default_permission)
        user.user_permissions.add(self.custom_permission)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertTrue(user.has_perm("auth." + permission.codename))
            self.assertFalse(user.has_perm("auth_tests." + permission.codename))
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
            update_proxy_permissions.revert_proxy_model_permissions(apps, editor)
        # Reload user to purge the _perm_cache.
        user = User._default_manager.get(pk=user.pk)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertTrue(user.has_perm("auth." + permission.codename))
            self.assertFalse(user.has_perm("auth_tests." + permission.codename))


class ProxyModelWithSameAppLabelTests(TransactionTestCase):
    available_apps = [
        "auth_tests",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    def setUp(self):
        """
        Create proxy permissions with content_type to the concrete model
        rather than the proxy model (as they were before Django 2.2 and
        migration 11).
        """
        Permission.objects.all().delete()
        self.concrete_content_type = ContentType.objects.get_for_model(Proxy)
        self.default_permission = Permission.objects.create(
            content_type=self.concrete_content_type,
            codename="add_proxy",
            name="Can add proxy",
        )
        self.custom_permission = Permission.objects.create(
            content_type=self.concrete_content_type,
            codename="display_proxys",
            name="May display proxys information",
        )

    def test_proxy_model_permissions_contenttype(self):
        proxy_model_content_type = ContentType.objects.get_for_model(
            Proxy, for_concrete_model=False
        )
        self.assertEqual(
            self.default_permission.content_type, self.concrete_content_type
        )
        self.assertEqual(
            self.custom_permission.content_type, self.concrete_content_type
        )
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        self.default_permission.refresh_from_db()
        self.custom_permission.refresh_from_db()
        self.assertEqual(self.default_permission.content_type, proxy_model_content_type)
        self.assertEqual(self.custom_permission.content_type, proxy_model_content_type)

    def test_user_still_has_proxy_model_permissions(self):
        """
        Tests whether a user retains proxy model permissions after updating the proxy model's permissions.

        This test case checks that a user's permissions are preserved when the proxy model's permissions are updated.
        It creates a test user, assigns default and custom permissions, and then verifies that the user has these permissions.
        After updating the proxy model's permissions, it re-fetches the user and re-checks that the permissions are still present.
        The test ensures that the update operation does not inadvertently remove or alter the user's existing permissions.
        """
        user = User.objects.create()
        user.user_permissions.add(self.default_permission)
        user.user_permissions.add(self.custom_permission)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertTrue(user.has_perm("auth_tests." + permission.codename))
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        # Reload user to purge the _perm_cache.
        user = User._default_manager.get(pk=user.pk)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertTrue(user.has_perm("auth_tests." + permission.codename))

    def test_migrate_backwards(self):
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
            update_proxy_permissions.revert_proxy_model_permissions(apps, editor)
        self.default_permission.refresh_from_db()
        self.assertEqual(
            self.default_permission.content_type, self.concrete_content_type
        )
        self.custom_permission.refresh_from_db()
        self.assertEqual(
            self.custom_permission.content_type, self.concrete_content_type
        )

    def test_user_keeps_same_permissions_after_migrating_backward(self):
        user = User.objects.create()
        user.user_permissions.add(self.default_permission)
        user.user_permissions.add(self.custom_permission)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertTrue(user.has_perm("auth_tests." + permission.codename))
        with connection.schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
            update_proxy_permissions.revert_proxy_model_permissions(apps, editor)
        # Reload user to purge the _perm_cache.
        user = User._default_manager.get(pk=user.pk)
        for permission in [self.default_permission, self.custom_permission]:
            self.assertTrue(user.has_perm("auth_tests." + permission.codename))

    def test_migrate_with_existing_target_permission(self):
        """
        Permissions may already exist:

        - Old workaround was to manually create permissions for proxy models.
        - Model may have been concrete and then converted to proxy.

        Output a reminder to audit relevant permissions.
        """
        proxy_model_content_type = ContentType.objects.get_for_model(
            Proxy, for_concrete_model=False
        )
        Permission.objects.create(
            content_type=proxy_model_content_type,
            codename="add_proxy",
            name="Can add proxy",
        )
        Permission.objects.create(
            content_type=proxy_model_content_type,
            codename="display_proxys",
            name="May display proxys information",
        )
        with captured_stdout() as stdout:
            with connection.schema_editor() as editor:
                update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        self.assertIn(
            "A problem arose migrating proxy model permissions", stdout.getvalue()
        )


class MultiDBProxyModelAppLabelTests(TransactionTestCase):
    databases = {"default", "other"}
    available_apps = [
        "auth_tests",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    def setUp(self):
        """

        Sets up the test environment by clearing existing content types and permissions, 
        then creates a new permission for adding proxy objects in the 'other' database.

        This method is used to establish a clean state for testing purposes, ensuring that 
        any previously created content types and permissions do not interfere with the test.
        It specifically creates a permission with the codename 'add_proxy' and name 'Can add proxy', 
        associated with the ContentType of the Proxy model in the 'other' database.

        """
        ContentType.objects.all().delete()
        Permission.objects.using("other").delete()
        concrete_content_type = ContentType.objects.db_manager("other").get_for_model(
            Proxy
        )
        self.permission = Permission.objects.using("other").create(
            content_type=concrete_content_type,
            codename="add_proxy",
            name="Can add proxy",
        )

    def test_migrate_other_database(self):
        """
        Test the migration of permissions for a proxy model in a secondary database.

        This test case ensures that the permissions for a proxy model are correctly updated
        in the 'other' database. It retrieves the content type for the proxy model,
        updates the permissions using the update_proxy_model_permissions function, and then
        verifies that the permission's content type matches the one retrieved for the proxy
        model.

        The test case uses the 'other' database connection, which is assumed to be a
        separate database from the default one, to test the migration of permissions in a
        multi-database setup.

        The update_proxy_model_permissions function is responsible for the actual
        permission update, and this test case focuses on verifying the outcome of this
        update in the context of the 'other' database.
        """
        proxy_model_content_type = ContentType.objects.db_manager(
            "other"
        ).get_for_model(Proxy, for_concrete_model=False)
        with connections["other"].schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        self.permission.refresh_from_db()
        self.assertEqual(self.permission.content_type, proxy_model_content_type)
