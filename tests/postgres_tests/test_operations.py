import unittest

from migrations.test_base import OperationTestBase

from django.db import IntegrityError, NotSupportedError, connection, transaction
from django.db.migrations.state import ProjectState
from django.db.migrations.writer import OperationWriter
from django.db.models import CheckConstraint, Index, Q, UniqueConstraint
from django.db.utils import ProgrammingError
from django.test import modify_settings, override_settings
from django.test.utils import CaptureQueriesContext

from . import PostgreSQLTestCase

try:
    from django.contrib.postgres.indexes import BrinIndex, BTreeIndex
    from django.contrib.postgres.operations import (
        AddConstraintNotValid,
        AddIndexConcurrently,
        BloomExtension,
        CreateCollation,
        CreateExtension,
        RemoveCollation,
        RemoveIndexConcurrently,
        ValidateConstraint,
    )
except ImportError:
    pass


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests.")
@modify_settings(INSTALLED_APPS={"append": "migrations"})
class AddIndexConcurrentlyTests(OperationTestBase):
    app_label = "test_add_concurrently"

    def test_requires_atomic_false(self):
        project_state = self.set_up_test_model(self.app_label)
        new_state = project_state.clone()
        operation = AddIndexConcurrently(
            "Pony",
            Index(fields=["pink"], name="pony_pink_idx"),
        )
        msg = (
            "The AddIndexConcurrently operation cannot be executed inside "
            "a transaction (set atomic = False on the migration)."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.schema_editor(atomic=True) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )

    def test_add(self):
        """
        Tests the AddIndexConcurrently operation, which concurrently adds an index to a model.

        This test case verifies that the operation correctly describes and formats its description,
        applies the index to the model state, and creates and drops the index in the database.
        It ensures that the index is created and dropped correctly, both in the model state and in the database.

        It checks that the operation's describe and formatted_description methods return the correct strings,
        and that the state_forwards method updates the model state with the new index.
        The test also verifies that the database_forwards method creates the index in the database,
        and that the database_backwards method drops the index.

        Additionally, it tests the deconstruct method to ensure it returns the correct name, arguments, and keyword arguments for the operation.
        """
        project_state = self.set_up_test_model(self.app_label, index=False)
        table_name = "%s_pony" % self.app_label
        index = Index(fields=["pink"], name="pony_pink_idx")
        new_state = project_state.clone()
        operation = AddIndexConcurrently("Pony", index)
        self.assertEqual(
            operation.describe(),
            "Concurrently create index pony_pink_idx on field(s) pink of model Pony",
        )
        self.assertEqual(
            operation.formatted_description(),
            "+ Concurrently create index pony_pink_idx on field(s) pink of model Pony",
        )
        operation.state_forwards(self.app_label, new_state)
        self.assertEqual(
            len(new_state.models[self.app_label, "pony"].options["indexes"]), 1
        )
        self.assertIndexNotExists(table_name, ["pink"])
        # Add index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )
        self.assertIndexExists(table_name, ["pink"])
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(
                self.app_label, editor, new_state, project_state
            )
        self.assertIndexNotExists(table_name, ["pink"])
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, "AddIndexConcurrently")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"model_name": "Pony", "index": index})

    def test_add_other_index_type(self):
        project_state = self.set_up_test_model(self.app_label, index=False)
        table_name = "%s_pony" % self.app_label
        new_state = project_state.clone()
        operation = AddIndexConcurrently(
            "Pony",
            BrinIndex(fields=["pink"], name="pony_pink_brin_idx"),
        )
        self.assertIndexNotExists(table_name, ["pink"])
        # Add index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )
        self.assertIndexExists(table_name, ["pink"], index_type="brin")
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(
                self.app_label, editor, new_state, project_state
            )
        self.assertIndexNotExists(table_name, ["pink"])

    def test_add_with_options(self):
        project_state = self.set_up_test_model(self.app_label, index=False)
        table_name = "%s_pony" % self.app_label
        new_state = project_state.clone()
        index = BTreeIndex(fields=["pink"], name="pony_pink_btree_idx", fillfactor=70)
        operation = AddIndexConcurrently("Pony", index)
        self.assertIndexNotExists(table_name, ["pink"])
        # Add index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )
        self.assertIndexExists(table_name, ["pink"], index_type="btree")
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(
                self.app_label, editor, new_state, project_state
            )
        self.assertIndexNotExists(table_name, ["pink"])


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests.")
@modify_settings(INSTALLED_APPS={"append": "migrations"})
class RemoveIndexConcurrentlyTests(OperationTestBase):
    app_label = "test_rm_concurrently"

    def test_requires_atomic_false(self):
        project_state = self.set_up_test_model(self.app_label, index=True)
        new_state = project_state.clone()
        operation = RemoveIndexConcurrently("Pony", "pony_pink_idx")
        msg = (
            "The RemoveIndexConcurrently operation cannot be executed inside "
            "a transaction (set atomic = False on the migration)."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.schema_editor(atomic=True) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )

    def test_remove(self):
        project_state = self.set_up_test_model(self.app_label, index=True)
        table_name = "%s_pony" % self.app_label
        self.assertTableExists(table_name)
        new_state = project_state.clone()
        operation = RemoveIndexConcurrently("Pony", "pony_pink_idx")
        self.assertEqual(
            operation.describe(),
            "Concurrently remove index pony_pink_idx from Pony",
        )
        self.assertEqual(
            operation.formatted_description(),
            "- Concurrently remove index pony_pink_idx from Pony",
        )
        operation.state_forwards(self.app_label, new_state)
        self.assertEqual(
            len(new_state.models[self.app_label, "pony"].options["indexes"]), 0
        )
        self.assertIndexExists(table_name, ["pink"])
        # Remove index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )
        self.assertIndexNotExists(table_name, ["pink"])
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(
                self.app_label, editor, new_state, project_state
            )
        self.assertIndexExists(table_name, ["pink"])
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, "RemoveIndexConcurrently")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"model_name": "Pony", "name": "pony_pink_idx"})


