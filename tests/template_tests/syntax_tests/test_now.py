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
        Tests the 'now' template tag with a custom date format.

        This test case verifies that the 'now' tag correctly renders the current date 
        in the specified format when used in a template. The expected output is compared 
        to the actual rendered string to ensure accuracy.

        :raises AssertionError: If the rendered output does not match the expected date 
                                format of the current date.

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
        """

        Tests the current date and time functionality in the templating engine.

        The function checks if the templating engine correctly renders the current date
        in the format \"day month year\" when using the now tag with the \"j n Y\" format.
        It compares the rendered output with the expected current date and time.

        The expected output format is: \"-day month year-\".

        """
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
