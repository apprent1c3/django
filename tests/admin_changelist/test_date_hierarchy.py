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

        Asserts that the date parameters in a query are correctly processed and passed to the changelist.

        This function simulates a GET request to the changelist view with the provided query parameters,
        and then verifies that the resulting lookup parameters match the expected from and to dates.

        :param query: A dictionary of query parameters to be passed to the changelist view.
        :param expected_from_date: The expected from date to be used in the lookup parameters.
        :param expected_to_date: The expected to date to be used in the lookup parameters.

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
        Tests the date parameter bounds with various year, month, and day query inputs.

        This test case validates the correctness of date parameters by checking that the 
        date ranges for different query inputs are as expected. It covers various scenarios, 
        including queries with year only, year and month, and year, month, and day. The test 
        verifies that the date ranges are calculated correctly for each scenario, ensuring 
        that the date parameters are bounded as expected. This helps ensure that date 
        filtering and querying work correctly in the system.
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

        Tests the bounded parameters functionality when working with daylight saving time (DST) and different time zones.

        This test function iterates over a set of predefined time zones and months to ensure that the date parameters are correctly bounded.
        It checks the boundaries by verifying that the start and end dates are correctly set for each time zone and month combination.
        The test covers different scenarios with DST transitions to ensure the functionality works as expected in various time zones.

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
        """

        Checks that the function correctly handles invalid parameters for date queries.

        This test case covers various invalid input scenarios, including non-numeric values,
        out-of-range values for months and days, and invalid combinations of date components.
        It verifies that the function raises an IncorrectLookupParameters exception for each
        of these invalid query parameters.

        The test scenarios include:
        - Non-numeric year, month, or day values
        - Month values outside the range 1-12
        - Day values outside the valid range for the given month and year
        - Invalid combinations of date components

        """
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
