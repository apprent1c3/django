import decimal

from django.core.exceptions import ValidationError
from django.forms import TypedMultipleChoiceField
from django.test import SimpleTestCase


class TypedMultipleChoiceFieldTest(SimpleTestCase):
    def test_typedmultiplechoicefield_1(self):
        """
        Tests the TypedMultipleChoiceField with integer choices.

        Verifies that the field correctly validates and cleans the input when a valid choice is provided.
        Additionally, checks that the field raises a ValidationError with a descriptive message when an invalid choice is submitted.

        Args:
            None

        Returns:
            None

        Raises:
            ValidationError: If the input choice is not one of the available options.

        """
        f = TypedMultipleChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=int)
        self.assertEqual([1], f.clean(["1"]))
        msg = "'Select a valid choice. 2 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["2"])

    def test_typedmultiplechoicefield_2(self):
        # Different coercion, same validation.
        f = TypedMultipleChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=float)
        self.assertEqual([1.0], f.clean(["1"]))

    def test_typedmultiplechoicefield_3(self):
        # This can also cause weirdness: be careful (bool(-1) == True, remember)
        f = TypedMultipleChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=bool)
        self.assertEqual([True], f.clean(["-1"]))

    def test_typedmultiplechoicefield_4(self):
        f = TypedMultipleChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=int)
        self.assertEqual([1, -1], f.clean(["1", "-1"]))
        msg = "'Select a valid choice. 2 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["1", "2"])

    def test_typedmultiplechoicefield_5(self):
        # Even more weirdness: if you have a valid choice but your coercion function
        # can't coerce, you'll still get a validation error. Don't do this!
        f = TypedMultipleChoiceField(choices=[("A", "A"), ("B", "B")], coerce=int)
        msg = "'Select a valid choice. B is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["B"])
        # Required fields require values
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean([])

    def test_typedmultiplechoicefield_6(self):
        # Non-required fields aren't required
        """
        Tests the TypedMultipleChoiceField's clean method with an empty input.

        This test case verifies that when an empty list is passed to the clean method,
        it correctly returns an empty list, given the field's parameters of having 
        integer choices, optional requirement, and a coercion to integer values.

        The test scenario checks the proper handling of empty input data for a field 
        configured with specific selection options, demonstrating its behavior when 
        no value is provided by the user, thus ensuring its correctness in such cases.
        """
        f = TypedMultipleChoiceField(
            choices=[(1, "+1"), (-1, "-1")], coerce=int, required=False
        )
        self.assertEqual([], f.clean([]))

    def test_typedmultiplechoicefield_7(self):
        # If you want cleaning an empty value to return a different type, tell the field
        f = TypedMultipleChoiceField(
            choices=[(1, "+1"), (-1, "-1")],
            coerce=int,
            required=False,
            empty_value=None,
        )
        self.assertIsNone(f.clean([]))

    def test_typedmultiplechoicefield_has_changed(self):
        # has_changed should not trigger required validation
        f = TypedMultipleChoiceField(
            choices=[(1, "+1"), (-1, "-1")], coerce=int, required=True
        )
        self.assertFalse(f.has_changed(None, ""))

    def test_typedmultiplechoicefield_special_coerce(self):
        """
        A coerce function which results in a value not present in choices
        should raise an appropriate error (#21397).
        """

        def coerce_func(val):
            return decimal.Decimal("1.%s" % val)

        f = TypedMultipleChoiceField(
            choices=[(1, "1"), (2, "2")], coerce=coerce_func, required=True
        )
        self.assertEqual([decimal.Decimal("1.2")], f.clean(["2"]))
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean([])
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["3"])
