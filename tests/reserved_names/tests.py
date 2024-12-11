import datetime

from django.test import TestCase

from .models import Thing


class ReservedNameTests(TestCase):
    def generate(self):
        """
        Generate a set of Thing objects in the database.

        This function creates two Thing instances with different attributes and saves them to the database. 
        The attributes include various database operation-related fields ('when', 'join', 'like', 'drop', 'alter', 'having') 
        and a date field ('where'). The function uses specific dates for each object: January 1, 2005, and February 2, 2006.

        Returns:
            None

        Note:
            This function appears to be used for seeding or testing the database with sample data.
            The generated data is hardcoded and may need to be modified to suit specific use cases.

        """
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

        Tests the creation of Thing objects with various attributes.

        Verifies that the 'when' attribute of a newly created Thing object
        is correctly set and retrieved. The test creates two Thing objects,
        one with a specific date and another with a different date, and
        checks that the 'when' attribute is correctly assigned in both cases.

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
        self.generate()
        things = [t.when for t in Thing.objects.order_by("when")]
        self.assertEqual(things, ["a", "h"])

    def test_fields(self):
        self.generate()
        v = Thing.objects.get(pk="a")
        self.assertEqual(v.join, "b")
        self.assertEqual(v.where, datetime.date(year=2005, month=1, day=1))

    def test_dates(self):
        """

        Tests that the dates method of the Thing object manager returns the correct list of dates.

        This test case verifies that the dates method, when called on the 'where' field with a 'year' kind, returns a list of dates as expected.

        The expected output includes dates from the years 2005 and 2006, specifically January 1st of each year. 

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
        """
        Tests the filtering of 'Thing' objects by month.

        Verify that the 'where__month' filter correctly returns objects with 'when' value set to the expected string, 
        in this case 'a', for the month of January (1).
        """
        self.generate()
        self.assertEqual(Thing.objects.filter(where__month=1)[0].when, "a")
