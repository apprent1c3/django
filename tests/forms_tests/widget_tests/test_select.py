import datetime

from django.forms import ChoiceField, Form, MultiWidget, Select, TextInput
from django.test import override_settings
from django.utils.safestring import mark_safe

from .test_choicewidget import ChoiceWidgetTest


class SelectTest(ChoiceWidgetTest):
    widget = Select

    def test_render(self):
        html = """
        <select name="beatle">
          <option value="J" selected>John</option>
          <option value="P">Paul</option>
          <option value="G">George</option>
          <option value="R">Ringo</option>
        </select>
        """
        for choices in (self.beatles, dict(self.beatles)):
            with self.subTest(choices):
                self.check_html(self.widget(choices=choices), "beatle", "J", html=html)

    def test_render_none(self):
        """
        If the value is None, none of the options are selected.
        """
        self.check_html(
            self.widget(choices=self.beatles),
            "beatle",
            None,
            html=(
                """<select name="beatle">
            <option value="J">John</option>
            <option value="P">Paul</option>
            <option value="G">George</option>
            <option value="R">Ringo</option>
            </select>"""
            ),
        )

    def test_render_label_value(self):
        """
        If the value corresponds to a label (but not to an option value), none
        of the options are selected.
        """
        self.check_html(
            self.widget(choices=self.beatles),
            "beatle",
            "John",
            html=(
                """<select name="beatle">
            <option value="J">John</option>
            <option value="P">Paul</option>
            <option value="G">George</option>
            <option value="R">Ringo</option>
            </select>"""
            ),
        )

    def test_render_selected(self):
        """
        Only one option can be selected (#8103).
        """
        choices = [("0", "0"), ("1", "1"), ("2", "2"), ("3", "3"), ("0", "extra")]

        self.check_html(
            self.widget(choices=choices),
            "choices",
            "0",
            html=(
                """<select name="choices">
            <option value="0" selected>0</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="0">extra</option>
            </select>"""
            ),
        )

    def test_constructor_attrs(self):
        """
        Select options shouldn't inherit the parent widget attrs.
        """
        widget = Select(
            attrs={"class": "super", "id": "super"},
            choices=[(1, 1), (2, 2), (3, 3)],
        )
        self.check_html(
            widget,
            "num",
            2,
            html=(
                """<select name="num" class="super" id="super">
              <option value="1">1</option>
              <option value="2" selected>2</option>
              <option value="3">3</option>
            </select>"""
            ),
        )

    def test_compare_to_str(self):
        """
        The value is compared to its str().
        """
        self.check_html(
            self.widget(choices=[("1", "1"), ("2", "2"), ("3", "3")]),
            "num",
            2,
            html=(
                """<select name="num">
                <option value="1">1</option>
                <option value="2" selected>2</option>
                <option value="3">3</option>
                </select>"""
            ),
        )
        self.check_html(
            self.widget(choices=[(1, 1), (2, 2), (3, 3)]),
            "num",
            "2",
            html=(
                """<select name="num">
                <option value="1">1</option>
                <option value="2" selected>2</option>
                <option value="3">3</option>
                </select>"""
            ),
        )
        self.check_html(
            self.widget(choices=[(1, 1), (2, 2), (3, 3)]),
            "num",
            2,
            html=(
                """<select name="num">
                <option value="1">1</option>
                <option value="2" selected>2</option>
                <option value="3">3</option>
                </select>"""
            ),
        )

    def test_choices_constructor(self):
        widget = Select(choices=[(1, 1), (2, 2), (3, 3)])
        self.check_html(
            widget,
            "num",
            2,
            html=(
                """<select name="num">
            <option value="1">1</option>
            <option value="2" selected>2</option>
            <option value="3">3</option>
            </select>"""
            ),
        )

    def test_choices_constructor_generator(self):
        """
        If choices is passed to the constructor and is a generator, it can be
        iterated over multiple times without getting consumed.
        """

        def get_choices():
            for i in range(5):
                yield (i, i)

        widget = Select(choices=get_choices())
        self.check_html(
            widget,
            "num",
            2,
            html=(
                """<select name="num">
            <option value="0">0</option>
            <option value="1">1</option>
            <option value="2" selected>2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            </select>"""
            ),
        )
        self.check_html(
            widget,
            "num",
            3,
            html=(
                """<select name="num">
            <option value="0">0</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3" selected>3</option>
            <option value="4">4</option>
            </select>"""
            ),
        )

    def test_choices_escaping(self):
        choices = (("bad", "you & me"), ("good", mark_safe("you &gt; me")))
        self.check_html(
            self.widget(choices=choices),
            "escape",
            None,
            html=(
                """<select name="escape">
            <option value="bad">you &amp; me</option>
            <option value="good">you &gt; me</option>
            </select>"""
            ),
        )

    def test_choices_unicode(self):
        self.check_html(
            self.widget(choices=[("ŠĐĆŽćžšđ", "ŠĐabcĆŽćžšđ"), ("ćžšđ", "abcćžšđ")]),
            "email",
            "ŠĐĆŽćžšđ",
            html=(
                """
                <select name="email">
                <option value="\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111"
                    selected>
                    \u0160\u0110abc\u0106\u017d\u0107\u017e\u0161\u0111
                </option>
                <option value="\u0107\u017e\u0161\u0111">abc\u0107\u017e\u0161\u0111
                </option>
                </select>
                """
            ),
        )

    def test_choices_optgroup(self):
        """
        Choices can be nested one level in order to create HTML optgroups.
        """
        html = """
        <select name="nestchoice">
          <option value="outer1">Outer 1</option>
          <optgroup label="Group &quot;1&quot;">
          <option value="inner1">Inner 1</option>
          <option value="inner2">Inner 2</option>
          </optgroup>
        </select>
        """
        for widget in self.nested_widgets:
            with self.subTest(widget):
                self.check_html(widget, "nestchoice", None, html=html)

    def test_choices_select_outer(self):
        html = """
        <select name="nestchoice">
          <option value="outer1" selected>Outer 1</option>
          <optgroup label="Group &quot;1&quot;">
          <option value="inner1">Inner 1</option>
          <option value="inner2">Inner 2</option>
          </optgroup>
        </select>
        """
        for widget in self.nested_widgets:
            with self.subTest(widget):
                self.check_html(widget, "nestchoice", "outer1", html=html)

    def test_choices_select_inner(self):
        """
        Tests the selection behavior of nested widgets within an HTML select element.

        This function verifies that the correct option is selected when a widget is 
        nested within an optgroup. The test checks for a specific HTML structure 
        containing a select element with a nested optgroup, and ensures that the 
        selected option is correctly identified for each widget in the nested structure.

        The function covers the following:

        * HTML structure with a select element and nested optgroup
        * Option selection behavior within the nested optgroup
        * Verification of the selected option for each widget

        It uses a predefined HTML string to test the behavior of the nested widgets 
        and checks that the expected option is selected for each widget in the test set.
        """
        html = """
        <select name="nestchoice">
          <option value="outer1">Outer 1</option>
          <optgroup label="Group &quot;1&quot;">
          <option value="inner1" selected>Inner 1</option>
          <option value="inner2">Inner 2</option>
          </optgroup>
        </select>
        """
        for widget in self.nested_widgets:
            with self.subTest(widget):
                self.check_html(widget, "nestchoice", "inner1", html=html)

    @override_settings(USE_THOUSAND_SEPARATOR=True)
    def test_doesnt_localize_option_value(self):
        choices = [
            (1, "One"),
            (1000, "One thousand"),
            (1000000, "One million"),
        ]
        html = """
        <select name="number">
        <option value="1">One</option>
        <option value="1000">One thousand</option>
        <option value="1000000">One million</option>
        </select>
        """
        self.check_html(self.widget(choices=choices), "number", None, html=html)

        choices = [
            (datetime.time(0, 0), "midnight"),
            (datetime.time(12, 0), "noon"),
        ]
        html = """
        <select name="time">
        <option value="00:00:00">midnight</option>
        <option value="12:00:00">noon</option>
        </select>
        """
        self.check_html(self.widget(choices=choices), "time", None, html=html)

    def _test_optgroups(self, choices):
        """

        Tests the rendering of option groups within a select widget.

        This function verifies that the widget correctly groups options by their
        optgroup labels and renders each option with the correct attributes.
        It checks that the optgroups are returned in the correct order, with 
        their corresponding labels, options, and indices.

        The test case covers three optgroups: 'Audio', 'Video', and an unknown 
        optgroup. It ensures that the 'Audio' and 'Video' optgroups contain 
        the expected options and that the unknown optgroup is rendered correctly.

        """
        groups = list(
            self.widget(choices=choices).optgroups(
                "name",
                ["vhs"],
                attrs={"class": "super"},
            )
        )
        audio, video, unknown = groups
        label, options, index = audio
        self.assertEqual(label, "Audio")
        self.assertEqual(
            options,
            [
                {
                    "value": "vinyl",
                    "type": "select",
                    "attrs": {},
                    "index": "0_0",
                    "label": "Vinyl",
                    "template_name": "django/forms/widgets/select_option.html",
                    "name": "name",
                    "selected": False,
                    "wrap_label": True,
                },
                {
                    "value": "cd",
                    "type": "select",
                    "attrs": {},
                    "index": "0_1",
                    "label": "CD",
                    "template_name": "django/forms/widgets/select_option.html",
                    "name": "name",
                    "selected": False,
                    "wrap_label": True,
                },
            ],
        )
        self.assertEqual(index, 0)
        label, options, index = video
        self.assertEqual(label, "Video")
        self.assertEqual(
            options,
            [
                {
                    "value": "vhs",
                    "template_name": "django/forms/widgets/select_option.html",
                    "label": "VHS Tape",
                    "attrs": {"selected": True},
                    "index": "1_0",
                    "name": "name",
                    "selected": True,
                    "type": "select",
                    "wrap_label": True,
                },
                {
                    "value": "dvd",
                    "template_name": "django/forms/widgets/select_option.html",
                    "label": "DVD",
                    "attrs": {},
                    "index": "1_1",
                    "name": "name",
                    "selected": False,
                    "type": "select",
                    "wrap_label": True,
                },
            ],
        )
        self.assertEqual(index, 1)
        label, options, index = unknown
        self.assertIsNone(label)
        self.assertEqual(
            options,
            [
                {
                    "value": "unknown",
                    "selected": False,
                    "template_name": "django/forms/widgets/select_option.html",
                    "label": "Unknown",
                    "attrs": {},
                    "index": "2",
                    "name": "name",
                    "type": "select",
                    "wrap_label": True,
                }
            ],
        )
        self.assertEqual(index, 2)

    def test_optgroups(self):
        """
        Tests the functionality of generating optgroups from various input formats.

        This test case covers different types of input choices, including dictionaries, lists of tuples, and nested dictionaries.
        It verifies that the function can handle these various formats and produce the expected output for each one.

        The test iterates over multiple input formats, including:
            - A dictionary with list values
            - A list of tuples
            - A dictionary with nested dictionaries

        Each input format is tested separately to ensure that the function behaves as expected in all scenarios.
        """
        choices_dict = {
            "Audio": [
                ("vinyl", "Vinyl"),
                ("cd", "CD"),
            ],
            "Video": [
                ("vhs", "VHS Tape"),
                ("dvd", "DVD"),
            ],
            "unknown": "Unknown",
        }
        choices_list = list(choices_dict.items())
        choices_nested_dict = {
            k: dict(v) if isinstance(v, list) else v for k, v in choices_dict.items()
        }

        for choices in (choices_dict, choices_list, choices_nested_dict):
            with self.subTest(choices):
                self._test_optgroups(choices)

    def test_doesnt_render_required_when_impossible_to_select_empty_field(self):
        """
        Tests that the required attribute is not rendered for a widget when it is impossible to select an empty field, indicating that at least one option must be chosen. This check ensures the widget behaves correctly when no initial value is provided and the field has a set of predefined choices, none of which represent an empty or null selection.
        """
        widget = self.widget(choices=[("J", "John"), ("P", "Paul")])
        self.assertIs(widget.use_required_attribute(initial=None), False)

    def test_doesnt_render_required_when_no_choices_are_available(self):
        widget = self.widget(choices=[])
        self.assertIs(widget.use_required_attribute(initial=None), False)

    def test_render_as_subwidget(self):
        """A RadioSelect as a subwidget of MultiWidget."""
        choices = (("", "------"),) + self.beatles
        self.check_html(
            MultiWidget([self.widget(choices=choices), TextInput()]),
            "beatle",
            ["J", "Some text"],
            html=(
                """
                <select name="beatle_0">
                  <option value="">------</option>
                  <option value="J" selected>John</option>
                  <option value="P">Paul</option>
                  <option value="G">George</option>
                  <option value="R">Ringo</option>
                </select>
                <input name="beatle_1" type="text" value="Some text">
                """
            ),
        )

    def test_fieldset(self):
        """

        Tests the rendering of a form field using a ChoiceField with a custom widget.

        This test case verifies that the form field is rendered correctly as a select element
        with options, without using a fieldset. It checks the HTML output of the form field
        against an expected HTML string to ensure that the widget and field are properly rendered.

        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = ChoiceField(widget=self.widget, choices=self.beatles)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            '<div><label for="id_field">Field:</label>'
            '<select name="field" id="id_field">'
            '<option value="J">John</option>  '
            '<option value="P">Paul</option>'
            '<option value="G">George</option>'
            '<option value="R">Ringo</option></select></div>',
            form.render(),
        )
