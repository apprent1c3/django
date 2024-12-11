from unittest import TestCase

from django.db.models.utils import AltersData
from django.template import Context, Engine


class CallableVariablesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Set up the class by initializing the engine and calling the superclass's setup method.

        This method is a class method that is automatically called before the first test method is executed.
        It is responsible for setting up the necessary dependencies and resources for the class, including
        the engine, which is an instance of the Engine class.

        """
        cls.engine = Engine()
        super().setUpClass()

    def test_callable(self):
        """

        Tests that a callable object is invoked correctly when used in a template.

        This test checks that an object with a __call__ method is called when its
        attributes are accessed in a template, and that the return value of the
        callable is used as the attribute value.

        It verifies that the callable is invoked the correct number of times and
        that the rendered output is as expected.

        """
        class Doodad:
            def __init__(self, value):
                """
                Initializes an instance of the class with a specified value.

                :param value: The initial value to store in the instance.
                :returns: None
                :description: This constructor sets up the basic state of the object, including the value provided and a counter for the number of calls, which is initialized to zero.
                """
                self.num_calls = 0
                self.value = value

            def __call__(self):
                """
                Invoke the object as a callable, incrementing the internal call counter and returning a dictionary containing the object's value.

                Returns:
                    dict: A dictionary with a single key 'the_value' representing the object's current value.

                Note:
                    Each call increments the internal counter, accessible via the num_calls attribute.

                """
                self.num_calls += 1
                return {"the_value": self.value}

        my_doodad = Doodad(42)
        c = Context({"my_doodad": my_doodad})

        # We can't access ``my_doodad.value`` in the template, because
        # ``my_doodad.__call__`` will be invoked first, yielding a dictionary
        # without a key ``value``.
        t = self.engine.from_string("{{ my_doodad.value }}")
        self.assertEqual(t.render(c), "")

        # We can confirm that the doodad has been called
        self.assertEqual(my_doodad.num_calls, 1)

        # But we can access keys on the dict that's returned
        # by ``__call__``, instead.
        t = self.engine.from_string("{{ my_doodad.the_value }}")
        self.assertEqual(t.render(c), "42")
        self.assertEqual(my_doodad.num_calls, 2)

    def test_alters_data(self):
        """
        Tests that calling an object that alters data does not execute the 
        object when accessing its attributes or properties. This ensures that 
        objects with side effects are not unexpectedly executed during template 
        rendering. The test verifies that the object's call counter remains 
        unchanged after rendering the template, indicating that the object was 
        not invoked during attribute access.
        """
        class Doodad:
            alters_data = True

            def __init__(self, value):
                """
                Initializes a new instance with the given value.

                Parameters
                ----------
                value : any
                    The value to be stored in the instance.

                Notes
                -----
                This constructor also initializes a counter for the number of calls made,
                starting at 0. The stored value and call count can be accessed through
                the instance's attributes.

                """
                self.num_calls = 0
                self.value = value

            def __call__(self):
                self.num_calls += 1
                return {"the_value": self.value}

        my_doodad = Doodad(42)
        c = Context({"my_doodad": my_doodad})

        # Since ``my_doodad.alters_data`` is True, the template system will not
        # try to call our doodad but will use string_if_invalid
        t = self.engine.from_string("{{ my_doodad.value }}")
        self.assertEqual(t.render(c), "")
        t = self.engine.from_string("{{ my_doodad.the_value }}")
        self.assertEqual(t.render(c), "")

        # Double-check that the object was really never called during the
        # template rendering.
        self.assertEqual(my_doodad.num_calls, 0)

    def test_alters_data_propagation(self):
        """
        Tests the propagation of `alters_data` attribute across multiple levels of inheritance in a class hierarchy.

        The function verifies that the `alters_data` attribute is correctly inherited and updated in child classes, 
        and that this inheritance affects the rendering of template variables in a templating engine.

        Specifically, it checks that:

        * The `alters_data` attribute is inherited from parent classes and can be overridden in child classes.
        * The attribute is propagated correctly through multiple levels of inheritance.
        * The templating engine renders variables differently based on the value of the `alters_data` attribute.

        """
        class GrandParentLeft(AltersData):
            def my_method(self):
                return 42

            my_method.alters_data = True

        class ParentLeft(GrandParentLeft):
            def change_alters_data_method(self):
                return 63

            change_alters_data_method.alters_data = True

            def sub_non_callable_method(self):
                return 64

            sub_non_callable_method.alters_data = True

        class ParentRight(AltersData):
            def other_method(self):
                return 52

            other_method.alters_data = True

        class Child(ParentLeft, ParentRight):
            def my_method(self):
                return 101

            def other_method(self):
                return 102

            def change_alters_data_method(self):
                return 103

            change_alters_data_method.alters_data = False

            sub_non_callable_method = 104

        class GrandChild(Child):
            pass

        child = Child()
        self.assertIs(child.my_method.alters_data, True)
        self.assertIs(child.other_method.alters_data, True)
        self.assertIs(child.change_alters_data_method.alters_data, False)

        grand_child = GrandChild()
        self.assertIs(grand_child.my_method.alters_data, True)
        self.assertIs(grand_child.other_method.alters_data, True)
        self.assertIs(grand_child.change_alters_data_method.alters_data, False)

        c = Context({"element": grand_child})

        t = self.engine.from_string("{{ element.my_method }}")
        self.assertEqual(t.render(c), "")
        t = self.engine.from_string("{{ element.other_method }}")
        self.assertEqual(t.render(c), "")
        t = self.engine.from_string("{{ element.change_alters_data_method }}")
        self.assertEqual(t.render(c), "103")
        t = self.engine.from_string("{{ element.sub_non_callable_method }}")
        self.assertEqual(t.render(c), "104")

    def test_do_not_call(self):
        """
        Tests that functions or callables marked with the `do_not_call_in_templates` attribute are not invoked when referenced in a template. 

         Verifies that the attribute correctly prevents the function from being called when attempting to access its return value in a template, while still allowing direct access to the object's attributes. 

         This ensures that templates cannot execute arbitrary code by calling functions that should not be executed in a template context.
        """
        class Doodad:
            do_not_call_in_templates = True

            def __init__(self, value):
                """
                Initializes an instance with a given value and tracks the number of times it is called.

                :param value: The initial value of the instance.
                :ivar num_calls: The number of times the instance has been called.
                :ivar value: The current value of the instance.
                """
                self.num_calls = 0
                self.value = value

            def __call__(self):
                """
                Invoke the object as a function, incrementing the internal call counter and returning a dictionary containing the object's value.

                Returns:
                    dict: A dictionary with a single key 'the_value' mapping to the object's value.

                """
                self.num_calls += 1
                return {"the_value": self.value}

        my_doodad = Doodad(42)
        c = Context({"my_doodad": my_doodad})

        # Since ``my_doodad.do_not_call_in_templates`` is True, the template
        # system will not try to call our doodad.  We can access its attributes
        # as normal, and we don't have access to the dict that it returns when
        # called.
        t = self.engine.from_string("{{ my_doodad.value }}")
        self.assertEqual(t.render(c), "42")
        t = self.engine.from_string("{{ my_doodad.the_value }}")
        self.assertEqual(t.render(c), "")

        # Double-check that the object was really never called during the
        # template rendering.
        self.assertEqual(my_doodad.num_calls, 0)

    def test_do_not_call_and_alters_data(self):
        # If we combine ``alters_data`` and ``do_not_call_in_templates``, the
        # ``alters_data`` attribute will not make any difference in the
        # template system's behavior.

        """
        Tests that an object with do_not_call_in_templates and alters_data set to True
        is not called when accessed as an attribute in a template, and its attributes are
        accessible. The object's __call__ method is not invoked, even when a template 
        attempts to access attributes that are only available through the __call__ method,
        and instead the attributes are resolved directly from the object itself if available.
        Ensures that the object's internal state, such as the call count, remains unchanged.
        """
        class Doodad:
            do_not_call_in_templates = True
            alters_data = True

            def __init__(self, value):
                self.num_calls = 0
                self.value = value

            def __call__(self):
                self.num_calls += 1
                return {"the_value": self.value}

        my_doodad = Doodad(42)
        c = Context({"my_doodad": my_doodad})

        t = self.engine.from_string("{{ my_doodad.value }}")
        self.assertEqual(t.render(c), "42")
        t = self.engine.from_string("{{ my_doodad.the_value }}")
        self.assertEqual(t.render(c), "")

        # Double-check that the object was really never called during the
        # template rendering.
        self.assertEqual(my_doodad.num_calls, 0)
