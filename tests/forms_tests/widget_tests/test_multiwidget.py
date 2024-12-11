import copy
from datetime import datetime

from django.forms import (
    CharField,
    FileInput,
    Form,
    MultipleChoiceField,
    MultiValueField,
    MultiWidget,
    RadioSelect,
    SelectMultiple,
    SplitDateTimeField,
    SplitDateTimeWidget,
    TextInput,
)

from .base import WidgetTest


class MyMultiWidget(MultiWidget):
    def decompress(self, value):
        """
        Decompresses a given value by splitting it into a list of substrings.

        The input value is split using '__' as the separator. If the input value is empty or None, a list containing two empty strings is returned.

        :returns: A list of substrings resulting from decompressing the input value.
        :rtype: list[str]
        """
        if value:
            return value.split("__")
        return ["", ""]


class ComplexMultiWidget(MultiWidget):
    def __init__(self, attrs=None):
        widgets = (
            TextInput(),
            SelectMultiple(choices=WidgetTest.beatles),
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
    def __init__(self, required=True, widget=None, label=None, initial=None):
        """
        Initializes a form with predefined fields.

        :param bool required: Specifies whether the form is required.
        :param widget: Optional widget to use for rendering the form.
        :param str label: Optional label to display for the form.
        :param initial: Initial value for the form.
        The form includes three predefined fields: a character field, a multiple choice field with options based on the Beatles, and a split date/time field.
        """
        fields = (
            CharField(),
            MultipleChoiceField(choices=WidgetTest.beatles),
            SplitDateTimeField(),
        )
        super().__init__(
            fields, required=required, widget=widget, label=label, initial=initial
        )

    def compress(self, data_list):
        """

        Compresses a list of data into a string.

        This function takes a list of data as input and returns a compressed string.
        The compression is performed by concatenating the first element, the joined remaining elements (excluding the last one), and the last element of the list, separated by commas.

        If the input list is empty, the function returns None.

        The resulting string follows a specific format: '<first_element>,<joined_middle_elements>,<last_element>'.
        It is the caller's responsibility to ensure the input data list is not empty and has at least three elements to produce a meaningful compressed string.

        """
        if data_list:
            return "%s,%s,%s" % (
                data_list[0],
                "".join(data_list[1]),
                data_list[2],
            )
        return None


class DeepCopyWidget(MultiWidget):
    """
    Used to test MultiWidget.__deepcopy__().
    """

    def __init__(self, choices=[]):
        widgets = [
            RadioSelect(choices=choices),
            TextInput,
        ]
        super().__init__(widgets)

    def _set_choices(self, choices):
        """
        When choices are set for this widget, we want to pass those along to
        the Select widget.
        """
        self.widgets[0].choices = choices

    def _get_choices(self):
        """
        The choices for this widget are the Select widget's choices.
        """
        return self.widgets[0].choices

    choices = property(_get_choices, _set_choices)


class MultiWidgetTest(WidgetTest):
    def test_subwidgets_name(self):
        """

        Tests the naming convention of subwidgets within a MultiWidget instance.

        Verifies that each subwidget is assigned a unique name based on the parent
        widget's name and its own identifier, ensuring proper naming and identification
        of subwidgets in the rendered HTML.

        This test case specifically checks the naming of subwidgets with empty,
        'big', and 'small' identifiers, confirming that the resulting HTML names
        are correctly formatted and prefixed with the parent widget's name.

        """
        widget = MultiWidget(
            widgets={
                "": TextInput(),
                "big": TextInput(attrs={"class": "big"}),
                "small": TextInput(attrs={"class": "small"}),
            },
        )
        self.check_html(
            widget,
            "name",
            ["John", "George", "Paul"],
            html=(
                '<input type="text" name="name" value="John">'
                '<input type="text" name="name_big" value="George" class="big">'
                '<input type="text" name="name_small" value="Paul" class="small">'
            ),
        )

    def test_text_inputs(self):
        widget = MyMultiWidget(
            widgets=(
                TextInput(attrs={"class": "big"}),
                TextInput(attrs={"class": "small"}),
            )
        )
        self.check_html(
            widget,
            "name",
            ["john", "lennon"],
            html=(
                '<input type="text" class="big" value="john" name="name_0">'
                '<input type="text" class="small" value="lennon" name="name_1">'
            ),
        )
        self.check_html(
            widget,
            "name",
            ("john", "lennon"),
            html=(
                '<input type="text" class="big" value="john" name="name_0">'
                '<input type="text" class="small" value="lennon" name="name_1">'
            ),
        )
        self.check_html(
            widget,
            "name",
            "john__lennon",
            html=(
                '<input type="text" class="big" value="john" name="name_0">'
                '<input type="text" class="small" value="lennon" name="name_1">'
            ),
        )
        self.check_html(
            widget,
            "name",
            "john__lennon",
            attrs={"id": "foo"},
            html=(
                '<input id="foo_0" type="text" class="big" value="john" name="name_0">'
                '<input id="foo_1" type="text" class="small" value="lennon" '
                'name="name_1">'
            ),
        )

    def test_constructor_attrs(self):
        """
        Tests that the constructor of MyMultiWidget correctly sets attributes on the widget and its child widgets.

        Checks that the 'attrs' parameter is applied to the widget itself and that the 'attrs' parameter of each child widget is also applied.
        Verifies the generated HTML matches the expected output, including the correct id, class, value, and name attributes for each input field.
        """
        widget = MyMultiWidget(
            widgets=(
                TextInput(attrs={"class": "big"}),
                TextInput(attrs={"class": "small"}),
            ),
            attrs={"id": "bar"},
        )
        self.check_html(
            widget,
            "name",
            ["john", "lennon"],
            html=(
                '<input id="bar_0" type="text" class="big" value="john" name="name_0">'
                '<input id="bar_1" type="text" class="small" value="lennon" '
                'name="name_1">'
            ),
        )

    def test_constructor_attrs_with_type(self):
        """
        Tests that the MyMultiWidget constructor correctly handles widget attributes and types.

        Verifies that the 'attrs' parameter is applied to the individual widgets at the top level,
        and that nested widget attributes are also applied correctly. The test checks the generated
        HTML to ensure that the attributes and types are properly rendered, including the 'type'
        attribute for input fields and any additional class attributes specified.

        The test covers two main scenarios: setting the 'type' attribute for all widgets,
        and overriding this attribute with additional attributes at the widget level.
        """
        attrs = {"type": "number"}
        widget = MyMultiWidget(widgets=(TextInput, TextInput()), attrs=attrs)
        self.check_html(
            widget,
            "code",
            ["1", "2"],
            html=(
                '<input type="number" value="1" name="code_0">'
                '<input type="number" value="2" name="code_1">'
            ),
        )
        widget = MyMultiWidget(
            widgets=(TextInput(attrs), TextInput(attrs)), attrs={"class": "bar"}
        )
        self.check_html(
            widget,
            "code",
            ["1", "2"],
            html=(
                '<input type="number" value="1" name="code_0" class="bar">'
                '<input type="number" value="2" name="code_1" class="bar">'
            ),
        )

    def test_value_omitted_from_data(self):
        """

        Checks whether a value for a given field is omitted from the provided data.

        This method determines if the field's value is present in the data based on the
        structure of the multi-widget. The field is considered omitted if none of its
        sub-fields are present in the data.

        :param data: The data to check for the field's value.
        :param files: The files to check for the field's value (not used in this implementation).
        :param field: The name of the field to check.

        :return: True if the field's value is omitted, False otherwise.

        """
        widget = MyMultiWidget(widgets=(TextInput(), TextInput()))
        self.assertIs(widget.value_omitted_from_data({}, {}, "field"), True)
        self.assertIs(
            widget.value_omitted_from_data({"field_0": "x"}, {}, "field"), False
        )
        self.assertIs(
            widget.value_omitted_from_data({"field_1": "y"}, {}, "field"), False
        )
        self.assertIs(
            widget.value_omitted_from_data(
                {"field_0": "x", "field_1": "y"}, {}, "field"
            ),
            False,
        )

    def test_value_from_datadict_subwidgets_name(self):
        widget = MultiWidget(widgets={"x": TextInput(), "": TextInput()})
        tests = [
            ({}, [None, None]),
            ({"field": "x"}, [None, "x"]),
            ({"field_x": "y"}, ["y", None]),
            ({"field": "x", "field_x": "y"}, ["y", "x"]),
        ]
        for data, expected in tests:
            with self.subTest(data):
                self.assertEqual(
                    widget.value_from_datadict(data, {}, "field"),
                    expected,
                )

    def test_value_omitted_from_data_subwidgets_name(self):
        widget = MultiWidget(widgets={"x": TextInput(), "": TextInput()})
        tests = [
            ({}, True),
            ({"field": "x"}, False),
            ({"field_x": "y"}, False),
            ({"field": "x", "field_x": "y"}, False),
        ]
        for data, expected in tests:
            with self.subTest(data):
                self.assertIs(
                    widget.value_omitted_from_data(data, {}, "field"),
                    expected,
                )

    def test_needs_multipart_true(self):
        """
        needs_multipart_form should be True if any widgets need it.
        """
        widget = MyMultiWidget(widgets=(TextInput(), FileInput()))
        self.assertTrue(widget.needs_multipart_form)

    def test_needs_multipart_false(self):
        """
        needs_multipart_form should be False if no widgets need it.
        """
        widget = MyMultiWidget(widgets=(TextInput(), TextInput()))
        self.assertFalse(widget.needs_multipart_form)

    def test_nested_multiwidget(self):
        """
        MultiWidgets can be composed of other MultiWidgets.
        """
        widget = ComplexMultiWidget()
        self.check_html(
            widget,
            "name",
            "some text,JP,2007-04-25 06:24:00",
            html=(
                """
            <input type="text" name="name_0" value="some text">
            <select multiple name="name_1">
                <option value="J" selected>John</option>
                <option value="P" selected>Paul</option>
                <option value="G">George</option>
                <option value="R">Ringo</option>
            </select>
            <input type="text" name="name_2_0" value="2007-04-25">
            <input type="text" name="name_2_1" value="06:24:00">
            """
            ),
        )

    def test_no_whitespace_between_widgets(self):
        """
        Tests that no whitespace is added between widgets in the rendered HTML.

        This test case verifies that when multiple widgets are grouped together,
        they are rendered without any extraneous whitespace between them, ensuring
        a clean and compact HTML output. The test uses a MyMultiWidget instance
        with two TextInput widgets and checks the resulting HTML for the expected
        structure and naming conventions. A strict comparison is performed to
        ensure that the generated HTML matches the expected output exactly.
        """
        widget = MyMultiWidget(widgets=(TextInput, TextInput()))
        self.check_html(
            widget,
            "code",
            None,
            html=('<input type="text" name="code_0"><input type="text" name="code_1">'),
            strict=True,
        )

    def test_deepcopy(self):
        """
        MultiWidget should define __deepcopy__() (#12048).
        """
        w1 = DeepCopyWidget(choices=[1, 2, 3])
        w2 = copy.deepcopy(w1)
        w2.choices = [4, 5, 6]
        # w2 ought to be independent of w1, since MultiWidget ought
        # to make a copy of its sub-widgets when it is copied.
        self.assertEqual(w1.choices, [1, 2, 3])

    def test_fieldset(self):
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = ComplexField(widget=ComplexMultiWidget)

        form = TestForm()
        self.assertIs(form["field"].field.widget.use_fieldset, True)
        self.assertHTMLEqual(
            "<div><fieldset><legend>Field:</legend>"
            '<input type="text" name="field_0" required id="id_field_0">'
            '<select name="field_1" required id="id_field_1" multiple>'
            '<option value="J">John</option><option value="P">Paul</option>'
            '<option value="G">George</option><option value="R">Ringo</option></select>'
            '<input type="text" name="field_2_0" required id="id_field_2_0">'
            '<input type="text" name="field_2_1" required id="id_field_2_1">'
            "</fieldset></div>",
            form.render(),
        )
