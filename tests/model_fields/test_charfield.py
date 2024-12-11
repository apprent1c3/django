from django.core.exceptions import ValidationError
from django.db import models
from django.test import SimpleTestCase, TestCase

from .models import Post


class TestCharField(TestCase):
    def test_max_length_passed_to_formfield(self):
        """
        CharField passes its max_length attribute to form fields created using
        the formfield() method.
        """
        cf1 = models.CharField()
        cf2 = models.CharField(max_length=1234)
        self.assertIsNone(cf1.formfield().max_length)
        self.assertEqual(1234, cf2.formfield().max_length)

    def test_lookup_integer_in_charfield(self):
        self.assertEqual(Post.objects.filter(title=9).count(), 0)

    def test_emoji(self):
        p = Post.objects.create(title="Smile 😀", body="Whatever.")
        p.refresh_from_db()
        self.assertEqual(p.title, "Smile 😀")

    def test_assignment_from_choice_enum(self):
        class Event(models.TextChoices):
            C = "Carnival!"
            F = "Festival!"

        p1 = Post.objects.create(title=Event.C, body=Event.F)
        p1.refresh_from_db()
        self.assertEqual(p1.title, "Carnival!")
        self.assertEqual(p1.body, "Festival!")
        self.assertEqual(p1.title, Event.C)
        self.assertEqual(p1.body, Event.F)
        p2 = Post.objects.get(title="Carnival!")
        self.assertEqual(p1, p2)
        self.assertEqual(p2.title, Event.C)


class TestMethods(SimpleTestCase):
    def test_deconstruct(self):
        """
        Tests the deconstruction of a CharField instance, verifying that it correctly separates its keyword arguments. The test checks two scenarios: 
            one with default keyword arguments and another with a custom database collation specified. 
            It asserts that the deconstructed keyword arguments match the expected output for both cases.
        """
        field = models.CharField()
        *_, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {})
        field = models.CharField(db_collation="utf8_esperanto_ci")
        *_, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {"db_collation": "utf8_esperanto_ci"})


class ValidationTests(SimpleTestCase):
    class Choices(models.TextChoices):
        C = "c", "C"

    def test_charfield_raises_error_on_empty_string(self):
        f = models.CharField()
        msg = "This field cannot be blank."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("", None)

    def test_charfield_cleans_empty_string_when_blank_true(self):
        f = models.CharField(blank=True)
        self.assertEqual("", f.clean("", None))

    def test_charfield_with_choices_cleans_valid_choice(self):
        """
        Verifies that a CharField with explicit choices correctly cleans a valid input choice.

        The function checks that when a valid choice is provided to the CharField's clean method, 
        it returns the cleaned value as expected, confirming that the choice validation works as intended.
        """
        f = models.CharField(max_length=1, choices=[("a", "A"), ("b", "B")])
        self.assertEqual("a", f.clean("a", None))

    def test_charfield_with_choices_raises_error_on_invalid_choice(self):
        f = models.CharField(choices=[("a", "A"), ("b", "B")])
        msg = "Value 'not a' is not a valid choice."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("not a", None)

    def test_enum_choices_cleans_valid_string(self):
        f = models.CharField(choices=self.Choices, max_length=1)
        self.assertEqual(f.clean("c", None), "c")

    def test_enum_choices_invalid_input(self):
        f = models.CharField(choices=self.Choices, max_length=1)
        msg = "Value 'a' is not a valid choice."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("a", None)

    def test_charfield_raises_error_on_empty_input(self):
        """
        Tests that CharField raises a ValidationError when given empty input and null is set to False.

        Verifies that attempting to clean a CharField with a null value, when null is explicitly
        set to False, results in a validation error with a meaningful error message.

        The test ensures that the model field correctly enforces its null constraint and provides
        a user-friendly error message in case of invalid input.
        """
        f = models.CharField(null=False)
        msg = "This field cannot be null."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(None, None)

    def test_callable_choices(self):
        def get_choices():
            return {str(i): f"Option {i}" for i in range(3)}

        f = models.CharField(max_length=1, choices=get_choices)

        for i in get_choices():
            with self.subTest(i=i):
                self.assertEqual(i, f.clean(i, None))

        with self.assertRaises(ValidationError):
            f.clean("A", None)
        with self.assertRaises(ValidationError):
            f.clean("3", None)
