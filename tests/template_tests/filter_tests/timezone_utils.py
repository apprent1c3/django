from datetime import date, datetime

from django.test import SimpleTestCase
from django.utils import timezone


class TimezoneTestCase(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
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
