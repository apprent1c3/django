from django.db import connection
from django.db.models import Value
from django.db.models.functions import Length, LPad, RPad
from django.test import TestCase

from ..models import Author


class PadTests(TestCase):
    def test_pad(self):
        """
        Tests the functionality of the LPad and RPad database functions for padding strings.

        The function creates an Author object and then performs a series of tests on the 
        LPad and RPad functions, checking that they correctly pad the string with the 
        specified characters or spaces, and that they handle edge cases such as null 
        values, zero-length padding, and padding with None. The test cases cover both 
        left and right padding, and verify that the results are as expected.

        The tests are performed on the 'name' field of the Author object, as well as on 
        a field with a null value ('goes_by'), and on a Value object with a null value. 
        The results are compared to the expected padded strings, and any deviations are 
        reported as test failures.
        """
        Author.objects.create(name="John", alias="j")
        none_value = (
            "" if connection.features.interprets_empty_strings_as_nulls else None
        )
        tests = (
            (LPad("name", 7, Value("xy")), "xyxJohn"),
            (RPad("name", 7, Value("xy")), "Johnxyx"),
            (LPad("name", 6, Value("x")), "xxJohn"),
            (RPad("name", 6, Value("x")), "Johnxx"),
            # The default pad string is a space.
            (LPad("name", 6), "  John"),
            (RPad("name", 6), "John  "),
            # If string is longer than length it is truncated.
            (LPad("name", 2), "Jo"),
            (RPad("name", 2), "Jo"),
            (LPad("name", 0), ""),
            (RPad("name", 0), ""),
            (LPad("name", None), none_value),
            (RPad("name", None), none_value),
            (LPad(Value(None), 1), none_value),
            (RPad(Value(None), 1), none_value),
            (LPad("goes_by", 1), none_value),
            (RPad("goes_by", 1), none_value),
        )
        for function, padded_name in tests:
            with self.subTest(function=function):
                authors = Author.objects.annotate(padded_name=function)
                self.assertQuerySetEqual(
                    authors, [padded_name], lambda a: a.padded_name, ordered=False
                )

    def test_pad_negative_length(self):
        """
        Tests that padding functions (LPad and RPad) correctly handle negative length values by raising a ValueError with an appropriate message, ensuring that 'length' is always greater than or equal to 0.
        """
        for function in (LPad, RPad):
            with self.subTest(function=function):
                with self.assertRaisesMessage(
                    ValueError, "'length' must be greater or equal to 0."
                ):
                    function("name", -1)

    def test_combined_with_length(self):
        """

        Tests the functionality of combining LPad function with Length function in a Django ORM query.

        This test case creates two authors with different names and aliases, then annotates the authors 
        with a new field 'filled' which is the result of left-padding the author's name with spaces to 
        match the length of their alias. The authors are then sorted by their aliases and the resulting 
        'filled' field values are compared to the expected output.

        """
        Author.objects.create(name="Rhonda", alias="john_smith")
        Author.objects.create(name="♥♣♠", alias="bytes")
        authors = Author.objects.annotate(filled=LPad("name", Length("alias")))
        self.assertQuerySetEqual(
            authors.order_by("alias"),
            ["  ♥♣♠", "    Rhonda"],
            lambda a: a.filled,
        )
