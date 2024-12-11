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
        """
        Tests the default value of choices in a ChoiceField.

        Verifies that when a ChoiceField is instantiated without explicitly setting choices,
        it defaults to an empty list. This ensures that the field does not contain any
        unexpected or predefined options, providing a clean slate for further configuration.
        """
        f = ChoiceField()
        self.assertEqual(f.choices, [])

    def test_choicefield_callable(self):
        def choices():
            return [("J", "John"), ("P", "Paul")]

        f = ChoiceField(choices=choices)
        self.assertEqual("J", f.clean("J"))

    def test_choicefield_callable_mapping(self):
        """

        Tests that a ChoiceField instance correctly cleans its input when the choices are provided via a callable.

        This test ensures that when the choices for a ChoiceField are generated dynamically by a function,
        the field can still properly validate and normalize its input.

        It verifies that the field returns the input value if it matches a key in the choices mapping,
        regardless of whether the choices are defined statically or generated at runtime.

        """
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
        f = ChoiceField(choices=[("J", "John"), ("P", "Paul")], disabled=True)
        self.assertWidgetRendersTo(
            f,
            '<select id="id_f" name="f" disabled><option value="J">John</option>'
            '<option value="P">Paul</option></select>',
        )

    def test_choicefield_enumeration(self):
        class FirstNames(models.TextChoices):
            JOHN = "J", "John"
            PAUL = "P", "Paul"

        f = ChoiceField(choices=FirstNames)
        self.assertEqual(f.choices, FirstNames.choices)
        self.assertEqual(f.clean("J"), "J")
        msg = "'Select a valid choice. 3 is not one of the available choices.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("3")
