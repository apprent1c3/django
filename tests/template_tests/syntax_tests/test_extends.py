from django.template import NodeList, TemplateSyntaxError
from django.template.base import Node
from django.template.loader_tags import ExtendsNode
from django.test import SimpleTestCase

from ..utils import setup

inheritance_templates = {
    "inheritance01": (
        "1{% block first %}&{% endblock %}3{% block second %}_{% endblock %}"
    ),
    "inheritance02": "{% extends 'inheritance01' %}"
    "{% block first %}2{% endblock %}{% block second %}4{% endblock %}",
    "inheritance03": "{% extends 'inheritance02' %}",
    "inheritance04": "{% extends 'inheritance01' %}",
    "inheritance05": "{% extends 'inheritance02' %}",
    "inheritance06": "{% extends foo %}",
    "inheritance07": "{% extends 'inheritance01' %}{% block second %}5{% endblock %}",
    "inheritance08": "{% extends 'inheritance02' %}{% block second %}5{% endblock %}",
    "inheritance09": "{% extends 'inheritance04' %}",
    "inheritance10": "{% extends 'inheritance04' %}      ",
    "inheritance11": "{% extends 'inheritance04' %}"
    "{% block first %}2{% endblock %}{% block second %}4{% endblock %}",
    "inheritance12": "{% extends 'inheritance07' %}{% block first %}2{% endblock %}",
    "inheritance13": "{% extends 'inheritance02' %}"
    "{% block first %}a{% endblock %}{% block second %}b{% endblock %}",
    "inheritance14": (
        "{% extends 'inheritance01' %}{% block newblock %}NO DISPLAY{% endblock %}"
    ),
    "inheritance15": "{% extends 'inheritance01' %}"
    "{% block first %}2{% block inner %}inner{% endblock %}{% endblock %}",
    "inheritance16": "{% extends 'inheritance15' %}{% block inner %}out{% endblock %}",
    "inheritance17": "{% load testtags %}{% block first %}1234{% endblock %}",
    "inheritance18": "{% load testtags %}{% echo this that theother %}5678",
    "inheritance19": "{% extends 'inheritance01' %}"
    "{% block first %}{% load testtags %}{% echo 400 %}5678{% endblock %}",
    "inheritance20": (
        "{% extends 'inheritance01' %}{% block first %}{{ block.super }}a{% endblock %}"
    ),
    "inheritance21": (
        "{% extends 'inheritance02' %}{% block first %}{{ block.super }}a{% endblock %}"
    ),
    "inheritance22": (
        "{% extends 'inheritance04' %}{% block first %}{{ block.super }}a{% endblock %}"
    ),
    "inheritance23": (
        "{% extends 'inheritance20' %}{% block first %}{{ block.super }}b{% endblock %}"
    ),
    "inheritance24": "{% extends context_template %}"
    "{% block first %}2{% endblock %}{% block second %}4{% endblock %}",
    "inheritance25": "{% extends context_template.1 %}"
    "{% block first %}2{% endblock %}{% block second %}4{% endblock %}",
    "inheritance26": "no tags",
    "inheritance27": "{% extends 'inheritance26' %}",
    "inheritance 28": "{% block first %}!{% endblock %}",
    "inheritance29": "{% extends 'inheritance 28' %}",
    "inheritance30": "1{% if optional %}{% block opt %}2{% endblock %}{% endif %}3",
    "inheritance31": "{% extends 'inheritance30' %}{% block opt %}two{% endblock %}",
    "inheritance32": "{% extends 'inheritance30' %}{% block opt %}two{% endblock %}",
    "inheritance33": (
        "1{% if optional == 1 %}{% block opt %}2{% endblock %}{% endif %}3"
    ),
    "inheritance34": "{% extends 'inheritance33' %}{% block opt %}two{% endblock %}",
    "inheritance35": "{% extends 'inheritance33' %}{% block opt %}two{% endblock %}",
    "inheritance36": (
        "{% for n in numbers %}_{% block opt %}{{ n }}{% endblock %}{% endfor %}_"
    ),
    "inheritance37": "{% extends 'inheritance36' %}{% block opt %}X{% endblock %}",
    "inheritance38": "{% extends 'inheritance36' %}{% block opt %}X{% endblock %}",
    "inheritance39": (
        "{% extends 'inheritance30' %}{% block opt %}new{{ block.super }}{% endblock %}"
    ),
    "inheritance40": (
        "{% extends 'inheritance33' %}{% block opt %}new{{ block.super }}{% endblock %}"
    ),
    "inheritance41": (
        "{% extends 'inheritance36' %}{% block opt %}new{{ block.super }}{% endblock %}"
    ),
    "inheritance42": "{% extends 'inheritance02'|cut:' ' %}",
    "inheritance_empty": "{% extends %}",
    "extends_duplicate": "{% extends 'base.html' %}{% extends 'base.html' %}",
    "duplicate_block": (
        "{% extends 'base.html' %}{% block content %}2{% endblock %}{% block content %}"
        "4{% endblock %}"
    ),
}


