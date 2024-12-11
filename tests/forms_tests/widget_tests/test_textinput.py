from django.forms import CharField, Form, TextInput
from django.utils.safestring import mark_safe

from .base import WidgetTest


class TextInputTest(WidgetTest):
    widget = TextInput()

    def test_render(self):
        self.check_html(
            self.widget, "email", "", html='<input type="text" name="email">'
        )

    def test_render_none(self):
        self.check_html(
            self.widget, "email", None, html='<input type="text" name="email">'
        )

    def test_render_value(self):
        self.check_html(
            self.widget,
            "email",
            "test@example.com",
            html=('<input type="text" name="email" value="test@example.com">'),
        )

    def test_render_boolean(self):
        """
        Boolean values are rendered to their string forms ("True" and
        "False").
        """
        self.check_html(
            self.widget,
            "get_spam",
            False,
            html=('<input type="text" name="get_spam" value="False">'),
        )
        self.check_html(
            self.widget,
            "get_spam",
            True,
            html=('<input type="text" name="get_spam" value="True">'),
        )

    def test_render_quoted(self):
        self.check_html(
            self.widget,
            "email",
            'some "quoted" & ampersanded value',
            html=(
                '<input type="text" name="email" '
                'value="some &quot;quoted&quot; &amp; ampersanded value">'
            ),
        )

    def test_render_custom_attrs(self):
        self.check_html(
            self.widget,
            "email",
            "test@example.com",
            attrs={"class": "fun"},
            html=(
                '<input type="text" name="email" value="test@example.com" class="fun">'
            ),
        )

    def test_render_unicode(self):
        self.check_html(
            self.widget,
            "email",
            "ŠĐĆŽćžšđ",
            attrs={"class": "fun"},
            html=(
                '<input type="text" name="email" '
                'value="\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111" class="fun">'
            ),
        )

    def test_constructor_attrs(self):
        widget = TextInput(attrs={"class": "fun", "type": "email"})
        self.check_html(
            widget, "email", "", html='<input type="email" class="fun" name="email">'
        )
        self.check_html(
            widget,
            "email",
            "foo@example.com",
            html=(
                '<input type="email" class="fun" value="foo@example.com" name="email">'
            ),
        )

    def test_attrs_precedence(self):
        """
        `attrs` passed to render() get precedence over those passed to the
        constructor
        """
        widget = TextInput(attrs={"class": "pretty"})
        self.check_html(
            widget,
            "email",
            "",
            attrs={"class": "special"},
            html='<input type="text" class="special" name="email">',
        )

    def test_attrs_safestring(self):
        """
        Tests that a TextInput widget with a SafeString attribute value is rendered correctly in the HTML output, ensuring that the attribute is properly escaped and the widget functions as expected.
        """
        widget = TextInput(attrs={"onBlur": mark_safe("function('foo')")})
        self.check_html(
            widget,
            "email",
            "",
            html='<input onBlur="function(\'foo\')" type="text" name="email">',
        )

    def test_use_required_attribute(self):
        # Text inputs can safely trigger the browser validation.
        """
        Tests the use_required_attribute method of the widget.

        This method checks whether the use_required_attribute method of the widget
        returns True for various inputs, including None, an empty string, and a file name.
        It verifies that the method behaves consistently and always returns True,
        regardless of the input provided.
        """
        self.assertIs(self.widget.use_required_attribute(None), True)
        self.assertIs(self.widget.use_required_attribute(""), True)
        self.assertIs(self.widget.use_required_attribute("resume.txt"), True)

    def test_fieldset(self):
        """
        Tests the functionality of a form fieldset.

        This test case verifies that a form field is correctly rendered without a fieldset.
        It creates a test form with a single character field and checks that the rendered
        HTML matches the expected output, ensuring that no fieldset is used.
        The test also confirms that the use_fieldset attribute of the widget is False.

        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = CharField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            '<div><label for="id_field">Field:</label>'
            '<input type="text" name="field" required id="id_field"></div>',
            form.render(),
        )
