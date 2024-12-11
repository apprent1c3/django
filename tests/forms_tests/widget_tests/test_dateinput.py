from datetime import date

from django.forms import CharField, DateInput, Form
from django.utils import translation

from .base import WidgetTest


class DateInputTest(WidgetTest):
    widget = DateInput()

    def test_render_none(self):
        self.check_html(
            self.widget, "date", None, html='<input type="text" name="date">'
        )

    def test_render_value(self):
        d = date(2007, 9, 17)
        self.assertEqual(str(d), "2007-09-17")

        self.check_html(
            self.widget,
            "date",
            d,
            html='<input type="text" name="date" value="2007-09-17">',
        )
        self.check_html(
            self.widget,
            "date",
            date(2007, 9, 17),
            html=('<input type="text" name="date" value="2007-09-17">'),
        )

    def test_string(self):
        """
        Should be able to initialize from a string value.
        """
        self.check_html(
            self.widget,
            "date",
            "2007-09-17",
            html=('<input type="text" name="date" value="2007-09-17">'),
        )

    def test_format(self):
        """
        Use 'format' to change the way a value is displayed.
        """
        d = date(2007, 9, 17)
        widget = DateInput(format="%d/%m/%Y", attrs={"type": "date"})
        self.check_html(
            widget, "date", d, html='<input type="date" name="date" value="17/09/2007">'
        )

    @translation.override("de-at")
    def test_l10n(self):
        self.check_html(
            self.widget,
            "date",
            date(2007, 9, 17),
            html='<input type="text" name="date" value="17.09.2007">',
        )

    def test_fieldset(self):
        """
        Tests the rendering of a form field without a fieldset.

        Verifies that the widget's use_fieldset attribute is False and that the form renders correctly as a single input field, 
        including the label and input element, wrapped in a div tag. The test case uses a simple form with a single text field 
        to validate the expected HTML output.
        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = CharField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            form.render(),
            '<div><label for="id_field">Field:</label>'
            '<input id="id_field" name="field" required type="text"></div>',
        )
