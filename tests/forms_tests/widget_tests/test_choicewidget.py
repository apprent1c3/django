import copy

from django.forms.widgets import ChoiceWidget

from .base import WidgetTest


class ChoiceWidgetTest(WidgetTest):
    widget = ChoiceWidget

    @property
    def nested_widgets(self):
        """
        .. property:: nested_widgets
            Retrieves a tuple of widgets with nested choices.

            The returned widgets have choices that are nested through tuples or dictionaries, 
            representing different types of grouped options. This can be useful for creating 
            hierarchical or categorized selections in a user interface.

            The returned tuple contains three types of nested widgets: 
            one with choices defined as tuples of tuples, 
            one with choices defined as a dictionary of dictionaries, 
            and one with choices defined as a dictionary containing both strings and tuples.

            :return: A tuple of three widgets with nested choices
            :rtype: tuple
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
        Tests whether the required attribute is rendered when it is possible to select an empty field with a value of None.

        This test case verifies that the required attribute is correctly applied to the widget when the initial value is None and there is an option to select an empty field. The goal is to ensure that the widget behaves as expected in scenarios where an empty selection is a valid choice, but a value is still required to be entered by the user.
        """
        widget = self.widget(choices=[(None, "select please"), ("P", "Paul")])
        self.assertIs(widget.use_required_attribute(initial=None), True)

    def test_renders_required_when_possible_to_select_empty_field_list(self):
        """
        Checks if the required attribute is used when it's possible to select an empty field from the provided choices.

        This test ensures that the widget applies the required attribute when there's an option to select an empty field, even if the initial value is None. This is important to enforce input validation and prevent empty submissions when at least one choice must be selected.

        The test case specifically looks at a scenario where the choices include an empty field option, represented by an empty string, and verifies that the widget's behavior aligns with the expected requirement rules in such cases.
        """
        widget = self.widget(choices=[["", "select please"], ["P", "Paul"]])
        self.assertIs(widget.use_required_attribute(initial=None), True)

    def test_renders_required_when_possible_to_select_empty_field_str(self):
        widget = self.widget(choices=[("", "select please"), ("P", "Paul")])
        self.assertIs(widget.use_required_attribute(initial=None), True)
