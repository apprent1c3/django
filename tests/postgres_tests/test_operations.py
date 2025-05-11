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
        """
        Tests that the AddIndexConcurrently operation raises a NotSupportedError when executed inside a transaction, as it requires atomic to be set to False.
        """
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
        Tests the AddIndexConcurrently operation by verifying its correctness in describing the operation and applying the changes to a model, as well as its ability to backward and deconstruct correctly.
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
        Unlike some other indexes, a BRIN index cannot simply be added concurrently in the same way.
        This test checks the functionality of adding and removing a BRIN index concurrently to a model,
        ensuring that the index is correctly added and removed, and that its existence is properly verified.
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
        Tests the addition and removal of a BTree index concurrently using the AddIndexConcurrently operation.\"\"\"

        \"\"\" 
            The function sets up a test model, adds a BTree index on the 'pink' field, 
            and then checks that the index has been successfully added and removed.

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
        """
        Tests that RemoveIndexConcurrently operation raises an error when executed inside a transaction.

        Ensures that the operation correctly enforces atomic=False on the migration.
        """
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
        """
        Tests the concurrent removal of an index from a database table.

        Verifies that the RemoveIndexConcurrently operation correctly removes an existing index
        from a model, and that it can be reversed to restore the index.
        """
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
        """
        Tests that the CreateExtension operation does not allow migrate actions, ensuring it doesn't execute any database queries when applied or reversed.
        """
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
        ```\"\"\"Tests the creation and reversal of a database extension using the CreateExtension operation.

        Verifies that the correct SQL queries are executed for both the forward and backward migration operations.
        \"\"\"```
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
        Tests the creation of an existing database extension, ensuring the correct operation name and number of SQL queries are executed during the migration process.
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
        """
        Tests that dropping a nonexistent extension results in a single SQL query to check its existence.
        """
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
        """

        Tests that the CreateCollation operation does not allow migrations to be applied.

        Verifies that neither the forwards nor backwards database operations result in any SQL queries being executed.

        """
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
        Tests the creation of a collation in a database schema.

        Verifies that the migration operation generates the correct SQL statements for creating and dropping a collation,
        as well as its string representation and deconstruction into component parts.
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
        """
        Tests the creation and removal of a non-deterministic database collation using the CreateCollation operation, verifying the correct SQL queries are executed and deconstruction of the operation produces the expected result.
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
        """
        Tests the creation and removal of a collation with a specific provider and locale, verifying that the correct SQL queries are executed.
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
        Tests removal of a database collation without allowing migrations.

        This test case verifies that removing a collation does not result in any database queries,
        either when applying or reversing the operation.
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
        Tests the removal of a collation, including the database operations and migration descriptions, 
        ensuring correct functionality in both forwards and backwards migrations and state reconstruction.
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
        """
        Tests the behavior of adding a not valid constraint to a model in a migration. 

        Checks that the operation correctly describes the constraint addition, 
        that it is not created initially, that database forwards and backwards 
        operations add and remove the constraint, and that it raises an integrity 
        error when trying to create an instance violating the constraint.
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
        """
        Test that a database constraint validation operation works correctly. 

        The operation adds a check constraint to the 'Pony' model, then attempts to validate this constraint under both valid and invalid conditions. The operation's effects on the database are also tested, as well as the operation's backwards migration and deconstruction.
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
