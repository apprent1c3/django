import datetime
import unittest

from django.utils.dateparse import parse_duration
from django.utils.duration import (
    duration_iso_string,
    duration_microseconds,
    duration_string,
)


class TestDurationString(unittest.TestCase):
    def test_simple(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_string(duration), "01:03:05")

    def test_days(self):
        """
        Tests the duration_string function with a timedelta object of 1 day, 1 hour, 3 minutes, and 5 seconds, 
        verifying that it correctly returns a string in the format 'days HH:MM:SS'.
        """
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_string(duration), "1 01:03:05")

    def test_microseconds(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(duration_string(duration), "01:03:05.012345")

    def test_negative(self):
        """
        Tests the duration_string function with a negative time duration.

        This test case verifies that the function correctly formats a timedelta object
        with a negative number of days and positive hours, minutes, and seconds into a string.
        The expected output format is a string representing the negative duration in days, 
        hours, minutes, and seconds, separated by spaces and with time components in 24-hour format.

        """
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_string(duration), "-1 01:03:05")


class TestParseDurationRoundtrip(unittest.TestCase):
    def test_simple(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_days(self):
        """
        Tests the functionality of parsing duration strings to time delta objects.

        Verifies that a duration string, generated from a time delta object with a specific number of days, hours, minutes, and seconds, can be successfully parsed back into its original time delta object.

        This test case ensures the accuracy and reliability of the duration parsing mechanism, confirming that it can correctly handle durations with various time components.
        """
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_microseconds(self):
        """
        Tests parsing of a duration string containing microseconds.

        Verifies that the parse_duration function correctly interprets a duration string 
        representing a time interval with hours, minutes, seconds, and microseconds, 
        and returns a corresponding timedelta object with the expected values.
        """
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_negative(self):
        """
        Tests the parsing of a negative duration string to ensure it correctly interprets and returns the equivalent timedelta object, covering scenarios where the duration has negative days and positive hours, minutes, and seconds.
        """
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)


class TestISODurationString(unittest.TestCase):
    def test_simple(self):
        """

        Tests the conversion of a time duration to its ISO 8601 string representation.

        Verifies that the duration_iso_string function correctly formats a duration 
        of one hour, three minutes, and five seconds into the expected ISO 8601 string.

        """
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "P0DT01H03M05S")

    def test_days(self):
        """

        Check that the duration_iso_string function correctly converts a timedelta object to its ISO 8601 duration string representation.

        The test case verifies that a duration of one day, one hour, three minutes, and five seconds is accurately represented as 'P1DT01H03M05S'.

        """
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "P1DT01H03M05S")

    def test_microseconds(self):
        """

        Tests the conversion of a duration with microseconds to an ISO 8601 string.

        Verifies that the function correctly formats a time duration with hours, minutes, seconds, and microseconds into a string according to the ISO 8601 standard.

        """
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(duration_iso_string(duration), "P0DT01H03M05.012345S")

    def test_negative(self):
        """
        Tests the duration_iso_string function with a negative duration, verifying that it correctly converts a time interval with a negative sign into ISO 8601 format.
        """
        duration = -1 * datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "-P1DT01H03M05S")


class TestParseISODurationRoundtrip(unittest.TestCase):
    def test_simple(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_iso_string(duration)), duration)

    def test_days(self):
        """
        .. method:: test_days()
           :noindex:

           Verifies the accuracy of parsing duration from an ISO string representation.

           This test checks if a duration, represented as a delta of days, hours, minutes, and seconds, can be correctly translated into its ISO string equivalent and then parsed back into a duration object, ensuring the original and parsed durations match exactly.
        """
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_iso_string(duration)), duration)

    def test_microseconds(self):
        """
        Tests the parsing of duration strings containing microseconds.

        Verifies that a duration with hours, minutes, seconds, and microseconds can be correctly 
        parsed from its ISO string representation and converted back to a timedelta object.

        The test case checks for precision in the conversion, ensuring that the parsed duration 
        matches the original duration object, including the microseconds component.
        """
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(parse_duration(duration_iso_string(duration)), duration)

    def test_negative(self):
        """

        Test parsing of negative duration ISO strings.

        Checks the correctness of the duration parsing functionality when dealing with negative time intervals, 
        ensuring that the parsed duration matches the original negative duration.

        """
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(
            parse_duration(duration_iso_string(duration)).total_seconds(),
            duration.total_seconds(),
        )


class TestDurationMicroseconds(unittest.TestCase):
    def test(self):
        """
        Tests the conversion of various time deltas to microseconds.

        Verifies that the function duration_microseconds correctly handles extreme cases, 
        including the maximum, minimum, and resolution limits of time deltas, as well as 
        edge cases like negative resolutions and large microsecond values.

        A series of subtests are performed with different time delta values to ensure 
        consistent and accurate results across various scenarios.
        """
        deltas = [
            datetime.timedelta.max,
            datetime.timedelta.min,
            datetime.timedelta.resolution,
            -datetime.timedelta.resolution,
            datetime.timedelta(microseconds=8999999999999999),
        ]
        for delta in deltas:
            with self.subTest(delta=delta):
                self.assertEqual(
                    datetime.timedelta(microseconds=duration_microseconds(delta)), delta
                )
