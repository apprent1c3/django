from datetime import date, datetime

from django.test import SimpleTestCase
from django.utils import timezone


class TimezoneTestCase(SimpleTestCase):
    def setUp(self):
        """
        Sets up the test environment by initializing various date and time variables.

        The function populates the following instance variables:

        * `now`: the current date and time
        * `now_tz`: the current date and time in the default timezone
        * `now_tz_i`: the current date and time in a timezone with a fixed offset of 195 minutes from UTC
        * `today`: the current date

        These variables can be used throughout the test suite to ensure consistent and predictable behavior.
        """
        self.now = datetime.now()
        self.now_tz = timezone.make_aware(
            self.now,
            timezone.get_default_timezone(),
        )
        self.now_tz_i = timezone.localtime(
            self.now_tz,
            timezone.get_fixed_timezone(195),
        )
        self.today = date.today()
