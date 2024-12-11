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
        """
        Tests the time formatting functionality of the template engine. 

        This test case verifies that a time object is properly formatted as a human-readable string, 
        including hour and minute, along with the appropriate AM/PM designator. The test uses a 
        specific time (4:25 PM) to ensure that the engine correctly handles the rendering of 
        12-hour clock time.
        """
        output = self.engine.render_to_string("time00", {"dt": time(16, 25)})
        self.assertEqual(output, "4:25 p.m.")

    @setup({"time00_l10n": "{{ dt|time }}"})
    def test_time00_l10n(self):
        """

        Tests the time localization feature of the template engine.

        This test verifies that the engine correctly formats a time object according to the locale settings.
        In this case, it renders a template with a time object set to 16:25 and checks that the output is '16:25' when the locale is set to French.
        The test ensures that the engine's time localization works as expected, producing the correct output for the given locale and time. 

        """
        with translation.override("fr"):
            output = self.engine.render_to_string("time00_l10n", {"dt": time(16, 25)})
        self.assertEqual(output, "16:25")

    @setup({"time01": '{{ dt|time:"e:O:T:Z" }}'})
    def test_time01(self):
        """
        Tests whether the time filter in the templating engine correctly formats a datetime object into a string in the specified format, checking for Eastern European Time (EET) offset and timezone representation.
        """
        output = self.engine.render_to_string("time01", {"dt": self.now_tz_i})
        self.assertEqual(output, "+0315:+0315:+0315:11700")

    @setup({"time02": '{{ dt|time:"e:T" }}'})
    def test_time02(self):
        """
        Tests the rendering of the current time zone's abbreviated name.

        This test case verifies that the 'time:\"e:T\"' format specifier correctly 
        renders the abbreviated time zone name of the current date and time. 

        The expected output is the colon (:) followed by the abbreviated time zone name.
        """
        output = self.engine.render_to_string("time02", {"dt": self.now})
        self.assertEqual(output, ":" + self.now_tz.tzinfo.tzname(self.now_tz))

    @setup({"time03": '{{ t|time:"P:e:O:T:Z" }}'})
    def test_time03(self):
        """
        Tests the time formatting functionality of the templating engine with a specific time zone offset.

         The function verifies that a time object with a fixed timezone offset is correctly rendered into a string according to the \"P:e:O:T:Z\" time format.

         :return: None 
         :raises AssertionError: if the rendered output does not match the expected string '4 a.m.::::'
        """
        output = self.engine.render_to_string(
            "time03", {"t": time(4, 0, tzinfo=timezone.get_fixed_timezone(30))}
        )
        self.assertEqual(output, "4 a.m.::::")

    @setup({"time04": '{{ t|time:"P:e:O:T:Z" }}'})
    def test_time04(self):
        """

        Tests the time formatting functionality of the templating engine.

        This test checks that the time is correctly formatted using the \"P:e:O:T:Z\" format string.
        The expected output is compared to the actual rendered string to ensure accuracy.

        The time format \"P:e:O:T:Z\" corresponds to the following components:
            - P: the time in 12-hour format with period (e.g., a.m., p.m.)
            - e: the hour in 12-hour format
            - O: the time zone offset (in this case, an empty string is expected)
            - T: the time zone (in this case, an empty string is expected)
            - Z: the time zone offset (in this case, an empty string is expected)

        The test case uses a time object set to 4:00 a.m. as input and verifies that the rendered output matches the expected string.

        """
        output = self.engine.render_to_string("time04", {"t": time(4, 0)})
        self.assertEqual(output, "4 a.m.::::")

    @setup({"time05": '{{ d|time:"P:e:O:T:Z" }}'})
    def test_time05(self):
        output = self.engine.render_to_string("time05", {"d": self.today})
        self.assertEqual(output, "")

    @setup({"time06": '{{ obj|time:"P:e:O:T:Z" }}'})
    def test_time06(self):
        output = self.engine.render_to_string("time06", {"obj": "non-datetime-value"})
        self.assertEqual(output, "")


class FunctionTests(SimpleTestCase):
    def test_no_args(self):
        """
        Tests the time_filter function with no arguments.

        This test case verifies that the time_filter function returns an empty string 
        when given either no input or None as input, ensuring it handles edge cases 
        correctly and does not throw any errors. 

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the time_filter function does not return an empty string 
            for the given inputs.

        """
        self.assertEqual(time_filter(""), "")
        self.assertEqual(time_filter(None), "")

    def test_inputs(self):
        self.assertEqual(time_filter(time(13), "h"), "01")
        self.assertEqual(time_filter(time(0), "h"), "12")
