import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.forms import (
    CharField,
    Form,
    JSONField,
    Textarea,
    TextInput,
    ValidationError,
)
from django.test import SimpleTestCase


class JSONFieldTest(SimpleTestCase):
    def test_valid(self):
        """

        Tests that a valid JSON string can be successfully cleaned and parsed into a Python dictionary.

        Verifies that the :class:`JSONField` is able to handle valid JSON input and convert it into a native Python data structure.

        The test checks that the output of the cleaning process matches the expected dictionary representation of the input JSON string.

        """
        field = JSONField()
        value = field.clean('{"a": "b"}')
        self.assertEqual(value, {"a": "b"})

    def test_valid_empty(self):
        """

        Tests the behavior of a JSONField with required=False when given empty input.

        Verifies that the clean method correctly handles and returns None for both an empty string and a None value, 
        indicating that these inputs are considered valid for a non-required field.

        """
        field = JSONField(required=False)
        self.assertIsNone(field.clean(""))
        self.assertIsNone(field.clean(None))

    def test_invalid(self):
        field = JSONField()
        with self.assertRaisesMessage(ValidationError, "Enter a valid JSON."):
            field.clean("{some badly formed: json}")

    def test_prepare_value(self):
        """
        Prepares a value to be stored or displayed as a JSON string.

        This method takes an input value, which can be of any type, and returns a JSON-formatted string representation of that value.
        It supports various input types, including dictionaries, lists, strings, and None, and ensures that the output is properly encoded as a JSON string.
        The method also handles Unicode characters and special characters correctly, making it suitable for use with a wide range of input data.
        The resulting string can be used for storage, display, or further processing as needed.
        """
        field = JSONField()
        self.assertEqual(field.prepare_value({"a": "b"}), '{"a": "b"}')
        self.assertEqual(field.prepare_value(None), "null")
        self.assertEqual(field.prepare_value("foo"), '"foo"')
        self.assertEqual(field.prepare_value("你好，世界"), '"你好，世界"')
        self.assertEqual(field.prepare_value({"a": "😀🐱"}), '{"a": "😀🐱"}')
        self.assertEqual(
            field.prepare_value(["你好，世界", "jaźń"]),
            '["你好，世界", "jaźń"]',
        )

    def test_widget(self):
        field = JSONField()
        self.assertIsInstance(field.widget, Textarea)

    def test_custom_widget_kwarg(self):
        """
        Tests the usage of a custom widget in a JSONField via keyword argument.

        Verifies that the widget specified in the field's constructor is correctly
        instantiated and assigned to the field's widget attribute. This ensures
        that custom widgets can be successfully integrated into JSON fields,
        providing flexibility in the field's presentation and interaction.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the widget assigned to the field is not an instance
                            of the expected widget class.
        """
        field = JSONField(widget=TextInput)
        self.assertIsInstance(field.widget, TextInput)

    def test_custom_widget_attribute(self):
        """The widget can be overridden with an attribute."""

        class CustomJSONField(JSONField):
            widget = TextInput

        field = CustomJSONField()
        self.assertIsInstance(field.widget, TextInput)

    def test_converted_value(self):
        """
        ..: 
            Tests the conversion of various JSON values through the :class:`JSONField` to ensure that cleaned values 
            are consistent and can be cleaned multiple times without changing the output. 

            This test verifies that the :class:`JSONField` correctly handles a wide range of JSON data types, 
            including arrays, objects, numbers, strings, booleans, and null values, by checking that the output 
            of the field's :meth:`clean` method is idempotent, meaning that further cleaning of the cleaned value 
            does not alter the result.
        """
        field = JSONField(required=False)
        tests = [
            '["a", "b", "c"]',
            '{"a": 1, "b": 2}',
            "1",
            "1.5",
            '"foo"',
            "true",
            "false",
            "null",
        ]
        for json_string in tests:
            with self.subTest(json_string=json_string):
                val = field.clean(json_string)
                self.assertEqual(field.clean(val), val)

    def test_has_changed(self):
        """

        Tests whether the value of a JSON field has changed.

        This function checks if the initial and current values of a JSON field are equal, 
        returning True if they have changed and False otherwise. The comparison is 
        performed by loading JSON strings into Python dictionaries and comparing their 
        contents, ignoring differences in ordering and formatting.

        The function is used to determine whether the JSON field's value has been 
        modified, which can be useful in various scenarios such as data validation, 
        logging, or triggering events.

        """
        field = JSONField()
        self.assertIs(field.has_changed({"a": True}, '{"a": 1}'), True)
        self.assertIs(field.has_changed({"a": 1, "b": 2}, '{"b": 2, "a": 1}'), False)

    def test_custom_encoder_decoder(self):
        """

        Tests the functionality of a custom JSON encoder and decoder.

        This test case verifies that a custom decoder can correctly convert a JSON string
        into a Python object with a UUID field, and that a custom encoder can convert the
        Python object back into a JSON string.

        The test utilizes a custom decoder class, CustomDecoder, which inherits from
        json.JSONDecoder and overrides the object_hook method to convert the 'uuid' field
        into a UUID object.

        It checks that the JSONField can successfully prepare and clean the value using
        the custom encoder and decoder, ensuring that the UUID is correctly converted
        between its string and object representations.

        """
        class CustomDecoder(json.JSONDecoder):
            def __init__(self, object_hook=None, *args, **kwargs):
                return super().__init__(object_hook=self.as_uuid, *args, **kwargs)

            def as_uuid(self, dct):
                """

                Converts a uuid string in a dictionary to a uuid object.

                If the dictionary contains a 'uuid' key, its corresponding value is 
                converted to a uuid.UUID object. The original dictionary is then 
                returned with the 'uuid' value as a uuid object if it existed. 

                :param dct: The dictionary to convert
                :rtype: dict

                """
                if "uuid" in dct:
                    dct["uuid"] = uuid.UUID(dct["uuid"])
                return dct

        value = {"uuid": uuid.UUID("{c141e152-6550-4172-a784-05448d98204b}")}
        encoded_value = '{"uuid": "c141e152-6550-4172-a784-05448d98204b"}'
        field = JSONField(encoder=DjangoJSONEncoder, decoder=CustomDecoder)
        self.assertEqual(field.prepare_value(value), encoded_value)
        self.assertEqual(field.clean(encoded_value), value)

    def test_formfield_disabled(self):
        """
        Checks if a disabled JSON form field is rendered correctly with its initial value when the form is instantiated. The function verifies that the initial value of the JSON field is displayed in the form, even when the field is disabled, and that the value is properly escaped for HTML rendering.
        """
        class JSONForm(Form):
            json_field = JSONField(disabled=True)

        form = JSONForm({"json_field": '["bar"]'}, initial={"json_field": ["foo"]})
        self.assertIn("[&quot;foo&quot;]</textarea>", form.as_p())

    def test_redisplay_none_input(self):
        """

        Tests the redisplay of a JSON form when no input is provided.

        This test case verifies the behavior of a JSON form when it is initialized with either an empty dictionary or a dictionary containing a null value for the JSON field.
        It checks that the form correctly displays the null value, includes the null value in its HTML representation, and raises a validation error indicating that the field is required.
        The test covers two scenarios: an empty input dictionary and a dictionary with an explicit null value for the JSON field.

        """
        class JSONForm(Form):
            json_field = JSONField(required=True)

        tests = [
            {},
            {"json_field": None},
        ]
        for data in tests:
            with self.subTest(data=data):
                form = JSONForm(data)
                self.assertEqual(form["json_field"].value(), "null")
                self.assertIn("null</textarea>", form.as_p())
                self.assertEqual(form.errors["json_field"], ["This field is required."])

    def test_redisplay_wrong_input(self):
        """
        Displaying a bound form (typically due to invalid input). The form
        should not overquote JSONField inputs.
        """

        class JSONForm(Form):
            name = CharField(max_length=2)
            json_field = JSONField()

        # JSONField input is valid, name is too long.
        form = JSONForm({"name": "xyz", "json_field": '["foo"]'})
        self.assertNotIn("json_field", form.errors)
        self.assertIn("[&quot;foo&quot;]</textarea>", form.as_p())
        # Invalid JSONField.
        form = JSONForm({"name": "xy", "json_field": '{"foo"}'})
        self.assertEqual(form.errors["json_field"], ["Enter a valid JSON."])
        self.assertIn("{&quot;foo&quot;}</textarea>", form.as_p())
