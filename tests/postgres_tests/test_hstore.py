import json

from django.core import checks, exceptions, serializers
from django.db import connection
from django.db.models import F, OuterRef, Subquery
from django.db.models.expressions import RawSQL
from django.forms import Form
from django.test.utils import CaptureQueriesContext, isolate_apps

from . import PostgreSQLSimpleTestCase, PostgreSQLTestCase
from .models import HStoreModel, PostgreSQLModel

try:
    from django.contrib.postgres import forms
    from django.contrib.postgres.fields import HStoreField
    from django.contrib.postgres.fields.hstore import KeyTransform
    from django.contrib.postgres.validators import KeysValidator
except ImportError:
    pass


class SimpleTests(PostgreSQLTestCase):
    def test_save_load_success(self):
        """

        Tests the successful saving and loading of an instance of HStoreModel.

        Verifies that an instance with a given value can be saved to the database and then reloaded with the same value intact.

        """
        value = {"a": "b"}
        instance = HStoreModel(field=value)
        instance.save()
        reloaded = HStoreModel.objects.get()
        self.assertEqual(reloaded.field, value)

    def test_null(self):
        """
        Tests that a null value is correctly saved and retrieved from the database for an HStore field.

        Verifies that when an instance of the model is created with a null field value, saved to the database, and then reloaded, the field value remains null.

        This test ensures data integrity and consistency for null values in HStore fields, confirming that the database interactions do not inadvertently modify or lose the null state of the field.
        """
        instance = HStoreModel(field=None)
        instance.save()
        reloaded = HStoreModel.objects.get()
        self.assertIsNone(reloaded.field)

    def test_value_null(self):
        """

        Tests the storage and retrieval of a null value in an HStore field.

        Verifies that a value with a null attribute can be saved to the database and 
        retrieved correctly, ensuring that the null value is preserved.

        """
        value = {"a": None}
        instance = HStoreModel(field=value)
        instance.save()
        reloaded = HStoreModel.objects.get()
        self.assertEqual(reloaded.field, value)

    def test_key_val_cast_to_string(self):
        """
        Tests if key-value pairs in an HStore field are correctly cast to strings.

        This test case ensures that the values of an HStore field are converted to strings, 
        regardless of their initial data type, when retrieved from the database. It also 
        verifies that the casting does not affect the filtering of HStore fields based on 
        specific keys and values, or when checking for the presence of certain keys.

        The test covers various data types and special characters in keys and values, 
        including numeric keys and non-ASCII characters. It checks the equivalence of the 
        original and retrieved HStore values, as well as the correctness of filtering 
        operations using the `field__a` and `field__has_keys` lookup types.
        """
        value = {"a": 1, "b": "B", 2: "c", "ï": "ê"}
        expected_value = {"a": "1", "b": "B", "2": "c", "ï": "ê"}

        instance = HStoreModel.objects.create(field=value)
        instance = HStoreModel.objects.get()
        self.assertEqual(instance.field, expected_value)

        instance = HStoreModel.objects.get(field__a=1)
        self.assertEqual(instance.field, expected_value)

        instance = HStoreModel.objects.get(field__has_keys=[2, "a", "ï"])
        self.assertEqual(instance.field, expected_value)

    def test_array_field(self):
        value = [
            {"a": 1, "b": "B", 2: "c", "ï": "ê"},
            {"a": 1, "b": "B", 2: "c", "ï": "ê"},
        ]
        expected_value = [
            {"a": "1", "b": "B", "2": "c", "ï": "ê"},
            {"a": "1", "b": "B", "2": "c", "ï": "ê"},
        ]
        instance = HStoreModel.objects.create(array_field=value)
        instance.refresh_from_db()
        self.assertEqual(instance.array_field, expected_value)


