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
        .Asserts that RenameModel operations in a migration plan are followed by corresponding RenameContentType operations.

        #:param plan: Migration plan to check
        #:param kwargs: Additional keyword arguments
        #:raises AssertionError: If the operations are not correctly injected
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
        Tests renaming of existing content types via migrations.

         Verifies that an existing content type can be renamed and then reverted back to its original name through database migrations.
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
        Tests that the content type rename operation works correctly when applied to a database other than the default. 
        Verifies that content types are renamed during a migration and restored to their original name when the migration is reversed.
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
        Tests the behavior of renaming content types with missing content types, 
        ensuring that the model 'foo' is correctly renamed to 'renamedfoo' and 
        restored after migration and reversal.
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

        Tests that content types with conflicting names can coexist after migration.

        This test case verifies that content types with clashing model names can be preserved
        when migrating the 'contenttypes_tests' app, without any renaming conflicts.

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
