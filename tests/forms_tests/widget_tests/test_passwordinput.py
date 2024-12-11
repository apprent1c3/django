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
        Verifies the rendering of a form field when the use_fieldset attribute of a widget is set to False.

        This test ensures that the field is rendered as expected, with the correct HTML structure and attributes, when the use_fieldset attribute is disabled.

        The test case creates a test form with a single field, renders the form, and then checks that the resulting HTML matches the expected output. The expected output includes a div element containing a label and input element, with the correct id, name, and type attributes.

        The test confirms that the widget's use_fieldset attribute is set to False and that the rendered HTML does not include any fieldset elements, as expected when this attribute is disabled.
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
