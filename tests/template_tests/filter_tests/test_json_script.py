from django.test import SimpleTestCase

from ..utils import setup


class JsonScriptTests(SimpleTestCase):
    @setup({"json-tag01": '{{ value|json_script:"test_id" }}'})
    def test_basic(self):
        """
        Renders a JSON object as a JSON script tag.

        This function tests the rendering of a JSON object into a JSON script tag.
        The rendered output is a JSON object wrapped in a script tag with a specified ID and MIME type.
        The function ensures proper escaping of special characters in the JSON string,
        including newlines, quotes, and HTML tags, to prevent injection vulnerabilities.

        :returns: A rendered JSON script tag as a string.

        """
        output = self.engine.render_to_string(
            "json-tag01", {"value": {"a": "testing\r\njson 'string\" <b>escaping</b>"}}
        )
        self.assertEqual(
            output,
            '<script id="test_id" type="application/json">'
            '{"a": "testing\\r\\njson \'string\\" '
            '\\u003Cb\\u003Eescaping\\u003C/b\\u003E"}'
            "</script>",
        )

    @setup({"json-tag02": "{{ value|json_script }}"})
    def test_without_id(self):
        """
        Tests rendering of an empty JSON object using the json_script filter, verifying that the output is a script tag with the correct type attribute and empty JSON data.
        """
        output = self.engine.render_to_string("json-tag02", {"value": {}})
        self.assertEqual(output, '<script type="application/json">{}</script>')
