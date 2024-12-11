from django.test import SimpleTestCase
from django.utils.hashable import make_hashable


class TestHashable(SimpleTestCase):
    def test_equal(self):
        tests = (
            ([], ()),
            (["a", 1], ("a", 1)),
            ({}, ()),
            ({"a"}, ("a",)),
            (frozenset({"a"}), {"a"}),
            ({"a": 1, "b": 2}, (("a", 1), ("b", 2))),
            ({"b": 2, "a": 1}, (("a", 1), ("b", 2))),
            (("a", ["b", 1]), ("a", ("b", 1))),
            (("a", {"b": 1}), ("a", (("b", 1),))),
        )
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(make_hashable(value), expected)

    def test_count_equal(self):
        """

        Tests the make_hashable function's ability to correctly convert different types of data structures into hashable objects.

        This test uses a series of test cases to verify that the conversion is done accurately.
        It checks for both simple and nested structures, including lists and tuples.
        The expected output for each test case is compared to the actual output from the make_hashable function,
        ensuring that the count of each element is equal, regardless of order.

        The test covers different scenarios, such as dictionaries with list or tuple values, to ensure the function works as expected.

        """
        tests = (
            ({"a": 1, "b": ["a", 1]}, (("a", 1), ("b", ("a", 1)))),
            ({"a": 1, "b": ("a", [1, 2])}, (("a", 1), ("b", ("a", (1, 2))))),
        )
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertCountEqual(make_hashable(value), expected)

    def test_unhashable(self):
        """
        Tests that attempting to make an unhashable object hashable raises a TypeError.

         The function creates an example unhashable class and attempts to make an instance 
         of it hashable, then verifies that a TypeError is raised with the expected message.

         This test case ensures that the make_hashable function correctly handles objects 
         that do not support hashing and provides a useful error message in such cases.
        """
        class Unhashable:
            __hash__ = None

        with self.assertRaisesMessage(TypeError, "unhashable type: 'Unhashable'"):
            make_hashable(Unhashable())
