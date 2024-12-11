from datetime import datetime

from django.template import TemplateSyntaxError
from django.test import SimpleTestCase
from django.utils.formats import date_format

from ..utils import setup


class NowTagTests(SimpleTestCase):
    @setup({"now01": '{% now "j n Y" %}'})
    def test_now01(self):
        """
        Simple case
        """
        output = self.engine.render_to_string("now01")
        self.assertEqual(
            output,
            "%d %d %d"
            % (
                datetime.now().day,
                datetime.now().month,
                datetime.now().year,
            ),
        )

    # Check parsing of locale strings
    @setup({"now02": '{% now "DATE_FORMAT" %}'})
    def test_now02(self):
        """

        Tests the 'now' template tag with the specified date format (DATE_FORMAT).
        This test case renders a template string containing the 'now' tag and verifies 
        that the output matches the current date and time formatted according to the 
        defined format.

        :raises AssertionError: If the rendered output does not match the expected 
            formatted date and time.

        """
        output = self.engine.render_to_string("now02")
        self.assertEqual(output, date_format(datetime.now()))

    @setup({"now03": "{% now 'j n Y' %}"})
    def test_now03(self):
        """
        #15092 - Also accept simple quotes
        """
        output = self.engine.render_to_string("now03")
        self.assertEqual(
            output,
            "%d %d %d"
            % (
                datetime.now().day,
                datetime.now().month,
                datetime.now().year,
            ),
        )

    @setup({"now04": "{% now 'DATE_FORMAT' %}"})
    def test_now04(self):
        output = self.engine.render_to_string("now04")
        self.assertEqual(output, date_format(datetime.now()))

    @setup({"now05": "{% now 'j \"n\" Y'%}"})
    def test_now05(self):
        output = self.engine.render_to_string("now05")
        self.assertEqual(
            output,
            '%d "%d" %d'
            % (
                datetime.now().day,
                datetime.now().month,
                datetime.now().year,
            ),
        )

    @setup({"now06": "{% now \"j 'n' Y\"%}"})
    def test_now06(self):
        """
        ..: Tests whether the now template tag renders the current date in the 'j \'n\' Y' format.

            The test checks if the output of the now tag matches the current date in the format 'day ' 'month' year', 
            where day is the day of the month, month is the month as a zero-padded decimal, and year is the full year.
        """
        output = self.engine.render_to_string("now06")
        self.assertEqual(
            output,
            "%d '%d' %d"
            % (
                datetime.now().day,
                datetime.now().month,
                datetime.now().year,
            ),
        )

    @setup({"now07": '{% now "j n Y" as N %}-{{N}}-'})
    def test_now07(self):
        output = self.engine.render_to_string("now07")
        self.assertEqual(
            output,
            "-%d %d %d-"
            % (
                datetime.now().day,
                datetime.now().month,
                datetime.now().year,
            ),
        )

    @setup({"no_args": "{% now %}"})
    def test_now_args(self):
        """

        Test that a 'now' statement requires an argument.

        This test case verifies that using the 'now' statement without providing 
        any arguments results in a TemplateSyntaxError. The error message is 
        checked to ensure it correctly indicates that the 'now' statement takes 
        one argument.

        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "'now' statement takes one argument"
        ):
            self.engine.render_to_string("no_args")
