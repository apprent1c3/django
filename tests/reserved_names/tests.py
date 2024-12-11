import datetime

from django.test import TestCase

from .models import Thing


class ReservedNameTests(TestCase):
    def generate(self):
        day1 = datetime.date(2005, 1, 1)
        Thing.objects.create(
            when="a",
            join="b",
            like="c",
            drop="d",
            alter="e",
            having="f",
            where=day1,
            has_hyphen="h",
        )
        day2 = datetime.date(2006, 2, 2)
        Thing.objects.create(
            when="h",
            join="i",
            like="j",
            drop="k",
            alter="l",
            having="m",
            where=day2,
        )

    def test_simple(self):
        """

        Tests the creation of Thing objects with different attribute values.

        This test function verifies that the 'when' attribute of a Thing object is correctly set upon creation.
        It checks this by creating two Thing objects with different 'when' values and asserting that the values are correctly stored.
        The test also covers the creation of objects with various other attributes, including 'join', 'like', 'drop', 'alter', 'having', 'where', and 'has_hyphen'.

        """
        day1 = datetime.date(2005, 1, 1)
        t = Thing.objects.create(
            when="a",
            join="b",
            like="c",
            drop="d",
            alter="e",
            having="f",
            where=day1,
            has_hyphen="h",
        )
        self.assertEqual(t.when, "a")

        day2 = datetime.date(2006, 2, 2)
        u = Thing.objects.create(
            when="h",
            join="i",
            like="j",
            drop="k",
            alter="l",
            having="m",
            where=day2,
        )
        self.assertEqual(u.when, "h")

    def test_order_by(self):
        """
        Tests the ordering functionality of Thing objects.

        This test case verifies that Thing objects are correctly ordered by their 'when' attribute.
        It generates a set of objects, retrieves them in the specified order, and checks if the result matches the expected order.

        The expected outcome is a list of 'when' values in ascending order, which in this case is ['a', 'h'].

        It ensures that the order_by method is working as intended, allowing for reliable sorting of Thing objects based on their 'when' attribute.
        """
        self.generate()
        things = [t.when for t in Thing.objects.order_by("when")]
        self.assertEqual(things, ["a", "h"])

    def test_fields(self):
        """
        Tests that the generated fields are correctly populated.

        This test case verifies that the `join` and `where` fields of a `Thing` object contain the expected values after generation.
        """
        self.generate()
        v = Thing.objects.get(pk="a")
        self.assertEqual(v.join, "b")
        self.assertEqual(v.where, datetime.date(year=2005, month=1, day=1))

    def test_dates(self):
        """

        Tests the retrieval of unique dates from the Thing model.

        This test case generates test data and then queries the database to retrieve
        a list of distinct years in which 'where' events occurred. The result is
        compared to an expected list of dates to ensure correctness.

        """
        self.generate()
        resp = Thing.objects.dates("where", "year")
        self.assertEqual(
            list(resp),
            [
                datetime.date(2005, 1, 1),
                datetime.date(2006, 1, 1),
            ],
        )

    def test_month_filter(self):
        self.generate()
        self.assertEqual(Thing.objects.filter(where__month=1)[0].when, "a")
