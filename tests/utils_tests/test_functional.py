from django.test import SimpleTestCase
from django.utils.functional import cached_property, classproperty, lazy
from django.utils.version import PY312


class FunctionalTests(SimpleTestCase):
    def test_lazy(self):
        """

        Test the functionality of lazy loading with multiple data types.

        This test case verifies that the lazy function can handle different data types, 
        specifically converting between list and tuple, and that it correctly generates 
        a sequence of numbers (0, 1, 2) when executed. The test ensures that the lazy 
        loading mechanism produces the expected output by comparing it with a predefined 
        range of values.

        The lazy function is expected to delay the evaluation of the provided lambda 
        function until it is actually needed, and to return the result in the specified 
        data type (list or tuple).

        """
        t = lazy(lambda: tuple(range(3)), list, tuple)
        for a, b in zip(t(), range(3)):
            self.assertEqual(a, b)

    def test_lazy_base_class(self):
        """lazy also finds base class methods in the proxy object"""

        class Base:
            def base_method(self):
                pass

        class Klazz(Base):
            pass

        t = lazy(lambda: Klazz(), Klazz)()
        self.assertIn("base_method", dir(t))

    def test_lazy_base_class_override(self):
        """lazy finds the correct (overridden) method implementation"""

        class Base:
            def method(self):
                return "Base"

        class Klazz(Base):
            def method(self):
                return "Klazz"

        t = lazy(lambda: Klazz(), Base)()
        self.assertEqual(t.method(), "Klazz")

    def test_lazy_object_to_string(self):
        """

        Tests the conversion of a lazy object to a string and bytes representation.

        This test checks that the lazy object, which is initialized with a class instance,
        can be correctly converted to a string and bytes using the str() and bytes()
        functions, respectively. The test verifies that the resulting string and bytes
        representations match the expected output defined in the class's __str__() and
        __bytes__() methods.

        """
        class Klazz:
            def __str__(self):
                return "Î am ā Ǩlâzz."

            def __bytes__(self):
                return b"\xc3\x8e am \xc4\x81 binary \xc7\xa8l\xc3\xa2zz."

        t = lazy(lambda: Klazz(), Klazz)()
        self.assertEqual(str(t), "Î am ā Ǩlâzz.")
        self.assertEqual(bytes(t), b"\xc3\x8e am \xc4\x81 binary \xc7\xa8l\xc3\xa2zz.")

    def assertCachedPropertyWorks(self, attr, Class):
        """

        Verify that a cached property behaves as expected.

        This test case checks the following aspects of a cached property:
        - The docstring is correctly preserved on both the class and its subclasses.
        - The property value is correctly cached on instance level.
        - The property values are distinct across different instances of the same class or its subclasses.
        - The property is of the correct type and is callable.

        The test is parameterized by an attribute name (`attr`) and a class (`Class`) to test the behavior of the specified cached property.

        """
        with self.subTest(attr=attr):

            def get(source):
                return getattr(source, attr)

            obj = Class()

            class SubClass(Class):
                pass

            subobj = SubClass()
            # Docstring is preserved.
            self.assertEqual(get(Class).__doc__, "Here is the docstring...")
            self.assertEqual(get(SubClass).__doc__, "Here is the docstring...")
            # It's cached.
            self.assertEqual(get(obj), get(obj))
            self.assertEqual(get(subobj), get(subobj))
            # The correct value is returned.
            self.assertEqual(get(obj)[0], 1)
            self.assertEqual(get(subobj)[0], 1)
            # State isn't shared between instances.
            obj2 = Class()
            subobj2 = SubClass()
            self.assertNotEqual(get(obj), get(obj2))
            self.assertNotEqual(get(subobj), get(subobj2))
            # It behaves like a property when there's no instance.
            self.assertIsInstance(get(Class), cached_property)
            self.assertIsInstance(get(SubClass), cached_property)
            # 'other_value' doesn't become a property.
            self.assertTrue(callable(obj.other_value))
            self.assertTrue(callable(subobj.other_value))

    def test_cached_property(self):
        """cached_property caches its value and behaves like a property."""

        class Class:
            @cached_property
            def value(self):
                """Here is the docstring..."""
                return 1, object()

            @cached_property
            def __foo__(self):
                """Here is the docstring..."""
                return 1, object()

            def other_value(self):
                """Here is the docstring..."""
                return 1, object()

            other = cached_property(other_value)

        attrs = ["value", "other", "__foo__"]
        for attr in attrs:
            self.assertCachedPropertyWorks(attr, Class)

    def test_cached_property_auto_name(self):
        """
        cached_property caches its value and behaves like a property
        on mangled methods or when the name kwarg isn't set.
        """

        class Class:
            @cached_property
            def __value(self):
                """Here is the docstring..."""
                return 1, object()

            def other_value(self):
                """Here is the docstring..."""
                return 1, object()

            other = cached_property(other_value)

        attrs = ["_Class__value", "other"]
        for attr in attrs:
            self.assertCachedPropertyWorks(attr, Class)

    def test_cached_property_reuse_different_names(self):
        """Disallow this case because the decorated function wouldn't be cached."""
        type_msg = (
            "Cannot assign the same cached_property to two different names ('a' and "
            "'b')."
        )
        if PY312:
            error_type = TypeError
            msg = type_msg
        else:
            error_type = RuntimeError
            msg = "Error calling __set_name__"

        with self.assertRaisesMessage(error_type, msg) as ctx:

            class ReusedCachedProperty:
                @cached_property
                def a(self):
                    pass

                b = a

        if not PY312:
            self.assertEqual(str(ctx.exception.__context__), str(TypeError(type_msg)))

    def test_cached_property_reuse_same_name(self):
        """
        Reusing a cached_property on different classes under the same name is
        allowed.
        """
        counter = 0

        @cached_property
        def _cp(_self):
            """
            Private cached property that increments and returns a counter value.

            This property is used to maintain a sequence of unique integers, where each access
            to the property returns the next integer in the sequence. The counter is
            automatically initialized and incremented internally.

            The returned value can be used to identify or distinguish between different
            instances or events, providing a simple and efficient way to keep track of a
            sequence of occurrences.

            Note: This property is intended for internal use and should not be accessed
            directly from outside the class. The underscore prefix indicates that it is a
            private attribute, and its use is not part of the public API.
            """
            nonlocal counter
            counter += 1
            return counter

        class A:
            cp = _cp

        class B:
            cp = _cp

        a = A()
        b = B()
        self.assertEqual(a.cp, 1)
        self.assertEqual(b.cp, 2)
        self.assertEqual(a.cp, 1)

    def test_cached_property_set_name_not_called(self):
        cp = cached_property(lambda s: None)

        class Foo:
            pass

        Foo.cp = cp
        msg = (
            "Cannot use cached_property instance without calling __set_name__() on it."
        )
        with self.assertRaisesMessage(TypeError, msg):
            Foo().cp

    def test_lazy_add_int(self):
        """

        Tests the addition of lazy values with integers.

        Verifies that lazy values can be added to integers and vice versa, 
        and also that lazy values can be added to each other, 
        resulting in the correct sum of their encapsulated values.

        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 + lazy_5(), 9)
        self.assertEqual(lazy_4() + 5, 9)
        self.assertEqual(lazy_4() + lazy_5(), 9)

    def test_lazy_add_list(self):
        """
        Tests the functionality of adding a list returned by a lazy function to another list.

         This test case verifies that the lazy function can be used on both sides of the addition operation.
         The test covers three scenarios: adding a lazy list to a regular list, adding a regular list to a lazy list, 
         and adding two lazy lists together, to ensure the result is consistent with regular list addition behavior.

        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: [5], list)
        self.assertEqual([4] + lazy_5(), [4, 5])
        self.assertEqual(lazy_4() + [5], [4, 5])
        self.assertEqual(lazy_4() + lazy_5(), [4, 5])

    def test_lazy_add_str(self):
        """

        Tests the lazy addition of string values.

        This test case verifies that the lazy evaluation of strings behaves correctly
        when added to other strings, either eagerly evaluated or lazily evaluated.
        It checks the concatenation of strings in various scenarios, including the
        addition of a lazy string to an eagerly evaluated string, an eagerly evaluated
        string to a lazy string, and the addition of two lazy strings.

        The test ensures that the expected concatenated string is produced in each case.

        """
        lazy_a = lazy(lambda: "a", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a" + lazy_b(), "ab")
        self.assertEqual(lazy_a() + "b", "ab")
        self.assertEqual(lazy_a() + lazy_b(), "ab")

    def test_lazy_mod_int(self):
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 % lazy_5(), 4)
        self.assertEqual(lazy_4() % 5, 4)
        self.assertEqual(lazy_4() % lazy_5(), 4)

    def test_lazy_mod_str(self):
        lazy_a = lazy(lambda: "a%s", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a%s" % lazy_b(), "ab")
        self.assertEqual(lazy_a() % "b", "ab")
        self.assertEqual(lazy_a() % lazy_b(), "ab")

    def test_lazy_mul_int(self):
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 * lazy_5(), 20)
        self.assertEqual(lazy_4() * 5, 20)
        self.assertEqual(lazy_4() * lazy_5(), 20)

    def test_lazy_mul_list(self):
        """
        Tests the functionality of the lazy multiplication operation with lists.

        This method verifies that the multiplication of a lazy list and an integer, 
        as well as the multiplication of a lazy list and another lazy integer, 
        produces the expected result, which is a new list with the original list 
        repeated the specified number of times.

        The test cases cover various scenarios, including lazy list multiplication 
        by a non-lazy integer and by another lazy integer, ensuring correct 
        functionality in both situations
        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual([4] * lazy_5(), [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * 5, [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * lazy_5(), [4, 4, 4, 4, 4])

    def test_lazy_mul_str(self):
        """
        Tests the lazy multiplication of strings.

                This function checks the correctness of multiplying a string by an integer 
                when either the string or the integer is lazily evaluated. It verifies that 
                the lazy evaluation does not affect the result of the multiplication, 
                regardless of whether the string or the integer is the lazily evaluated operand.

                The test covers three scenarios: 
                - multiplying a lazily evaluated string by an integer
                - multiplying a string by a lazily evaluated integer
                - multiplying a lazily evaluated string by a lazily evaluated integer

                In all cases, the function ensures that the result of the multiplication 
                is the same as if both operands were eagerly evaluated.

        """
        lazy_a = lazy(lambda: "a", str)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual("a" * lazy_5(), "aaaaa")
        self.assertEqual(lazy_a() * 5, "aaaaa")
        self.assertEqual(lazy_a() * lazy_5(), "aaaaa")

    def test_lazy_format(self):
        """
        Tests the lazy formatting of a string value.

        This function verifies that a lazily evaluated string can be correctly formatted 
        and used in a string context. It checks that the formatted value is wrapped in 
        double quotes, as specified by the custom QuotedString class.

        The test covers two scenarios: direct formatting using the format function and 
        embedding the formatted value in a larger string using an f-string. 

        The expected output is a string with double quotes around the original value, 
        indicating successful lazy formatting.
        """
        class QuotedString(str):
            def __format__(self, format_spec):
                value = super().__format__(format_spec)
                return f"“{value}”"

        lazy_f = lazy(lambda: QuotedString("Hello!"), QuotedString)
        self.assertEqual(format(lazy_f(), ""), "“Hello!”")
        f = lazy_f()
        self.assertEqual(f"I said, {f}", "I said, “Hello!”")

    def test_lazy_equality(self):
        """
        == and != work correctly for Promises.
        """
        lazy_a = lazy(lambda: 4, int)
        lazy_b = lazy(lambda: 4, int)
        lazy_c = lazy(lambda: 5, int)

        self.assertEqual(lazy_a(), lazy_b())
        self.assertNotEqual(lazy_b(), lazy_c())

    def test_lazy_repr_text(self):
        """
        Tests whether the representation of a lazily translated text object matches the representation of its original string equivalent when evaluated. 

        This function verifies that the lazy object, when executed, produces the same string representation as the original object, ensuring consistency in how the object is displayed.
        """
        original_object = "Lazy translation text"
        lazy_obj = lazy(lambda: original_object, str)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_int(self):
        """
        Tests the representation of a lazily evaluated integer object.

        With lazy evaluation, the actual computation of the object's value is delayed until it is needed.
        This test verifies that the string representation of a lazily evaluated integer is the same as its non-lazy counterpart.
        In other words, it checks that the lazy representation of an integer object is functionally equivalent to the original object's representation, ensuring seamless interaction with the lazily evaluated object in various contexts.
        The test confirms this equivalence by comparing the string representations of both the lazy and non-lazy integer objects using the repr() function.
        """
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_bytes(self):
        original_object = b"J\xc3\xbcst a str\xc3\xadng"
        lazy_obj = lazy(lambda: original_object, bytes)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_regular_method(self):
        """

        Tests the lazy evaluation of a regular method.

        This test case verifies that a method call on a lazy object returns the same result 
        as the same method call on the original object. It uses the bit_length method as 
        an example and checks for equality between the results of the method call on the 
        original object and the lazy object.

        The test covers the scenario where the lazy object is evaluated and its method 
        call matches the expected behavior of the original object.

        """
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(original_object.bit_length(), lazy_obj().bit_length())

    def test_lazy_bytes_and_str_result_classes(self):
        """

        Test the functionality of lazy loaded objects that return either bytes or string results.

        This test case validates the behavior of objects that utilize lazy loading, 
        allowing them to return values of both string and bytes types.

        The test focuses on verifying the correctness of the string representation 
        of the lazy loaded object when it is explicitly converted to a string.

        """
        lazy_obj = lazy(lambda: "test", str, bytes)
        self.assertEqual(str(lazy_obj()), "test")

    def test_lazy_str_cast_mixed_result_types(self):
        """
        Tests if the lazy string casting functionality correctly handles mixed result types by comparing the string representation of a lazy value to its expected output. 

        The function verifies that the lazy value, which is generated using a lambda function that returns a list, can be successfully cast to a string and matches the anticipated result. This ensures that the lazy string casting mechanism can handle a variety of data types and provide the expected output.
        """
        lazy_value = lazy(lambda: [1], str, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_lazy_str_cast_mixed_bytes_result_types(self):
        """

        Tests the string representation of a lazy value with mixed bytes result types.

        Verifies that the lazy value, which is initialized with a bytes and list type,
        returns a string representation of its evaluated value when cast to a string.

        """
        lazy_value = lazy(lambda: [1], bytes, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_classproperty_getter(self):
        class Foo:
            foo_attr = 123

            def __init__(self):
                self.foo_attr = 456

            @classproperty
            def foo(cls):
                return cls.foo_attr

        class Bar:
            bar = classproperty()

            @bar.getter
            def bar(cls):
                return 123

        self.assertEqual(Foo.foo, 123)
        self.assertEqual(Foo().foo, 123)
        self.assertEqual(Bar.bar, 123)
        self.assertEqual(Bar().bar, 123)

    def test_classproperty_override_getter(self):
        class Foo:
            @classproperty
            def foo(cls):
                return 123

            @foo.getter
            def foo(cls):
                return 456

        self.assertEqual(Foo.foo, 456)
        self.assertEqual(Foo().foo, 456)
