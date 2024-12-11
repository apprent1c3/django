from django.forms import ChoiceField, Field, Form, Select
from django.test import SimpleTestCase


class BasicFieldsTests(SimpleTestCase):
    def test_field_sets_widget_is_required(self):
        """
        Tests whether a Field's widget reflects the Field's required status.

        Verifies that when a Field is created with required set to True, its associated widget
        is also marked as required, and conversely, when required is set to False, the widget
        is not marked as required. This ensures consistency between the Field's configuration
        and its widget's behavior.
        """
        self.assertTrue(Field(required=True).widget.is_required)
        self.assertFalse(Field(required=False).widget.is_required)

    def test_cooperative_multiple_inheritance(self):
        """

        Tests that multiple inheritance in Python works cooperatively, ensuring that 
        the initialization methods of all parent classes are correctly called, even 
        if they are not directly referenced in the child class's initialization method.

        This test case checks that the required superclass's __init__ method is 
        called when using multiple inheritance, thus verifying that attributes 
        defined in those superclasses are properly initialized and accessible in 
        the subclass instance.

        """
        class A:
            def __init__(self):
                """
                Initializes a new instance of the class.

                This constructor sets the initial state of the object, including the class_a_var attribute, which is set to True by default.
                It also calls the superclass constructor to perform any necessary initialization.

                """
                self.class_a_var = True
                super().__init__()

        class ComplexField(Field, A):
            def __init__(self):
                super().__init__()

        f = ComplexField()
        self.assertTrue(f.class_a_var)

    def test_field_deepcopies_widget_instance(self):
        """

        Tests that each field instance of a form deep copies its widget, ensuring 
        that changes made to a widget's attributes in one field do not affect other fields.

        This is particularly important when using custom widgets or overriding 
        default widget attributes, as it guarantees that each field's widget 
        behaves independently and does not inherit changes made to other fields' widgets.

        """
        class CustomChoiceField(ChoiceField):
            widget = Select(attrs={"class": "my-custom-class"})

        class TestForm(Form):
            field1 = CustomChoiceField(choices=[])
            field2 = CustomChoiceField(choices=[])

        f = TestForm()
        f.fields["field1"].choices = [("1", "1")]
        f.fields["field2"].choices = [("2", "2")]
        self.assertEqual(f.fields["field1"].widget.choices, [("1", "1")])
        self.assertEqual(f.fields["field2"].widget.choices, [("2", "2")])


class DisabledFieldTests(SimpleTestCase):
    def test_disabled_field_has_changed_always_false(self):
        disabled_field = Field(disabled=True)
        self.assertFalse(disabled_field.has_changed("x", "y"))
