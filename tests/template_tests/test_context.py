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

        Tests the functionality of the Context object.

        Verifies that the Context object can store, retrieve, and update values.
        It also checks that the push and pop operations work as expected,
        preserving the original context after changes are made.

        The test covers the following scenarios:
        - Retrieving values by key
        - Updating values
        - Getting values with a default if the key is not present
        - Pushing and popping changes to the context

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

        Update Context Manager Test

        Tests the update context manager functionality of the Context class.
        Verifies that changes made within the update block are reverted upon exit,
        and that new values passed to the update block are applied correctly.
        Ensures the original context remains unchanged after the update block is exited.

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
        Tests the push context manager to ensure it correctly updates and reverts the context object.

        The push context manager is used to temporarily modify a context object by pushing a new set of values onto it. 
        After the context manager goes out of scope, the original values are restored. 

        This test verifies that the context object is updated with the new values while the context manager is active, 
        and that the original values are restored when the manager is exited. 
        """
        c = Context({"a": 1})
        with c.push(Context({"a": 3})):
            self.assertEqual(c["a"], 3)
        self.assertEqual(c["a"], 1)

    def test_update_context_manager_with_context_object(self):
        """

        Tests the Context manager's update functionality with a context object.

        Verifies that the context manager correctly updates its internal state 
        when used with a nested context object and that the changes are reverted 
        after exiting the 'with' block, ensuring the original state is restored.

        This test case ensures that the Context class behaves as expected when 
        used with the 'update' method and a 'with' statement, providing a safe 
        and controlled way to modify the context without affecting its original state.

        """
        c = Context({"a": 1})
        with c.update(Context({"a": 3})):
            self.assertEqual(c["a"], 3)
        self.assertEqual(c["a"], 1)

    def test_push_proper_layering(self):
        """
        Tests the layering functionality of the Context class by pushing multiple layers onto a base context and verifying that the resulting layered structure is correct. 

        The test case creates a base context with a single key-value pair, then pushes two additional layers onto it, each with their own key-value pairs. It then checks that the final layered structure matches the expected arrangement, ensuring that the base context and the pushed layers are correctly stacked. This test ensures that the Context class properly handles the layering of contexts, allowing for the creation of nested and hierarchical structures.
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

        Sets or retrieves a value from the context, returning the existing value if it exists.

        This method inserts the specified value into the context if the key does not exist.
        If the key already exists, it returns the existing value without modifying it.

        :param key: the key to be set or retrieved
        :param default: the value to be set if the key does not exist in the context
        :return: the value associated with the key

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
        #17778 -- Variable shouldn't resolve RequestContext methods
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

        Tests the functionality of rendering context by verifying the behavior of pushing a new context.

        The test checks that after pushing a new context, the original context values are no longer accessible,
        and any new values added are correctly stored in the new context. It also verifies that attempting to
        access a non-existent key in the new context raises a KeyError, while using the get method returns None.

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
        .. method:: test_flatten_context

            Tests the ability of the Context class to flatten its contents into a single dictionary.

            Verifies that the flattened dictionary contains all default boolean and nil values, 
            along with any key-value pairs added to the Context instance.
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
        Context.push() with a Context argument should work.
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

        Tests the behavior of flattening a context with a copied context.

        Verifies that when a new context is created from an existing one, the resulting 
        context's dictionaries are correctly combined and that the flattened context 
        contains all the expected key-value pairs. This ensures that context 
        manipulations do not lose or corrupt data.

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
        #21765 -- equality comparison should work
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
        #24273 -- Copy twice shouldn't raise an exception
        """
        RequestContext(HttpRequest()).new().new()

    def test_set_upward(self):
        c = Context({"a": 1})
        c.set_upward("a", 2)
        self.assertEqual(c.get("a"), 2)

    def test_set_upward_empty_context(self):
        """

        Tests setting an upward value in an empty context.

        Verifies that the :meth:`set_upward` method correctly stores a value 
        in the context and that the :meth:`get` method retrieves the 
        correct value.

        Checks that the initial state of the context does not affect the 
        outcome, ensuring that the context can be populated with values 
        from the start.

        """
        empty_context = Context()
        empty_context.set_upward("a", 1)
        self.assertEqual(empty_context.get("a"), 1)

    def test_set_upward_with_push(self):
        """
        The highest context which has the given key is used.
        """
        c = Context({"a": 1})
        c.push({"a": 2})
        c.set_upward("a", 3)
        self.assertEqual(c.get("a"), 3)
        c.pop()
        self.assertEqual(c.get("a"), 1)

    def test_set_upward_with_push_no_match(self):
        """
        The highest context is used if the given key isn't found.
        """
        c = Context({"b": 1})
        c.push({"b": 2})
        c.set_upward("a", 2)
        self.assertEqual(len(c.dicts), 3)
        self.assertEqual(c.dicts[-1]["a"], 2)


def context_process_returning_none(request):
    return None


class RequestContextTests(SimpleTestCase):
    request_factory = RequestFactory()

    def test_include_only(self):
        """
        #15721 -- ``{% include %}`` and ``RequestContext`` should work
        together.
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
        """Optimized RequestContext construction (#7116)."""
        request = self.request_factory.get("/")
        ctx = RequestContext(request, {})
        # The stack contains 4 items:
        # [builtins, supplied context, context processor, empty dict]
        self.assertEqual(len(ctx.dicts), 4)

    def test_context_comparable(self):
        # Create an engine without any context processors.
        test_data = {"x": "y", "v": "z", "d": {"o": object, "a": "b"}}

        # test comparing RequestContext to prevent problems if somebody
        # adds __eq__ in the future
        request = self.request_factory.get("/")

        self.assertEqual(
            RequestContext(request, dict_=test_data),
            RequestContext(request, dict_=test_data),
        )

    def test_modify_context_and_render(self):
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
        Tests a template context processor that returns None to ensure it raises a TypeError.

        Checks that when a context processor returns None, a TypeError is raised with a message 
        indicating that the context processor did not return a dictionary, as expected by the 
        template engine.

        This test validates the proper handling of invalid return types from context processors,
        ensuring the correct failure mode and diagnostic message are provided to the developer.
        """
        request_context = RequestContext(HttpRequest())
        msg = (
            "Context processor context_process_returning_none didn't return a "
            "dictionary."
        )
        with self.assertRaisesMessage(TypeError, msg):
            with request_context.bind_template(Template("")):
                pass
