from django.template import Context, Engine
from django.template.base import TextNode, VariableNode
from django.test import SimpleTestCase


class NodelistTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine()
        super().setUpClass()

    def test_for(self):
        template = self.engine.from_string("{% for i in 1 %}{{ a }}{% endfor %}")
        vars = template.nodelist.get_nodes_by_type(VariableNode)
        self.assertEqual(len(vars), 1)

    def test_if(self):
        """
        #: Tests if an if statement in a template renders correctly as a single VariableNode.
        #: 
        #: This test case ensures that the templating engine correctly interprets 
        #: conditional statements and translates them into the expected number of 
        #: VariableNodes. The test creates a simple template with an if statement, 
        #: parses it, and then verifies that only one VariableNode is produced.
        """
        template = self.engine.from_string("{% if x %}{{ a }}{% endif %}")
        vars = template.nodelist.get_nodes_by_type(VariableNode)
        self.assertEqual(len(vars), 1)

    def test_ifchanged(self):
        """

        Tests the functionality of the ifchanged template tag.

        This test case verifies that the ifchanged tag behaves as expected by rendering
        a template with a variable inside the tag and checking if the correct number
        of variable nodes are generated.

        The ifchanged tag is used to check if a value has changed since the last iteration
        of a loop. In this test, the tag is used to render a template with a single variable.

        """
        template = self.engine.from_string("{% ifchanged x %}{{ a }}{% endifchanged %}")
        vars = template.nodelist.get_nodes_by_type(VariableNode)
        self.assertEqual(len(vars), 1)


class TextNodeTest(SimpleTestCase):
    def test_textnode_repr(self):
        """

        Tests the representation of TextNode objects.

        Verifies that the repr() function returns the expected string representation for TextNode objects, 
        containing the node type and its text content. The test covers simple text nodes with and without 
        newline characters, ensuring that special characters are properly escaped in the representation.

        """
        engine = Engine()
        for temptext, reprtext in [
            ("Hello, world!", "<TextNode: 'Hello, world!'>"),
            ("One\ntwo.", "<TextNode: 'One\\ntwo.'>"),
        ]:
            template = engine.from_string(temptext)
            texts = template.nodelist.get_nodes_by_type(TextNode)
            self.assertEqual(repr(texts[0]), reprtext)


class ErrorIndexTest(SimpleTestCase):
    """
    Checks whether index of error is calculated correctly in
    template debugger in for loops. Refs ticket #5831
    """

    def test_correct_exception_index(self):
        tests = [
            (
                "{% load bad_tag %}{% for i in range %}{% badsimpletag %}{% endfor %}",
                (38, 56),
            ),
            (
                "{% load bad_tag %}{% for i in range %}{% for j in range %}"
                "{% badsimpletag %}{% endfor %}{% endfor %}",
                (58, 76),
            ),
            (
                "{% load bad_tag %}{% for i in range %}{% badsimpletag %}"
                "{% for j in range %}Hello{% endfor %}{% endfor %}",
                (38, 56),
            ),
            (
                "{% load bad_tag %}{% for i in range %}{% for j in five %}"
                "{% badsimpletag %}{% endfor %}{% endfor %}",
                (38, 57),
            ),
            (
                "{% load bad_tag %}{% for j in five %}{% badsimpletag %}{% endfor %}",
                (18, 37),
            ),
        ]
        context = Context(
            {
                "range": range(5),
                "five": 5,
            }
        )
        engine = Engine(
            debug=True, libraries={"bad_tag": "template_tests.templatetags.bad_tag"}
        )
        for source, expected_error_source_index in tests:
            template = engine.from_string(source)
            try:
                template.render(context)
            except (RuntimeError, TypeError) as e:
                debug = e.template_debug
                self.assertEqual(
                    (debug["start"], debug["end"]), expected_error_source_index
                )
