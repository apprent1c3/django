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
        Tests the 'now' template tag used with a specific date format.

        This test case checks if the 'now' template tag correctly renders the current date
        in the specified format. It verifies that the output of the template tag matches
        the expected date format when rendered by the template engine.

        :param None:
        :returns: None
        :raises: AssertionError if the rendered output does not match the expected date format
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
        """

        Tests the rendering of the 'now' template tag with a custom format.

        The 'now' tag is used to display the current date and time. This test case 
        verifies that the tag correctly formats the date as 'day \"month\" year' when 
        provided with the format string 'j \"n\" Y'.

        The test compares the rendered output with the expected string, which is 
        generated using the current date and time.


        """
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
        with self.assertRaisesMessage(
            TemplateSyntaxError, "'now' statement takes one argument"
        ):
            self.engine.render_to_string("no_args")
