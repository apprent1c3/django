from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ChoiceField, Form
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class ChoiceFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_choicefield_1(self):
        """
        Tests the validation behavior of a ChoiceField instance.

        This test case verifies that the field raises a ValidationError when given an empty or null value, 
        and when given an invalid choice. It also checks that the field correctly selects a valid choice 
        from the provided options, regardless of whether the input is a string or an integer.

        Validations tested include:
        - Required field validation
        - Invalid choice validation
        - Input type flexibility (string or integer)
        """
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
        f = ChoiceField(choices=[("1", "One"), ("2", "Two")], required=False)
        self.assertEqual("", f.clean(""))
        self.assertEqual("", f.clean(None))
        self.assertEqual("1", f.clean(1))
        self.assertEqual("1", f.clean("1"))
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("3")

    def test_choicefield_3(self):
        f = ChoiceField(choices=[("J", "John"), ("P", "Paul")])
        self.assertEqual("J", f.clean("J"))
        msg = "'Select a valid choice. John is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("John")

    def test_choicefield_4(self):
        """
        Tests the functionality of the ChoiceField when given a choice with nested options.

        The ChoiceField is initialized with a subset of choices, divided into groups ('Numbers', 'Letters') and a standalone option. 

        The function then checks that valid input (both string and integer representations) is cleaned and returned correctly. 

        It also verifies that attempting to clean an invalid choice raises a ValidationError with the expected message, indicating that the provided choice is not one of the available options.
        """
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
        def test_choicefield_callable_may_evaluate_to_different_values(self):
            \"\"\"
            Tests that a ChoiceField's choices can be defined by a callable that may return different values each time it is evaluated.

            This test checks that the choices returned by the callable are correctly used by the ChoiceField and its associated widget, 
            even when the callable's return value changes between different instances of the form.

            It verifies that the choices are correctly initialized and updated when the form is instantiated with different return values 
            from the callable, ensuring that the form's fields and widget are properly synchronized with the dynamic choices.

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

        Tests the rendering of a disabled ChoiceField widget.

        This method verifies that a ChoiceField with the 'disabled' attribute set to True
        is rendered as a disabled HTML select element. The choices provided to the field
        are correctly translated into HTML option elements within the select element.

        The test case checks that the expected HTML output matches the actual output of
        the widget.

        """
        f = ChoiceField(choices=[("J", "John"), ("P", "Paul")], disabled=True)
        self.assertWidgetRendersTo(
            f,
            '<select id="id_f" name="f" disabled><option value="J">John</option>'
            '<option value="P">Paul</option></select>',
        )

    def test_choicefield_enumeration(self):
        """
        Tests the functionality of ChoiceField with TextChoices enumeration.

        This test case verifies that the ChoiceField correctly populates its choices
        from the provided TextChoices enumeration. It also checks that the clean method
        properly validates user input, allowing valid choices and raising a ValidationError
        for invalid choices.

        The test uses a simple TextChoices enumeration, FirstNames, with two options:
        JOHN and PAUL. It creates a ChoiceField instance with this enumeration and then
        asserts that the field's choices match the enumeration's choices. The test also
        verifies that the clean method returns the expected value for a valid choice and
        raises a ValidationError with the correct message for an invalid choice.
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
