from django.apps.registry import apps
from django.conf import settings
from django.contrib.contenttypes import management as contenttypes_management
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import migrations, models
from django.test import TransactionTestCase, override_settings


@override_settings(
    MIGRATION_MODULES=dict(
        settings.MIGRATION_MODULES,
        contenttypes_tests="contenttypes_tests.operations_migrations",
    ),
)
class ContentTypeOperationsTests(TransactionTestCase):
    databases = {"default", "other"}
    available_apps = [
        "contenttypes_tests",
        "django.contrib.contenttypes",
    ]

    class TestRouter:
        def db_for_write(self, model, **hints):
            return "default"

    def setUp(self):
        """

        Set up the test environment by connecting a signal receiver to the post_migrate signal.
        The receiver, assertOperationsInjected, will be called after the migration operation to verify
        that the expected operations have been injected.
        A cleanup function is also registered to disconnect the signal receiver after the test is completed,
        ensuring that the test environment is restored to its original state.

        """
        app_config = apps.get_app_config("contenttypes_tests")
        models.signals.post_migrate.connect(
            self.assertOperationsInjected, sender=app_config
        )
        self.addCleanup(
            models.signals.post_migrate.disconnect,
            self.assertOperationsInjected,
            sender=app_config,
        )

    def assertOperationsInjected(self, plan, **kwargs):
        """
        /assertOperationsInjected/

        Checks that operations in a migration plan have the correct injected content type operations.

        :arg plan: A list of tuples containing a migration and its associated backward operation.
        :arg \**kwargs: Additional keyword arguments.

        This function verifies that for each RenameModel operation in the migration plan, a corresponding RenameContentType operation exists with the correct app label, old model name, and new model name. It ensures that content type operations are properly injected into the migration plan.
        """
        for migration, _backward in plan:
            operations = iter(migration.operations)
            for operation in operations:
                if isinstance(operation, migrations.RenameModel):
                    next_operation = next(operations)
                    self.assertIsInstance(
                        next_operation, contenttypes_management.RenameContentType
                    )
                    self.assertEqual(next_operation.app_label, migration.app_label)
                    self.assertEqual(next_operation.old_model, operation.old_name_lower)
                    self.assertEqual(next_operation.new_model, operation.new_name_lower)

    def test_existing_content_type_rename(self):
        """

        Test that renaming an existing content type works correctly.

        This function tests that a content type can be successfully renamed and 
        the changes can be reversed. It creates a content type, renames it, 
        verifies the rename operation, reverses the rename operation, and 
        finally verifies that the original content type has been restored.

        The test covers the following scenarios:
        - Creation of a content type
        - Renaming of the content type
        - Reversal of the rename operation

        It ensures that the content type is correctly updated in the database 
        after the rename and reversal operations.

        """
        ContentType.objects.create(app_label="contenttypes_tests", model="foo")
        call_command(
            "migrate",
            "contenttypes_tests",
            database="default",
            interactive=False,
            verbosity=0,
        )
        self.assertFalse(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="foo"
            ).exists()
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="renamedfoo"
            ).exists()
        )
        call_command(
            "migrate",
            "contenttypes_tests",
            "zero",
            database="default",
            interactive=False,
            verbosity=0,
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="foo"
            ).exists()
        )
        self.assertFalse(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="renamedfoo"
            ).exists()
        )

    @override_settings(DATABASE_ROUTERS=[TestRouter()])
    def test_existing_content_type_rename_other_database(self):
        """

        Tests the renaming of existing content types in the 'other' database.

        This test case checks the renaming and later reversal of a content type model name.
        It verifies that after migration, the original model name no longer exists and the
        renamed model exists, and that after reversing the migration, the original state
        is restored.

        The test uses the 'other' database, which is managed by a custom database router
         specified in the `DATABASE_ROUTERS` setting.

        """
        ContentType.objects.using("other").create(
            app_label="contenttypes_tests", model="foo"
        )
        other_content_types = ContentType.objects.using("other").filter(
            app_label="contenttypes_tests"
        )
        call_command(
            "migrate",
            "contenttypes_tests",
            database="other",
            interactive=False,
            verbosity=0,
        )
        self.assertFalse(other_content_types.filter(model="foo").exists())
        self.assertTrue(other_content_types.filter(model="renamedfoo").exists())
        call_command(
            "migrate",
            "contenttypes_tests",
            "zero",
            database="other",
            interactive=False,
            verbosity=0,
        )
        self.assertTrue(other_content_types.filter(model="foo").exists())
        self.assertFalse(other_content_types.filter(model="renamedfoo").exists())

    def test_missing_content_type_rename_ignore(self):
        """
        Tests that the ContentType model instances are correctly renamed and then 
        ignored when the corresponding model is removed, and vice versa.

        This test case covers a migration scenario where a model is renamed, and then 
        the original model name is reinstated. It verifies that the ContentType instances 
        are updated accordingly to reflect these changes, ensuring data consistency during 
        the migration process.

        The test performs the following actions:
        - Applies a migration that renames a model, checking that the corresponding 
          ContentType instance is updated.
        - Reverts the migration, checking that the original model name is restored and 
          the renamed ContentType instance is removed.

        This test helps ensure that the migration process correctly handles model 
        renaming and removal, maintaining the integrity of the ContentType instances 
        in the database.
        """
        call_command(
            "migrate",
            "contenttypes_tests",
            database="default",
            interactive=False,
            verbosity=0,
        )
        self.assertFalse(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="foo"
            ).exists()
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="renamedfoo"
            ).exists()
        )
        call_command(
            "migrate",
            "contenttypes_tests",
            "zero",
            database="default",
            interactive=False,
            verbosity=0,
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="foo"
            ).exists()
        )
        self.assertFalse(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="renamedfoo"
            ).exists()
        )

    def test_content_type_rename_conflict(self):
        """

        Test the migration behavior when a content type rename conflicts with an existing model.

        This test case checks that when a content type is renamed to a name that already exists,
        both the original and renamed content types continue to exist in the database after migration.
        It verifies this behavior for both forward and reverse migrations.

        The test involves creating two content types, running migrations, and asserting the presence of both
        content types after each migration step.

        """
        ContentType.objects.create(app_label="contenttypes_tests", model="foo")
        ContentType.objects.create(app_label="contenttypes_tests", model="renamedfoo")
        call_command(
            "migrate",
            "contenttypes_tests",
            database="default",
            interactive=False,
            verbosity=0,
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="foo"
            ).exists()
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="renamedfoo"
            ).exists()
        )
        call_command(
            "migrate",
            "contenttypes_tests",
            "zero",
            database="default",
            interactive=False,
            verbosity=0,
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="foo"
            ).exists()
        )
        self.assertTrue(
            ContentType.objects.filter(
                app_label="contenttypes_tests", model="renamedfoo"
            ).exists()
        )
