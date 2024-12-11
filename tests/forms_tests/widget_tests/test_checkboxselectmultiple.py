import datetime

from django import forms
from django.forms import CheckboxSelectMultiple, ChoiceField, Form
from django.test import override_settings

from .base import WidgetTest


class CheckboxSelectMultipleTest(WidgetTest):
    widget = CheckboxSelectMultiple

    def test_render_value(self):
        self.check_html(
            self.widget(choices=self.beatles),
            "beatles",
            ["J"],
            html="""
            <div>
            <div><label><input checked type="checkbox" name="beatles" value="J"> John
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="P"> Paul
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="G"> George
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="R"> Ringo
            </label></div>
            </div>
        """,
        )

    def test_render_value_multiple(self):
        self.check_html(
            self.widget(choices=self.beatles),
            "beatles",
            ["J", "P"],
            html="""
            <div>
            <div><label><input checked type="checkbox" name="beatles" value="J"> John
            </label></div>
            <div><label><input checked type="checkbox" name="beatles" value="P"> Paul
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="G"> George
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="R"> Ringo
            </label></div>
            </div>
        """,
        )

    def test_render_none(self):
        """
        If the value is None, none of the options are selected, even if the
        choices have an empty option.
        """
        self.check_html(
            self.widget(choices=(("", "Unknown"),) + self.beatles),
            "beatles",
            None,
            html="""
            <div>
            <div><label><input type="checkbox" name="beatles" value=""> Unknown
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="J"> John
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="P"> Paul
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="G"> George
            </label></div>
            <div><label><input type="checkbox" name="beatles" value="R"> Ringo
            </label></div>
            </div>
        """,
        )

    def test_nested_choices(self):
        """
        cwd
        .. method:: test_nested_choices

            Tests the rendering of a widget with nested choices.

            This test case verifies that the widget correctly handles a set of nested choices, 
            where each choice may have a set of sub-choices. The test checks that the HTML 
            output matches the expected structure, including the correct rendering of 
            checkboxes, labels, and nesting.

            :return: None 
            :raises: AssertionError if the HTML output does not match the expected structure.
        """
        nested_choices = (
            ("unknown", "Unknown"),
            ("Audio", (("vinyl", "Vinyl"), ("cd", "CD"))),
            ("Video", (("vhs", "VHS"), ("dvd", "DVD"))),
        )
        html = """
        <div id="media">
        <div> <label for="media_0">
        <input type="checkbox" name="nestchoice" value="unknown" id="media_0"> Unknown
        </label></div>
        <div>
        <label>Audio</label>
        <div> <label for="media_1_0">
        <input checked type="checkbox" name="nestchoice" value="vinyl" id="media_1_0">
        Vinyl</label></div>
        <div> <label for="media_1_1">
        <input type="checkbox" name="nestchoice" value="cd" id="media_1_1"> CD
        </label></div>
        </div><div>
        <label>Video</label>
        <div> <label for="media_2_0">
        <input type="checkbox" name="nestchoice" value="vhs" id="media_2_0"> VHS
        </label></div>
        <div> <label for="media_2_1">
        <input type="checkbox" name="nestchoice" value="dvd" id="media_2_1" checked> DVD
        </label></div>
        </div>
        </div>
        """
        self.check_html(
            self.widget(choices=nested_choices),
            "nestchoice",
            ("vinyl", "dvd"),
            attrs={"id": "media"},
            html=html,
        )

    def test_nested_choices_without_id(self):
        nested_choices = (
            ("unknown", "Unknown"),
            ("Audio", (("vinyl", "Vinyl"), ("cd", "CD"))),
            ("Video", (("vhs", "VHS"), ("dvd", "DVD"))),
        )
        html = """
        <div>
        <div> <label>
        <input type="checkbox" name="nestchoice" value="unknown"> Unknown</label></div>
        <div>
        <label>Audio</label>
        <div> <label>
        <input checked type="checkbox" name="nestchoice" value="vinyl"> Vinyl
        </label></div>
        <div> <label>
        <input type="checkbox" name="nestchoice" value="cd"> CD</label></div>
        </div><div>
        <label>Video</label>
        <div> <label>
        <input type="checkbox" name="nestchoice" value="vhs"> VHS</label></div>
        <div> <label>
        <input type="checkbox" name="nestchoice" value="dvd"checked> DVD</label></div>
        </div>
        </div>
        """
        self.check_html(
            self.widget(choices=nested_choices),
            "nestchoice",
            ("vinyl", "dvd"),
            html=html,
        )

    def test_separate_ids(self):
        """
        Each input gets a separate ID.
        """
        choices = [("a", "A"), ("b", "B"), ("c", "C")]
        html = """
        <div id="abc">
        <div>
        <label for="abc_0">
        <input checked type="checkbox" name="letters" value="a" id="abc_0"> A</label>
        </div>
        <div><label for="abc_1">
        <input type="checkbox" name="letters" value="b" id="abc_1"> B</label></div>
        <div>
        <label for="abc_2">
        <input checked type="checkbox" name="letters" value="c" id="abc_2"> C</label>
        </div>
        </div>
        """
        self.check_html(
            self.widget(choices=choices),
            "letters",
            ["a", "c"],
            attrs={"id": "abc"},
            html=html,
        )

    def test_separate_ids_constructor(self):
        """
        Each input gets a separate ID when the ID is passed to the constructor.
        """
        widget = CheckboxSelectMultiple(
            attrs={"id": "abc"}, choices=[("a", "A"), ("b", "B"), ("c", "C")]
        )
        html = """
        <div id="abc">
        <div>
        <label for="abc_0">
        <input checked type="checkbox" name="letters" value="a" id="abc_0"> A</label>
        </div>
        <div><label for="abc_1">
        <input type="checkbox" name="letters" value="b" id="abc_1"> B</label></div>
        <div>
        <label for="abc_2">
        <input checked type="checkbox" name="letters" value="c" id="abc_2"> C</label>
        </div>
        </div>
        """
        self.check_html(widget, "letters", ["a", "c"], html=html)

    @override_settings(USE_THOUSAND_SEPARATOR=True)
    def test_doesnt_localize_input_value(self):
        """
        Tests that the widget does not localize the input value when rendering checkboxes.

            Verifies the output HTML for checkbox widgets with different types of choices, 
            including integers and time objects, to ensure that the input values are not 
            formatted according to locale settings. The test cases cover various scenarios, 
            such as numbers with thousand separators and time values in 24-hour format.

            The test checks the generated HTML against expected output, confirming that 
            the widget produces the correct markup for the given choices and input values.

            The test is run with USE_THOUSAND_SEPARATOR set to True to ensure that the 
            localization setting does not affect the input values in the rendered HTML.
        """
        choices = [
            (1, "One"),
            (1000, "One thousand"),
            (1000000, "One million"),
        ]
        html = """
        <div>
        <div><label><input type="checkbox" name="numbers" value="1"> One</label></div>
        <div><label>
        <input type="checkbox" name="numbers" value="1000"> One thousand</label></div>
        <div><label>
        <input type="checkbox" name="numbers" value="1000000"> One million</label></div>
        </div>
        """
        self.check_html(self.widget(choices=choices), "numbers", None, html=html)

        choices = [
            (datetime.time(0, 0), "midnight"),
            (datetime.time(12, 0), "noon"),
        ]
        html = """
        <div>
        <div><label>
        <input type="checkbox" name="times" value="00:00:00"> midnight</label></div>
        <div><label>
        <input type="checkbox" name="times" value="12:00:00"> noon</label></div>
        </div>
        """
        self.check_html(self.widget(choices=choices), "times", None, html=html)

    def test_use_required_attribute(self):
        """
        Tests the usage of the required attribute in a widget.

        This test case verifies the behavior of the :meth:`use_required_attribute` method 
        in a widget when provided with different input values. It checks if the method 
        correctly returns False for various input scenarios, including None, an empty list, 
        and a list containing values. The purpose of this test is to ensure the widget's 
        required attribute is handled appropriately in different situations.
        """
        widget = self.widget(choices=self.beatles)
        # Always False because browser validation would require all checkboxes
        # to be checked instead of at least one.
        self.assertIs(widget.use_required_attribute(None), False)
        self.assertIs(widget.use_required_attribute([]), False)
        self.assertIs(widget.use_required_attribute(["J", "P"]), False)

    def test_value_omitted_from_data(self):
        """

        Checks whether a value is omitted from the data in a widget.

        The function determines whether a field is missing from the data by checking the presence of the field in the given data dictionaries. 
        It returns False if the field is present in either dictionary, indicating the value is not omitted, and is used to test the behavior of the widget in different data scenarios.

        """
        widget = self.widget(choices=self.beatles)
        self.assertIs(widget.value_omitted_from_data({}, {}, "field"), False)
        self.assertIs(
            widget.value_omitted_from_data({"field": "value"}, {}, "field"), False
        )

    def test_label(self):
        """
        CheckboxSelectMultiple doesn't contain 'for="field_0"' in the <label>
        because clicking that would toggle the first checkbox.
        """

        class TestForm(forms.Form):
            f = forms.MultipleChoiceField(widget=CheckboxSelectMultiple)

        bound_field = TestForm()["f"]
        self.assertEqual(bound_field.field.widget.id_for_label("id"), "")
        self.assertEqual(bound_field.label_tag(), "<label>F:</label>")
        self.assertEqual(bound_field.legend_tag(), "<legend>F:</legend>")

    def test_fieldset(self):
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = ChoiceField(widget=self.widget, choices=self.beatles)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, True)
        self.assertHTMLEqual(
            form.render(),
            '<div><fieldset><legend>Field:</legend><div id="id_field">'
            '<div><label for="id_field_0"><input type="checkbox" '
            'name="field" value="J" id="id_field_0"> John</label></div>'
            '<div><label for="id_field_1"><input type="checkbox" '
            'name="field" value="P" id="id_field_1">Paul</label></div>'
            '<div><label for="id_field_2"><input type="checkbox" '
            'name="field" value="G" id="id_field_2"> George</label></div>'
            '<div><label for="id_field_3"><input type="checkbox" '
            'name="field" value="R" id="id_field_3">'
            "Ringo</label></div></div></fieldset></div>",
        )
