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
        """
        Tests assigning values from a TextChoices enum to a model field.

        This test case verifies that model instances can be created and retrieved with 
        enum values, and that the assigned enum values are correctly stored and 
        retrieved as strings. It also checks that the model instances are equal when 
        created and retrieved with the same enum values. The test covers the following 
        scenarios: 

        - Creating a model instance with enum values
        - Refreshing the instance from the database to verify stored values
        - Comparing the stored values with the original enum values
        - Retrieving a model instance by an enum value stored as a string
        - Verifying the equality of model instances created with the same enum values
        """
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
        Tests the deconstruction of a CharField into its constituent parts.

        Verifies that a CharField with default parameters deconstructs with an empty
        keyword arguments dictionary, and that a CharField with non-default parameters
        (specifically, a database collation) correctly includes these parameters in
        the deconstructed keyword arguments dictionary.
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
        """
        Tests that a CharField raises a ValidationError when given an empty string.

        Verifies that the CharField's validation correctly identifies and rejects empty strings,
        ensuring that this field type cannot be left blank.

        The expected error message is \"This field cannot be blank.\"

        """
        f = models.CharField()
        msg = "This field cannot be blank."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("", None)

    def test_charfield_cleans_empty_string_when_blank_true(self):
        f = models.CharField(blank=True)
        self.assertEqual("", f.clean("", None))

    def test_charfield_with_choices_cleans_valid_choice(self):
        """
        Checks that a CharField with choices correctly cleans a valid choice.

        This test ensures that when a valid choice is passed to the clean method of a CharField with choices, it returns the choice as is, without any modifications or errors. The test covers the scenario where the choice is a single character, and verifies that the cleaned value matches the original input.
        """
        f = models.CharField(max_length=1, choices=[("a", "A"), ("b", "B")])
        self.assertEqual("a", f.clean("a", None))

    def test_charfield_with_choices_raises_error_on_invalid_choice(self):
        """
        Test that a CharField with choices raises a ValidationError when an invalid choice is provided. 

        Verifies that when a value not present in the choices list is used to populate the CharField, 
        it correctly raises a ValidationError with a meaningful error message.
        """
        f = models.CharField(choices=[("a", "A"), ("b", "B")])
        msg = "Value 'not a' is not a valid choice."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("not a", None)

    def test_enum_choices_cleans_valid_string(self):
        """

        Tests if the enum choices cleanup validates a string with a valid choice and returns the cleaned value.

        The function verifies that the CharField, configured with a specific set of choices and a maximum length of 1, 
        correctly cleans and returns a string input that matches one of the defined choices. This ensures that the 
        validation process correctly identifies and returns valid input.

        """
        f = models.CharField(choices=self.Choices, max_length=1)
        self.assertEqual(f.clean("c", None), "c")

    def test_enum_choices_invalid_input(self):
        """
        Tests that a CharField raises a ValidationError when cleaned with an invalid choice from an enum. 

         The function creates a CharField with enum choices and a specified maximum length, then attempts to clean an invalid value. 

         It verifies that a ValidationError is raised with a message indicating that the value is not a valid choice.
        """
        f = models.CharField(choices=self.Choices, max_length=1)
        msg = "Value 'a' is not a valid choice."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("a", None)

    def test_charfield_raises_error_on_empty_input(self):
        f = models.CharField(null=False)
        msg = "This field cannot be null."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(None, None)

    def test_callable_choices(self):
        """
        Tests that the CharField can handle dynamic callable choices.

        Verifies that a CharField with choices generated by a callable function
        correctly validates input values. The test checks that valid choices are
        accepted and cleaned correctly, and that invalid choices raise a ValidationError.

        The callable choices are generated dynamically using a function that returns
        a dictionary of options. This test case ensures that the CharField can handle
        such dynamic choices and provides the expected validation behavior.
        """
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
