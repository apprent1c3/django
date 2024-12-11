from datetime import datetime
from unittest import mock

from django.db.models import DateTimeField, Value
from django.db.models.lookups import Lookup, YearLookup
from django.test import SimpleTestCase


class CustomLookup(Lookup):
    pass


class LookupTests(SimpleTestCase):
    def test_equality(self):
        lookup = Lookup(Value(1), Value(2))
        self.assertEqual(lookup, lookup)
        self.assertEqual(lookup, Lookup(lookup.lhs, lookup.rhs))
        self.assertEqual(lookup, mock.ANY)
        self.assertNotEqual(lookup, Lookup(lookup.lhs, Value(3)))
        self.assertNotEqual(lookup, Lookup(Value(3), lookup.rhs))
        self.assertNotEqual(lookup, CustomLookup(lookup.lhs, lookup.rhs))

    def test_repr(self):
        """

        Tests the representation of lookup objects by comparing their string representation with expected results.

        This test ensures that the repr function returns a string that accurately represents the lookup object, including its type and values. The test covers various lookup types, such as Lookup and YearLookup, and verifies that they are correctly formatted as strings.

        """
        tests = [
            (Lookup(Value(1), Value("a")), "Lookup(Value(1), Value('a'))"),
            (
                YearLookup(
                    Value(datetime(2010, 1, 1, 0, 0, 0)),
                    Value(datetime(2010, 1, 1, 23, 59, 59)),
                ),
                "YearLookup("
                "Value(datetime.datetime(2010, 1, 1, 0, 0)), "
                "Value(datetime.datetime(2010, 1, 1, 23, 59, 59)))",
            ),
        ]
        for lookup, expected in tests:
            with self.subTest(lookup=lookup):
                self.assertEqual(repr(lookup), expected)

    def test_hash(self):
        """

        Tests the hash function of the Lookup object.

        Ensures the hash value of a Lookup object is correctly calculated and is equal 
        to another Lookup object with the same lhs and rhs values. The test also 
        verifies that the hash value is different from Lookup objects with different 
        lhs or rhs values, as well as from objects of a different class (CustomLookup) 
        that have the same lhs and rhs values.

        This test validates the properties of the hash function, including reflexivity, 
        symmetry and non-equality for different objects.

        """
        lookup = Lookup(Value(1), Value(2))
        self.assertEqual(hash(lookup), hash(lookup))
        self.assertEqual(hash(lookup), hash(Lookup(lookup.lhs, lookup.rhs)))
        self.assertNotEqual(hash(lookup), hash(Lookup(lookup.lhs, Value(3))))
        self.assertNotEqual(hash(lookup), hash(Lookup(Value(3), lookup.rhs)))
        self.assertNotEqual(hash(lookup), hash(CustomLookup(lookup.lhs, lookup.rhs)))


class YearLookupTests(SimpleTestCase):
    def test_get_bound_params(self):
        """

        Tests that the get_bound_params method in subclasses of YearLookup is implemented.
        This test case checks if attempting to use the get_bound_params method of YearLookup
        directly results in a NotImplementedError, ensuring that subclasses provide their own implementation.

        """
        look_up = YearLookup(
            lhs=Value(datetime(2010, 1, 1, 0, 0, 0), output_field=DateTimeField()),
            rhs=Value(datetime(2010, 1, 1, 23, 59, 59), output_field=DateTimeField()),
        )
        msg = "subclasses of YearLookup must provide a get_bound_params() method"
        with self.assertRaisesMessage(NotImplementedError, msg):
            look_up.get_bound_params(
                datetime(2010, 1, 1, 0, 0, 0), datetime(2010, 1, 1, 23, 59, 59)
            )