class NoMigrationRouter:
    def allow_migrate(self, db, app_label, **hints):
        return False


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests.")
class CreateExtensionTests(PostgreSQLTestCase):
    app_label = "test_allow_create_extention"

    @override_settings(DATABASE_ROUTERS=[NoMigrationRouter()])
    def test_no_allow_migrate(self):
        operation = CreateExtension("tablefunc")
        self.assertEqual(
            operation.formatted_description(), "+ Creates extension tablefunc"
        )
        project_state = ProjectState()
        new_state = project_state.clone()
        # Don't create an extension.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 0)
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 0)

    def test_allow_migrate(self):
        operation = CreateExtension("tablefunc")
        self.assertEqual(
            operation.migration_name_fragment, "create_extension_tablefunc"
        )
        project_state = ProjectState()
        new_state = project_state.clone()
        # Create an extension.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 4)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS", captured_queries[1]["sql"])
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 2)
        self.assertIn("DROP EXTENSION IF EXISTS", captured_queries[1]["sql"])

    def test_create_existing_extension(self):
        """

        Tests the creation of an existing database extension.

        This test case verifies that the :class:`BloomExtension` operation correctly
        creates the extension in the database. It checks the migration name fragment, 
        clones the project state, and applies the operation to the database. The test 
        also captures the SQL queries executed during the operation and verifies that 
        the correct number and type of queries are executed.

        The test ensures that the extension is created as expected, without any errors, 
        and that the database state is updated correctly.

        """
        operation = BloomExtension()
        self.assertEqual(operation.migration_name_fragment, "create_extension_bloom")
        project_state = ProjectState()
        new_state = project_state.clone()
        # Don't create an existing extension.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 3)
        self.assertIn("SELECT", captured_queries[0]["sql"])

    def test_drop_nonexistent_extension(self):
        operation = CreateExtension("tablefunc")
        project_state = ProjectState()
        new_state = project_state.clone()
        # Don't drop a nonexistent extension.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("SELECT", captured_queries[0]["sql"])


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests.")
class CreateCollationTests(PostgreSQLTestCase):
    app_label = "test_allow_create_collation"

    @override_settings(DATABASE_ROUTERS=[NoMigrationRouter()])
    def test_no_allow_migrate(self):
        operation = CreateCollation("C_test", locale="C")
        project_state = ProjectState()
        new_state = project_state.clone()
        # Don't create a collation.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 0)
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 0)

    def test_create(self):
        """

        Tests the creation of a database collation.

        This test case verifies that the CreateCollation operation correctly generates the 
        migration name fragment, description, and formatted description. It also checks that 
        the operation applies the necessary database queries to create and drop the collation, 
        and that it correctly handles cases where the collation already exists or does not exist. 
        Additionally, it validates the deconstruction of the operation into its constituent parts.

        """
        operation = CreateCollation("C_test", locale="C")
        self.assertEqual(operation.migration_name_fragment, "create_collation_c_test")
        self.assertEqual(operation.describe(), "Create collation C_test")
        self.assertEqual(operation.formatted_description(), "+ Create collation C_test")
        project_state = ProjectState()
        new_state = project_state.clone()
        # Create a collation.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("CREATE COLLATION", captured_queries[0]["sql"])
        # Creating the same collation raises an exception.
        with self.assertRaisesMessage(ProgrammingError, "already exists"):
            with connection.schema_editor(atomic=True) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("DROP COLLATION", captured_queries[0]["sql"])
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, "CreateCollation")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"name": "C_test", "locale": "C"})

    def test_create_non_deterministic_collation(self):
        operation = CreateCollation(
            "case_insensitive_test",
            "und-u-ks-level2",
            provider="icu",
            deterministic=False,
        )
        project_state = ProjectState()
        new_state = project_state.clone()
        # Create a collation.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("CREATE COLLATION", captured_queries[0]["sql"])
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("DROP COLLATION", captured_queries[0]["sql"])
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, "CreateCollation")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "name": "case_insensitive_test",
                "locale": "und-u-ks-level2",
                "provider": "icu",
                "deterministic": False,
            },
        )

    def test_create_collation_alternate_provider(self):
        """
        Tests the creation of a collation with an alternate provider.

        This tests the CreateCollation operation with the ICU provider and a specific locale.
        It verifies that the collation is created and dropped correctly on the database,
        and that the expected SQL queries are generated.

        The test covers the forward and backward operations of the CreateCollation
        operation, ensuring that the collation is successfully created and then dropped
        from the database, and that the correct SQL queries are executed in both cases.
        """
        operation = CreateCollation(
            "german_phonebook_test",
            provider="icu",
            locale="de-u-co-phonebk",
        )
        project_state = ProjectState()
        new_state = project_state.clone()
        # Create an collation.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("CREATE COLLATION", captured_queries[0]["sql"])
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("DROP COLLATION", captured_queries[0]["sql"])

    def test_writer(self):
        operation = CreateCollation(
            "sample_collation",
            "und-u-ks-level2",
            provider="icu",
            deterministic=False,
        )
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import django.contrib.postgres.operations"})
        self.assertEqual(
            buff,
            "django.contrib.postgres.operations.CreateCollation(\n"
            "    name='sample_collation',\n"
            "    locale='und-u-ks-level2',\n"
            "    provider='icu',\n"
            "    deterministic=False,\n"
            "),",
        )


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests.")
class RemoveCollationTests(PostgreSQLTestCase):
    app_label = "test_allow_remove_collation"

    @override_settings(DATABASE_ROUTERS=[NoMigrationRouter()])
    def test_no_allow_migrate(self):
        """
        Tests that the RemoveCollation operation does not execute any database queries.

        This test covers both the forward and backward operations of removing a collation.
        It verifies that no queries are executed on the database during these operations,
        ensuring that the operation is effectively a no-op from a database perspective.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If any database queries are executed during the operation.
        """
        operation = RemoveCollation("C_test", locale="C")
        project_state = ProjectState()
        new_state = project_state.clone()
        # Don't create a collation.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 0)
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 0)

    def test_remove(self):
        """

        Test the RemoveCollation operation to ensure it correctly removes a collation from a database.

        This test checks the following functionality:
        - The migration name fragment generated by the operation
        - The description and formatted description of the operation
        - The database operation itself, including the SQL query generated
        - The behavior when attempting to remove a non-existent collation
        - The reversal of the operation, including the SQL query generated for re-creating the collation
        - The deconstruction of the operation into its constituent parts

        The test uses a test collation 'C_test' with locale 'C' to verify the expected behavior.

        """
        operation = CreateCollation("C_test", locale="C")
        project_state = ProjectState()
        new_state = project_state.clone()
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )

        operation = RemoveCollation("C_test", locale="C")
        self.assertEqual(operation.migration_name_fragment, "remove_collation_c_test")
        self.assertEqual(operation.describe(), "Remove collation C_test")
        self.assertEqual(operation.formatted_description(), "- Remove collation C_test")
        project_state = ProjectState()
        new_state = project_state.clone()
        # Remove a collation.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("DROP COLLATION", captured_queries[0]["sql"])
        # Removing a nonexistent collation raises an exception.
        with self.assertRaisesMessage(ProgrammingError, "does not exist"):
            with connection.schema_editor(atomic=True) as editor:
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        # Reversal.
        with CaptureQueriesContext(connection) as captured_queries:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("CREATE COLLATION", captured_queries[0]["sql"])
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, "RemoveCollation")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"name": "C_test", "locale": "C"})


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests.")
@modify_settings(INSTALLED_APPS={"append": "migrations"})
class AddConstraintNotValidTests(OperationTestBase):
    app_label = "test_add_constraint_not_valid"

    def test_non_check_constraint_not_supported(self):
        constraint = UniqueConstraint(fields=["pink"], name="pony_pink_uniq")
        msg = "AddConstraintNotValid.constraint must be a check constraint."
        with self.assertRaisesMessage(TypeError, msg):
            AddConstraintNotValid(model_name="pony", constraint=constraint)

    def test_add(self):
        table_name = f"{self.app_label}_pony"
        constraint_name = "pony_pink_gte_check"
        constraint = CheckConstraint(condition=Q(pink__gte=4), name=constraint_name)
        operation = AddConstraintNotValid("Pony", constraint=constraint)
        project_state, new_state = self.make_test_state(self.app_label, operation)
        self.assertEqual(
            operation.describe(),
            f"Create not valid constraint {constraint_name} on model Pony",
        )
        self.assertEqual(
            operation.formatted_description(),
            f"+ Create not valid constraint {constraint_name} on model Pony",
        )
        self.assertEqual(
            operation.migration_name_fragment,
            f"pony_{constraint_name}_not_valid",
        )
        self.assertEqual(
            len(new_state.models[self.app_label, "pony"].options["constraints"]),
            1,
        )
        self.assertConstraintNotExists(table_name, constraint_name)
        Pony = new_state.apps.get_model(self.app_label, "Pony")
        self.assertEqual(len(Pony._meta.constraints), 1)
        Pony.objects.create(pink=2, weight=1.0)
        # Add constraint.
        with connection.schema_editor(atomic=True) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )
        msg = f'check constraint "{constraint_name}"'
        with self.assertRaisesMessage(IntegrityError, msg), transaction.atomic():
            Pony.objects.create(pink=3, weight=1.0)
        self.assertConstraintExists(table_name, constraint_name)
        # Reversal.
        with connection.schema_editor(atomic=True) as editor:
            operation.database_backwards(
                self.app_label, editor, project_state, new_state
            )
        self.assertConstraintNotExists(table_name, constraint_name)
        Pony.objects.create(pink=3, weight=1.0)
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, "AddConstraintNotValid")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"model_name": "Pony", "constraint": constraint})


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests.")
@modify_settings(INSTALLED_APPS={"append": "migrations"})
class ValidateConstraintTests(OperationTestBase):
    app_label = "test_validate_constraint"

    def test_validate(self):
        """

        Tests the validation of a database constraint.

        This method creates a test state with a Pony model, adds a CheckConstraint
        to the model, and then attempts to validate the constraint. It checks that
        the constraint validation fails when the constraint is not met, and passes
        when the constraint is met.

        The test covers both forward and backward operations, ensuring that the
        constraint validation behaves as expected in both directions.

        It also verifies the operation's description, formatted description, and
        migration name fragment.

        """
        constraint_name = "pony_pink_gte_check"
        constraint = CheckConstraint(condition=Q(pink__gte=4), name=constraint_name)
        operation = AddConstraintNotValid("Pony", constraint=constraint)
        project_state, new_state = self.make_test_state(self.app_label, operation)
        Pony = new_state.apps.get_model(self.app_label, "Pony")
        obj = Pony.objects.create(pink=2, weight=1.0)
        # Add constraint.
        with connection.schema_editor(atomic=True) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )
        project_state = new_state
        new_state = new_state.clone()
        operation = ValidateConstraint("Pony", name=constraint_name)
        operation.state_forwards(self.app_label, new_state)
        self.assertEqual(
            operation.describe(),
            f"Validate constraint {constraint_name} on model Pony",
        )
        self.assertEqual(
            operation.formatted_description(),
            f"~ Validate constraint {constraint_name} on model Pony",
        )
        self.assertEqual(
            operation.migration_name_fragment,
            f"pony_validate_{constraint_name}",
        )
        # Validate constraint.
        with connection.schema_editor(atomic=True) as editor:
            msg = f'check constraint "{constraint_name}"'
            with self.assertRaisesMessage(IntegrityError, msg):
                operation.database_forwards(
                    self.app_label, editor, project_state, new_state
                )
        obj.pink = 5
        obj.save()
        with connection.schema_editor(atomic=True) as editor:
            operation.database_forwards(
                self.app_label, editor, project_state, new_state
            )
        # Reversal is a noop.
        with connection.schema_editor() as editor:
            with self.assertNumQueries(0):
                operation.database_backwards(
                    self.app_label, editor, new_state, project_state
                )
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, "ValidateConstraint")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"model_name": "Pony", "name": constraint_name})
