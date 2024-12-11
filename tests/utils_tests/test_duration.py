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
        Tests the conversion of a timedelta object to a string representing days, hours, minutes, and seconds.

            The function verifies that the duration_string function correctly formats a timedelta object into a human-readable string,
            including the number of days and time components. The test case checks a specific duration of 1 day, 1 hour, 3 minutes, and 5 seconds,
            ensuring the output matches the expected format of 'X YYYY:MM:SS', where X is the number of days and YYYY:MM:SS represents the time component.
        """
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_string(duration), "1 01:03:05")

    def test_microseconds(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(duration_string(duration), "01:03:05.012345")

    def test_negative(self):
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_string(duration), "-1 01:03:05")


class TestParseDurationRoundtrip(unittest.TestCase):
    def test_simple(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_days(self):
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_microseconds(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_negative(self):
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)


class TestISODurationString(unittest.TestCase):
    def test_simple(self):
        """
        Tests the duration_iso_string function to convert a datetime.timedelta object into an ISO 8601 duration string.

        The test verifies that a duration of 1 hour, 3 minutes, and 5 seconds is correctly represented as 'P0DT01H03M05S'.
        """
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "P0DT01H03M05S")

    def test_days(self):
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "P1DT01H03M05S")

    def test_microseconds(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(duration_iso_string(duration), "P0DT01H03M05.012345S")

    def test_negative(self):
        duration = -1 * datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "-P1DT01H03M05S")


class TestParseISODurationRoundtrip(unittest.TestCase):
    def test_simple(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_iso_string(duration)), duration)

    def test_days(self):
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_iso_string(duration)), duration)

    def test_microseconds(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(parse_duration(duration_iso_string(duration)), duration)

    def test_negative(self):
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(
            parse_duration(duration_iso_string(duration)).total_seconds(),
            duration.total_seconds(),
        )


class TestDurationMicroseconds(unittest.TestCase):
    def test(self):
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
