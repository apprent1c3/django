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
        """

        Test that proxy model permissions are updated to reference the correct content type.

        Verifies that default and custom permissions are correctly updated to point to the
        proxy model content type after running the update_proxy_model_permissions function.

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
        Tests that a user's proxy model permissions are updated correctly when 
        the proxy model permissions are applied. Verifies that the user initially 
        has the standard model permissions, then checks that these are replaced 
        by the proxy model permissions after the update is applied.
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

        Tests the migration of proxy permissions in reverse.
        Checks that permissions are correctly updated and reverted to their original state.

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

        Tests that a user's permissions remain unchanged after migrating backward.
        Verifies that the user retains their original permissions after the migration.

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
        """

        Verifies that the content types of permissions are updated correctly when switching to a proxy model.

        Tests that the content type of default and custom permissions are initially set to the concrete model,
        and after running the update proxy model permissions function, they are updated to the proxy model.

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
        Tests that a user's proxy model permissions are preserved after updating the proxy model permissions.
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
        Tests the migration of proxy model permissions backwards, ensuring that content types are correctly reverted to their original state after an update.
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

        Checks that a user's permissions remain unchanged after migrating the database schema backward.

        Verifies that a user retains their assigned permissions after reverting proxy model permissions.

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
        Tests migration of database permissions to the 'other' database, verifying 
        that proxy model permissions are correctly updated and associated with the 
        correct content type.
        """
        proxy_model_content_type = ContentType.objects.db_manager(
            "other"
        ).get_for_model(Proxy, for_concrete_model=False)
        with connections["other"].schema_editor() as editor:
            update_proxy_permissions.update_proxy_model_permissions(apps, editor)
        self.permission.refresh_from_db()
        self.assertEqual(self.permission.content_type, proxy_model_content_type)
