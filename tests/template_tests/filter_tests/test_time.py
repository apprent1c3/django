from datetime import time

from django.template.defaultfilters import time as time_filter
from django.test import SimpleTestCase
from django.utils import timezone, translation

from ..utils import setup
from .timezone_utils import TimezoneTestCase


class TimeTests(TimezoneTestCase):
    """
    #20693: Timezone support for the time template filter
    """

    @setup({"time00": "{{ dt|time }}"})
    def test_time00(self):
        output = self.engine.render_to_string("time00", {"dt": time(16, 25)})
        self.assertEqual(output, "4:25 p.m.")

    @setup({"time00_l10n": "{{ dt|time }}"})
    def test_time00_l10n(self):
        """

        Tests the time localization feature when the locale is set to French.

        Verifies that a given datetime object is rendered correctly in the 'HH:MM' format.
        The test assumes a time of 16:25 and checks if the rendered output matches the expected string '16:25'.

        """
        with translation.override("fr"):
            output = self.engine.render_to_string("time00_l10n", {"dt": time(16, 25)})
        self.assertEqual(output, "16:25")

    @setup({"time01": '{{ dt|time:"e:O:T:Z" }}'})
    def test_time01(self):
        output = self.engine.render_to_string("time01", {"dt": self.now_tz_i})
        self.assertEqual(output, "+0315:+0315:+0315:11700")

    @setup({"time02": '{{ dt|time:"e:T" }}'})
    def test_time02(self):
        output = self.engine.render_to_string("time02", {"dt": self.now})
        self.assertEqual(output, ":" + self.now_tz.tzinfo.tzname(self.now_tz))

    @setup({"time03": '{{ t|time:"P:e:O:T:Z" }}'})
    def test_time03(self):
        """
        Test rendering of time object in format 'P:e:O:T:Z'.

        This function checks if the time object is correctly formatted as per the given format.
        It tests if the time '4 a.m.' in a specific timezone is correctly rendered as '4 a.m.::::'
        """
        output = self.engine.render_to_string(
            "time03", {"t": time(4, 0, tzinfo=timezone.get_fixed_timezone(30))}
        )
        self.assertEqual(output, "4 a.m.::::")

    @setup({"time04": '{{ t|time:"P:e:O:T:Z" }}'})
    def test_time04(self):
        output = self.engine.render_to_string("time04", {"t": time(4, 0)})
        self.assertEqual(output, "4 a.m.::::")

    @setup({"time05": '{{ d|time:"P:e:O:T:Z" }}'})
    def test_time05(self):
        """
        Tests the rendering of a time string in the format 'P:e:O:T:Z' to an empty string when the input date is today.

        The function verifies that when the current date is provided as input, the function correctly handles the time format and produces the expected output, which in this case is an empty string.

        :raises AssertionError: If the rendered output does not match the expected empty string
        """
        output = self.engine.render_to_string("time05", {"d": self.today})
        self.assertEqual(output, "")

    @setup({"time06": '{{ obj|time:"P:e:O:T:Z" }}'})
    def test_time06(self):
        """

        Tests the time filter with a non-datetime value.

        Verifies that when a non-datetime value is passed to the time filter, 
        it returns an empty string.

        Args:
            self: The test instance.

        Returns:
            None

        """
        output = self.engine.render_to_string("time06", {"obj": "non-datetime-value"})
        self.assertEqual(output, "")


class FunctionTests(SimpleTestCase):
    def test_no_args(self):
        self.assertEqual(time_filter(""), "")
        self.assertEqual(time_filter(None), "")

    def test_inputs(self):
        self.assertEqual(time_filter(time(13), "h"), "01")
        self.assertEqual(time_filter(time(0), "h"), "12")
