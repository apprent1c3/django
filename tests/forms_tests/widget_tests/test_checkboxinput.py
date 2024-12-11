from django.forms import BooleanField, CheckboxInput, Form

from .base import WidgetTest


class CheckboxInputTest(WidgetTest):
    widget = CheckboxInput()

    def test_render_empty(self):
        self.check_html(
            self.widget, "is_cool", "", html='<input type="checkbox" name="is_cool">'
        )

    def test_render_none(self):
        self.check_html(
            self.widget, "is_cool", None, html='<input type="checkbox" name="is_cool">'
        )

    def test_render_false(self):
        self.check_html(
            self.widget, "is_cool", False, html='<input type="checkbox" name="is_cool">'
        )

    def test_render_true(self):
        self.check_html(
            self.widget,
            "is_cool",
            True,
            html='<input checked type="checkbox" name="is_cool">',
        )

    def test_render_value(self):
        """
        Using any value that's not in ('', None, False, True) will check the
        checkbox and set the 'value' attribute.
        """
        self.check_html(
            self.widget,
            "is_cool",
            "foo",
            html='<input checked type="checkbox" name="is_cool" value="foo">',
        )

    def test_render_int(self):
        """
        Integers are handled by value, not as booleans (#17114).
        """
        self.check_html(
            self.widget,
            "is_cool",
            0,
            html='<input checked type="checkbox" name="is_cool" value="0">',
        )
        self.check_html(
            self.widget,
            "is_cool",
            1,
            html='<input checked type="checkbox" name="is_cool" value="1">',
        )

    def test_render_check_test(self):
        """
        You can pass 'check_test' to the constructor. This is a callable that
        takes the value and returns True if the box should be checked.
        """
        widget = CheckboxInput(check_test=lambda value: value.startswith("hello"))
        self.check_html(
            widget, "greeting", "", html=('<input type="checkbox" name="greeting">')
        )
        self.check_html(
            widget,
            "greeting",
            "hello",
            html=('<input checked type="checkbox" name="greeting" value="hello">'),
        )
        self.check_html(
            widget,
            "greeting",
            "hello there",
            html=(
                '<input checked type="checkbox" name="greeting" value="hello there">'
            ),
        )
        self.check_html(
            widget,
            "greeting",
            "hello & goodbye",
            html=(
                '<input checked type="checkbox" name="greeting" '
                'value="hello &amp; goodbye">'
            ),
        )

    def test_render_check_exception(self):
        """
        Calling check_test() shouldn't swallow exceptions (#17888).
        """
        widget = CheckboxInput(
            check_test=lambda value: value.startswith("hello"),
        )

        with self.assertRaises(AttributeError):
            widget.render("greeting", True)

    def test_value_from_datadict(self):
        """
        The CheckboxInput widget will return False if the key is not found in
        the data dictionary (because HTML form submission doesn't send any
        result for unchecked checkboxes).
        """
        self.assertFalse(self.widget.value_from_datadict({}, {}, "testing"))

    def test_value_from_datadict_string_int(self):
        """
        Tests the conversion of a string integer '0' to a boolean value from a data dictionary.

        This test case verifies that the :meth:`value_from_datadict` method correctly interprets a string
        representation of an integer '0' as a boolean True value.

        The test expects the method to return True when given a data dictionary containing a string '0'
        value for the specified key.

        This ensures the widget handles boolean values represented as strings in the data dictionary
        correctly and consistently. 
        """
        value = self.widget.value_from_datadict({"testing": "0"}, {}, "testing")
        self.assertIs(value, True)

    def test_value_omitted_from_data(self):
        """
        Determines whether a specific value is omitted from the provided data.

        This method checks if the given field is present in the data dictionary and returns a boolean value indicating whether the field's value is omitted. 

        The method considers a value to be omitted if the field is not present in the data or if the field's value is not provided, but it does not consider the field's value to be omitted if it is explicitly set to any value, even if it is an empty string or other empty value. 

        Args:
            data (dict): The dictionary containing the data to be checked.
            initial (dict): The initial data, used for reference.
            field (str): The field whose value is to be checked.

        Returns:
            bool: False if the field's value is not omitted from the data, indicating that the field is present or its value is provided.
        """
        self.assertIs(
            self.widget.value_omitted_from_data({"field": "value"}, {}, "field"), False
        )
        self.assertIs(self.widget.value_omitted_from_data({}, {}, "field"), False)

    def test_get_context_does_not_mutate_attrs(self):
        """
        Tests that the get_context method of the widget does not modify the provided attributes dictionary.

            This test case verifies that the widget's get_context method is designed to work 
            without side effects, ensuring that the original attributes dictionary remains 
            unchanged after the method invocation. Specifically, it checks that the 'checked' 
            attribute is not modified when the method is called with an existing attributes 
            dictionary.
        """
        attrs = {"checked": False}
        self.widget.get_context("name", True, attrs)
        self.assertIs(attrs["checked"], False)

    def test_fieldset(self):
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = BooleanField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            form.render(),
            '<div><label for="id_field">Field:</label>'
            '<input id="id_field" name="field" required type="checkbox"></div>',
        )
