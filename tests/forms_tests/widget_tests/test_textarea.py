from django.forms import CharField, Form, Textarea
from django.utils.safestring import mark_safe

from .base import WidgetTest


class TextareaTest(WidgetTest):
    widget = Textarea()

    def test_render(self):
        self.check_html(
            self.widget,
            "msg",
            "value",
            html=('<textarea rows="10" cols="40" name="msg">value</textarea>'),
        )

    def test_render_required(self):
        widget = Textarea()
        widget.is_required = True
        self.check_html(
            widget,
            "msg",
            "value",
            html='<textarea rows="10" cols="40" name="msg">value</textarea>',
        )

    def test_render_empty(self):
        self.check_html(
            self.widget,
            "msg",
            "",
            html='<textarea rows="10" cols="40" name="msg"></textarea>',
        )

    def test_render_none(self):
        self.check_html(
            self.widget,
            "msg",
            None,
            html='<textarea rows="10" cols="40" name="msg"></textarea>',
        )

    def test_escaping(self):
        self.check_html(
            self.widget,
            "msg",
            'some "quoted" & ampersanded value',
            html=(
                '<textarea rows="10" cols="40" name="msg">'
                "some &quot;quoted&quot; &amp; ampersanded value</textarea>"
            ),
        )

    def test_mark_safe(self):
        self.check_html(
            self.widget,
            "msg",
            mark_safe("pre &quot;quoted&quot; value"),
            html=(
                '<textarea rows="10" cols="40" name="msg">pre &quot;quoted&quot; value'
                "</textarea>"
            ),
        )

    def test_fieldset(self):
        """
        Tests the rendering of a form field using a custom widget.

        Verifies that the widget does not use a fieldset by default and that the 
        form field renders correctly with the expected HTML structure, including 
        a label and textarea elements with the correct attributes.

        The test creates a simple form with a single character field using the 
        custom widget and checks the rendered HTML output against an expected 
        template to ensure accurate rendering. 
        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = CharField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            '<div><label for="id_field">Field:</label>'
            '<textarea cols="40" id="id_field" name="field" '
            'required rows="10"></textarea></div>',
            form.render(),
        )
