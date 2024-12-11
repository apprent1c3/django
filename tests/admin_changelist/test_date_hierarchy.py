from datetime import datetime

from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils.timezone import make_aware

from .admin import EventAdmin
from .admin import site as custom_site
from .models import Event


class DateHierarchyTests(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="super", email="a@b.com", password="xxx"
        )

    def assertDateParams(self, query, expected_from_date, expected_to_date):
        """
        Asserts that the date parameters in a query are correctly interpreted.

            This method takes in a query dictionary with date parameters, 
            the expected 'from' date and the expected 'to' date. It then 
            simulates a GET request with the query parameters, retrieves 
            the changelist instance for the Event model, and checks that 
            the lookup parameters match the expected date range.

            :param query: A dictionary containing date parameters.
            :param expected_from_date: The expected 'from' date.
            :param expected_to_date: The expected 'to' date.
            :return: None
        """
        query = {"date__%s" % field: val for field, val in query.items()}
        request = self.factory.get("/", query)
        request.user = self.superuser
        changelist = EventAdmin(Event, custom_site).get_changelist_instance(request)
        _, _, lookup_params, *_ = changelist.get_filters(request)
        self.assertEqual(lookup_params["date__gte"], [expected_from_date])
        self.assertEqual(lookup_params["date__lt"], [expected_to_date])

    def test_bounded_params(self):
        """

        Tests the bounding of parameters for date queries.

        This test checks that date parameters are correctly bounded based on the provided query parameters.
        It tests for various combinations of year, month, and day parameters, ensuring that the expected
        from and to dates are generated correctly.

        The test covers different scenarios, including queries that span across months and years, as well as
        those that are bounded by specific days.

        """
        tests = (
            ({"year": 2017}, datetime(2017, 1, 1), datetime(2018, 1, 1)),
            ({"year": 2017, "month": 2}, datetime(2017, 2, 1), datetime(2017, 3, 1)),
            ({"year": 2017, "month": 12}, datetime(2017, 12, 1), datetime(2018, 1, 1)),
            (
                {"year": 2017, "month": 12, "day": 15},
                datetime(2017, 12, 15),
                datetime(2017, 12, 16),
            ),
            (
                {"year": 2017, "month": 12, "day": 31},
                datetime(2017, 12, 31),
                datetime(2018, 1, 1),
            ),
            (
                {"year": 2017, "month": 2, "day": 28},
                datetime(2017, 2, 28),
                datetime(2017, 3, 1),
            ),
        )
        for query, expected_from_date, expected_to_date in tests:
            with self.subTest(query=query):
                self.assertDateParams(query, expected_from_date, expected_to_date)

    def test_bounded_params_with_time_zone(self):
        with self.settings(USE_TZ=True, TIME_ZONE="Asia/Jerusalem"):
            self.assertDateParams(
                {"year": 2017, "month": 2, "day": 28},
                make_aware(datetime(2017, 2, 28)),
                make_aware(datetime(2017, 3, 1)),
            )

    def test_bounded_params_with_dst_time_zone(self):
        """
        Tests bounded parameters when using daylight saving time (DST) aware time zones.

        This test case ensures that date parameters are correctly bounded when dealing with
        time zones that observe DST. It checks various time zones with different DST start
        and end dates, verifying that the bounded parameters accurately reflect the
        transition dates.

        The test iterates over a set of predefined time zones and months, simulating
        requests with different settings to validate the correctness of the bounded
        parameters. The test covers time zones with varying DST rules, such as Asia/Jerusalem
        and Pacific/Chatham, to ensure robustness and accuracy.

        Parameters are considered correctly bounded if they accurately reflect the DST
        transition dates for the given time zone and month. The test uses the
        :func:`make_aware` function to create aware datetime objects, which are then
        used to validate the bounded parameters.

        The test uses the :attr:`USE_TZ` and :attr:`TIME_ZONE` settings to simulate
        different time zone configurations, ensuring that the test results are accurate
        and reliable in various environments.
        """
        tests = [
            # Northern hemisphere.
            ("Asia/Jerusalem", 3),
            ("Asia/Jerusalem", 10),
            # Southern hemisphere.
            ("Pacific/Chatham", 4),
            ("Pacific/Chatham", 9),
        ]
        for time_zone, month in tests:
            with self.subTest(time_zone=time_zone, month=month):
                with self.settings(USE_TZ=True, TIME_ZONE=time_zone):
                    self.assertDateParams(
                        {"year": 2019, "month": month},
                        make_aware(datetime(2019, month, 1)),
                        make_aware(datetime(2019, month + 1, 1)),
                    )

    def test_invalid_params(self):
        tests = (
            {"year": "x"},
            {"year": 2017, "month": "x"},
            {"year": 2017, "month": 12, "day": "x"},
            {"year": 2017, "month": 13},
            {"year": 2017, "month": 12, "day": 32},
            {"year": 2017, "month": 0},
            {"year": 2017, "month": 12, "day": 0},
        )
        for invalid_query in tests:
            with (
                self.subTest(query=invalid_query),
                self.assertRaises(IncorrectLookupParameters),
            ):
                self.assertDateParams(invalid_query, None, None)
