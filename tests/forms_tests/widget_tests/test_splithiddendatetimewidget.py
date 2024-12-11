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

        Tests the localization (L10n) of a date widget in the 'de-at' locale.

        This test case verifies that the date widget is correctly rendered in the German (Austria) format.
        It checks that the date is displayed in the 'dd.mm.yyyy' format and the time in the 'hh:mm:ss' format.

        The expected output is a specific HTML format containing two hidden input fields for the date and time.

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
        """

        Tests the constructor of SplitHiddenDateTimeWidget with different attribute settings.

        This test case verifies that the widget correctly generates HTML when 
        different attributes are specified for date, time, and general input fields. 

        The test scenarios cover the following attribute configurations:
        - date and time attributes specified separately
        - date attributes specified separately and general attributes specified
        - time attributes specified separately and general attributes specified

        The resulting HTML is compared with an expected output to ensure correctness.

        """
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
        """
        Tests the rendering of a form fieldset using the SplitDateTimeField widget.

        Checks that the widget's use_fieldset attribute is correctly set to True and 
        verifies that the field is rendered as two hidden input fields with the expected 
        structure and attributes.

        The test case covers the expected HTML output of the form field when using the 
        SplitDateTimeField widget, ensuring that the rendered fieldset matches the 
        expected format. 
        """
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
        Tests the rendering of a form with a fieldset when one field is hidden and another is not.

        The test case checks that a SplitDateTimeField with the default widget is properly wrapped in a fieldset with a legend in the rendered HTML,
        while a SplitDateTimeField with the specified widget but applied to a hidden field is not included in the fieldset.

        The expected output is a div element containing a fieldset for the unhidden field, including input fields for the date and time,
        and separate hidden input fields for the hidden SplitDateTimeField.
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
