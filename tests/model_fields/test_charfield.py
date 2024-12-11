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
        """
        Tests that a post with an emoji in its title is created and retrieved correctly.

        Verifies that the post title containing an emoji is properly stored and retrieved
        from the database, ensuring that the emoji is preserved and not altered during
        the process.

        The test creates a new post with a title containing an emoji, refreshes the
        post object from the database, and then asserts that the retrieved title matches
        the original title, including the emoji.
        """
        p = Post.objects.create(title="Smile 😀", body="Whatever.")
        p.refresh_from_db()
        self.assertEqual(p.title, "Smile 😀")

    def test_assignment_from_choice_enum(self):
        """

        Tests the assignment and comparison of enumeration choices to model fields.

        This test case verifies that enumerations defined using :class:`models.TextChoices`
        can be successfully assigned to model fields and that the assigned value can be
        retrieved and compared correctly.

        It checks for correct assignment, database storage, and retrieval of enumeration
        choices, as well as equality between the model instance and a queried instance.

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

        Checks that the deconstruct method returns the keyword arguments used to 
        instantiate the field. Specifically, verifies that an empty dictionary is 
        returned when no additional arguments are provided, and that the 
        db_collation argument is correctly captured when specified.

        The test ensures that the deconstruction process accurately reflects the 
        original field configuration, allowing for reliable reconstruction of the 
        field from its deconstructed parts.

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
        """
        Tests that a CharField with blank=True correctly cleans an empty string input, ensuring it is returned as an empty string rather than raising an error. This verifies the field's behavior aligns with its configuration, allowing empty strings when blank is set to True.
        """
        f = models.CharField(blank=True)
        self.assertEqual("", f.clean("", None))

    def test_charfield_with_choices_cleans_valid_choice(self):
        f = models.CharField(max_length=1, choices=[("a", "A"), ("b", "B")])
        self.assertEqual("a", f.clean("a", None))

    def test_charfield_with_choices_raises_error_on_invalid_choice(self):
        """
        Tests that a CharField with choices defined raises a ValidationError when an invalid choice is provided, ensuring data consistency and integrity by preventing invalid options from being selected.
        """
        f = models.CharField(choices=[("a", "A"), ("b", "B")])
        msg = "Value 'not a' is not a valid choice."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("not a", None)

    def test_enum_choices_cleans_valid_string(self):
        f = models.CharField(choices=self.Choices, max_length=1)
        self.assertEqual(f.clean("c", None), "c")

    def test_enum_choices_invalid_input(self):
        """

        Tests that the CharField validation fails when given an invalid choice.

        The function attempts to clean an invalid input ('a') using a CharField with
        predefined choices. It verifies that a ValidationError is raised with the
        expected error message, confirming that the input is correctly identified as
        invalid.

        """
        f = models.CharField(choices=self.Choices, max_length=1)
        msg = "Value 'a' is not a valid choice."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("a", None)

    def test_charfield_raises_error_on_empty_input(self):
        """
        Tests that a CharField instance with null=False raises a ValidationError when given empty input.

            This test case ensures the field's null constraint is enforced, providing a validation
            error message when null or empty input is provided, confirming the field's integrity.

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
