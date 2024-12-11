import copy

from django.forms.widgets import ChoiceWidget

from .base import WidgetTest


class ChoiceWidgetTest(WidgetTest):
    widget = ChoiceWidget

    @property
    def nested_widgets(self):
        """

        Retrieves examples of nested widgets, illustrating different ways to structure choices.

        The returned tuple contains three variations of nested widgets:
        1. A nested widget using tuple-based choices.
        2. A nested widget using dictionary-based choices with inner dictionaries.
        3. A nested widget using dictionary-based choices with inner tuples.

        These examples demonstrate how to create nested options for the widget, with 'outer' and 'inner' choices.

        """
        nested_widget = self.widget(
            choices=(
                ("outer1", "Outer 1"),
                ('Group "1"', (("inner1", "Inner 1"), ("inner2", "Inner 2"))),
            ),
        )
        nested_widget_dict = self.widget(
            choices={
                "outer1": "Outer 1",
                'Group "1"': {"inner1": "Inner 1", "inner2": "Inner 2"},
            },
        )
        nested_widget_dict_tuple = self.widget(
            choices={
                "outer1": "Outer 1",
                'Group "1"': (("inner1", "Inner 1"), ("inner2", "Inner 2")),
            },
        )
        return (nested_widget, nested_widget_dict, nested_widget_dict_tuple)

    def test_deepcopy(self):
        """
        __deepcopy__() should copy all attributes properly.
        """
        widget = self.widget()
        obj = copy.deepcopy(widget)
        self.assertIsNot(widget, obj)
        self.assertEqual(widget.choices, obj.choices)
        self.assertIsNot(widget.choices, obj.choices)
        self.assertEqual(widget.attrs, obj.attrs)
        self.assertIsNot(widget.attrs, obj.attrs)

    def test_options(self):
        options = list(
            self.widget(choices=self.beatles).options(
                "name",
                ["J"],
                attrs={"class": "super"},
            )
        )
        self.assertEqual(len(options), 4)
        self.assertEqual(options[0]["name"], "name")
        self.assertEqual(options[0]["value"], "J")
        self.assertEqual(options[0]["label"], "John")
        self.assertEqual(options[0]["index"], "0")
        self.assertIs(options[0]["selected"], True)
        # Template-related attributes
        self.assertEqual(options[1]["name"], "name")
        self.assertEqual(options[1]["value"], "P")
        self.assertEqual(options[1]["label"], "Paul")
        self.assertEqual(options[1]["index"], "1")
        self.assertIs(options[1]["selected"], False)

    def test_optgroups_integer_choices(self):
        """The option 'value' is the same type as what's in `choices`."""
        groups = list(
            self.widget(choices=[[0, "choice text"]]).optgroups("name", ["vhs"])
        )
        label, options, index = groups[0]
        self.assertEqual(options[0]["value"], 0)

    def test_renders_required_when_possible_to_select_empty_field_none(self):
        """
        Tests that the 'required' attribute is added when rendering a widget with an empty field that can be selected as None, ensuring validation for fields that require input.
        """
        widget = self.widget(choices=[(None, "select please"), ("P", "Paul")])
        self.assertIs(widget.use_required_attribute(initial=None), True)

    def test_renders_required_when_possible_to_select_empty_field_list(self):
        """
        Tests that the widget renders the required attribute when it is possible to select an empty field list.

        The test case covers a scenario where the widget is initialized with a list of choices, including an empty option.
        The expected outcome is that the widget should use the required attribute, indicated by the return value of True,
        when no initial value is provided, thus ensuring that the user must select a valid option from the list of choices.
        """
        widget = self.widget(choices=[["", "select please"], ["P", "Paul"]])
        self.assertIs(widget.use_required_attribute(initial=None), True)

    def test_renders_required_when_possible_to_select_empty_field_str(self):
        """
        Checks if a widget is correctly set to required when it's possible to select an empty field, ensuring that the form validation behaves as expected in such scenarios, preventing the submission of forms with empty required fields.
        """
        widget = self.widget(choices=[("", "select please"), ("P", "Paul")])
        self.assertIs(widget.use_required_attribute(initial=None), True)
