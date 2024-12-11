import pickle

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.test import SimpleTestCase, TestCase
from django.utils.choices import CallableChoiceIterator
from django.utils.functional import lazy

from .models import (
    Bar,
    Choiceful,
    Foo,
    RenamedField,
    VerboseNameField,
    Whiz,
    WhizDelayed,
    WhizIter,
    WhizIterEmpty,
)


class Nested:
    class Field(models.Field):
        pass


class BasicFieldTests(SimpleTestCase):
    def test_show_hidden_initial(self):
        """
        Fields with choices respect show_hidden_initial as a kwarg to
        formfield().
        """
        choices = [(0, 0), (1, 1)]
        model_field = models.Field(choices=choices)
        form_field = model_field.formfield(show_hidden_initial=True)
        self.assertTrue(form_field.show_hidden_initial)

        form_field = model_field.formfield(show_hidden_initial=False)
        self.assertFalse(form_field.show_hidden_initial)

    def test_field_repr(self):
        """
        __repr__() of a field displays its name.
        """
        f = Foo._meta.get_field("a")
        self.assertEqual(repr(f), "<django.db.models.fields.CharField: a>")
        f = models.fields.CharField()
        self.assertEqual(repr(f), "<django.db.models.fields.CharField>")

    def test_field_repr_nested(self):
        """__repr__() uses __qualname__ for nested class support."""
        self.assertEqual(repr(Nested.Field()), "<model_fields.tests.Nested.Field>")

    def test_field_name(self):
        """
        A defined field name (name="fieldname") is used instead of the model
        model's attribute name (modelname).
        """
        instance = RenamedField()
        self.assertTrue(hasattr(instance, "get_fieldname_display"))
        self.assertFalse(hasattr(instance, "get_modelname_display"))

    def test_field_verbose_name(self):
        """

        Test the verbose name of fields in the VerboseNameField model.

        This test case verifies that the verbose names of all fields in the model
        are correctly defined. It checks the verbose names of 21 fields (field1 to field21)
        and ensures they follow the expected pattern. Additionally, it checks the verbose name
        of the primary key field to confirm it matches the expected value.

        """
        m = VerboseNameField
        for i in range(1, 22):
            self.assertEqual(
                m._meta.get_field("field%d" % i).verbose_name, "verbose field%d" % i
            )

        self.assertEqual(m._meta.get_field("id").verbose_name, "verbose pk")

    def test_choices_form_class(self):
        """Can supply a custom choices form class to Field.formfield()"""
        choices = [("a", "a")]
        field = models.CharField(choices=choices)
        klass = forms.TypedMultipleChoiceField
        self.assertIsInstance(field.formfield(choices_form_class=klass), klass)

    def test_formfield_disabled(self):
        """Field.formfield() sets disabled for fields with choices."""
        field = models.CharField(choices=[("a", "b")])
        form_field = field.formfield(disabled=True)
        self.assertIs(form_field.disabled, True)

    def test_field_str(self):
        """
        Tests the string representation of a Django model Field instance.

        The test case covers two scenarios: 
        1. The string representation of a generic Field instance, 
        2. The string representation of a Field instance retrieved from a specific model. 

        It verifies that the string representations match the expected output formats, 
        helping to ensure that the Field instances can be correctly represented as strings.
        """
        f = models.Field()
        self.assertEqual(str(f), "<django.db.models.fields.Field>")
        f = Foo._meta.get_field("a")
        self.assertEqual(str(f), "model_fields.Foo.a")

    def test_field_ordering(self):
        """Fields are ordered based on their creation."""
        f1 = models.Field()
        f2 = models.Field(auto_created=True)
        f3 = models.Field()
        self.assertLess(f2, f1)
        self.assertGreater(f3, f1)
        self.assertIsNotNone(f1)
        self.assertNotIn(f2, (None, 1, ""))

    def test_field_instance_is_picklable(self):
        """Field instances can be pickled."""
        field = models.Field(max_length=100, default="a string")
        # Must be picklable with this cached property populated (#28188).
        field._get_default
        pickle.dumps(field)

    def test_deconstruct_nested_field(self):
        """deconstruct() uses __qualname__ for nested class support."""
        name, path, args, kwargs = Nested.Field().deconstruct()
        self.assertEqual(path, "model_fields.tests.Nested.Field")

    def test_abstract_inherited_fields(self):
        """Field instances from abstract models are not equal."""

        class AbstractModel(models.Model):
            field = models.IntegerField()

            class Meta:
                abstract = True

        class InheritAbstractModel1(AbstractModel):
            pass

        class InheritAbstractModel2(AbstractModel):
            pass

        abstract_model_field = AbstractModel._meta.get_field("field")
        inherit1_model_field = InheritAbstractModel1._meta.get_field("field")
        inherit2_model_field = InheritAbstractModel2._meta.get_field("field")

        self.assertNotEqual(abstract_model_field, inherit1_model_field)
        self.assertNotEqual(abstract_model_field, inherit2_model_field)
        self.assertNotEqual(inherit1_model_field, inherit2_model_field)

        self.assertLess(abstract_model_field, inherit1_model_field)
        self.assertLess(abstract_model_field, inherit2_model_field)
        self.assertLess(inherit1_model_field, inherit2_model_field)

    def test_hash_immutability(self):
        """
        Tests that the hash value of a model field remains unchanged after it's assigned to a model.

        This test ensures that model fields are immutable in the sense that their hash value does not change
        when they are assigned to a model instance, which is a crucial property for reliable hash-based
        operations, such as dictionary lookups or set membership tests.

        The test creates a simple model with an integer field and verifies that the hash value of the field
        remains the same before and after it's assigned to the model, providing assurance about the field's
        immutability with respect to its hash value.
        """
        field = models.IntegerField()
        field_hash = hash(field)

        class MyModel(models.Model):
            rank = field

        self.assertEqual(field_hash, hash(field))


class ChoicesTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """

        Sets up the class by retrieving and storing various fields from the Choiceful model for later use.

        This method is a class-level setup hook that is called before running any tests in the class.
        It initializes class attributes that represent fields from the Choiceful model, including fields with
        different types of choices (e.g., empty choices, choices with dictionaries, choices from enums, etc.).
        These fields are stored as class attributes for easy access throughout the test class.

        """
        super().setUpClass()
        cls.no_choices = Choiceful._meta.get_field("no_choices")
        cls.empty_choices = Choiceful._meta.get_field("empty_choices")
        cls.empty_choices_bool = Choiceful._meta.get_field("empty_choices_bool")
        cls.empty_choices_text = Choiceful._meta.get_field("empty_choices_text")
        cls.with_choices = Choiceful._meta.get_field("with_choices")
        cls.with_choices_dict = Choiceful._meta.get_field("with_choices_dict")
        cls.with_choices_nested_dict = Choiceful._meta.get_field(
            "with_choices_nested_dict"
        )
        cls.choices_from_enum = Choiceful._meta.get_field("choices_from_enum")
        cls.choices_from_iterator = Choiceful._meta.get_field("choices_from_iterator")
        cls.choices_from_callable = Choiceful._meta.get_field("choices_from_callable")

    def test_choices(self):
        self.assertIsNone(self.no_choices.choices)
        self.assertEqual(self.empty_choices.choices, [])
        self.assertEqual(self.empty_choices_bool.choices, [])
        self.assertEqual(self.empty_choices_text.choices, [])
        self.assertEqual(self.with_choices.choices, [(1, "A")])
        self.assertEqual(self.with_choices_dict.choices, [(1, "A")])
        self.assertEqual(self.with_choices_nested_dict.choices, [("Thing", [(1, "A")])])
        self.assertEqual(
            self.choices_from_iterator.choices, [(0, "0"), (1, "1"), (2, "2")]
        )
        self.assertIsInstance(
            self.choices_from_callable.choices, CallableChoiceIterator
        )
        self.assertEqual(
            self.choices_from_callable.choices.func(), [(0, "0"), (1, "1"), (2, "2")]
        )

    def test_flatchoices(self):
        """
        Tests the flatchoices attribute of model fields.

        Verifies that the attribute correctly returns a flat list of choices for
        various scenarios, including empty choices, choices with different data
        types, and choices generated from iterators or callables. The test covers
        different edge cases to ensure that the flatchoices attribute behaves as
        expected in various situations.

        The test cases check for the following scenarios:
        - Fields with no choices
        - Fields with empty choices
        - Fields with choices defined in different formats (e.g., lists, dictionaries)
        - Fields with choices generated dynamically from iterators or callables

        By ensuring that the flatchoices attribute works correctly in these
        scenarios, this test provides confidence in the overall functionality of
        the model field's choices handling.
        """
        self.assertEqual(self.no_choices.flatchoices, [])
        self.assertEqual(self.empty_choices.flatchoices, [])
        self.assertEqual(self.empty_choices_bool.flatchoices, [])
        self.assertEqual(self.empty_choices_text.flatchoices, [])
        self.assertEqual(self.with_choices.flatchoices, [(1, "A")])
        self.assertEqual(self.with_choices_dict.flatchoices, [(1, "A")])
        self.assertEqual(self.with_choices_nested_dict.flatchoices, [(1, "A")])
        self.assertEqual(
            self.choices_from_iterator.flatchoices, [(0, "0"), (1, "1"), (2, "2")]
        )
        self.assertEqual(
            self.choices_from_callable.flatchoices, [(0, "0"), (1, "1"), (2, "2")]
        )

    def test_check(self):
        self.assertEqual(Choiceful.check(), [])

    def test_invalid_choice(self):
        """
        Tests that validation fails with an error when an invalid choice is provided to a choice validator. 

         Specifically, it checks that a :class:`ValidationError` is raised when a value that is not in the list of valid choices is passed to the validator, regardless of whether the list of choices is empty or populated. The validation error message includes the invalid value and indicates that it is not a valid choice.
        """
        model_instance = None  # Actual model instance not needed.
        self.no_choices.validate(0, model_instance)
        msg = "['Value 99 is not a valid choice.']"
        with self.assertRaisesMessage(ValidationError, msg):
            self.empty_choices.validate(99, model_instance)
        with self.assertRaisesMessage(ValidationError, msg):
            self.with_choices.validate(99, model_instance)

    def test_formfield(self):
        """

        Tests the formfield method of various field instances to ensure correct form field types are generated.

        Verifies that a field without choices generates an IntegerField, while fields with choices generate a ChoiceField,
        regardless of the choice data structure (e.g., list, tuple, dict, enum, iterator, or callable).

        """
        no_choices_formfield = self.no_choices.formfield()
        self.assertIsInstance(no_choices_formfield, forms.IntegerField)
        fields = (
            self.empty_choices,
            self.empty_choices_bool,
            self.empty_choices_text,
            self.with_choices,
            self.with_choices_dict,
            self.with_choices_nested_dict,
            self.choices_from_enum,
            self.choices_from_iterator,
            self.choices_from_callable,
        )
        for field in fields:
            with self.subTest(field=field):
                self.assertIsInstance(field.formfield(), forms.ChoiceField)

    def test_choices_from_enum(self):
        # Choices class was transparently resolved when given as argument.
        self.assertEqual(self.choices_from_enum.choices, Choiceful.Suit.choices)
        self.assertEqual(self.choices_from_enum.flatchoices, Choiceful.Suit.choices)


