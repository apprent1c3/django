from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ChoiceField, Form
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class ChoiceFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_choicefield_1(self):
        f = ChoiceField(choices=[("1", "One"), ("2", "Two")])
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual("1", f.clean(1))
        self.assertEqual("1", f.clean("1"))
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("3")

    def test_choicefield_2(self):
        """
        Tests the functionality of the ChoiceField when the required parameter is set to False.

        The test covers various scenarios, including when the input is empty, None, a valid choice, and an invalid choice.
        It verifies that the field correctly returns an empty string for empty inputs, and the corresponding key for valid choices.
        Additionally, it checks that the field raises a ValidationError with the expected error message when an invalid choice is provided.
        """
        f = ChoiceField(choices=[("1", "One"), ("2", "Two")], required=False)
        self.assertEqual("", f.clean(""))
        self.assertEqual("", f.clean(None))
        self.assertEqual("1", f.clean(1))
        self.assertEqual("1", f.clean("1"))
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("3")

    def test_choicefield_3(self):
        """

        Tests the functionality of a ChoiceField with a predefined set of choices.

        The test verifies that when a valid choice is provided, it is successfully 
        cleaned and returned by the field. Additionally, it checks that when an 
        invalid choice is provided, a ValidationError is raised with an appropriate 
        error message, indicating that the selected value is not one of the 
        available choices.

        """
        f = ChoiceField(choices=[("J", "John"), ("P", "Paul")])
        self.assertEqual("J", f.clean("J"))
        msg = "'Select a valid choice. John is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("John")

    def test_choicefield_4(self):
        f = ChoiceField(
            choices=[
                ("Numbers", (("1", "One"), ("2", "Two"))),
                ("Letters", (("3", "A"), ("4", "B"))),
                ("5", "Other"),
            ]
        )
        self.assertEqual("1", f.clean(1))
        self.assertEqual("1", f.clean("1"))
        self.assertEqual("3", f.clean(3))
        self.assertEqual("3", f.clean("3"))
        self.assertEqual("5", f.clean(5))
        self.assertEqual("5", f.clean("5"))
        msg = "'Select a valid choice. 6 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("6")

    def test_choicefield_choices_default(self):
        f = ChoiceField()
        self.assertEqual(f.choices, [])

    def test_choicefield_callable(self):
        """

        Tests the functionality of a ChoiceField when its choices are provided by a callable.

        This test case verifies that the ChoiceField correctly retrieves and uses the choices
        provided by a callable function, and that it validates user input against these choices.

        In this scenario, the callable function returns a list of tuples representing the choices,
        where each tuple contains a value and its corresponding human-readable name. The test
        then uses the ChoiceField to clean a user-provided value and checks if it matches one
        of the expected choices.

        """
        def choices():
            return [("J", "John"), ("P", "Paul")]

        f = ChoiceField(choices=choices)
        self.assertEqual("J", f.clean("J"))

    def test_choicefield_callable_mapping(self):
        def choices():
            return {"J": "John", "P": "Paul"}

        f = ChoiceField(choices=choices)
        self.assertEqual("J", f.clean("J"))

    def test_choicefield_callable_grouped_mapping(self):
        """
        Tests that the ChoiceField cleans the input correctly when a callable returns a grouped mapping of choices.

        The test verifies that when the choices are returned as a dictionary with grouped options,
        the ChoiceField is able to properly validate and clean the input values.

        The test case covers both valid and implicitly valid inputs, checking that the cleaned
        value matches the original input. This ensures that the ChoiceField behaves as expected
        when dealing with callable choices that return a grouped mapping structure.
        """
        def choices():
            return {
                "Numbers": {"1": "One", "2": "Two"},
                "Letters": {"3": "A", "4": "B"},
            }

        f = ChoiceField(choices=choices)
        for i in ("1", "2", "3", "4"):
            with self.subTest(i):
                self.assertEqual(i, f.clean(i))

    def test_choicefield_mapping(self):
        f = ChoiceField(choices={"J": "John", "P": "Paul"})
        self.assertEqual("J", f.clean("J"))

    def test_choicefield_grouped_mapping(self):
        f = ChoiceField(
            choices={
                "Numbers": (("1", "One"), ("2", "Two")),
                "Letters": (("3", "A"), ("4", "B")),
            }
        )
        for i in ("1", "2", "3", "4"):
            with self.subTest(i):
                self.assertEqual(i, f.clean(i))

    def test_choicefield_grouped_mapping_inner_dict(self):
        f = ChoiceField(
            choices={
                "Numbers": {"1": "One", "2": "Two"},
                "Letters": {"3": "A", "4": "B"},
            }
        )
        for i in ("1", "2", "3", "4"):
            with self.subTest(i):
                self.assertEqual(i, f.clean(i))

    def test_choicefield_callable_may_evaluate_to_different_values(self):
        """

        Tests that a ChoiceField with a callable choices argument can evaluate to different values.

        This test case verifies that when the choices are provided as a callable function,
        the ChoiceField correctly updates its choices and widget choices when the callable
        returns different values. It checks that both the field and its widget have the
        correct choices after the form is instantiated with different choices.

        """
        choices = []

        def choices_as_callable():
            return choices

        class ChoiceFieldForm(Form):
            choicefield = ChoiceField(choices=choices_as_callable)

        choices = [("J", "John")]
        form = ChoiceFieldForm()
        self.assertEqual(choices, list(form.fields["choicefield"].choices))
        self.assertEqual(choices, list(form.fields["choicefield"].widget.choices))

        choices = [("P", "Paul")]
        form = ChoiceFieldForm()
        self.assertEqual(choices, list(form.fields["choicefield"].choices))
        self.assertEqual(choices, list(form.fields["choicefield"].widget.choices))

    def test_choicefield_disabled(self):
        """
        Tests that a ChoiceField widget renders correctly when disabled.

        The test verifies that the select element is rendered with the disabled attribute
        and that the choices are properly displayed as options.

        This ensures that a disabled ChoiceField widget is displayed in a read-only state,
        without allowing user input or selection, while still showing the available choices.

        Args:
            None

        Returns:
            None
        """
        f = ChoiceField(choices=[("J", "John"), ("P", "Paul")], disabled=True)
        self.assertWidgetRendersTo(
            f,
            '<select id="id_f" name="f" disabled><option value="J">John</option>'
            '<option value="P">Paul</option></select>',
        )

    def test_choicefield_enumeration(self):
        """

        Tests the behavior of a ChoiceField using TextChoices enumeration.

        Verifies that the choices in the field match the provided enumeration, 
        that valid choices can be cleaned successfully, and that attempting to 
        clean an invalid choice raises a ValidationError with the expected message.

        """
        class FirstNames(models.TextChoices):
            JOHN = "J", "John"
            PAUL = "P", "Paul"

        f = ChoiceField(choices=FirstNames)
        self.assertEqual(f.choices, FirstNames.choices)
        self.assertEqual(f.clean("J"), "J")
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("3")
