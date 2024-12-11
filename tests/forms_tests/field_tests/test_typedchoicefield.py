import decimal

from django.core.exceptions import ValidationError
from django.forms import TypedChoiceField
from django.test import SimpleTestCase


class TypedChoiceFieldTest(SimpleTestCase):
    def test_typedchoicefield_1(self):
        """

        Tests the behavior of a TypedChoiceField with integer choices.

        Verifies that the field correctly coerces the input to an integer and returns
        the corresponding value. Additionally, it checks that an error is raised when
        an invalid choice is provided, ensuring that the field enforces its defined choices.

        The test covers two primary scenarios: a valid choice and an invalid choice.

        """
        f = TypedChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=int)
        self.assertEqual(1, f.clean("1"))
        msg = "'Select a valid choice. 2 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("2")

    def test_typedchoicefield_2(self):
        # Different coercion, same validation.
        """
        Tests the TypedChoiceField with a list of float choices to ensure the input value is correctly coerced and validated. 

        The test verifies that when the input value is '1', the clean method returns 1.0, demonstrating the successful coercion from string to float. 

        This test case helps ensure the TypedChoiceField behaves as expected when handling typed choices with a float coercion function.
        """
        f = TypedChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=float)
        self.assertEqual(1.0, f.clean("1"))

    def test_typedchoicefield_3(self):
        # This can also cause weirdness: be careful (bool(-1) == True, remember)
        """
        Tests the TypedChoiceField with boolean coercion.

        This test case verifies that the TypedChoiceField correctly coerces the input value to a boolean when the coerce parameter is set to bool.

        The field is configured with two choices: +1 and -1, mapped to the integer values 1 and -1 respectively.

        The test passes if the field successfully validates and cleans the input value '-1', resulting in a boolean value of True.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the field fails to validate or clean the input value.
        """
        f = TypedChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=bool)
        self.assertTrue(f.clean("-1"))

    def test_typedchoicefield_4(self):
        # Even more weirdness: if you have a valid choice but your coercion function
        # can't coerce, you'll still get a validation error. Don't do this!
        f = TypedChoiceField(choices=[("A", "A"), ("B", "B")], coerce=int)
        msg = "'Select a valid choice. B is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("B")
        # Required fields require values
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")

    def test_typedchoicefield_5(self):
        # Non-required fields aren't required
        """
        Tests the behavior of TypedChoiceField when cleaning an empty string input.

        This test case verifies that the TypedChoiceField correctly handles an empty string
        when the field is not required. The test checks if the clean method returns an empty
        string when given an empty string input, ensuring that the field does not raise an
        error or return an incorrect value.

        The test uses a TypedChoiceField instance with integer choices and coercion, and
        asserts that the clean method returns an empty string when given an empty string input.\"\"\"

         However it would be even more idiomatic in Sphinx to use a short summary line followed by an empty line and then the detailed description. Here is how it would look like:

        \"\"\"Tests TypedChoiceField cleaning of empty string input.

        The test verifies that the clean method of a TypedChoiceField instance returns an
        empty string when given an empty string input, ensuring that the field does not
        raise an error or return an incorrect value. The test uses a TypedChoiceField
        instance with integer choices and coercion.\"\"\"

         Let's use the second variant for easier usage in a Sphinx documentation system. Here it is again:

        \"\"\"Tests TypedChoiceField cleaning of empty string input.

        The test verifies that the clean method of a TypedChoiceField instance returns an
        empty string when given an empty string input, ensuring that the field does not
        raise an error or return an incorrect value. The test uses a TypedChoiceField
        instance with integer choices and coercion.
        """
        f = TypedChoiceField(
            choices=[(1, "+1"), (-1, "-1")], coerce=int, required=False
        )
        self.assertEqual("", f.clean(""))
        # If you want cleaning an empty value to return a different type, tell the field

    def test_typedchoicefield_6(self):
        f = TypedChoiceField(
            choices=[(1, "+1"), (-1, "-1")],
            coerce=int,
            required=False,
            empty_value=None,
        )
        self.assertIsNone(f.clean(""))

    def test_typedchoicefield_has_changed(self):
        # has_changed should not trigger required validation
        f = TypedChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=int, required=True)
        self.assertFalse(f.has_changed(None, ""))
        self.assertFalse(f.has_changed(1, "1"))
        self.assertFalse(f.has_changed("1", "1"))

        f = TypedChoiceField(
            choices=[("", "---------"), ("a", "a"), ("b", "b")],
            coerce=str,
            required=False,
            initial=None,
            empty_value=None,
        )
        self.assertFalse(f.has_changed(None, ""))
        self.assertTrue(f.has_changed("", "a"))
        self.assertFalse(f.has_changed("a", "a"))

    def test_typedchoicefield_special_coerce(self):
        """
        A coerce function which results in a value not present in choices
        should raise an appropriate error (#21397).
        """

        def coerce_func(val):
            return decimal.Decimal("1.%s" % val)

        f = TypedChoiceField(
            choices=[(1, "1"), (2, "2")], coerce=coerce_func, required=True
        )
        self.assertEqual(decimal.Decimal("1.2"), f.clean("2"))
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("3")
