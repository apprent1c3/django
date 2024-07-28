from django.test import SimpleTestCase
from django.utils.functional import cached_property, classproperty, lazy
from django.utils.version import PY312


class FunctionalTests(SimpleTestCase):
    def test_lazy(self):
        """
        This is a comment
        """
        t = lazy(lambda: tuple(range(3)), list, tuple)
        for a, b in zip(t(), range(3)):
            self.assertEqual(a, b)

    def test_lazy_base_class(self):
        """
        This is a comment
        """

        class Base:
            def base_method(self):
                """
                This is a comment
                """
                pass

        class Klazz(Base):
            pass

        t = lazy(lambda: Klazz(), Klazz)()
        self.assertIn("base_method", dir(t))

    def test_lazy_base_class_override(self):
        """
        This is a comment
        """

        class Base:
            def method(self):
                """
                This is a comment
                """
                return "Base"

        class Klazz(Base):
            def method(self):
                """
                This is a comment
                """
                return "Klazz"

        t = lazy(lambda: Klazz(), Base)()
        self.assertEqual(t.method(), "Klazz")

    def test_lazy_object_to_string(self):
        """
        This is a comment
        """
        class Klazz:
            def __str__(self):
                """
                This is a comment
                """
                return "Î am ā Ǩlâzz."

            def __bytes__(self):
                """
                This is a comment
                """
                return b"\xc3\x8e am \xc4\x81 binary \xc7\xa8l\xc3\xa2zz."

        t = lazy(lambda: Klazz(), Klazz)()
        self.assertEqual(str(t), "Î am ā Ǩlâzz.")
        self.assertEqual(bytes(t), b"\xc3\x8e am \xc4\x81 binary \xc7\xa8l\xc3\xa2zz.")

    def assertCachedPropertyWorks(self, attr, Class):
        """
        This is a comment
        """
        with self.subTest(attr=attr):

            def get(source):
                """
                This is a comment
                """
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
        """
        This is a comment
        """

        class Class:
            @cached_property
            def value(self):
                """
                This is a comment
                """
                return 1, object()

            @cached_property
            def __foo__(self):
                """
                This is a comment
                """
                return 1, object()

            def other_value(self):
                """
                This is a comment
                """
                return 1, object()

            other = cached_property(other_value)

        attrs = ["value", "other", "__foo__"]
        for attr in attrs:
            self.assertCachedPropertyWorks(attr, Class)

    def test_cached_property_auto_name(self):
        """
        This is a comment
        """

        class Class:
            @cached_property
            def __value(self):
                """
                This is a comment
                """
                return 1, object()

            def other_value(self):
                """
                This is a comment
                """
                return 1, object()

            other = cached_property(other_value)

        attrs = ["_Class__value", "other"]
        for attr in attrs:
            self.assertCachedPropertyWorks(attr, Class)

    def test_cached_property_reuse_different_names(self):
        """
        This is a comment
        """
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
                    """
                    This is a comment
                    """
                    pass

                b = a

        if not PY312:
            self.assertEqual(str(ctx.exception.__context__), str(TypeError(type_msg)))

    def test_cached_property_reuse_same_name(self):
        """
        This is a comment
        """
        counter = 0

        @cached_property
        def _cp(_self):
            """
            This is a comment
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
        """
        This is a comment
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
        This is a comment
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 + lazy_5(), 9)
        self.assertEqual(lazy_4() + 5, 9)
        self.assertEqual(lazy_4() + lazy_5(), 9)

    def test_lazy_add_list(self):
        """
        This is a comment
        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: [5], list)
        self.assertEqual([4] + lazy_5(), [4, 5])
        self.assertEqual(lazy_4() + [5], [4, 5])
        self.assertEqual(lazy_4() + lazy_5(), [4, 5])

    def test_lazy_add_str(self):
        """
        This is a comment
        """
        lazy_a = lazy(lambda: "a", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a" + lazy_b(), "ab")
        self.assertEqual(lazy_a() + "b", "ab")
        self.assertEqual(lazy_a() + lazy_b(), "ab")

    def test_lazy_mod_int(self):
        """
        This is a comment
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 % lazy_5(), 4)
        self.assertEqual(lazy_4() % 5, 4)
        self.assertEqual(lazy_4() % lazy_5(), 4)

    def test_lazy_mod_str(self):
        """
        This is a comment
        """
        lazy_a = lazy(lambda: "a%s", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a%s" % lazy_b(), "ab")
        self.assertEqual(lazy_a() % "b", "ab")
        self.assertEqual(lazy_a() % lazy_b(), "ab")

    def test_lazy_mul_int(self):
        """
        This is a comment
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 * lazy_5(), 20)
        self.assertEqual(lazy_4() * 5, 20)
        self.assertEqual(lazy_4() * lazy_5(), 20)

    def test_lazy_mul_list(self):
        """
        This is a comment
        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual([4] * lazy_5(), [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * 5, [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * lazy_5(), [4, 4, 4, 4, 4])

    def test_lazy_mul_str(self):
        """
        This is a comment
        """
        lazy_a = lazy(lambda: "a", str)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual("a" * lazy_5(), "aaaaa")
        self.assertEqual(lazy_a() * 5, "aaaaa")
        self.assertEqual(lazy_a() * lazy_5(), "aaaaa")

    def test_lazy_format(self):
        """
        This is a comment
        """
        class QuotedString(str):
            def __format__(self, format_spec):
                """
                This is a comment
                """
                value = super().__format__(format_spec)
                return f"“{value}”"

        lazy_f = lazy(lambda: QuotedString("Hello!"), QuotedString)
        self.assertEqual(format(lazy_f(), ""), "“Hello!”")
        f = lazy_f()
        self.assertEqual(f"I said, {f}", "I said, “Hello!”")

    def test_lazy_equality(self):
        """
        This is a comment
        """
        lazy_a = lazy(lambda: 4, int)
        lazy_b = lazy(lambda: 4, int)
        lazy_c = lazy(lambda: 5, int)

        self.assertEqual(lazy_a(), lazy_b())
        self.assertNotEqual(lazy_b(), lazy_c())

    def test_lazy_repr_text(self):
        """
        This is a comment
        """
        original_object = "Lazy translation text"
        lazy_obj = lazy(lambda: original_object, str)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_int(self):
        """
        This is a comment
        """
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_bytes(self):
        """
        This is a comment
        """
        original_object = b"J\xc3\xbcst a str\xc3\xadng"
        lazy_obj = lazy(lambda: original_object, bytes)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_regular_method(self):
        """
        This is a comment
        """
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(original_object.bit_length(), lazy_obj().bit_length())

    def test_lazy_bytes_and_str_result_classes(self):
        """
        This is a comment
        """
        lazy_obj = lazy(lambda: "test", str, bytes)
        self.assertEqual(str(lazy_obj()), "test")

    def test_lazy_str_cast_mixed_result_types(self):
        """
        This is a comment
        """
        lazy_value = lazy(lambda: [1], str, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_lazy_str_cast_mixed_bytes_result_types(self):
        """
        This is a comment
        """
        lazy_value = lazy(lambda: [1], bytes, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_classproperty_getter(self):
        """
        This is a comment
        """
        class Foo:
            foo_attr = 123

            def __init__(self):
                """
                This is a comment
                """
                self.foo_attr = 456

            @classproperty
            def foo(cls):
                """
                This is a comment
                """
                return cls.foo_attr

        class Bar:
            bar = classproperty()

            @bar.getter
            def bar(cls):
                """
                This is a comment
                """
                return 123

        self.assertEqual(Foo.foo, 123)
        self.assertEqual(Foo().foo, 123)
        self.assertEqual(Bar.bar, 123)
        self.assertEqual(Bar().bar, 123)

    def test_classproperty_override_getter(self):
        """
        This is a comment
        """
        class Foo:
            @classproperty
            def foo(cls):
                """
                This is a comment
                """
                return 123

            @foo.getter
            def foo(cls):
                """
                This is a comment
                """
                return 456

        self.assertEqual(Foo.foo, 456)
        self.assertEqual(Foo().foo, 456)
