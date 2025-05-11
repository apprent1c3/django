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

        Sets up proxy permissions for the UserProxy model.

        This method creates the necessary permissions with the correct content type,
        migrating from the legacy behavior prior to Django 2.2 and migration 11.
        It deletes all existing permissions and creates two new ones: 'Can add userproxy'
        and 'May use a different app label'.

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
        """
        Tests that the content type of proxy model permissions is correctly updated.

        Verifies that the default and custom permissions are initially associated with the concrete model content type,
        and then successfully updated to the proxy model content type after running the update_proxy_model_permissions function.
        """
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
        """
        Tests that a user's proxy model permissions are correctly updated after running the update_proxy_model_permissions function.

        Verifies that the user initially has the assigned permissions, then checks that the permissions are transferred to a proxy model after updating, and the original permissions are removed.
        """
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
        """
        Tests that migrating backwards reverts proxy model permissions to their original concrete content type.
        """
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
        Tests that a user retains their permissions after migrating backward.

        Verifies that user permissions are preserved when reverting proxy model permissions,
        ensuring that the user's access remains unchanged throughout the migration process.
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
        Sets up proxy permissions by creating content types and default permissions for the Proxy model, replacing the legacy behavior prior to Django 2.2 and migration 11.
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
        """
        Tests the content type of proxy model permissions are correctly updated.

        Verifies that model permissions are initially associated with the concrete model,
        then updates the permissions to use the proxy model, and checks the content type
        is correct after the update.
        """
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

        Tests that a user still retains proxy model permissions after updating them.

        Verifies that adding permissions to a user and then updating the proxy model
        permissions does not remove the existing permissions from the user.

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
        """
        Tests the migration of permissions in the reverse direction, ensuring that the content type of default and custom permissions is correctly updated to the concrete content type after reverting proxy model permissions.
        """
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

        Tests that a user's permissions remain unchanged after migrating a proxy model
        backward and then forward again, to ensure that permissions are properly
        preserved through the migration process.

        """
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
        Tests the migration of proxy model permissions when target permissions already exist, ensuring a reminder is output to audit relevant permissions.
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
        Tests the migration of permissions to a different database for a proxy model, verifying that the content type of the permission is updated correctly after the migration.
        """
        proxy_model_content_type = ContentType.objects.db_manager(
            "other"
        ).get_for_model(Proxy, for_concrete_model=False)
        with connections["other"].schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        self.permission.refresh_from_db()
        self.assertEqual(self.permission.content_type, proxy_model_content_type)