class GetFieldDisplayTests(SimpleTestCase):
    def test_choices_and_field_display(self):
        """
        get_choices() interacts with get_FIELD_display() to return the expected
        values.
        """
        self.assertEqual(Whiz(c=1).get_c_display(), "First")  # A nested value
        self.assertEqual(Whiz(c=0).get_c_display(), "Other")  # A top level value
        self.assertEqual(Whiz(c=9).get_c_display(), 9)  # Invalid value
        self.assertIsNone(Whiz(c=None).get_c_display())  # Blank value
        self.assertEqual(Whiz(c="").get_c_display(), "")  # Empty value
        self.assertEqual(WhizDelayed(c=0).get_c_display(), "Other")  # Delayed choices

    def test_get_FIELD_display_translated(self):
        """A translated display value is coerced to str."""
        val = Whiz(c=5).get_c_display()
        self.assertIsInstance(val, str)
        self.assertEqual(val, "translated")

    def test_overriding_FIELD_display(self):
        """

        Tests that the display method for a model field is correctly overridden.

        This test case verifies that a custom implementation of a display method,
        such as get_foo_bar_display, takes precedence over the default display behavior.
        It ensures that the overridden method returns the expected value, rather than
        the default display value provided by the field's choices.

        """
        class FooBar(models.Model):
            foo_bar = models.IntegerField(choices=[(1, "foo"), (2, "bar")])

            def get_foo_bar_display(self):
                return "something"

        f = FooBar(foo_bar=1)
        self.assertEqual(f.get_foo_bar_display(), "something")

    def test_overriding_inherited_FIELD_display(self):
        """

        Tests that the display value of an inherited field can be overridden in a subclass.

        When a subclass inherits a field from its parent class, it can override the field's
        display values. This test ensures that the display value is correctly retrieved
        from the subclass's overridden field, rather than the parent class's field.

        """
        class Base(models.Model):
            foo = models.CharField(max_length=254, choices=[("A", "Base A")])

            class Meta:
                abstract = True

        class Child(Base):
            foo = models.CharField(
                max_length=254, choices=[("A", "Child A"), ("B", "Child B")]
            )

        self.assertEqual(Child(foo="A").get_foo_display(), "Child A")
        self.assertEqual(Child(foo="B").get_foo_display(), "Child B")

    def test_iterator_choices(self):
        """
        get_choices() works with Iterators.
        """
        self.assertEqual(WhizIter(c=1).c, 1)  # A nested value
        self.assertEqual(WhizIter(c=9).c, 9)  # Invalid value
        self.assertIsNone(WhizIter(c=None).c)  # Blank value
        self.assertEqual(WhizIter(c="").c, "")  # Empty value

    def test_empty_iterator_choices(self):
        """
        get_choices() works with empty iterators.
        """
        self.assertEqual(WhizIterEmpty(c="a").c, "a")  # A nested value
        self.assertEqual(WhizIterEmpty(c="b").c, "b")  # Invalid value
        self.assertIsNone(WhizIterEmpty(c=None).c)  # Blank value
        self.assertEqual(WhizIterEmpty(c="").c, "")  # Empty value


