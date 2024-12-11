from datetime import datetime

from django.forms import Form, SplitDateTimeField, SplitHiddenDateTimeWidget
from django.utils import translation

from .base import WidgetTest


class SplitHiddenDateTimeWidgetTest(WidgetTest):
    widget = SplitHiddenDateTimeWidget()

    def test_render_empty(self):
        self.check_html(
            self.widget,
            "date",
            "",
            html=(
                '<input type="hidden" name="date_0"><input type="hidden" name="date_1">'
            ),
        )

    def test_render_value(self):
        """
        Tests the rendering of date values using the widget.

        This test case verifies that the widget correctly renders date values in HTML format.
        It checks the output for dates with varying levels of precision, including dates with 
        microseconds, seconds, and minutes. The expected output is a pair of hidden input 
        fields, one for the date and one for the time, with the date and time values formatted 
        according to the widget's rendering rules.

        Args:
            None

        Returns:
            None

        Note:
            This test method relies on the `check_html` method to verify the rendered HTML output.

        """
        d = datetime(2007, 9, 17, 12, 51, 34, 482548)
        self.check_html(
            self.widget,
            "date",
            d,
            html=(
                '<input type="hidden" name="date_0" value="2007-09-17">'
                '<input type="hidden" name="date_1" value="12:51:34">'
            ),
        )
        self.check_html(
            self.widget,
            "date",
            datetime(2007, 9, 17, 12, 51, 34),
            html=(
                '<input type="hidden" name="date_0" value="2007-09-17">'
                '<input type="hidden" name="date_1" value="12:51:34">'
            ),
        )
        self.check_html(
            self.widget,
            "date",
            datetime(2007, 9, 17, 12, 51),
            html=(
                '<input type="hidden" name="date_0" value="2007-09-17">'
                '<input type="hidden" name="date_1" value="12:51:00">'
            ),
        )

    @translation.override("de-at")
    def test_l10n(self):
        """

        Tests the localization of a date widget in the 'de-at' locale.

        Verifies that the date is correctly formatted and rendered as two hidden input fields,
        one for the date and one for the time, using the locale-specific formatting.

        """
        d = datetime(2007, 9, 17, 12, 51)
        self.check_html(
            self.widget,
            "date",
            d,
            html=(
                """
            <input type="hidden" name="date_0" value="17.09.2007">
            <input type="hidden" name="date_1" value="12:51:00">
            """
            ),
        )

    def test_constructor_different_attrs(self):
        html = (
            '<input type="hidden" class="foo" value="2006-01-10" name="date_0">'
            '<input type="hidden" class="bar" value="07:30:00" name="date_1">'
        )
        widget = SplitHiddenDateTimeWidget(
            date_attrs={"class": "foo"}, time_attrs={"class": "bar"}
        )
        self.check_html(widget, "date", datetime(2006, 1, 10, 7, 30), html=html)
        widget = SplitHiddenDateTimeWidget(
            date_attrs={"class": "foo"}, attrs={"class": "bar"}
        )
        self.check_html(widget, "date", datetime(2006, 1, 10, 7, 30), html=html)
        widget = SplitHiddenDateTimeWidget(
            time_attrs={"class": "bar"}, attrs={"class": "foo"}
        )
        self.check_html(widget, "date", datetime(2006, 1, 10, 7, 30), html=html)

    def test_fieldset(self):
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = SplitDateTimeField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, True)
        self.assertHTMLEqual(
            '<input type="hidden" name="field_0" id="id_field_0">'
            '<input type="hidden" name="field_1" id="id_field_1">',
            form.render(),
        )

    def test_fieldset_with_unhidden_field(self):
        """
        Tests the rendering of a form with a fieldset that contains an unhidden field when the widget is configured to use a fieldset.

        Verifies that the form is correctly rendered with the unhidden field wrapped in a fieldset and the hidden field outside of it, while ensuring the widget's use_fieldset attribute is properly set to True.

        The test case checks the expected HTML output of the form against a predefined markup, ensuring that the fieldset is correctly applied to the unhidden field and the hidden field is properly excluded from it.
        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            hidden_field = SplitDateTimeField(widget=self.widget)
            unhidden_field = SplitDateTimeField()

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, True)
        self.assertHTMLEqual(
            "<div><fieldset><legend>Unhidden field:</legend>"
            '<input type="text" name="unhidden_field_0" required '
            'id="id_unhidden_field_0"><input type="text" '
            'name="unhidden_field_1" required id="id_unhidden_field_1">'
            '</fieldset><input type="hidden" name="hidden_field_0" '
            'id="id_hidden_field_0"><input type="hidden" '
            'name="hidden_field_1" id="id_hidden_field_1"></div>',
            form.render(),
        )
