from datetime import datetime

from django.core.exceptions import ValidationError
from django.forms import (
    CharField,
    Form,
    MultipleChoiceField,
    MultiValueField,
    MultiWidget,
    SelectMultiple,
    SplitDateTimeField,
    SplitDateTimeWidget,
    TextInput,
)
from django.test import SimpleTestCase

beatles = (("J", "John"), ("P", "Paul"), ("G", "George"), ("R", "Ringo"))


class PartiallyRequiredField(MultiValueField):
    def compress(self, data_list):
        return ",".join(data_list) if data_list else None


class PartiallyRequiredForm(Form):
    f = PartiallyRequiredField(
        fields=(CharField(required=True), CharField(required=False)),
        required=True,
        require_all_fields=False,
        widget=MultiWidget(widgets=[TextInput(), TextInput()]),
    )


class ComplexMultiWidget(MultiWidget):
    def __init__(self, attrs=None):
        """
        Initializes a form instance with a set of predefined widgets.

        The form is composed of several input fields, including a text input, a multiple-select dropdown containing options related to the Beatles, and a split date-time widget for date and time input.

        The initialization process allows for optional attributes to be passed to the form, providing flexibility in its usage and customization.

        :param attrs: Optional attributes to be applied to the form
        :type attrs: dict, optional
        """
        widgets = (
            TextInput(),
            SelectMultiple(choices=beatles),
            SplitDateTimeWidget(),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        """
        #: Decompress a compressed string into its constituent parts.
        #: 
        #: Args:
        #:     value (str): The compressed string to decompress. It is expected to be a comma-separated string containing 
        #:                 a primary value, a secondary list of values, and a timestamp.
        #: 
        #: Returns:
        #:     list: A list containing the primary value, a list of secondary values, and a datetime object representing the timestamp. 
        #:           If the input string is empty, returns [None, None, None].
        """
        if value:
            data = value.split(",")
            return [
                data[0],
                list(data[1]),
                datetime.strptime(data[2], "%Y-%m-%d %H:%M:%S"),
            ]
        return [None, None, None]


class ComplexField(MultiValueField):
    def __init__(self, **kwargs):
        """
        Initializes a form instance with predefined fields.

        The form is composed of three fields: a character field, a multiple choice field 
        with predefined options related to the Beatles, and a split date and time field.

        :param kwargs: Additional keyword arguments to be passed to the parent class.

        """
        fields = (
            CharField(),
            MultipleChoiceField(choices=beatles),
            SplitDateTimeField(),
        )
        super().__init__(fields, **kwargs)

    def compress(self, data_list):
        """
        Compresses a list of data into a formatted string.

        This method takes a list of data as input and returns a string with the first element,
        the concatenation of the second element, and the third element, separated by commas.
        If the input list is empty, the method returns None.

        The resulting string has the format 'first_element,concatenated_second,third_element'.
        The function is useful for combining data into a single string for storage or transmission.

        :returns: A compressed string representation of the input data, or None if the input list is empty
        """
        if data_list:
            return "%s,%s,%s" % (data_list[0], "".join(data_list[1]), data_list[2])
        return None


class ComplexFieldForm(Form):
    field1 = ComplexField(widget=ComplexMultiWidget())


class MultiValueFieldTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """
        ..:summary: Sets up the class by initializing a ComplexField instance and calling the superclass setup method.

        :Description: 
            This class method is used to perform class-level setup, which is executed once before running any tests in the class.
            It creates an instance of ComplexField and assigns it to the class attribute `field`, utilizing a ComplexMultiWidget for input handling.
            Additionally, it calls the superclass's setup method to ensure proper initialization of all inherited attributes and functionality.
        """
        cls.field = ComplexField(widget=ComplexMultiWidget())
        super().setUpClass()

    def test_clean(self):
        self.assertEqual(
            self.field.clean(["some text", ["J", "P"], ["2007-04-25", "6:24:00"]]),
            "some text,JP,2007-04-25 06:24:00",
        )

    def test_clean_disabled_multivalue(self):
        """
        Tests the behavior of a ComplexField when it is disabled and has a multi-value widget.

        Ensures that the form validation succeeds and the cleaned data is correctly populated
        when the ComplexField is initialized with different types of data, including strings and lists.

        Verifies that the form errors are empty and the cleaned data matches the expected output
        after calling the full_clean method on the form.

        This test case helps to confirm that the ComplexField behaves as expected when it is
        disabled and configured to use a multi-value widget, such as ComplexMultiWidget.
        """
        class ComplexFieldForm(Form):
            f = ComplexField(disabled=True, widget=ComplexMultiWidget)

        inputs = (
            "some text,JP,2007-04-25 06:24:00",
            ["some text", ["J", "P"], ["2007-04-25", "6:24:00"]],
        )
        for data in inputs:
            with self.subTest(data=data):
                form = ComplexFieldForm({}, initial={"f": data})
                form.full_clean()
                self.assertEqual(form.errors, {})
                self.assertEqual(form.cleaned_data, {"f": inputs[0]})

    def test_bad_choice(self):
        msg = "'Select a valid choice. X is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            self.field.clean(["some text", ["X"], ["2007-04-25", "6:24:00"]])

    def test_no_value(self):
        """
        If insufficient data is provided, None is substituted.
        """
        msg = "'This field is required.'"
        with self.assertRaisesMessage(ValidationError, msg):
            self.field.clean(["some text", ["JP"]])

    def test_has_changed_no_initial(self):
        self.assertTrue(
            self.field.has_changed(
                None, ["some text", ["J", "P"], ["2007-04-25", "6:24:00"]]
            )
        )

    def test_has_changed_same(self):
        self.assertFalse(
            self.field.has_changed(
                "some text,JP,2007-04-25 06:24:00",
                ["some text", ["J", "P"], ["2007-04-25", "6:24:00"]],
            )
        )

    def test_has_changed_first_widget(self):
        """
        Test when the first widget's data has changed.
        """
        self.assertTrue(
            self.field.has_changed(
                "some text,JP,2007-04-25 06:24:00",
                ["other text", ["J", "P"], ["2007-04-25", "6:24:00"]],
            )
        )

    def test_has_changed_last_widget(self):
        """
        Test when the last widget's data has changed. This ensures that it is
        not short circuiting while testing the widgets.
        """
        self.assertTrue(
            self.field.has_changed(
                "some text,JP,2007-04-25 06:24:00",
                ["some text", ["J", "P"], ["2009-04-25", "11:44:00"]],
            )
        )

    def test_disabled_has_changed(self):
        """

        Checks if a disabled MultiValueField with two CharField instances has changed.

        This test verifies that when a MultiValueField is disabled, it does not report
        any changes, even if the input values are different from the initial values.

        The function passes in identical input values and different initial values, then
        asserts that the `has_changed` method returns False, indicating no change.

        """
        f = MultiValueField(fields=(CharField(), CharField()), disabled=True)
        self.assertIs(f.has_changed(["x", "x"], ["y", "y"]), False)

    def test_form_as_table(self):
        """
        Tests that the ComplexFieldForm can be rendered as an HTML table.

        This test case verifies that the form fields are properly formatted and
        populated with the expected HTML elements, including labels, text inputs,
        and select options. The expected output is a table row with a label and
        a table data cell containing the field inputs.

        The form is tested for its ability to display a complex field structure,
        including a text input, a multiple select field, and nested text inputs.
        The test passes if the rendered HTML matches the expected output string.
        """
        form = ComplexFieldForm()
        self.assertHTMLEqual(
            form.as_table(),
            """
            <tr><th><label>Field1:</label></th>
            <td><input type="text" name="field1_0" id="id_field1_0" required>
            <select multiple name="field1_1" id="id_field1_1" required>
            <option value="J">John</option>
            <option value="P">Paul</option>
            <option value="G">George</option>
            <option value="R">Ringo</option>
            </select>
            <input type="text" name="field1_2_0" id="id_field1_2_0" required>
            <input type="text" name="field1_2_1" id="id_field1_2_1" required></td></tr>
            """,
        )

    def test_form_as_table_data(self):
        """

        Test rendering of the ComplexFieldForm as an HTML table.

        Verifies that the form's fields are correctly displayed as table rows, 
        including text inputs, multiple select boxes, and date/time inputs. 
        The test checks that the output HTML matches the expected structure 
        and content, ensuring proper rendering of form fields and their values.

        """
        form = ComplexFieldForm(
            {
                "field1_0": "some text",
                "field1_1": ["J", "P"],
                "field1_2_0": "2007-04-25",
                "field1_2_1": "06:24:00",
            }
        )
        self.assertHTMLEqual(
            form.as_table(),
            """
            <tr><th><label>Field1:</label></th>
            <td><input type="text" name="field1_0" value="some text" id="id_field1_0"
                required>
            <select multiple name="field1_1" id="id_field1_1" required>
            <option value="J" selected>John</option>
            <option value="P" selected>Paul</option>
            <option value="G">George</option>
            <option value="R">Ringo</option>
            </select>
            <input type="text" name="field1_2_0" value="2007-04-25" id="id_field1_2_0"
                required>
            <input type="text" name="field1_2_1" value="06:24:00" id="id_field1_2_1"
                required></td></tr>
            """,
        )

    def test_form_cleaned_data(self):
        form = ComplexFieldForm(
            {
                "field1_0": "some text",
                "field1_1": ["J", "P"],
                "field1_2_0": "2007-04-25",
                "field1_2_1": "06:24:00",
            }
        )
        form.is_valid()
        self.assertEqual(
            form.cleaned_data["field1"], "some text,JP,2007-04-25 06:24:00"
        )

    def test_render_required_attributes(self):
        """

        Tests the rendering of form fields with required attributes.

        Verifies that the form is valid when a required field has a value, and that the corresponding HTML input field includes the 'required' attribute.
        Also checks that the form is invalid when both required and non-required fields are empty, and that the non-required field's HTML input does not include the 'required' attribute.

        """
        form = PartiallyRequiredForm({"f_0": "Hello", "f_1": ""})
        self.assertTrue(form.is_valid())
        self.assertInHTML(
            '<input type="text" name="f_0" value="Hello" required id="id_f_0">',
            form.as_p(),
        )
        self.assertInHTML('<input type="text" name="f_1" id="id_f_1">', form.as_p())
        form = PartiallyRequiredForm({"f_0": "", "f_1": ""})
        self.assertFalse(form.is_valid())
