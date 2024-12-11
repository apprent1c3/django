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
        Tests the AddIndexConcurrently operation to ensure it correctly adds an index to a model concurrently.

        The test case verifies the operation's behavior by checking its description, 
        formatted description, and the effect of applying the operation to the project state 
        and the database. It also ensures the operation can be properly deconstructed.

        The operation is tested in both forward and backward directions, confirming that 
        the index is successfully added and removed from the database as expected.

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
        """
        Tests the addition of a BRIN index to a model concurrently.

        This test case verifies that an index of type BRIN can be successfully added to a model 
        using the AddIndexConcurrently operation. It checks that the index does not exist before 
        the operation, is created correctly after the operation, and is removed after the 
        reverse operation. The test covers the database forwards and backwards methods of the 
        AddIndexConcurrently operation to ensure correct index creation and removal.

        The test creates a new state for the project, clones it, and uses a schema editor to 
        apply the AddIndexConcurrently operation. The index created is a BRIN index with a 
        specific name and field, which is then verified to exist after the operation and not 
        exist after the reverse operation.

        This test case ensures that the AddIndexConcurrently operation correctly handles the 
        addition of BRIN indexes to models concurrently, and that the indexes are properly 
        created and removed from the database.
        """
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
        """
        Tests the addition of a B-tree index to a table using the AddIndexConcurrently operation.

        This test case verifies that the index is successfully added to the table, and then
        removed, using the database forwards and backwards operations.

        The test uses a sample 'Pony' model to create a table and attempts to add a B-tree
        index named 'pony_pink_btree_idx' with a fill factor of 70 on the 'pink' field.
        The test assertions ensure that the index exists after the forwards operation and
        does not exist after the backwards operation, confirming the correct functionality
        of the AddIndexConcurrently operation.
        """
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
        """

        Tests the allow_migrate functionality for creating and dropping a PostgreSQL extension.

        This test case covers the database operations involved in creating and reversing 
        an extension, specifically the 'tablefunc' extension. It verifies that the 
        migration name fragment is correctly generated and that the required SQL queries 
        are executed during the forwards and backwards operations. The test asserts that 
        the correct number of queries are captured and that they contain the expected 
        CREATE and DROP EXTENSION statements.

        """
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

        Tests the creation of an existing Bloom extension by simulating a database migration.

        Checks that the migration name fragment is correctly set, and then clones the current project state to test the database forwards operation.
        The test asserts that the correct number of database queries are executed and that the initial query is a SELECT statement.

        This test case ensures that the Bloom extension is properly set up and that the database operations are performed as expected.

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
        """
        Tests the creation of a non-deterministic collation.

        This test case verifies the successful creation and subsequent dropping of a
        collation in a database. It checks that the correct SQL queries are executed
        during both the forward and backward operations. Additionally, it validates the
        deconstruction of the CreateCollation operation to ensure it correctly returns
        its constituent parts.

        The test creates a non-deterministic collation named 'case_insensitive_test' with
        the locale 'und-u-ks-level2' and provider 'icu', and then verifies that the
        expected database queries are executed during creation and dropping of the
        collation. The test also checks the deconstruction of the CreateCollation
        operation to ensure it correctly returns its name, arguments, and keyword
        arguments. 
        """
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

        Tests the removal of a collation to ensure no database migrations are applied.

        This test case verifies that the removal of a collation through the database
        forwards and backwards operations does not trigger any database queries.
        It checks that no migrations are executed by verifying the query capture is empty
        during both the forwards and backwards operations.

        The test utilises a dummy project state and a CaptureQueriesContext to monitor
        database queries. It uses the NoMigrationRouter to ensure no migrations are run.

        The test covers the following scenarios:

        * Removing a collation through the database forwards operation
        * Removing a collation through the database backwards operation
        * Ensuring no database queries are executed during these operations

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

        Removes a database collation.

        Test the removal of a collation from the database, verifying that the collation
        is properly removed and the expected database queries are executed.

        Checks that the operation's name, description, and formatted description are
        correct, as well as its deconstruction into its constituent parts.

        Verifies the forward migration by applying the operation to the database and
        checking that the expected DROP COLLATION query is executed, and that attempting
        to apply the operation again raises a ProgrammingError.

        Also checks the backward migration by reversing the operation and verifying that
        the expected CREATE COLLATION query is executed.

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
        """
        Tests that adding a non-check constraint is not supported.

        Checks that attempting to add a constraint that is not a check constraint raises a
        TypeError with a specific error message. The constraint used in this test is a
        unique constraint. This ensures that only check constraints can be added, and any
        other type of constraint will result in an error.
        """
        constraint = UniqueConstraint(fields=["pink"], name="pony_pink_uniq")
        msg = "AddConstraintNotValid.constraint must be a check constraint."
        with self.assertRaisesMessage(TypeError, msg):
            AddConstraintNotValid(model_name="pony", constraint=constraint)

    def test_add(self):
        """
        ..: 
            Tests the addition of a not valid constraint to a model.

            This test case checks the following:

            * The description and formatted description of the operation are correct.
            * The migration name fragment is correct.
            * The constraint is added to the model's metadata.
            * The constraint does not exist on the database table before the operation.
            * The constraint is created on the database table after the operation.
            * The constraint is enforced on the database table.
            * The constraint can be removed from the database table.
            * The operation can be deconstructed correctly.
        """
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
