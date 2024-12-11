from django.forms.widgets import Input

from .base import WidgetTest


class InputTests(WidgetTest):
    def test_attrs_with_type(self):
        """
        Tests the functionality of the Input widget when different HTML input types are specified.

        Verifies that the widget's HTML output matches the expected format for different input types, 
        such as date and number. It checks whether the widget correctly handles attribute changes 
        after it has been instantiated.

        In particular, this test case checks that the 'type' attribute is correctly rendered in the 
        output HTML and that changes to this attribute do not affect the widget's output as expected 
        for a date type input, even if the type is changed to a different type, such as number.
        """
        attrs = {"type": "date"}
        widget = Input(attrs)
        self.check_html(
            widget, "name", "value", '<input type="date" name="name" value="value">'
        )
        # reuse the same attrs for another widget
        self.check_html(
            Input(attrs),
            "name",
            "value",
            '<input type="date" name="name" value="value">',
        )
        attrs["type"] = "number"  # shouldn't change the widget type
        self.check_html(
            widget, "name", "value", '<input type="date" name="name" value="value">'
        )
