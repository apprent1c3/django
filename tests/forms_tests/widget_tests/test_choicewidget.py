import copy

from django.forms.widgets import ChoiceWidget

from .base import WidgetTest


class ChoiceWidgetTest(WidgetTest):
    widget = ChoiceWidget

    @property
    def nested_widgets(self):
        """
        This is a comment
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
        This is a comment
        """
        widget = self.widget()
        obj = copy.deepcopy(widget)
        self.assertIsNot(widget, obj)
        self.assertEqual(widget.choices, obj.choices)
        self.assertIsNot(widget.choices, obj.choices)
        self.assertEqual(widget.attrs, obj.attrs)
        self.assertIsNot(widget.attrs, obj.attrs)

    def test_options(self):
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        groups = list(
            self.widget(choices=[[0, "choice text"]]).optgroups("name", ["vhs"])
        )
        label, options, index = groups[0]
        self.assertEqual(options[0]["value"], 0)

    def test_renders_required_when_possible_to_select_empty_field_none(self):
        """
        This is a comment
        """
        widget = self.widget(choices=[(None, "select please"), ("P", "Paul")])
        self.assertIs(widget.use_required_attribute(initial=None), True)

    def test_renders_required_when_possible_to_select_empty_field_list(self):
        """
        This is a comment
        """
        widget = self.widget(choices=[["", "select please"], ["P", "Paul"]])
        self.assertIs(widget.use_required_attribute(initial=None), True)

    def test_renders_required_when_possible_to_select_empty_field_str(self):
        """
        This is a comment
        """
        widget = self.widget(choices=[("", "select please"), ("P", "Paul")])
        self.assertIs(widget.use_required_attribute(initial=None), True)
