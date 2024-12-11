import copy
import datetime
import os
from unittest import mock

from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.db.backends.base.creation import TEST_DATABASE_PREFIX, BaseDatabaseCreation
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import override_settings

from ..models import (
    CircularA,
    CircularB,
    Object,
    ObjectReference,
    ObjectSelfReference,
    SchoolBus,
    SchoolClass,
)


def get_connection_copy():
    # Get a copy of the default connection. (Can't use django.db.connection
    # because it'll modify the default connection itself.)
    test_connection = copy.copy(connections[DEFAULT_DB_ALIAS])
    test_connection.settings_dict = copy.deepcopy(
        connections[DEFAULT_DB_ALIAS].settings_dict
    )
    return test_connection


class TestDbSignatureTests(SimpleTestCase):
    def test_default_name(self):
        # A test db name isn't set.
        """

        Tests that the default test database name is correctly generated when the 'TEST' setting is not specified.

        The test case checks if the test database name is prefixed with the test database prefix and the production database name.

        This ensures that the test database is properly named and can be identified when running tests.

        """
        prod_name = "hodor"
        test_connection = get_connection_copy()
        test_connection.settings_dict["NAME"] = prod_name
        test_connection.settings_dict["TEST"] = {"NAME": None}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], TEST_DATABASE_PREFIX + prod_name)

    def test_custom_test_name(self):
        # A regular test db name is set.
        """
        Tests that the test database name is correctly generated when a custom test name is provided.

        Verifies that the database connection settings are properly updated and the
        generated database signature matches the expected test name.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the generated database signature does not match the expected test name.
        """
        test_name = "hodor"
        test_connection = get_connection_copy()
        test_connection.settings_dict["TEST"] = {"NAME": test_name}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], test_name)

    def test_custom_test_name_with_test_prefix(self):
        # A test db name prefixed with TEST_DATABASE_PREFIX is set.
        test_name = TEST_DATABASE_PREFIX + "hodor"
        test_connection = get_connection_copy()
        test_connection.settings_dict["TEST"] = {"NAME": test_name}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], test_name)


