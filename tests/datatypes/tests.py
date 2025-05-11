import datetime

from django.test import TestCase, skipIfDBFeature

from .models import Donut, RumBaba


class DataTypesTestCase(TestCase):
    def test_boolean_type(self):
        """

        Tests the boolean fields of a Donut object, specifically the is_frosted and has_sprinkles attributes, to ensure they behave as expected upon instantiation, modification, and retrieval from the database.

        """
        d = Donut(name="Apple Fritter")
        self.assertFalse(d.is_frosted)
        self.assertIsNone(d.has_sprinkles)
        d.has_sprinkles = True
        self.assertTrue(d.has_sprinkles)

        d.save()

        d2 = Donut.objects.get(name="Apple Fritter")
        self.assertFalse(d2.is_frosted)
        self.assertTrue(d2.has_sprinkles)

    def test_date_type(self):
        """
        Tests whether the date-related fields of a Donut instance are correctly stored and retrieved from the database, specifically the baked date, time of baking, and time of consumption.
        """
        d = Donut(name="Apple Fritter")
        d.baked_date = datetime.date(year=1938, month=6, day=4)
        d.baked_time = datetime.time(hour=5, minute=30)
        d.consumed_at = datetime.datetime(
            year=2007, month=4, day=20, hour=16, minute=19, second=59
        )
        d.save()

        d2 = Donut.objects.get(name="Apple Fritter")
        self.assertEqual(d2.baked_date, datetime.date(1938, 6, 4))
        self.assertEqual(d2.baked_time, datetime.time(5, 30))
        self.assertEqual(d2.consumed_at, datetime.datetime(2007, 4, 20, 16, 19, 59))

    def test_time_field(self):
        # Test for ticket #12059: TimeField wrongly handling datetime.datetime object.
        """
        Verifies that the baked_time field is saved and retrieved as a time object, discarding the date component.
        """
        d = Donut(name="Apple Fritter")
        d.baked_time = datetime.datetime(
            year=2007, month=4, day=20, hour=16, minute=19, second=59
        )
        d.save()

        d2 = Donut.objects.get(name="Apple Fritter")
        self.assertEqual(d2.baked_time, datetime.time(16, 19, 59))

    def test_year_boundaries(self):
        """
        Tests the correct handling of year boundaries in Donut model date filtering, ensuring that queries using the `baked_date` and `consumed_at` fields properly account for the start and end of a year.
        """
        Donut.objects.create(
            name="Date Test 2007",
            baked_date=datetime.datetime(year=2007, month=12, day=31),
            consumed_at=datetime.datetime(
                year=2007, month=12, day=31, hour=23, minute=59, second=59
            ),
        )
        Donut.objects.create(
            name="Date Test 2006",
            baked_date=datetime.datetime(year=2006, month=1, day=1),
            consumed_at=datetime.datetime(year=2006, month=1, day=1),
        )
        self.assertEqual(
            "Date Test 2007", Donut.objects.filter(baked_date__year=2007)[0].name
        )
        self.assertEqual(
            "Date Test 2006", Donut.objects.filter(baked_date__year=2006)[0].name
        )

        Donut.objects.create(
            name="Apple Fritter",
            consumed_at=datetime.datetime(
                year=2007, month=4, day=20, hour=16, minute=19, second=59
            ),
        )

        self.assertEqual(
            ["Apple Fritter", "Date Test 2007"],
            list(
                Donut.objects.filter(consumed_at__year=2007)
                .order_by("name")
                .values_list("name", flat=True)
            ),
        )
        self.assertEqual(0, Donut.objects.filter(consumed_at__year=2005).count())
        self.assertEqual(0, Donut.objects.filter(consumed_at__year=2008).count())

    def test_textfields_str(self):
        """TextField values returned from the database should be str."""
        d = Donut.objects.create(name="Jelly Donut", review="Outstanding")
        newd = Donut.objects.get(id=d.id)
        self.assertIsInstance(newd.review, str)

    @skipIfDBFeature("supports_timezones")
    def test_error_on_timezone(self):
        """
        Tests that a ValueError is raised when trying to save a datetime object with timezone information to backends that do not support timezones, such as MySQL and Oracle.
        """
        dt = datetime.datetime(2008, 8, 31, 16, 20, tzinfo=datetime.timezone.utc)
        d = Donut(name="Bear claw", consumed_at=dt)
        # MySQL backend does not support timezone-aware datetimes.
        with self.assertRaises(ValueError):
            d.save()

    def test_datefield_auto_now_add(self):
        """
        Verifies the correct storage of datetime values for DateField with auto_now_add, ensuring a datetime.date object is stored instead of a datetime.datetime object.
        """
        b = RumBaba.objects.create()
        # Verify we didn't break DateTimeField behavior
        self.assertIsInstance(b.baked_timestamp, datetime.datetime)
        # We need to test this way because datetime.datetime inherits
        # from datetime.date:
        self.assertIsInstance(b.baked_date, datetime.date)
        self.assertNotIsInstance(b.baked_date, datetime.datetime)
