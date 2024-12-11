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

        Initializes a form widget with a set of predefined input fields.

        The form includes a text input field, a multiple selection field with predefined choices,
        and a split date and time input field. The initialization process also accepts an optional
        dictionary of attributes that can be used to customize the form's appearance and behavior.

        """
        widgets = (
            TextInput(),
            SelectMultiple(choices=beatles),
            SplitDateTimeWidget(),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
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
        fields = (
            CharField(),
            MultipleChoiceField(choices=beatles),
            SplitDateTimeField(),
        )
        super().__init__(fields, **kwargs)

    def compress(self, data_list):
        """
        Compresses a list of data into a compact string format.

        This function takes a list of data as input and returns a string where the first and last elements of the list are separated by a comma and the middle elements (if any) are concatenated without any separators. If the input list is empty, the function returns None. The resulting string is formatted as 'first_element,middle_elements,last_element'.
        """
        if data_list:
            return "%s,%s,%s" % (data_list[0], "".join(data_list[1]), data_list[2])
        return None


class ComplexFieldForm(Form):
    field1 = ComplexField(widget=ComplexMultiWidget())


class MultiValueFieldTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.field = ComplexField(widget=ComplexMultiWidget())
        super().setUpClass()

    def test_clean(self):
        self.assertEqual(
            self.field.clean(["some text", ["J", "P"], ["2007-04-25", "6:24:00"]]),
            "some text,JP,2007-04-25 06:24:00",
        )

    def test_clean_disabled_multivalue(self):
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
        """

        Tests the behavior of the field when an invalid choice is selected.

        Verifies that a ValidationError is raised when the clean method is called with
        a choice that is not among the available options.

        The test checks for a specific error message indicating that the selected choice
        is not valid. The expected error message is: 'Select a valid choice. X is not one
        of the available choices.'

        """
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
        f = MultiValueField(fields=(CharField(), CharField()), disabled=True)
        self.assertIs(f.has_changed(["x", "x"], ["y", "y"]), False)

    def test_form_as_table(self):
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
        Tests that the ComplexFieldForm is rendered as a table with the correct HTML structure and field values.

        The test form is expected to contain a text input, a multiple select field, and two date/time fields. 
        The rendered table should include a header cell containing the label for the field and a data cell containing the form fields.
        This test ensures that the form's as_table() method returns the expected HTML output for the given input data.
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
        """
        Tests the cleaned data of the ComplexFieldForm.

        Verifies that the form's cleaned_data attribute correctly combines and formats the input data from multiple fields into a single string.

        The test case covers a scenario where the form receives data for a complex field consisting of a text field, multiple choice field, and a datetime field. It checks if the cleaned data is properly concatenated and formatted as expected.

        The expected output is a string in the format 'text,multi_choice_values,datetime', where datetime is in the format 'YYYY-MM-DD HH:MM:SS'.
        """
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
        form = PartiallyRequiredForm({"f_0": "Hello", "f_1": ""})
        self.assertTrue(form.is_valid())
        self.assertInHTML(
            '<input type="text" name="f_0" value="Hello" required id="id_f_0">',
            form.as_p(),
        )
        self.assertInHTML('<input type="text" name="f_1" id="id_f_1">', form.as_p())
        form = PartiallyRequiredForm({"f_0": "", "f_1": ""})
        self.assertFalse(form.is_valid())
