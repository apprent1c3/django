from django.core.exceptions import ValidationError
from django.forms import MultipleChoiceField
from django.test import SimpleTestCase


class MultipleChoiceFieldTest(SimpleTestCase):
    def test_multiplechoicefield_1(self):
        """

        Tests the functionality of a MultipleChoiceField.

        Checks that the field raises a ValidationError when no value is provided, 
        and when an invalid input type (e.g. a string) is given.

        Also, verifies that the field correctly cleans and returns valid input 
        (e.g. a list or tuple of choices), regardless of whether the choices are 
        provided as integers or strings.

        Additionally, it checks that the field raises an error when an invalid choice 
        is selected, and when an empty list or tuple is provided.

        """
        f = MultipleChoiceField(choices=[("1", "One"), ("2", "Two")])
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual(["1"], f.clean([1]))
        self.assertEqual(["1"], f.clean(["1"]))
        self.assertEqual(["1", "2"], f.clean(["1", "2"]))
        self.assertEqual(["1", "2"], f.clean([1, "2"]))
        self.assertEqual(["1", "2"], f.clean((1, "2")))
        with self.assertRaisesMessage(ValidationError, "'Enter a list of values.'"):
            f.clean("hello")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean([])
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(())
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["3"])

    def test_multiplechoicefield_2(self):
        f = MultipleChoiceField(choices=[("1", "One"), ("2", "Two")], required=False)
        self.assertEqual([], f.clean(""))
        self.assertEqual([], f.clean(None))
        self.assertEqual(["1"], f.clean([1]))
        self.assertEqual(["1"], f.clean(["1"]))
        self.assertEqual(["1", "2"], f.clean(["1", "2"]))
        self.assertEqual(["1", "2"], f.clean([1, "2"]))
        self.assertEqual(["1", "2"], f.clean((1, "2")))
        with self.assertRaisesMessage(ValidationError, "'Enter a list of values.'"):
            f.clean("hello")
        self.assertEqual([], f.clean([]))
        self.assertEqual([], f.clean(()))
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["3"])

    def test_multiplechoicefield_3(self):
        """
        Tests the MultipleChoiceField to ensure it correctly handles various input types and validates choices.

        The test verifies that the field can process integer and string inputs, as well as combinations of both, and returns the corresponding choice values.

        Additionally, it checks that the field raises a ValidationError when an invalid choice is provided, either as a single value or as part of a list of choices.

        The expected behavior is that the field returns a list of valid choice values, or raises an error if any invalid choices are encountered.
        """
        f = MultipleChoiceField(
            choices=[
                ("Numbers", (("1", "One"), ("2", "Two"))),
                ("Letters", (("3", "A"), ("4", "B"))),
                ("5", "Other"),
            ]
        )
        self.assertEqual(["1"], f.clean([1]))
        self.assertEqual(["1"], f.clean(["1"]))
        self.assertEqual(["1", "5"], f.clean([1, 5]))
        self.assertEqual(["1", "5"], f.clean([1, "5"]))
        self.assertEqual(["1", "5"], f.clean(["1", 5]))
        self.assertEqual(["1", "5"], f.clean(["1", "5"]))
        msg = "'Select a valid choice. 6 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["6"])
        msg = "'Select a valid choice. 6 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(["1", "6"])

    def test_multiplechoicefield_changed(self):
        """
        Tests whether the MultipleChoiceField has changed based on its initial and current values.

        The test includes various scenarios to evaluate the field's has_changed method, considering empty, 
        single, and multiple choices as initial and current values. It ensures the method correctly identifies 
        when a change has occurred, regardless of the order or presence of choices.

        The test cases cover scenarios such as:
        - Initial and current values being the same or different
        - Choices being added, removed, or reordered

        """
        f = MultipleChoiceField(choices=[("1", "One"), ("2", "Two"), ("3", "Three")])
        self.assertFalse(f.has_changed(None, None))
        self.assertFalse(f.has_changed([], None))
        self.assertTrue(f.has_changed(None, ["1"]))
        self.assertFalse(f.has_changed([1, 2], ["1", "2"]))
        self.assertFalse(f.has_changed([2, 1], ["1", "2"]))
        self.assertTrue(f.has_changed([1, 2], ["1"]))
        self.assertTrue(f.has_changed([1, 2], ["1", "3"]))

    def test_disabled_has_changed(self):
        """
        Tests whether the :meth:`has_changed` method of a disabled MultipleChoiceField returns False, 
        indicating that the field's value has not changed, regardless of the provided initial and current values.
        """
        f = MultipleChoiceField(choices=[("1", "One"), ("2", "Two")], disabled=True)
        self.assertIs(f.has_changed("x", "y"), False)
