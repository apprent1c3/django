from django.forms import CharField, Form, PasswordInput

from .base import WidgetTest


class PasswordInputTest(WidgetTest):
    widget = PasswordInput()

    def test_render(self):
        self.check_html(
            self.widget, "password", "", html='<input type="password" name="password">'
        )

    def test_render_ignore_value(self):
        self.check_html(
            self.widget,
            "password",
            "secret",
            html='<input type="password" name="password">',
        )

    def test_render_value_true(self):
        """
        The render_value argument lets you specify whether the widget should
        render its value. For security reasons, this is off by default.
        """
        widget = PasswordInput(render_value=True)
        self.check_html(
            widget, "password", "", html='<input type="password" name="password">'
        )
        self.check_html(
            widget, "password", None, html='<input type="password" name="password">'
        )
        self.check_html(
            widget,
            "password",
            "test@example.com",
            html='<input type="password" name="password" value="test@example.com">',
        )

    def test_fieldset(self):
        """

        Tests that a form field is rendered correctly without a fieldset.

        This test ensures that when the :attr:`use_fieldset` attribute of a widget is set to False,
        the field is rendered as a simple label and input, wrapped in a div tag, rather than being enclosed in a fieldset.

        The test case renders a form with a single field and verifies that the resulting HTML matches the expected output.

        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = CharField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            '<div><label for="id_field">Field:</label>'
            '<input type="password" name="field" required id="id_field"></div>',
            form.render(),
        )
