import pickle
from functools import wraps

from django.db import IntegrityError, connections, transaction
from django.test import TestCase, skipUnlessDBFeature
from django.test.testcases import (
    DatabaseOperationForbidden,
    SimpleTestCase,
    TestData,
    is_pickable,
)

from .models import Car, Person, PossessedCar


class UnpicklableObject:
    def __getstate__(self):
        raise pickle.PickleError("cannot be pickled for testing reasons")


class TestSimpleTestCase(SimpleTestCase):
    def test_is_picklable_with_non_picklable_properties(self):
        """ParallelTestSuite requires that all TestCases are picklable."""
        self.non_picklable = lambda: 0
        self.assertEqual(self, pickle.loads(pickle.dumps(self)))

    def test_is_picklable_with_non_picklable_object(self):
        """
        Tests whether the is_pickable function correctly identifies an object as non-picklable when it contains a non-picklable component. 

        This test utilizes an UnpicklableObject instance, which intentionally lacks the necessary properties for successful pickling, to verify the is_pickable function's capability to handle such cases. The function's expected output, in this case, is False, indicating that the object is indeed non-picklable.
        """
        unpicklable_obj = UnpicklableObject()
        self.assertEqual(is_pickable(unpicklable_obj), False)


class TestTestCase(TestCase):
    @skipUnlessDBFeature("can_defer_constraint_checks")
    @skipUnlessDBFeature("supports_foreign_keys")
    def test_fixture_teardown_checks_constraints(self):
        rollback_atomics = self._rollback_atomics
        self._rollback_atomics = lambda connection: None  # noop
        try:
            car = PossessedCar.objects.create(car_id=1, belongs_to_id=1)
            with self.assertRaises(IntegrityError), transaction.atomic():
                self._fixture_teardown()
            car.delete()
        finally:
            self._rollback_atomics = rollback_atomics

    def test_disallowed_database_connection(self):
        """
        Tests that connecting to a disallowed database raises a DatabaseOperationForbidden exception.

        This test ensures that attempting to establish a connection to a database not
        included in the test case's allowed databases results in a failure. The test
        verifies that both a regular connection and a temporary connection to the
        disallowed database raise the expected exception with a specific error message.

        The test is designed to enforce proper test isolation by preventing unauthorized
        database connections. To silence this failure, the disallowed database must be
        added to the list of allowed databases in test_utils.test_testcase.TestTestCase.databases.

        """
        message = (
            "Database connections to 'other' are not allowed in this test. "
            "Add 'other' to test_utils.test_testcase.TestTestCase.databases to "
            "ensure proper test isolation and silence this failure."
        )
        with self.assertRaisesMessage(DatabaseOperationForbidden, message):
            connections["other"].connect()
        with self.assertRaisesMessage(DatabaseOperationForbidden, message):
            connections["other"].temporary_connection()

    def test_disallowed_database_queries(self):
        message = (
            "Database queries to 'other' are not allowed in this test. "
            "Add 'other' to test_utils.test_testcase.TestTestCase.databases to "
            "ensure proper test isolation and silence this failure."
        )
        with self.assertRaisesMessage(DatabaseOperationForbidden, message):
            Car.objects.using("other").get()

    @skipUnlessDBFeature("supports_transactions")
    def test_reset_sequences(self):
        old_reset_sequences = self.reset_sequences
        self.reset_sequences = True
        msg = "reset_sequences cannot be used on TestCase instances"
        try:
            with self.assertRaisesMessage(TypeError, msg):
                self._fixture_setup()
        finally:
            self.reset_sequences = old_reset_sequences


def assert_no_queries(test):
    @wraps(test)
    """

    Decorator to assert that a test function does not execute any database queries.

    This decorator is used to validate that a test method does not interact with the database.
    It uses the :meth:`assertNumQueries` method to verify that no database queries are executed
    during the test. If any queries are executed, the test will fail.

    :arg test: The test function to be decorated.

    :raises AssertionError: If any database queries are executed during the test.

    """
    def inner(self):
        """

        Decorator inner function that temporarily disables database query assertions.

        This function wraps another test function, ensuring that no database queries are executed during its execution.
        It achieves this by utilizing a context manager that suppresses query assertions, allowing the wrapped test to run without interfering with database query checks.

        """
        with self.assertNumQueries(0):
            test(self)

    return inner


