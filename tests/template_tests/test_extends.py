import os

from django.template import Context, Engine, TemplateDoesNotExist
from django.test import SimpleTestCase

from .utils import ROOT

RECURSIVE = os.path.join(ROOT, "recursive_templates")


class ExtendsBehaviorTests(SimpleTestCase):
    def test_normal_extend(self):
        """
        Handles the rendering of a template named 'one.html' using the Engine from a specific directory, 
        verifies that the output is as expected after rendering with an empty context. 
        The test checks the successful extension of templates in normal scenarios.
        """
        engine = Engine(dirs=[os.path.join(RECURSIVE, "fs")])
        template = engine.get_template("one.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one")

    def test_extend_recursive(self):
        """
        Tests the recursive extension mechanism by rendering a template named 'recursive.html' 
        from multiple directories. The function verifies that the template is rendered correctly 
        by comparing the output with an expected string, ensuring that the recursive extension 
        works as intended and loads templates from all specified directories in the correct order.
        """
        engine = Engine(
            dirs=[
                os.path.join(RECURSIVE, "fs"),
                os.path.join(RECURSIVE, "fs2"),
                os.path.join(RECURSIVE, "fs3"),
            ]
        )
        template = engine.get_template("recursive.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "fs3/recursive fs2/recursive fs/recursive")

    def test_extend_missing(self):
        """
        Tests the extend functionality when a parent template is missing.

        This test case verifies that when a child template attempts to extend a parent 
        template that does not exist, the `TemplateDoesNotExist` exception is raised.
        The test checks the number of templates that are tried during the rendering 
        process and ensures that only the missing parent template is attempted to be 
        loaded, confirming the expected behavior of the template engine in handling 
        non-existent parent templates.
        """
        engine = Engine(dirs=[os.path.join(RECURSIVE, "fs")])
        template = engine.get_template("extend-missing.html")
        with self.assertRaises(TemplateDoesNotExist) as e:
            template.render(Context({}))

        tried = e.exception.tried
        self.assertEqual(len(tried), 1)
        self.assertEqual(tried[0][0].template_name, "missing.html")

    def test_recursive_multiple_loaders(self):
        engine = Engine(
            dirs=[os.path.join(RECURSIVE, "fs")],
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "one.html": (
                            '{% extends "one.html" %}{% block content %}'
                            "{{ block.super }} locmem-one{% endblock %}"
                        ),
                        "two.html": (
                            '{% extends "two.html" %}{% block content %}'
                            "{{ block.super }} locmem-two{% endblock %}"
                        ),
                        "three.html": (
                            '{% extends "three.html" %}{% block content %}'
                            "{{ block.super }} locmem-three{% endblock %}"
                        ),
                    },
                ),
                "django.template.loaders.filesystem.Loader",
            ],
        )
        template = engine.get_template("one.html")
        output = template.render(Context({}))
        self.assertEqual(
            output.strip(), "three locmem-three two locmem-two one locmem-one"
        )

    def test_extend_self_error(self):
        """
        Catch if a template extends itself and no other matching
        templates are found.
        """
        engine = Engine(dirs=[os.path.join(RECURSIVE, "fs")])
        template = engine.get_template("self.html")
        with self.assertRaises(TemplateDoesNotExist) as e:
            template.render(Context({}))
        tried = e.exception.tried
        self.assertEqual(len(tried), 1)
        origin, message = tried[0]
        self.assertEqual(origin.template_name, "self.html")
        self.assertEqual(message, "Skipped to avoid recursion")

    def test_extend_cached(self):
        """

        Tests the extension of the template cache when using the cached template loader.

        This test case verifies that the template cache is correctly extended when
        rendering templates from multiple directories. It checks that the cache is
        populated with the expected templates and that the origin of the templates is
        correctly set. The test also ensures that rendering multiple templates with the
        same content but different names does not result in duplicate cache entries.

        """
        engine = Engine(
            dirs=[
                os.path.join(RECURSIVE, "fs"),
                os.path.join(RECURSIVE, "fs2"),
                os.path.join(RECURSIVE, "fs3"),
            ],
            loaders=[
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                    ],
                ),
            ],
        )
        template = engine.get_template("recursive.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "fs3/recursive fs2/recursive fs/recursive")

        cache = engine.template_loaders[0].get_template_cache
        self.assertEqual(len(cache), 3)
        expected_path = os.path.join("fs", "recursive.html")
        self.assertTrue(cache["recursive.html"].origin.name.endswith(expected_path))

        # Render another path that uses the same templates from the cache
        template = engine.get_template("other-recursive.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "fs3/recursive fs2/recursive fs/recursive")

        # Template objects should not be duplicated.
        self.assertEqual(len(cache), 4)
        expected_path = os.path.join("fs", "other-recursive.html")
        self.assertTrue(
            cache["other-recursive.html"].origin.name.endswith(expected_path)
        )

    def test_unique_history_per_loader(self):
        """
        Extending should continue even if two loaders return the same
        name for a template.
        """
        engine = Engine(
            loaders=[
                [
                    "django.template.loaders.locmem.Loader",
                    {
                        "base.html": (
                            '{% extends "base.html" %}{% block content %}'
                            "{{ block.super }} loader1{% endblock %}"
                        ),
                    },
                ],
                [
                    "django.template.loaders.locmem.Loader",
                    {
                        "base.html": "{% block content %}loader2{% endblock %}",
                    },
                ],
            ]
        )
        template = engine.get_template("base.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "loader2 loader1")

    def test_block_override_in_extended_included_template(self):
        """
        ExtendsNode.find_template() initializes history with self.origin
        (#28071).
        """
        engine = Engine(
            loaders=[
                [
                    "django.template.loaders.locmem.Loader",
                    {
                        "base.html": (
                            "{% extends 'base.html' %}{% block base %}{{ block.super }}"
                            "2{% endblock %}"
                        ),
                        "included.html": (
                            "{% extends 'included.html' %}{% block included %}"
                            "{{ block.super }}B{% endblock %}"
                        ),
                    },
                ],
                [
                    "django.template.loaders.locmem.Loader",
                    {
                        "base.html": (
                            "{% block base %}1{% endblock %}"
                            "{% include 'included.html' %}"
                        ),
                        "included.html": "{% block included %}A{% endblock %}",
                    },
                ],
            ],
        )
        template = engine.get_template("base.html")
        self.assertEqual(template.render(Context({})), "12AB")
