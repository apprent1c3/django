import decimal

from django.core.exceptions import ValidationError
from django.forms import TypedMultipleChoiceField
from django.test import SimpleTestCase


class TypedMultipleChoiceFieldTest(SimpleTestCase):
    def test_typedmultiplechoicefield_1(self):
        f = TypedMultipleChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=int)
        self.assertEqual([1], f.clean(["1"]))
        msg = "'Select a valid choice. 2 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["2"])

    def test_typedmultiplechoicefield_2(self):
        # Different coercion, same validation.
        """
        Tests the TypedMultipleChoiceField with a list of choices and a float coercion.

        This test case verifies that the TypedMultipleChoiceField correctly cleans and validates
        a list of input values against the defined choices, converting the selected value to a float.

        The test uses a field with two choices: '+1' and '-1', with corresponding values of 1 and -1.
        It then attempts to clean a list containing the string '1' and checks that the result is a list
        containing a single float value, 1.0, which is the expected output after coercion to float.
        """
        f = TypedMultipleChoiceField(choices=[(1, "+1"), (-1, "-1")], coerce=float)
        self.assertEqual([1.0], f.clean(["1"]))

    def test_typedmultiplechoicefield_3(self):
        # This can also cause weirdness: be careful (bool(-1) == True, remember)
        """

        Tests the TypedMultipleChoiceField for correct value coercion and cleaning of input.

        This test ensures that when the field is given a list of raw values, it correctly 
        coerces the values to the specified type and returns a cleaned list of values.

        In this specific test case, the field is configured with boolean coercion and 
        the input value '-1' is expected to be cleaned and returned as True.

        """
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
        """
        Tests the TypedMultipleChoiceField with a coerce function.

        This function verifies that the TypedMultipleChoiceField raises a ValidationError when
        an invalid choice or an empty list is passed to its clean method. The field is
        defined with two available choices, 'A' and 'B', and the coerce function is set
        to convert the input to an integer. 

        The test checks two scenarios: 
        1. When a choice that does not match the available options is selected, 
           a ValidationError with a message indicating the invalid choice is raised.
        2. When an empty list is passed, a ValidationError with a message indicating 
           that the field is required is raised.
        """
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
        ..: 
            Tests the TypedMultipleChoiceField with specific settings to ensure it behaves as expected when no input is provided.

            The test creates a field with the following properties:
            - Choices: a list of tuples containing an integer value and a corresponding string representation.
            - Coerce function: converts the selected choice to an integer.
            - Required: the field is not required, meaning it can be left empty.

            It then verifies that when no input is given (i.e., an empty list), the field's clean method returns an empty list, indicating that the field's validation succeeds without any errors or values.
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
        """

        Checks if the TypedMultipleChoiceField has changed when the input is empty.

        This test ensures that the TypedMultipleChoiceField does not incorrectly report a change when 
        the field's value remains empty.

        The test covers the scenario where the field is required and has a set of choices, but no 
        selection is made. The expected behavior is for the field to return False, indicating that 
        the field's value has not changed.

        """
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