@override_settings(INSTALLED_APPS=["backends.base.app_unmigrated"])
@mock.patch.object(connection, "ensure_connection")
@mock.patch.object(connection, "prepare_database")
@mock.patch(
    "django.db.migrations.recorder.MigrationRecorder.has_table", return_value=False
)
@mock.patch("django.core.management.commands.migrate.Command.sync_apps")
class TestDbCreationTests(SimpleTestCase):
    available_apps = ["backends.base.app_unmigrated"]

    @mock.patch("django.db.migrations.executor.MigrationExecutor.migrate")
    def test_migrate_test_setting_false(
        self, mocked_migrate, mocked_sync_apps, *mocked_objects
    ):
        """

        Tests that migration occurs correctly when test settings dictate it should not.
        Verifies that the migration executor's migrate method is called despite the 
        test setting 'MIGRATE' being set to False, and that the migration plan is 
        empty. Also checks that sync_apps function is called with the correct 
        arguments.

        """
        test_connection = get_connection_copy()
        test_connection.settings_dict["TEST"]["MIGRATE"] = False
        creation = test_connection.creation_class(test_connection)
        if connection.vendor == "oracle":
            # Don't close connection on Oracle.
            creation.connection.close = mock.Mock()
        old_database_name = test_connection.settings_dict["NAME"]
        try:
            with mock.patch.object(creation, "_create_test_db"):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            # Migrations don't run.
            mocked_migrate.assert_called()
            args, kwargs = mocked_migrate.call_args
            self.assertEqual(args, ([],))
            self.assertEqual(kwargs["plan"], [])
            # App is synced.
            mocked_sync_apps.assert_called()
            mocked_args, _ = mocked_sync_apps.call_args
            self.assertEqual(mocked_args[1], {"app_unmigrated"})
        finally:
            with mock.patch.object(creation, "_destroy_test_db"):
                creation.destroy_test_db(old_database_name, verbosity=0)

    @mock.patch("django.db.migrations.executor.MigrationRecorder.ensure_schema")
    def test_migrate_test_setting_false_ensure_schema(
        self,
        mocked_ensure_schema,
        mocked_sync_apps,
        *mocked_objects,
    ):
        """

        Tests the migration behavior when the TEST MIGRATE setting is set to False.

        This test case verifies that the migration recorder's ensure schema method is not called
        and the sync apps method is called with the correct arguments when the TEST MIGRATE setting
        is set to False. It also ensures that the test database is properly created and destroyed
        in the process.

        The test handles the specific case of Oracle databases by mocking the connection close method.

        """
        test_connection = get_connection_copy()
        test_connection.settings_dict["TEST"]["MIGRATE"] = False
        creation = test_connection.creation_class(test_connection)
        if connection.vendor == "oracle":
            # Don't close connection on Oracle.
            creation.connection.close = mock.Mock()
        old_database_name = test_connection.settings_dict["NAME"]
        try:
            with mock.patch.object(creation, "_create_test_db"):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            # The django_migrations table is not created.
            mocked_ensure_schema.assert_not_called()
            # App is synced.
            mocked_sync_apps.assert_called()
            mocked_args, _ = mocked_sync_apps.call_args
            self.assertEqual(mocked_args[1], {"app_unmigrated"})
        finally:
            with mock.patch.object(creation, "_destroy_test_db"):
                creation.destroy_test_db(old_database_name, verbosity=0)

    @mock.patch("django.db.migrations.executor.MigrationExecutor.migrate")
    def test_migrate_test_setting_true(
        self, mocked_migrate, mocked_sync_apps, *mocked_objects
    ):
        """

        Test the migration process when the 'MIGRATE' setting is True in the test database settings.

        This function verifies that the migration is executed correctly when the 'MIGRATE' setting is enabled.
        It tests the creation of the test database, the migration process, and the subsequent destruction of the test database.
        The test case covers the scenario where the migration is applied to the test database and ensures that the migration plan is correctly generated.
        Additionally, it checks that the 'sync_apps' method is not called during the migration process.
        The test is designed to work with different database vendors, including Oracle, and handles specific edge cases for each vendor.

        """
        test_connection = get_connection_copy()
        test_connection.settings_dict["TEST"]["MIGRATE"] = True
        creation = test_connection.creation_class(test_connection)
        if connection.vendor == "oracle":
            # Don't close connection on Oracle.
            creation.connection.close = mock.Mock()
        old_database_name = test_connection.settings_dict["NAME"]
        try:
            with mock.patch.object(creation, "_create_test_db"):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            # Migrations run.
            mocked_migrate.assert_called()
            args, kwargs = mocked_migrate.call_args
            self.assertEqual(args, ([("app_unmigrated", "0001_initial")],))
            self.assertEqual(len(kwargs["plan"]), 1)
            # App is not synced.
            mocked_sync_apps.assert_not_called()
        finally:
            with mock.patch.object(creation, "_destroy_test_db"):
                creation.destroy_test_db(old_database_name, verbosity=0)

    @mock.patch.dict(os.environ, {"RUNNING_DJANGOS_TEST_SUITE": ""})
    @mock.patch("django.db.migrations.executor.MigrationExecutor.migrate")
    @mock.patch.object(BaseDatabaseCreation, "mark_expected_failures_and_skips")
    def test_mark_expected_failures_and_skips_call(
        self, mark_expected_failures_and_skips, *mocked_objects
    ):
        """
        mark_expected_failures_and_skips() isn't called unless
        RUNNING_DJANGOS_TEST_SUITE is 'true'.
        """
        test_connection = get_connection_copy()
        creation = test_connection.creation_class(test_connection)
        if connection.vendor == "oracle":
            # Don't close connection on Oracle.
            creation.connection.close = mock.Mock()
        old_database_name = test_connection.settings_dict["NAME"]
        try:
            with mock.patch.object(creation, "_create_test_db"):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            self.assertIs(mark_expected_failures_and_skips.called, False)
        finally:
            with mock.patch.object(creation, "_destroy_test_db"):
                creation.destroy_test_db(old_database_name, verbosity=0)


