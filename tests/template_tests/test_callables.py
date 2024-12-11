from unittest import TestCase

from django.db.models.utils import AltersData
from django.template import Context, Engine


class CallableVariablesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine()
        super().setUpClass()

    def test_callable(self):
        class Doodad:
            def __init__(self, value):
                self.num_calls = 0
                self.value = value

            def __call__(self):
                """
                Invoke the instance and return its value.

                Returns a dictionary containing the current value of the instance, 
                incrementing a counter to track the number of calls made.

                :return: A dictionary with a single key 'the_value' mapping to the instance's value.
                :rtype: dict
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

        Test that the templating engine does not call objects when accessing attributes, 
        unless the object has explicitly declared it alters data.

        Checks that a custom object with a method invocation (e.g., a callable) is not 
        invoked when referenced in a template, resulting in no side effects or state 
        changes if the object's attributes are accessed directly in the template.

        """
        class Doodad:
            alters_data = True

            def __init__(self, value):
                """
                Initialize an instance with a given value.

                The initializer sets up the object with the provided value and tracks the number of times it is called.
                It sets the initial number of calls to zero and stores the given value for later use.

                :param value: The value to be stored in the instance

                """
                self.num_calls = 0
                self.value = value

            def __call__(self):
                """
                Invoke the instance as a callable, incrementing the internal counter and returning a dictionary with a single key-value pair.

                Returns:
                    dict: A dictionary containing 'the_value' key with the instance's value.

                Notes:
                    The number of times this instance has been called is tracked internally and incremented each time this method is invoked.
                """
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

        Tests the behavior of the templating engine when a callable object is marked 
        with the do_not_call_in_templates attribute.

        This test case verifies that when an object has this attribute set to True, 
        the templating engine will not call the object, even if it is referenced in a 
        template. Instead, it will only access the object's attributes directly.

        """
        class Doodad:
            do_not_call_in_templates = True

            def __init__(self, value):
                self.num_calls = 0
                self.value = value

            def __call__(self):
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
        Tests the behavior of the templating engine when a object has the 
        do_not_call_in_templates and alters_data flags set to True.

        Verifies that the templating engine does not call the object when 
        its attribute is accessed in a template, and that trying to access 
        the result of the object's call in a template results in an empty 
        string. Also checks that the object's call count remains zero after 
        rendering the template. 

        This test ensures that the templating engine properly handles objects 
        marked as do_not_call_in_templates and alters_data, and does not 
        inadvertently call or modify them during template rendering.
        """
        class Doodad:
            do_not_call_in_templates = True
            alters_data = True

            def __init__(self, value):
                """
                Initializes the object with a given value.

                :param value: The initial value to be stored in the object.
                :returns: None
                :attr num_calls: An internal counter tracking the number of times the object is accessed or called.
                :attr value: The value passed during initialization, stored as an instance attribute.
                """
                self.num_calls = 0
                self.value = value

            def __call__(self):
                """
                Invoke the object, returning a dictionary containing the stored value.

                This method increments an internal counter tracking the number of times the object is called.
                The returned dictionary contains a single key-value pair, where the key is 'the_value' and the value is the object's stored value.

                :return: A dictionary with the stored value.
                :rtype: dict
                """
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
