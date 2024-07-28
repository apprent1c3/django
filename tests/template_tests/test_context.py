from unittest import mock

from django.http import HttpRequest
from django.template import (
    Context,
    Engine,
    RequestContext,
    Template,
    Variable,
    VariableDoesNotExist,
)
from django.template.context import RenderContext
from django.test import RequestFactory, SimpleTestCase, override_settings


class ContextTests(SimpleTestCase):
    def test_context(self):
        """
        This is a comment
        """
        c = Context({"a": 1, "b": "xyzzy"})
        self.assertEqual(c["a"], 1)
        self.assertEqual(c.push(), {})
        c["a"] = 2
        self.assertEqual(c["a"], 2)
        self.assertEqual(c.get("a"), 2)
        self.assertEqual(c.pop(), {"a": 2})
        self.assertEqual(c["a"], 1)
        self.assertEqual(c.get("foo", 42), 42)
        self.assertEqual(c, mock.ANY)

    def test_push_context_manager(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        with c.push():
            c["a"] = 2
            self.assertEqual(c["a"], 2)
        self.assertEqual(c["a"], 1)

        with c.push(a=3):
            self.assertEqual(c["a"], 3)
        self.assertEqual(c["a"], 1)

    def test_update_context_manager(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        with c.update({}):
            c["a"] = 2
            self.assertEqual(c["a"], 2)
        self.assertEqual(c["a"], 1)

        with c.update({"a": 3}):
            self.assertEqual(c["a"], 3)
        self.assertEqual(c["a"], 1)

    def test_push_context_manager_with_context_object(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        with c.push(Context({"a": 3})):
            self.assertEqual(c["a"], 3)
        self.assertEqual(c["a"], 1)

    def test_update_context_manager_with_context_object(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        with c.update(Context({"a": 3})):
            self.assertEqual(c["a"], 3)
        self.assertEqual(c["a"], 1)

    def test_push_proper_layering(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        c.push(Context({"b": 2}))
        c.push(Context({"c": 3, "d": {"z": "26"}}))
        self.assertEqual(
            c.dicts,
            [
                {"False": False, "None": None, "True": True},
                {"a": 1},
                {"b": 2},
                {"c": 3, "d": {"z": "26"}},
            ],
        )

    def test_update_proper_layering(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        c.update(Context({"b": 2}))
        c.update(Context({"c": 3, "d": {"z": "26"}}))
        self.assertEqual(
            c.dicts,
            [
                {"False": False, "None": None, "True": True},
                {"a": 1},
                {"b": 2},
                {"c": 3, "d": {"z": "26"}},
            ],
        )

    def test_setdefault(self):
        """
        This is a comment
        """
        c = Context()

        x = c.setdefault("x", 42)
        self.assertEqual(x, 42)
        self.assertEqual(c["x"], 42)

        x = c.setdefault("x", 100)
        self.assertEqual(x, 42)
        self.assertEqual(c["x"], 42)

    def test_resolve_on_context_method(self):
        """
        This is a comment
        """
        empty_context = Context()

        with self.assertRaises(VariableDoesNotExist):
            Variable("no_such_variable").resolve(empty_context)

        with self.assertRaises(VariableDoesNotExist):
            Variable("new").resolve(empty_context)

        self.assertEqual(
            Variable("new").resolve(Context({"new": "foo"})),
            "foo",
        )

    def test_render_context(self):
        """
        This is a comment
        """
        test_context = RenderContext({"fruit": "papaya"})

        # push() limits access to the topmost dict
        test_context.push()

        test_context["vegetable"] = "artichoke"
        self.assertEqual(list(test_context), ["vegetable"])

        self.assertNotIn("fruit", test_context)
        with self.assertRaises(KeyError):
            test_context["fruit"]
        self.assertIsNone(test_context.get("fruit"))

    def test_flatten_context(self):
        """
        This is a comment
        """
        a = Context()
        a.update({"a": 2})
        a.update({"b": 4})
        a.update({"c": 8})

        self.assertEqual(
            a.flatten(),
            {"False": False, "None": None, "True": True, "a": 2, "b": 4, "c": 8},
        )

    def test_flatten_context_with_context(self):
        """
        This is a comment
        """
        a = Context({"a": 2})
        a.push(Context({"z": "8"}))
        self.assertEqual(
            a.flatten(),
            {
                "False": False,
                "None": None,
                "True": True,
                "a": 2,
                "z": "8",
            },
        )

    def test_flatten_context_with_context_copy(self):
        """
        This is a comment
        """
        ctx1 = Context({"a": 2})
        ctx2 = ctx1.new(Context({"b": 4}))
        self.assertEqual(
            ctx2.dicts, [{"True": True, "False": False, "None": None}, {"b": 4}]
        )
        self.assertEqual(
            ctx2.flatten(),
            {"False": False, "None": None, "True": True, "b": 4},
        )

    def test_context_comparable(self):
        """
        This is a comment
        """

        test_data = {"x": "y", "v": "z", "d": {"o": object, "a": "b"}}

        self.assertEqual(Context(test_data), Context(test_data))

        a = Context()
        b = Context()
        self.assertEqual(a, b)

        # update only a
        a.update({"a": 1})
        self.assertNotEqual(a, b)

        # update both to check regression
        a.update({"c": 3})
        b.update({"c": 3})
        self.assertNotEqual(a, b)

        # make contexts equals again
        b.update({"a": 1})
        self.assertEqual(a, b)

    def test_copy_request_context_twice(self):
        """
        This is a comment
        """
        RequestContext(HttpRequest()).new().new()

    def test_set_upward(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        c.set_upward("a", 2)
        self.assertEqual(c.get("a"), 2)

    def test_set_upward_empty_context(self):
        """
        This is a comment
        """
        empty_context = Context()
        empty_context.set_upward("a", 1)
        self.assertEqual(empty_context.get("a"), 1)

    def test_set_upward_with_push(self):
        """
        This is a comment
        """
        c = Context({"a": 1})
        c.push({"a": 2})
        c.set_upward("a", 3)
        self.assertEqual(c.get("a"), 3)
        c.pop()
        self.assertEqual(c.get("a"), 1)

    def test_set_upward_with_push_no_match(self):
        """
        This is a comment
        """
        c = Context({"b": 1})
        c.push({"b": 2})
        c.set_upward("a", 2)
        self.assertEqual(len(c.dicts), 3)
        self.assertEqual(c.dicts[-1]["a"], 2)


def context_process_returning_none(request):
    """
    This is a comment
    """
    return None


class RequestContextTests(SimpleTestCase):
    request_factory = RequestFactory()

    def test_include_only(self):
        """
        This is a comment
        """
        engine = Engine(
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "child": '{{ var|default:"none" }}',
                    },
                ),
            ]
        )
        request = self.request_factory.get("/")
        ctx = RequestContext(request, {"var": "parent"})
        self.assertEqual(
            engine.from_string('{% include "child" %}').render(ctx), "parent"
        )
        self.assertEqual(
            engine.from_string('{% include "child" only %}').render(ctx), "none"
        )

    def test_stack_size(self):
        """
        This is a comment
        """
        request = self.request_factory.get("/")
        ctx = RequestContext(request, {})
        # The stack contains 4 items:
        # [builtins, supplied context, context processor, empty dict]
        self.assertEqual(len(ctx.dicts), 4)

    def test_context_comparable(self):
        # Create an engine without any context processors.
        """
        This is a comment
        """
        test_data = {"x": "y", "v": "z", "d": {"o": object, "a": "b"}}

        # test comparing RequestContext to prevent problems if somebody
        # adds __eq__ in the future
        request = self.request_factory.get("/")

        self.assertEqual(
            RequestContext(request, dict_=test_data),
            RequestContext(request, dict_=test_data),
        )

    def test_modify_context_and_render(self):
        """
        This is a comment
        """
        template = Template("{{ foo }}")
        request = self.request_factory.get("/")
        context = RequestContext(request, {})
        context["foo"] = "foo"
        self.assertEqual(template.render(context), "foo")

    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "template_tests.test_context.context_process_returning_none",
                    ],
                },
            }
        ],
    )
    def test_template_context_processor_returning_none(self):
        """
        This is a comment
        """
        request_context = RequestContext(HttpRequest())
        msg = (
            "Context processor context_process_returning_none didn't return a "
            "dictionary."
        )
        with self.assertRaisesMessage(TypeError, msg):
            with request_context.bind_template(Template("")):
                pass