class GetChoicesTests(SimpleTestCase):
    def test_empty_choices(self):
        choices = []
        f = models.CharField(choices=choices)
        self.assertEqual(f.get_choices(include_blank=False), choices)

    def test_blank_in_choices(self):
        """
        Tests that CharField.get_choices() correctly includes a blank option when specified.

        The function verifies that when the include_blank parameter is set to True, 
        the field's choices, including any blank options, are returned as expected.

        It checks the functionality of get_choices() method in case of a CharField 
        with predefined choices and confirms that it behaves as expected when 
        including blank choices.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the function's get_choices() method does not return 
            the expected choices when including blank options.

        """
        choices = [("", "<><>"), ("a", "A")]
        f = models.CharField(choices=choices)
        self.assertEqual(f.get_choices(include_blank=True), choices)

    def test_blank_in_grouped_choices(self):
        """

        Tests that :meth:`get_choices` returns the full list of choices when include_blank is True,
        even when the choices are grouped. This ensures that all available options, including
        any blank or default choices, are correctly retrieved for fields with grouped choices.

        """
        choices = [
            ("f", "Foo"),
            ("b", "Bar"),
            (
                "Group",
                [
                    ("", "No Preference"),
                    ("fg", "Foo"),
                    ("bg", "Bar"),
                ],
            ),
        ]
        f = models.CharField(choices=choices)
        self.assertEqual(f.get_choices(include_blank=True), choices)

    def test_lazy_strings_not_evaluated(self):
        """
        Tests that lazy strings are not prematurely evaluated when used as choices in a CharField.

        This test ensures that lazy functions are only executed when their values are actually needed,
        preventing potential errors or exceptions that may occur during evaluation.

        The test case covers the scenario where a lazy function is used to generate choices for a CharField,
        and verifies that the choices are correctly generated without causing any evaluation errors.

        The expected behavior is that the lazy function is not evaluated until its value is required,
        at which point it should return the expected choices without raising any exceptions.
        """
        lazy_func = lazy(lambda x: 0 / 0, int)  # raises ZeroDivisionError if evaluated.
        f = models.CharField(choices=[(lazy_func("group"), [("a", "A"), ("b", "B")])])
        self.assertEqual(f.get_choices(include_blank=True)[0], ("", "---------"))


class GetChoicesOrderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for testing purposes.

        This method creates sample instances of Foo and Bar objects, 
        associating them with each other, to provide a test dataset.
        The created objects are stored as class attributes, allowing 
        for easy access and manipulation in subsequent tests.
        The method also retrieves the field 'a' from the Bar model's metadata.

        """
        cls.foo1 = Foo.objects.create(a="a", d="12.35")
        cls.foo2 = Foo.objects.create(a="b", d="12.34")
        cls.bar1 = Bar.objects.create(a=cls.foo1, b="b")
        cls.bar2 = Bar.objects.create(a=cls.foo2, b="a")
        cls.field = Bar._meta.get_field("a")

    def assertChoicesEqual(self, choices, objs):
        self.assertEqual(choices, [(obj.pk, str(obj)) for obj in objs])

    def test_get_choices(self):
        self.assertChoicesEqual(
            self.field.get_choices(include_blank=False, ordering=("a",)),
            [self.foo1, self.foo2],
        )
        self.assertChoicesEqual(
            self.field.get_choices(include_blank=False, ordering=("-a",)),
            [self.foo2, self.foo1],
        )

    def test_get_choices_default_ordering(self):
        """

        Tests that the get_choices method returns choices in the default ordering specified by the model's Meta class.

        The test case verifies that when the model's default ordering is changed, the choices returned by the get_choices method are ordered accordingly. 

        The test specifically checks that when the default ordering is set to a single field 'd', the choices are returned in the correct order, from lowest to highest based on the 'd' field.

        :param None: This method does not take any parameters.
        :return: None

        """
        self.addCleanup(setattr, Foo._meta, "ordering", Foo._meta.ordering)
        Foo._meta.ordering = ("d",)
        self.assertChoicesEqual(
            self.field.get_choices(include_blank=False), [self.foo2, self.foo1]
        )

    def test_get_choices_reverse_related_field(self):
        """

        Tests the functionality of retrieving choices for a reverse related field.

        This test case verifies that the `get_choices` method of a remote field returns the correct choices 
        in the specified order. It checks both ascending and descending orderings, ensuring that 
        the choices are correctly ordered based on the 'a' attribute of the related objects.

        The test includes two separate assertions, one for each ordering direction, 
        to guarantee that the choices are correctly retrieved and ordered. 

        """
        self.assertChoicesEqual(
            self.field.remote_field.get_choices(include_blank=False, ordering=("a",)),
            [self.bar1, self.bar2],
        )
        self.assertChoicesEqual(
            self.field.remote_field.get_choices(include_blank=False, ordering=("-a",)),
            [self.bar2, self.bar1],
        )

    def test_get_choices_reverse_related_field_default_ordering(self):
        """

        Tests the ordering of choices for a reverse related field when the default ordering is applied.

        The function verifies that the choices returned by a remote field are ordered according to the default ordering specified in the related model's metadata.

        In this case, it checks that the choices are ordered by the 'b' field of the related model, and returns the choices in the correct order.

        """
        self.addCleanup(setattr, Bar._meta, "ordering", Bar._meta.ordering)
        Bar._meta.ordering = ("b",)
        self.assertChoicesEqual(
            self.field.remote_field.get_choices(include_blank=False),
            [self.bar2, self.bar1],
        )


class GetChoicesLimitChoicesToTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.foo1 = Foo.objects.create(a="a", d="12.34")
        cls.foo2 = Foo.objects.create(a="b", d="12.34")
        cls.bar1 = Bar.objects.create(a=cls.foo1, b="b")
        cls.bar2 = Bar.objects.create(a=cls.foo2, b="a")
        cls.field = Bar._meta.get_field("a")

    def assertChoicesEqual(self, choices, objs):
        self.assertCountEqual(choices, [(obj.pk, str(obj)) for obj in objs])

    def test_get_choices(self):
        self.assertChoicesEqual(
            self.field.get_choices(include_blank=False, limit_choices_to={"a": "a"}),
            [self.foo1],
        )
        self.assertChoicesEqual(
            self.field.get_choices(include_blank=False, limit_choices_to={}),
            [self.foo1, self.foo2],
        )

    def test_get_choices_reverse_related_field(self):
        """

        Tests the functionality of the get_choices method for reverse related fields.

        This method tests the get_choices functionality by providing different parameters to
        limit the choices returned. Specifically, it checks that when a limit_choices_to
        dictionary is provided, the method only returns choices that match the given
        conditions. When no limit_choices_to dictionary is provided, the method returns
        all possible choices.

        It ensures that the get_choices method behaves correctly for reverse related
        fields, returning the expected choices based on the provided parameters.

        """
        field = self.field.remote_field
        self.assertChoicesEqual(
            field.get_choices(include_blank=False, limit_choices_to={"b": "b"}),
            [self.bar1],
        )
        self.assertChoicesEqual(
            field.get_choices(include_blank=False, limit_choices_to={}),
            [self.bar1, self.bar2],
        )
