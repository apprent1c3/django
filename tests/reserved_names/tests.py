import datetime

from django.test import TestCase

from .models import Thing


class ReservedNameTests(TestCase):
    def generate(self):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
        """
        self.generate()
        things = [t.when for t in Thing.objects.order_by("when")]
        self.assertEqual(things, ["a", "h"])

    def test_fields(self):
        """
        This is a comment
        """
        self.generate()
        v = Thing.objects.get(pk="a")
        self.assertEqual(v.join, "b")
        self.assertEqual(v.where, datetime.date(year=2005, month=1, day=1))

    def test_dates(self):
        """
        This is a comment
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
        This is a comment
        """
        self.generate()
        self.assertEqual(Thing.objects.filter(where__month=1)[0].when, "a")
