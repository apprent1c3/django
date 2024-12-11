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
        Tests whether the is_pickable function correctly identifies an object as non-picklable.

        This test case verifies that the is_pickable function returns False when given an object of a class that does not support pickling, ensuring that the function behaves as expected in the presence of non-picklable objects.

        :raises AssertionError: If the is_pickable function does not correctly identify the object as non-picklable
        """
        unpicklable_obj = UnpicklableObject()
        self.assertEqual(is_pickable(unpicklable_obj), False)


class TestTestCase(TestCase):
    @skipUnlessDBFeature("can_defer_constraint_checks")
    @skipUnlessDBFeature("supports_foreign_keys")
    def test_fixture_teardown_checks_constraints(self):
        """
        Tests if the constraints are checked during fixture teardown when foreign key support is available.

        This test case specifically checks the behavior when an object with a foreign key relationship is created and then the fixture teardown is triggered within an atomic transaction.

        It verifies that an IntegrityError is raised during the teardown process, ensuring that the database constraints are enforced as expected.

        The test is only executed if the database supports foreign key constraints and can defer constraint checks, providing a robust validation of the fixture teardown mechanism in supported environments.
        """
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
        """
        Test that database queries to a disallowed database raise an exception.

        This test checks that attempting to query a database that is not explicitly allowed
        for the test case in question will result in a :class:`DatabaseOperationForbidden`
        exception being raised, ensuring test isolation by preventing unintended database
        interactions. The allowed databases are specified in
        :test_attr:`test_utils.test_testcase.TestTestCase.databases`.
        """
        message = (
            "Database queries to 'other' are not allowed in this test. "
            "Add 'other' to test_utils.test_testcase.TestTestCase.databases to "
            "ensure proper test isolation and silence this failure."
        )
        with self.assertRaisesMessage(DatabaseOperationForbidden, message):
            Car.objects.using("other").get()

    @skipUnlessDBFeature("supports_transactions")
    def test_reset_sequences(self):
        """
        Tests that attempting to reset sequences on a TestCase instance raises a TypeError. 

        This test case checks the behavior when the reset_sequences property is set to True, 
        verifying that an error occurs as expected. The test is only run if the database 
        supports transactions.
        """
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
    Decorator to assert that a test case does not execute any database queries.

    Use this decorator to wrap a test method and ensure that it does not perform any queries on the database.
    It will raise an AssertionError if any queries are executed during the test.

    This is useful for testing methods that should not interact with the database, and can help catch unexpected database access.

    """
    def inner(self):
        """

        Wraps a test method to ensure it does not execute any database queries.

        This decorator is used to verify that a test does not perform any database operations,
        by asserting that the number of queries executed is zero.

        Use this decorator to guarantee that tests are isolated and do not inadvertently
        interact with the database, which can improve test reliability and performance.

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

        Sets up test data for the class.

        This method creates a set of test data, including a person, a car, and a relationship between the two.
        It also creates a person with binary data and retrieves it to test data integrity.

        The test data includes:
            - A person named Jim Douglas
            - A car, the 1963 Volkswagen Beetle
            - A possession relationship between Jim Douglas and the car
            - A person with binary data
            - A retrieved version of the person with binary data to test data consistency

        This data is used as a foundation for subsequent tests in the class.

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

        Tests the data type of BinaryField in the model.

        Verifies that the BinaryField contains the correct binary data and that the 
        data type is consistent across instances. The test checks for both 
         freshly retrieved and predefined binary data.

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
        """

        Tests the handling of a book name in German.

        Verifies that the name of the car object is initially set to the expected value, 
        then updates the name to a German equivalent and saves the changes.

        """
        self.assertEqual(self.car.name, "Volkswagen Beetle")
        self.car.name = "VW sKäfer"
        self.car.save()

    def test_book_name_french(self):
        """

        Tests that the car name is correctly updated to its French equivalent.

        This test case first verifies that the car's initial name is 'Volkswagen Beetle', 
        then updates the name to the French version 'Volkswagen Coccinelle', and 
        saves the changes to ensure the update is persisted.

        """
        self.assertEqual(self.car.name, "Volkswagen Beetle")
        self.car.name = "Volkswagen Coccinelle"
        self.car.save()