class TestQuerying(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.objs = HStoreModel.objects.bulk_create(
            [
                HStoreModel(field={"a": "b"}),
                HStoreModel(field={"a": "b", "c": "d"}),
                HStoreModel(field={"c": "d"}),
                HStoreModel(field={}),
                HStoreModel(field=None),
                HStoreModel(field={"cat": "TigrOu", "breed": "birman"}),
                HStoreModel(field={"cat": "minou", "breed": "ragdoll"}),
                HStoreModel(field={"cat": "kitty", "breed": "Persian"}),
                HStoreModel(field={"cat": "Kit Kat", "breed": "persian"}),
            ]
        )

    def test_exact(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__exact={"a": "b"}), self.objs[:1]
        )

    def test_contained_by(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__contained_by={"a": "b", "c": "d"}),
            self.objs[:4],
        )

    def test_contains(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__contains={"a": "b"}), self.objs[:2]
        )

    def test_in_generator(self):
        """
        Tests filtering of HStoreModel objects using a generator for the 'in' lookup.

            This test case verifies that the 'in' lookup can handle a generator that yields
            dictionaries, returning the correct subset of objects from the database.

            Args:
                None

            Returns:
                None

            Note:
                The test checks if the filter returns the first object from the list of objects,
                asserting that the sequence of filtered objects matches the expected result.

        """
        def search():
            yield {"a": "b"}

        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__in=search()), self.objs[:1]
        )

    def test_has_key(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__has_key="c"), self.objs[1:3]
        )

    def test_has_keys(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__has_keys=["a", "c"]), self.objs[1:2]
        )

    def test_has_any_keys(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__has_any_keys=["a", "c"]), self.objs[:3]
        )

    def test_key_transform(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__a="b"), self.objs[:2]
        )

    def test_key_transform_raw_expression(self):
        expr = RawSQL("%s::hstore", ["x => b, y => c"])
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__a=KeyTransform("x", expr)), self.objs[:2]
        )

    def test_key_transform_annotation(self):
        qs = HStoreModel.objects.annotate(a=F("field__a"))
        self.assertCountEqual(
            qs.values_list("a", flat=True),
            ["b", "b", None, None, None, None, None, None, None],
        )

    def test_keys(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__keys=["a"]), self.objs[:1]
        )

    def test_values(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__values=["b"]), self.objs[:1]
        )

    def test_field_chaining_contains(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__a__contains="b"), self.objs[:2]
        )

    def test_field_chaining_icontains(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__cat__icontains="INo"),
            [self.objs[6]],
        )

    def test_field_chaining_startswith(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__cat__startswith="kit"),
            [self.objs[7]],
        )

    def test_field_chaining_istartswith(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__cat__istartswith="kit"),
            self.objs[7:],
        )

    def test_field_chaining_endswith(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__cat__endswith="ou"),
            [self.objs[6]],
        )

    def test_field_chaining_iendswith(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__cat__iendswith="ou"),
            self.objs[5:7],
        )

    def test_field_chaining_iexact(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__breed__iexact="persian"),
            self.objs[7:],
        )

    def test_field_chaining_regex(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__cat__regex=r"ou$"),
            [self.objs[6]],
        )

    def test_field_chaining_iregex(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__cat__iregex=r"oU$"),
            self.objs[5:7],
        )

    def test_order_by_field(self):
        """

        Tests the ordering of HStoreModel objects by a specific field.

        This test creates multiple HStoreModel instances with different values for the 'g' key in the 'field' dictionary.
        It then verifies that the objects are ordered correctly when retrieved using the 'order_by' method with the 'field__g' argument.
        The expected ordering is based on the numeric value of the 'g' key, demonstrating that the 'order_by' method correctly handles string values that represent numbers.

        """
        more_objs = (
            HStoreModel.objects.create(field={"g": "637"}),
            HStoreModel.objects.create(field={"g": "002"}),
            HStoreModel.objects.create(field={"g": "042"}),
            HStoreModel.objects.create(field={"g": "981"}),
        )
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__has_key="g").order_by("field__g"),
            [more_objs[1], more_objs[2], more_objs[0], more_objs[3]],
        )

    def test_keys_contains(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__keys__contains=["a"]), self.objs[:2]
        )

    def test_values_overlap(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__values__overlap=["b", "d"]), self.objs[:3]
        )

    def test_key_isnull(self):
        """
        Tests if the key in a model field is null.

        This function verifies the functionality of filtering objects based on the presence or absence of a value for a specific key in a dictionary field.
        It creates an object with a null value for a certain key and then checks if the object is correctly filtered in and out of query results when querying for null or non-null values for that key.
        """
        obj = HStoreModel.objects.create(field={"a": None})
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__a__isnull=True),
            self.objs[2:9] + [obj],
        )
        self.assertSequenceEqual(
            HStoreModel.objects.filter(field__a__isnull=False), self.objs[:2]
        )

    def test_usage_in_subquery(self):
        self.assertSequenceEqual(
            HStoreModel.objects.filter(id__in=HStoreModel.objects.filter(field__a="b")),
            self.objs[:2],
        )

    def test_key_sql_injection(self):
        """

        Test that the HStoreModel filter prevents SQL injection attacks.

        Verifies that a malicious query with a SQL injection payload is properly escaped
        and does not match any existing objects. Also checks that the resulting SQL query
        contains the escaped payload, ensuring that the database is not vulnerable to
        injection attacks.

        This test demonstrates the security of the HStoreModel filtering mechanism against
        common SQL injection techniques.

        """
        with CaptureQueriesContext(connection) as queries:
            self.assertFalse(
                HStoreModel.objects.filter(
                    **{
                        "field__test' = 'a') OR 1 = 1 OR ('d": "x",
                    }
                ).exists()
            )
        self.assertIn(
            """."field" -> 'test'' = ''a'') OR 1 = 1 OR (''d') = 'x' """,
            queries[0]["sql"],
        )

    def test_obj_subquery_lookup(self):
        qs = HStoreModel.objects.annotate(
            value=Subquery(
                HStoreModel.objects.filter(pk=OuterRef("pk")).values("field")
            ),
        ).filter(value__a="b")
        self.assertSequenceEqual(qs, self.objs[:2])


