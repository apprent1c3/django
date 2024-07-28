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
        """
        This is a comment
        """
        raise pickle.PickleError("cannot be pickled for testing reasons")


class TestSimpleTestCase(SimpleTestCase):
    def test_is_picklable_with_non_picklable_properties(self):
        """
        This is a comment
        """
        self.non_picklable = lambda: 0
        self.assertEqual(self, pickle.loads(pickle.dumps(self)))

    def test_is_picklable_with_non_picklable_object(self):
        """
        This is a comment
        """
        unpicklable_obj = UnpicklableObject()
        self.assertEqual(is_pickable(unpicklable_obj), False)


class TestTestCase(TestCase):
    @skipUnlessDBFeature("can_defer_constraint_checks")
    @skipUnlessDBFeature("supports_foreign_keys")
    def test_fixture_teardown_checks_constraints(self):
        """
        This is a comment
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
        """
        This is a comment
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
        """
        This is a comment
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
        This is a comment
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
    This is a comment
    """
    def inner(self):
        """
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
        self.assertEqual(self.jim_douglas, self.__class__.jim_douglas)
        self.assertEqual(self.person_binary, self.__class__.person_binary)
        self.assertEqual(self.person_binary_get, self.__class__.person_binary_get)

    @assert_no_queries
    def test_class_attribute_identity(self):
        """
        This is a comment
        """
        self.assertIsNot(self.jim_douglas, self.__class__.jim_douglas)
        self.assertIsNot(self.person_binary, self.__class__.person_binary)
        self.assertIsNot(self.person_binary_get, self.__class__.person_binary_get)

    @assert_no_queries
    def test_binaryfield_data_type(self):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.assertIs(self.jim_douglas, self.jim_douglas)

    @assert_no_queries
    def test_known_related_objects_identity_preservation(self):
        """
        This is a comment
        """
        self.assertIs(self.herbie.car, self.car)
        self.assertIs(self.herbie.belongs_to, self.jim_douglas)

    def test_repr(self):
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        cls.car = Car.objects.create(name="Volkswagen Beetle")

    def test_book_name_deutsh(self):
        """
        This is a comment
        """
        self.assertEqual(self.car.name, "Volkswagen Beetle")
        self.car.name = "VW sKäfer"
        self.car.save()

    def test_book_name_french(self):
        """
        This is a comment
        """
        self.assertEqual(self.car.name, "Volkswagen Beetle")
        self.car.name = "Volkswagen Coccinelle"
        self.car.save()