class InheritanceTests(SimpleTestCase):
    libraries = {"testtags": "template_tests.templatetags.testtags"}

    @setup(inheritance_templates)
    def test_inheritance01(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance01")
        self.assertEqual(output, "1&3_")

    @setup(inheritance_templates)
    def test_inheritance02(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance02")
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance03(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance03")
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance04(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance04")
        self.assertEqual(output, "1&3_")

    @setup(inheritance_templates)
    def test_inheritance05(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance05")
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance06(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance06", {"foo": "inheritance02"})
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance07(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance07")
        self.assertEqual(output, "1&35")

    @setup(inheritance_templates)
    def test_inheritance08(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance08")
        self.assertEqual(output, "1235")

    @setup(inheritance_templates)
    def test_inheritance09(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance09")
        self.assertEqual(output, "1&3_")

    @setup(inheritance_templates)
    def test_inheritance10(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance10")
        self.assertEqual(output, "1&3_")

    @setup(inheritance_templates)
    def test_inheritance11(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance11")
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance12(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance12")
        self.assertEqual(output, "1235")

    @setup(inheritance_templates)
    def test_inheritance13(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance13")
        self.assertEqual(output, "1a3b")

    @setup(inheritance_templates)
    def test_inheritance14(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance14")
        self.assertEqual(output, "1&3_")

    @setup(inheritance_templates)
    def test_inheritance15(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance15")
        self.assertEqual(output, "12inner3_")

    @setup(inheritance_templates)
    def test_inheritance16(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance16")
        self.assertEqual(output, "12out3_")

    @setup(inheritance_templates)
    def test_inheritance17(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance17")
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance18(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance18")
        self.assertEqual(output, "this that theother5678")

    @setup(inheritance_templates)
    def test_inheritance19(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance19")
        self.assertEqual(output, "140056783_")

    @setup(inheritance_templates)
    def test_inheritance20(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance20")
        self.assertEqual(output, "1&a3_")

    @setup(inheritance_templates)
    def test_inheritance21(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance21")
        self.assertEqual(output, "12a34")

    @setup(inheritance_templates)
    def test_inheritance22(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance22")
        self.assertEqual(output, "1&a3_")

    @setup(inheritance_templates)
    def test_inheritance23(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance23")
        self.assertEqual(output, "1&ab3_")

    @setup(inheritance_templates)
    def test_inheritance24(self):
        """
        This is a comment
        """
        context_template = self.engine.from_string(
            "1{% block first %}_{% endblock %}3{% block second %}_{% endblock %}"
        )
        output = self.engine.render_to_string(
            "inheritance24", {"context_template": context_template}
        )
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance25(self):
        """
        This is a comment
        """
        context_template = [
            self.engine.from_string("Wrong"),
            self.engine.from_string(
                "1{% block first %}_{% endblock %}3{% block second %}_{% endblock %}"
            ),
        ]
        output = self.engine.render_to_string(
            "inheritance25", {"context_template": context_template}
        )
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance26(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance26")
        self.assertEqual(output, "no tags")

    @setup(inheritance_templates)
    def test_inheritance27(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance27")
        self.assertEqual(output, "no tags")

    @setup(inheritance_templates)
    def test_inheritance_28(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance 28")
        self.assertEqual(output, "!")

    @setup(inheritance_templates)
    def test_inheritance29(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance29")
        self.assertEqual(output, "!")

    @setup(inheritance_templates)
    def test_inheritance30(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance30", {"optional": True})
        self.assertEqual(output, "123")

    # Inherit from a template with block wrapped in an {% if %} tag
    # (in parent), still gets overridden
    @setup(inheritance_templates)
    def test_inheritance31(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance31", {"optional": True})
        self.assertEqual(output, "1two3")

    @setup(inheritance_templates)
    def test_inheritance32(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance32")
        self.assertEqual(output, "13")

    @setup(inheritance_templates)
    def test_inheritance33(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance33", {"optional": 1})
        self.assertEqual(output, "123")

    @setup(inheritance_templates)
    def test_inheritance34(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance34", {"optional": 1})
        self.assertEqual(output, "1two3")

    @setup(inheritance_templates)
    def test_inheritance35(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance35", {"optional": 2})
        self.assertEqual(output, "13")

    @setup(inheritance_templates)
    def test_inheritance36(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance36", {"numbers": "123"})
        self.assertEqual(output, "_1_2_3_")

    @setup(inheritance_templates)
    def test_inheritance37(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance37", {"numbers": "123"})
        self.assertEqual(output, "_X_X_X_")

    @setup(inheritance_templates)
    def test_inheritance38(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance38")
        self.assertEqual(output, "_")

    # The super block will still be found.
    @setup(inheritance_templates)
    def test_inheritance39(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance39", {"optional": True})
        self.assertEqual(output, "1new23")

    @setup(inheritance_templates)
    def test_inheritance40(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance40", {"optional": 1})
        self.assertEqual(output, "1new23")

    @setup(inheritance_templates)
    def test_inheritance41(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance41", {"numbers": "123"})
        self.assertEqual(output, "_new1_new2_new3_")

    @setup(inheritance_templates)
    def test_inheritance42(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("inheritance42")
        self.assertEqual(output, "1234")

    @setup(inheritance_templates)
    def test_inheritance_empty(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "'extends' takes one argument"
        ):
            self.engine.render_to_string("inheritance_empty")

    @setup(inheritance_templates)
    def test_extends_duplicate(self):
        """
        This is a comment
        """
        msg = "'extends' cannot appear more than once in the same template"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("extends_duplicate")

    @setup(inheritance_templates)
    def test_duplicate_block(self):
        """
        This is a comment
        """
        msg = "'block' tag with name 'content' appears more than once"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("duplicate_block")


class ExtendsNodeTests(SimpleTestCase):
    def test_extends_node_repr(self):
        """
        This is a comment
        """
        extends_node = ExtendsNode(
            nodelist=NodeList([]),
            parent_name=Node(),
            template_dirs=[],
        )
        self.assertEqual(repr(extends_node), "<ExtendsNode: extends None>")