class TestDeserializeDbFromString(TransactionTestCase):
    available_apps = ["backends"]

    def test_circular_reference(self):
        # deserialize_db_from_string() handles circular references.
        """
        .. method:: test_circular_reference

            Tests the correct handling of a circular reference between two objects.

            This test case verifies that when two objects reference each other, the 
            deserialization and retrieval of these objects results in the correct 
            relationships being established. It creates objects with a circular 
            reference in the database and checks that the object references are 
            correctly resolved, confirming that the forward and reverse relationships 
            between the objects are properly set up.
        """
        data = """
        [
            {
                "model": "backends.object",
                "pk": 1,
                "fields": {"obj_ref": 1, "related_objects": []}
            },
            {
                "model": "backends.objectreference",
                "pk": 1,
                "fields": {"obj": 1}
            }
        ]
        """
        connection.creation.deserialize_db_from_string(data)
        obj = Object.objects.get()
        obj_ref = ObjectReference.objects.get()
        self.assertEqual(obj.obj_ref, obj_ref)
        self.assertEqual(obj_ref.obj, obj)

    def test_self_reference(self):
        # serialize_db_to_string() and deserialize_db_from_string() handles
        # self references.
        """

        Tests the self-referential relationship between objects in the ObjectSelfReference model.

        Verifies that when an object references another object, and that referenced object is then updated to reference the original object,
        the relationship is correctly established and persisted in the database.

        The test creates two objects with a self-referential relationship, saves them to the database, serializes the database state,
        deserializes it back, and then checks that the objects still correctly reference each other.

        """
        obj_1 = ObjectSelfReference.objects.create(key="X")
        obj_2 = ObjectSelfReference.objects.create(key="Y", obj=obj_1)
        obj_1.obj = obj_2
        obj_1.save()
        # Serialize objects.
        with mock.patch("django.db.migrations.loader.MigrationLoader") as loader:
            # serialize_db_to_string() serializes only migrated apps, so mark
            # the backends app as migrated.
            loader_instance = loader.return_value
            loader_instance.migrated_apps = {"backends"}
            data = connection.creation.serialize_db_to_string()
        ObjectSelfReference.objects.all().delete()
        # Deserialize objects.
        connection.creation.deserialize_db_from_string(data)
        obj_1 = ObjectSelfReference.objects.get(key="X")
        obj_2 = ObjectSelfReference.objects.get(key="Y")
        self.assertEqual(obj_1.obj, obj_2)
        self.assertEqual(obj_2.obj, obj_1)

    def test_circular_reference_with_natural_key(self):
        # serialize_db_to_string() and deserialize_db_from_string() handles
        # circular references for models with natural keys.
        """

        Tests the handling of circular references between objects with natural keys.

        This test creates instances of CircularA and CircularB, establishes a circular reference between them,
        and then tests whether the reference is correctly restored after serializing and deserializing the database.

        The test covers the following scenarios:
        - Creation of objects with circular references
        - Serialization of the database with circular references
        - Deserialization of the database and restoration of circular references
        - Verification that the restored references are correct

        The goal of this test is to ensure that the system can handle complex relationships between objects and restore them correctly after serialization and deserialization.

        """
        obj_a = CircularA.objects.create(key="A")
        obj_b = CircularB.objects.create(key="B", obj=obj_a)
        obj_a.obj = obj_b
        obj_a.save()
        # Serialize objects.
        with mock.patch("django.db.migrations.loader.MigrationLoader") as loader:
            # serialize_db_to_string() serializes only migrated apps, so mark
            # the backends app as migrated.
            loader_instance = loader.return_value
            loader_instance.migrated_apps = {"backends"}
            data = connection.creation.serialize_db_to_string()
        CircularA.objects.all().delete()
        CircularB.objects.all().delete()
        # Deserialize objects.
        connection.creation.deserialize_db_from_string(data)
        obj_a = CircularA.objects.get()
        obj_b = CircularB.objects.get()
        self.assertEqual(obj_a.obj, obj_b)
        self.assertEqual(obj_b.obj, obj_a)

    def test_serialize_db_to_string_base_manager(self):
        """

        Tests the serialization of the database to a string using the base manager.

        Verifies that the database can be successfully serialized to a string, including
        the created model instances. Specifically, this test checks that the serialized
        string contains the expected model and field data.

        The test creates a `SchoolClass` object, patches the migration loader to return a
        migrated apps dictionary, and then calls the `serialize_db_to_string` method to
        generate the serialized string. The resulting string is then checked for the
        presence of the expected model and field data.

        """
        SchoolClass.objects.create(year=1000, last_updated=datetime.datetime.now())
        with mock.patch("django.db.migrations.loader.MigrationLoader") as loader:
            # serialize_db_to_string() serializes only migrated apps, so mark
            # the backends app as migrated.
            loader_instance = loader.return_value
            loader_instance.migrated_apps = {"backends"}
            data = connection.creation.serialize_db_to_string()
        self.assertIn('"model": "backends.schoolclass"', data)
        self.assertIn('"year": 1000', data)

    def test_serialize_db_to_string_base_manager_with_prefetch_related(self):
        """
        Tests the serialization of a database to a string, specifically focusing on a base manager with prefetch related objects.

        Verifies that the serialized data contains the expected models, including SchoolBus and SchoolClass, as well as the relationships between them, such as the school classes assigned to a school bus.

        Ensures that the serialization process correctly captures the data, including the primary keys of related objects, to guarantee data integrity and complete representation of the database state.

        Validation is performed by checking the presence of specific model and relationship indicators in the serialized data, confirming that the expected information is included and correctly formatted.
        """
        sclass = SchoolClass.objects.create(
            year=2000, last_updated=datetime.datetime.now()
        )
        bus = SchoolBus.objects.create(number=1)
        bus.schoolclasses.add(sclass)
        with mock.patch("django.db.migrations.loader.MigrationLoader") as loader:
            # serialize_db_to_string() serializes only migrated apps, so mark
            # the backends app as migrated.
            loader_instance = loader.return_value
            loader_instance.migrated_apps = {"backends"}
            data = connection.creation.serialize_db_to_string()
        self.assertIn('"model": "backends.schoolbus"', data)
        self.assertIn('"model": "backends.schoolclass"', data)
        self.assertIn(f'"schoolclasses": [{sclass.pk}]', data)


