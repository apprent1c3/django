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
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_string(duration), "1 01:03:05")

    def test_microseconds(self):
        """
        Tests the conversion of a datetime.timedelta object to a string representing the duration in hours, minutes, seconds, and microseconds.

        The function verifies that the duration_string function correctly formats the time components of the datetime.timedelta object, including the microseconds, into a human-readable string.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        This test case ensures that the duration_string function handles the conversion of datetime.timedelta objects to string format correctly, including the precision of microseconds.
        """
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(duration_string(duration), "01:03:05.012345")

    def test_negative(self):
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_string(duration), "-1 01:03:05")


class TestParseDurationRoundtrip(unittest.TestCase):
    def test_simple(self):
        """

        Tests the parsing of a simple duration string into a datetime.timedelta object.

        This test case checks if the parse_duration function can correctly convert a duration
        string generated from a given datetime.timedelta object back into its original form.
        The test duration used is 1 hour, 3 minutes, and 5 seconds.

        """
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_days(self):
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_microseconds(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5, microseconds=12345)
        self.assertEqual(parse_duration(duration_string(duration)), duration)

    def test_negative(self):
        """
        Tests the ability to parse a duration string representing a negative time interval.

        This test case verifies that the duration parsing functionality correctly handles
        a negative time period, ensuring that the resulting duration object accurately
        represents the expected time interval.

        The test duration used in this case is a negative time period with a specific
        number of days, hours, minutes, and seconds, allowing for a comprehensive
        evaluation of the parsing functionality's ability to handle various time units
        and signs.
        """
        duration = datetime.timedelta(days=-1, hours=1, minutes=3, seconds=5)
        self.assertEqual(parse_duration(duration_string(duration)), duration)


class TestISODurationString(unittest.TestCase):
    def test_simple(self):
        duration = datetime.timedelta(hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "P0DT01H03M05S")

    def test_days(self):
        duration = datetime.timedelta(days=1, hours=1, minutes=3, seconds=5)
        self.assertEqual(duration_iso_string(duration), "P1DT01H03M05S")

    def test_microseconds(self):
        """
        Tests the duration_iso_string function with a time duration containing microseconds.

        Verifies that the function correctly converts a datetime.timedelta object with hours, minutes, seconds, and microseconds into an ISO duration string.

        """
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
        """
        Tests parsing of a duration string containing microseconds.

        Verifies that a duration string created from a datetime.timedelta object
        with hours, minutes, seconds, and microseconds can be successfully parsed
        back into the original duration object.

        The test checks for exact equality between the original and parsed duration
        objects, ensuring that all components, including microseconds, are preserved
        during the parsing process.
        """
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