@isolate_apps("postgres_tests")
class TestChecks(PostgreSQLSimpleTestCase):
    def test_invalid_default(self):
        class MyModel(PostgreSQLModel):
            field = HStoreField(default={})

        model = MyModel()
        self.assertEqual(
            model.check(),
            [
                checks.Warning(
                    msg=(
                        "HStoreField default should be a callable instead of an "
                        "instance so that it's not shared between all field "
                        "instances."
                    ),
                    hint="Use a callable instead, e.g., use `dict` instead of `{}`.",
                    obj=MyModel._meta.get_field("field"),
                    id="fields.E010",
                )
            ],
        )

    def test_valid_default(self):
        """
        Tests that a model with an HStoreField having a default value of an empty dictionary is valid.

        This test case ensures that the model validation process does not raise any errors when an instance of the model is created with the default value for the HStoreField. It verifies that the model's check method returns an empty list, indicating that the model is valid and there are no errors or warnings.
        """
        class MyModel(PostgreSQLModel):
            field = HStoreField(default=dict)

        self.assertEqual(MyModel().check(), [])


class TestSerialization(PostgreSQLSimpleTestCase):
    test_data = json.dumps(
        [
            {
                "model": "postgres_tests.hstoremodel",
                "pk": None,
                "fields": {
                    "field": json.dumps({"a": "b"}),
                    "array_field": json.dumps(
                        [
                            json.dumps({"a": "b"}),
                            json.dumps({"b": "a"}),
                        ]
                    ),
                },
            }
        ]
    )

    def test_dumping(self):
        """
        Tests the dumping of HStoreModel instances to JSON.

        Verifies that the serialization of an HStoreModel instance with field and array_field attributes matches the expected JSON output.

        This test ensures that the model's data is correctly converted to JSON format, including nested fields and array fields, and that the resulting JSON is consistent with the predefined test data.
        """
        instance = HStoreModel(field={"a": "b"}, array_field=[{"a": "b"}, {"b": "a"}])
        data = serializers.serialize("json", [instance])
        self.assertEqual(json.loads(data), json.loads(self.test_data))

    def test_loading(self):
        instance = list(serializers.deserialize("json", self.test_data))[0].object
        self.assertEqual(instance.field, {"a": "b"})
        self.assertEqual(instance.array_field, [{"a": "b"}, {"b": "a"}])

    def test_roundtrip_with_null(self):
        instance = HStoreModel(field={"a": "b", "c": None})
        data = serializers.serialize("json", [instance])
        new_instance = list(serializers.deserialize("json", data))[0].object
        self.assertEqual(instance.field, new_instance.field)


