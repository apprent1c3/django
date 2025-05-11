from django.test import SimpleTestCase
from django.utils.functional import cached_property, classproperty, lazy
from django.utils.version import PY312


class FunctionalTests(SimpleTestCase):
    def test_lazy(self):
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
        Tests that a lazy object can be properly converted to a string and bytes representation when its target object implements __str__ and __bytes__ methods.
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

        Tests the functionality and behavior of a cached property in a class.

        Verifies that the cached property works correctly for the given attribute,
        including its documentation string, value consistency, and different instances.
        Also checks the type of the cached property and ensures that other class methods remain callable.

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
        """
        Tests that attempting to access a cached property without setting its name raises a TypeError.
        """
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
        Tests the lazy addition of integers, verifying that instances of lazy objects can be added to integers and other lazy objects, resolving their values correctly.
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 + lazy_5(), 9)
        self.assertEqual(lazy_4() + 5, 9)
        self.assertEqual(lazy_4() + lazy_5(), 9)

    def test_lazy_add_list(self):
        """
        Tests the addition of lists when mixed with lazy values, ensuring correct results when using both immediate and delayed evaluations.
        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: [5], list)
        self.assertEqual([4] + lazy_5(), [4, 5])
        self.assertEqual(lazy_4() + [5], [4, 5])
        self.assertEqual(lazy_4() + lazy_5(), [4, 5])

    def test_lazy_add_str(self):
        """

        Tests the addition of lazy strings with and without immediate evaluation.
        Verifies that the lazy addition produces the expected concatenated string results.

        """
        lazy_a = lazy(lambda: "a", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a" + lazy_b(), "ab")
        self.assertEqual(lazy_a() + "b", "ab")
        self.assertEqual(lazy_a() + lazy_b(), "ab")

    def test_lazy_mod_int(self):
        """
        Checks the correctness of the modulus operator when applied to lazy integers, ensuring it produces the expected results in various operand combinations.
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 % lazy_5(), 4)
        self.assertEqual(lazy_4() % 5, 4)
        self.assertEqual(lazy_4() % lazy_5(), 4)

    def test_lazy_mod_str(self):
        """
        Verifies the functioning of lazy string modifications using the modulus operator. Tests string formatting with both string literals and lazy string objects as operands.
        """
        lazy_a = lazy(lambda: "a%s", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a%s" % lazy_b(), "ab")
        self.assertEqual(lazy_a() % "b", "ab")
        self.assertEqual(lazy_a() % lazy_b(), "ab")

    def test_lazy_mul_int(self):
        """
        Tests multiplication of lazy values with integers, verifying correct results when the lazy value is on the left or right side of the operation or when both operands are lazy.
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 * lazy_5(), 20)
        self.assertEqual(lazy_4() * 5, 20)
        self.assertEqual(lazy_4() * lazy_5(), 20)

    def test_lazy_mul_list(self):
        """
        Tests the multiplication operation on LazyList instances, verifying that the list is correctly repeated when multiplied by an integer or another Lazy instance.
        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual([4] * lazy_5(), [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * 5, [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * lazy_5(), [4, 4, 4, 4, 4])

    def test_lazy_mul_str(self):
        """
        Tests the multiplication operation with lazy string values, ensuring correct results when a lazy string is multiplied by an integer or another lazy integer value, and vice versa.
        """
        lazy_a = lazy(lambda: "a", str)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual("a" * lazy_5(), "aaaaa")
        self.assertEqual(lazy_a() * 5, "aaaaa")
        self.assertEqual(lazy_a() * lazy_5(), "aaaaa")

    def test_lazy_format(self):
        """
        Verifies that a lazy-formatted string correctly applies custom formatting when requested, ensuring proper output with or without explicit format specification.
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
        original_object = "Lazy translation text"
        lazy_obj = lazy(lambda: original_object, str)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_int(self):
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_bytes(self):
        original_object = b"J\xc3\xbcst a str\xc3\xadng"
        lazy_obj = lazy(lambda: original_object, bytes)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_regular_method(self):
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(original_object.bit_length(), lazy_obj().bit_length())

    def test_lazy_bytes_and_str_result_classes(self):
        lazy_obj = lazy(lambda: "test", str, bytes)
        self.assertEqual(str(lazy_obj()), "test")

    def test_lazy_str_cast_mixed_result_types(self):
        lazy_value = lazy(lambda: [1], str, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_lazy_str_cast_mixed_bytes_result_types(self):
        lazy_value = lazy(lambda: [1], bytes, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_classproperty_getter(self):
        """
        (\"\"\"
        Tests the behavior of the classproperty getter.

        Verifies that classproperties can be accessed via the class and instance,
        and that they return the expected values. This ensures that classproperties
        are working correctly, including when using the decorator syntax.
        \"\"\")
        """
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
        """
        Tests that a class property's getter can be overridden, ensuring the overridden getter is used when accessing the property on both the class and instances of the class.
        """
        class Foo:
            @classproperty
            def foo(cls):
                return 123

            @foo.getter
            def foo(cls):
                return 456

        self.assertEqual(Foo.foo, 456)
        self.assertEqual(Foo().foo, 456)
