from datetime import time

from django.forms import CharField, Form, TimeInput
from django.utils import translation

from .base import WidgetTest


class TimeInputTest(WidgetTest):
    widget = TimeInput()

    def test_render_none(self):
        self.check_html(
            self.widget, "time", None, html='<input type="text" name="time">'
        )

    def test_render_value(self):
        """
        The microseconds are trimmed on display, by default.
        """
        t = time(12, 51, 34, 482548)
        self.assertEqual(str(t), "12:51:34.482548")
        self.check_html(
            self.widget,
            "time",
            t,
            html='<input type="text" name="time" value="12:51:34">',
        )
        self.check_html(
            self.widget,
            "time",
            time(12, 51, 34),
            html=('<input type="text" name="time" value="12:51:34">'),
        )
        self.check_html(
            self.widget,
            "time",
            time(12, 51),
            html=('<input type="text" name="time" value="12:51:00">'),
        )

    def test_string(self):
        """Initializing from a string value."""
        self.check_html(
            self.widget,
            "time",
            "13:12:11",
            html=('<input type="text" name="time" value="13:12:11">'),
        )

    def test_format(self):
        """
        Use 'format' to change the way a value is displayed.
        """
        t = time(12, 51, 34, 482548)
        widget = TimeInput(format="%H:%M", attrs={"type": "time"})
        self.check_html(
            widget, "time", t, html='<input type="time" name="time" value="12:51">'
        )

    @translation.override("de-at")
    def test_l10n(self):
        t = time(12, 51, 34, 482548)
        self.check_html(
            self.widget,
            "time",
            t,
            html='<input type="text" name="time" value="12:51:34">',
        )

    def test_fieldset(self):
        """

        Tests the fieldset functionality of a form field widget.

        This test case creates a form with a single field and verifies that the widget
        does not use a fieldset by default. It then checks the rendered HTML output of
        the form to ensure it matches the expected format.

        The test covers the basic rendering of a form field without a fieldset, which
        is useful for understanding how form fields are displayed when not grouped
        together. The test helps ensure that the widget behaves as expected when
        rendered in a form, and that the HTML output is correct.

        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = CharField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            '<div><label for="id_field">Field:</label>'
            '<input id="id_field" name="field" required type="text"></div>',
            form.render(),
        )