class TestValidation(PostgreSQLSimpleTestCase):
    def test_not_a_string(self):
        """
        Tests the validation of a non-string value in an HStoreField.

        The test checks that a ValidationError is raised when a non-string value is passed to the clean method.
        It verifies the error code is 'not_a_string' and the error message is correctly formatted, indicating the field's value should be a string or null.
        """
        field = HStoreField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean({"a": 1}, None)
        self.assertEqual(cm.exception.code, "not_a_string")
        self.assertEqual(
            cm.exception.message % cm.exception.params,
            "The value of “a” is not a string or null.",
        )

    def test_none_allowed_as_value(self):
        """
        Tests if the HStoreField allows None as a valid value.

        Verifies that when the given value is None, the field's clean method returns the input value unchanged, 
        indicating that None is an allowed value for this field type. This ensures that the field can handle 
        and store null values as expected.
        """
        field = HStoreField()
        self.assertEqual(field.clean({"a": None}, None), {"a": None})


class TestFormField(PostgreSQLSimpleTestCase):
    def test_valid(self):
        """

        Tests the cleaning of a valid HStore field value.

        Verifies that a valid HStore dictionary string is correctly deserialized into a Python dictionary.

        The test checks that a given input string in a specific HStore format is cleaned and converted into the expected dictionary output, ensuring the correctness of the HStore field cleaning process.

        """
        field = forms.HStoreField()
        value = field.clean('{"a": "b"}')
        self.assertEqual(value, {"a": "b"})

    def test_invalid_json(self):
        field = forms.HStoreField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean('{"a": "b"')
        self.assertEqual(cm.exception.messages[0], "Could not load JSON data.")
        self.assertEqual(cm.exception.code, "invalid_json")

    def test_non_dict_json(self):
        """
        Tests that the HStoreField raises a ValidationError when given a non-dictionary JSON input.

        Verifies that the field correctly identifies and rejects JSON data that is not in dictionary format, 
        such as lists or other non-key/value pair structures, and that the resulting error message is 
        informative and the error code is 'invalid_format'.
        """
        field = forms.HStoreField()
        msg = "Input must be a JSON dictionary."
        with self.assertRaisesMessage(exceptions.ValidationError, msg) as cm:
            field.clean('["a", "b", 1]')
        self.assertEqual(cm.exception.code, "invalid_format")

    def test_not_string_values(self):
        field = forms.HStoreField()
        value = field.clean('{"a": 1}')
        self.assertEqual(value, {"a": "1"})

    def test_none_value(self):
        field = forms.HStoreField()
        value = field.clean('{"a": null}')
        self.assertEqual(value, {"a": None})

    def test_empty(self):
        """

        Tests that an empty string is cleaned to an empty dictionary by HStoreField.

        When required is set to False, an empty string input should result in an empty dictionary.
        This ensures that the field correctly handles cases where no data is provided.

        """
        field = forms.HStoreField(required=False)
        value = field.clean("")
        self.assertEqual(value, {})

    def test_model_field_formfield(self):
        """
        Tests that a model field of type HStoreField generates a form field of type HStoreField.

        Verifies the correct mapping of a specific model field type to its corresponding form field, ensuring that the generated form field matches the expected type, which is a crucial step in creating forms based on model definitions.

        This test case validates the proper functioning of the formfield method for HStoreField model fields, which is essential for the creation of form representations of database model fields, particularly those requiring specialized handling like HStore fields.

        The test checks if the form field generated from an HStoreField instance is indeed an instance of forms.HStoreField, aligning with the expectations for field type mapping in form handling frameworks.
        """
        model_field = HStoreField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, forms.HStoreField)

    def test_field_has_changed(self):
        class HStoreFormTest(Form):
            f1 = forms.HStoreField()

        form_w_hstore = HStoreFormTest()
        self.assertFalse(form_w_hstore.has_changed())

        form_w_hstore = HStoreFormTest({"f1": '{"a": 1}'})
        self.assertTrue(form_w_hstore.has_changed())

        form_w_hstore = HStoreFormTest({"f1": '{"a": 1}'}, initial={"f1": '{"a": 1}'})
        self.assertFalse(form_w_hstore.has_changed())

        form_w_hstore = HStoreFormTest({"f1": '{"a": 2}'}, initial={"f1": '{"a": 1}'})
        self.assertTrue(form_w_hstore.has_changed())

        form_w_hstore = HStoreFormTest({"f1": '{"a": 1}'}, initial={"f1": {"a": 1}})
        self.assertFalse(form_w_hstore.has_changed())

        form_w_hstore = HStoreFormTest({"f1": '{"a": 2}'}, initial={"f1": {"a": 1}})
        self.assertTrue(form_w_hstore.has_changed())

    def test_prepare_value(self):
        field = forms.HStoreField()
        self.assertEqual(
            field.prepare_value({"aira_maplayer": "Αρδευτικό δίκτυο"}),
            '{"aira_maplayer": "Αρδευτικό δίκτυο"}',
        )


