from django.test import SimpleTestCase

from ..utils import setup


class TruncatecharsTests(SimpleTestCase):
    @setup({"truncatechars01": "{{ a|truncatechars:3 }}"})
    def test_truncatechars01(self):
        """

        Tests the truncatechars filter by rendering a template with a string 'Testing, testing' 
        and verifying the output is truncated to 3 characters and appended with an ellipsis ('Te…').

        """
        output = self.engine.render_to_string(
            "truncatechars01", {"a": "Testing, testing"}
        )
        self.assertEqual(output, "Te…")

    @setup({"truncatechars02": "{{ a|truncatechars:7 }}"})
    def test_truncatechars02(self):
        output = self.engine.render_to_string("truncatechars02", {"a": "Testing"})
        self.assertEqual(output, "Testing")

    @setup({"truncatechars03": "{{ a|truncatechars:'e' }}"})
    def test_fail_silently_incorrect_arg(self):
        output = self.engine.render_to_string(
            "truncatechars03", {"a": "Testing, testing"}
        )
        self.assertEqual(output, "Testing, testing")

    @setup({"truncatechars04": "{{ a|truncatechars:3 }}"})
    def test_truncatechars04(self):
        output = self.engine.render_to_string("truncatechars04", {"a": "abc"})
        self.assertEqual(output, "abc")