class SkipTestClass:
    def skip_function(self):
        pass


def skip_test_function():
    pass


def expected_failure_test_function():
    pass


class TestMarkTests(SimpleTestCase):
    def test_mark_expected_failures_and_skips(self):
        """
        Marks expected failures and skips in database creation tests, allowing for the identification of tests that are expected to fail or should be skipped.

        The expected failures are denoted by a list of test functions that are anticipated to fail during execution. Similarly, skips are categorized by test classes or functions that should be bypassed along with a corresponding reason for skipping.

        This function is essential for managing test cases that may not pass due to various reasons, such as incomplete implementations, known issues, or external dependencies. By marking these tests as expected failures or skips, developers can distinguish between genuine test failures and those that are anticipated or intentionally skipped, facilitating a more efficient and targeted testing process.
        """
        test_connection = get_connection_copy()
        creation = BaseDatabaseCreation(test_connection)
        creation.connection.features.django_test_expected_failures = {
            "backends.base.test_creation.expected_failure_test_function",
        }
        creation.connection.features.django_test_skips = {
            "skip test class": {
                "backends.base.test_creation.SkipTestClass",
            },
            "skip test function": {
                "backends.base.test_creation.skip_test_function",
            },
        }
        creation.mark_expected_failures_and_skips()
        self.assertIs(
            expected_failure_test_function.__unittest_expecting_failure__,
            True,
        )
        self.assertIs(SkipTestClass.__unittest_skip__, True)
        self.assertEqual(
            SkipTestClass.__unittest_skip_why__,
            "skip test class",
        )
        self.assertIs(skip_test_function.__unittest_skip__, True)
        self.assertEqual(
            skip_test_function.__unittest_skip_why__,
            "skip test function",
        )