class TestValidator(PostgreSQLSimpleTestCase):
    def test_simple_valid(self):
        """

        Tests the validation of a dictionary with simple valid keys.

        This test case checks if a dictionary containing the required keys ('a' and 'b') and an optional key ('c') is successfully validated by the KeysValidator.

        """
        validator = KeysValidator(keys=["a", "b"])
        validator({"a": "foo", "b": "bar", "c": "baz"})

    def test_missing_keys(self):
        """
        Tests that a KeysValidator instance correctly raises a ValidationError when a dictionary is missing required keys.

        The function validates a test case where a dictionary with some, but not all, required keys is passed to a KeysValidator.
        It checks that the resulting ValidationError includes the expected error message and code, ensuring that the validator correctly identifies and reports missing keys.
        """
        validator = KeysValidator(keys=["a", "b"])
        with self.assertRaises(exceptions.ValidationError) as cm:
            validator({"a": "foo", "c": "baz"})
        self.assertEqual(cm.exception.messages[0], "Some keys were missing: b")
        self.assertEqual(cm.exception.code, "missing_keys")

    def test_strict_valid(self):
        """
        Tests the strict validation of a dictionary against a set of predefined keys.

        This method verifies that a dictionary conforms to the expected structure by 
        containing only the specified keys and no additional ones. The validation is 
        performed in strict mode, which means any extra key in the dictionary will 
        result in a validation failure.

        :raises: Exception if the dictionary contains any keys outside the predefined set.

        """
        validator = KeysValidator(keys=["a", "b"], strict=True)
        validator({"a": "foo", "b": "bar"})

    def test_extra_keys(self):
        validator = KeysValidator(keys=["a", "b"], strict=True)
        with self.assertRaises(exceptions.ValidationError) as cm:
            validator({"a": "foo", "b": "bar", "c": "baz"})
        self.assertEqual(cm.exception.messages[0], "Some unknown keys were provided: c")
        self.assertEqual(cm.exception.code, "extra_keys")

    def test_custom_messages(self):
        """
        Tests that the KeysValidator class correctly raises ValidationErrors with custom messages.

        This function checks that when the required keys are missing from the input dictionary,
        the validator raises an error with a custom message specified in the 'messages' parameter.
        It also tests that when extra keys are provided in the input dictionary, the validator
        raises an error with a default message. The function verifies that the error messages
        and codes are as expected in both cases.

        :raises: ValidationError

        """
        messages = {
            "missing_keys": "Foobar",
        }
        validator = KeysValidator(keys=["a", "b"], strict=True, messages=messages)
        with self.assertRaises(exceptions.ValidationError) as cm:
            validator({"a": "foo", "c": "baz"})
        self.assertEqual(cm.exception.messages[0], "Foobar")
        self.assertEqual(cm.exception.code, "missing_keys")
        with self.assertRaises(exceptions.ValidationError) as cm:
            validator({"a": "foo", "b": "bar", "c": "baz"})
        self.assertEqual(cm.exception.messages[0], "Some unknown keys were provided: c")
        self.assertEqual(cm.exception.code, "extra_keys")

    def test_deconstruct(self):
        """
        Deconstructs the KeysValidator instance into its constituent parts, including the path to the validator class and the arguments used to instantiate it. 

        This method returns a tuple containing the path, args, and kwargs, which can be used to reconstruct the validator instance. The path is the fully qualified name of the KeysValidator class, args is an empty tuple as the class does not take any positional arguments, and kwargs is a dictionary containing the keys, strict, and messages parameters used to create the validator. 

        The deconstructed parts can be used for serialization or other forms of validation reconstruction.
        """
        messages = {
            "missing_keys": "Foobar",
        }
        validator = KeysValidator(keys=["a", "b"], strict=True, messages=messages)
        path, args, kwargs = validator.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.validators.KeysValidator")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs, {"keys": ["a", "b"], "strict": True, "messages": messages}
        )