# On databases with no transaction support (for instance, MySQL with the MyISAM
# engine), setUpTestData() is called before each test, so there is no need to
# clone class level test data.
@skipUnlessDBFeature("supports_transactions")
class TestDataTests(TestCase):
    # setUpTestData re-assignment are also wrapped in TestData.
    jim_douglas = None

    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the test class.

        This method creates a set of test objects, including a person named 'Jim Douglas', 
        a car named '1963 Volkswagen Beetle', and an ownership relationship between them. 
        It also creates a person with binary data and retrieves this person by their primary key.

        These objects are stored as class attributes, allowing them to be reused across tests.

        """
        cls.jim_douglas = Person.objects.create(name="Jim Douglas")
        cls.car = Car.objects.create(name="1963 Volkswagen Beetle")
        cls.herbie = cls.jim_douglas.possessed_cars.create(
            car=cls.car,
            belongs_to=cls.jim_douglas,
        )

        cls.person_binary = Person.objects.create(name="Person", data=b"binary data")
        cls.person_binary_get = Person.objects.get(pk=cls.person_binary.pk)

    @assert_no_queries
    def test_class_attribute_equality(self):
        """Class level test data is equal to instance level test data."""
        self.assertEqual(self.jim_douglas, self.__class__.jim_douglas)
        self.assertEqual(self.person_binary, self.__class__.person_binary)
        self.assertEqual(self.person_binary_get, self.__class__.person_binary_get)

    @assert_no_queries
    def test_class_attribute_identity(self):
        """
        Class level test data is not identical to instance level test data.
        """
        self.assertIsNot(self.jim_douglas, self.__class__.jim_douglas)
        self.assertIsNot(self.person_binary, self.__class__.person_binary)
        self.assertIsNot(self.person_binary_get, self.__class__.person_binary_get)

    @assert_no_queries
    def test_binaryfield_data_type(self):
        """
        Tests the data type of BinaryField instances.

        Verifies that BinaryField data is correctly stored and retrieved as bytes, 
        and that the data type of the retrieved data matches the expected type.

        The test checks if the data stored in BinaryField instances is equal to the 
        expected binary data, and also ensures that the types of the data stored 
        in the instance and class variables are consistent.

        """
        self.assertEqual(bytes(self.person_binary.data), b"binary data")
        self.assertEqual(bytes(self.person_binary_get.data), b"binary data")
        self.assertEqual(
            type(self.person_binary_get.data),
            type(self.__class__.person_binary_get.data),
        )
        self.assertEqual(
            type(self.person_binary.data),
            type(self.__class__.person_binary.data),
        )

    @assert_no_queries
    def test_identity_preservation(self):
        """Identity of test data is preserved between accesses."""
        self.assertIs(self.jim_douglas, self.jim_douglas)

    @assert_no_queries
    def test_known_related_objects_identity_preservation(self):
        """Known related objects identity is preserved."""
        self.assertIs(self.herbie.car, self.car)
        self.assertIs(self.herbie.belongs_to, self.jim_douglas)

    def test_repr(self):
        self.assertEqual(
            repr(TestData("attr", "value")),
            "<TestData: name='attr', data='value'>",
        )


class SetupTestDataIsolationTests(TestCase):
    """
    In-memory data isolation is respected for model instances assigned to class
    attributes during setUpTestData.
    """

    @classmethod
    def setUpTestData(cls):
        cls.car = Car.objects.create(name="Volkswagen Beetle")

    def test_book_name_deutsh(self):
        self.assertEqual(self.car.name, "Volkswagen Beetle")
        self.car.name = "VW sKäfer"
        self.car.save()

    def test_book_name_french(self):
        """
        Tests that the car's name in French ('Coccinelle') is correctly set and saved.

        This test case verifies that a car object's name can be updated to its French
        equivalent and that the change is properly persisted when saved.
        """
        self.assertEqual(self.car.name, "Volkswagen Beetle")
        self.car.name = "Volkswagen Coccinelle"
        self.car.save()
