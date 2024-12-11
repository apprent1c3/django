import unittest
import uuid

from django.core.checks import Error
from django.core.checks import Warning as DjangoWarning
from django.db import connection, models
from django.db.models.functions import Coalesce, LPad, Pi
from django.test import SimpleTestCase, TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.test.utils import isolate_apps, override_settings
from django.utils.functional import lazy
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.version import get_docs_version


@isolate_apps("invalid_models_tests")
class AutoFieldTests(SimpleTestCase):
    def test_valid_case(self):
        class Model(models.Model):
            id = models.AutoField(primary_key=True)

        field = Model._meta.get_field("id")
        self.assertEqual(field.check(), [])

    def test_primary_key(self):
        # primary_key must be True. Refs #12467.
        class Model(models.Model):
            field = models.AutoField(primary_key=False)

            # Prevent Django from autocreating `id` AutoField, which would
            # result in an error, because a model must have exactly one
            # AutoField.
            another = models.IntegerField(primary_key=True)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "AutoFields must set primary_key=True.",
                    obj=field,
                    id="fields.E100",
                ),
            ],
        )

    def test_max_length_warning(self):
        class Model(models.Model):
            auto = models.AutoField(primary_key=True, max_length=2)

        field = Model._meta.get_field("auto")
        self.assertEqual(
            field.check(),
            [
                DjangoWarning(
                    "'max_length' is ignored when used with %s."
                    % field.__class__.__name__,
                    hint="Remove 'max_length' from field",
                    obj=field,
                    id="fields.W122",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class BinaryFieldTests(SimpleTestCase):
    def test_valid_default_value(self):
        """
        Tests that BinaryField default values are valid.

        This test case checks that BinaryField instances with default values can pass
        the field's validation checks. Specifically, it verifies that fields with both
        non-null and null default values do not raise any errors during validation.

        The test covers the following scenarios:
        - BinaryField with a non-null default value (e.g., b'test')
        - BinaryField with a null default value (e.g., None)

        It ensures that both cases produce no validation errors, confirming the fields
        are properly configured and functional.
        """
        class Model(models.Model):
            field1 = models.BinaryField(default=b"test")
            field2 = models.BinaryField(default=None)

        for field_name in ("field1", "field2"):
            field = Model._meta.get_field(field_name)
            self.assertEqual(field.check(), [])

    def test_str_default_value(self):
        class Model(models.Model):
            field = models.BinaryField(default="test")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "BinaryField's default cannot be a string. Use bytes content "
                    "instead.",
                    obj=field,
                    id="fields.E170",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class CharFieldTests(TestCase):
    def test_valid_field(self):
        class Model(models.Model):
            field = models.CharField(
                max_length=255,
                choices=[
                    ("1", "item1"),
                    ("2", "item2"),
                ],
                db_index=True,
            )

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(), [])

    def test_missing_max_length(self):
        class Model(models.Model):
            field = models.CharField()

        field = Model._meta.get_field("field")
        expected = (
            []
            if connection.features.supports_unlimited_charfield
            else [
                Error(
                    "CharFields must define a 'max_length' attribute.",
                    obj=field,
                    id="fields.E120",
                ),
            ]
        )
        self.assertEqual(field.check(), expected)

    def test_negative_max_length(self):
        """
        Tests the validation of a CharField in a model when its max_length is set to a negative value.

        This test case checks if the field validation correctly raises an error when the max_length attribute is set to an invalid negative integer value. The test verifies that the expected error message is returned, indicating that 'max_length' must be a positive integer.
        """
        class Model(models.Model):
            field = models.CharField(max_length=-1)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'max_length' must be a positive integer.",
                    obj=field,
                    id="fields.E121",
                ),
            ],
        )

    def test_bad_max_length_value(self):
        class Model(models.Model):
            field = models.CharField(max_length="bad")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'max_length' must be a positive integer.",
                    obj=field,
                    id="fields.E121",
                ),
            ],
        )

    def test_str_max_length_value(self):
        class Model(models.Model):
            field = models.CharField(max_length="20")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'max_length' must be a positive integer.",
                    obj=field,
                    id="fields.E121",
                ),
            ],
        )

    def test_str_max_length_type(self):
        """
        Tests that a CharField with an invalid max_length type raises the correct error.

        The test case checks that setting max_length to a boolean value (True) results in a fields.E121 error, 
        indicating that 'max_length' must be a positive integer. This ensures the field is properly validated 
        to prevent potential data integrity issues.
        """
        class Model(models.Model):
            field = models.CharField(max_length=True)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'max_length' must be a positive integer.",
                    obj=field,
                    id="fields.E121",
                ),
            ],
        )

    def test_non_iterable_choices(self):
        class Model(models.Model):
            field = models.CharField(max_length=10, choices="bad")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'choices' must be a mapping (e.g. a dictionary) or an iterable "
                    "(e.g. a list or tuple).",
                    obj=field,
                    id="fields.E004",
                ),
            ],
        )

    def test_non_iterable_choices_two_letters(self):
        """Two letters isn't a valid choice pair."""

        class Model(models.Model):
            field = models.CharField(max_length=10, choices=["ab"])

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'choices' must be a mapping of actual values to human readable "
                    "names or an iterable containing (actual value, human readable "
                    "name) tuples.",
                    obj=field,
                    id="fields.E005",
                ),
            ],
        )

    def test_iterable_of_iterable_choices(self):
        class ThingItem:
            def __init__(self, value, display):
                """
                Initializes an instance of the class with a value and a display representation.

                :param value: The underlying value of the instance.
                :param display: The display representation of the instance.
                """
                self.value = value
                self.display = display

            def __iter__(self):
                return iter((self.value, self.display))

            def __len__(self):
                return 2

        class Things:
            def __iter__(self):
                return iter((ThingItem(1, 2), ThingItem(3, 4)))

        class ThingWithIterableChoices(models.Model):
            thing = models.CharField(max_length=100, blank=True, choices=Things())

        self.assertEqual(ThingWithIterableChoices._meta.get_field("thing").check(), [])

    def test_choices_containing_non_pairs(self):
        class Model(models.Model):
            field = models.CharField(max_length=10, choices=[(1, 2, 3), (1, 2, 3)])

        class Model2(models.Model):
            field = models.IntegerField(choices=[0])

        for model in (Model, Model2):
            with self.subTest(model.__name__):
                field = model._meta.get_field("field")
                self.assertEqual(
                    field.check(),
                    [
                        Error(
                            "'choices' must be a mapping of actual values to human "
                            "readable names or an iterable containing (actual value, "
                            "human readable name) tuples.",
                            obj=field,
                            id="fields.E005",
                        ),
                    ],
                )

    def test_choices_containing_lazy(self):
        """
        Tests that CharField choices containing lazy translations do not raise any validation errors.

        Checks that the field's validation does not fail when its choices contain lazy translations,
        ensuring that the use of lazy translations in choices does not cause any issues.

        This test case verifies that the check method of a model field returns an empty list,
        indicating no validation errors, when the field's choices contain lazy translations.
        """
        class Model(models.Model):
            field = models.CharField(
                max_length=10, choices=[["1", _("1")], ["2", _("2")]]
            )

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_lazy_choices(self):
        class Model(models.Model):
            field = models.CharField(
                max_length=10, choices=lazy(lambda: [[1, "1"], [2, "2"]], tuple)()
            )

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_choices_named_group(self):
        """

        Checks that the choices for a named group in a model's CharField are correctly defined.
        The function verifies that the 'check' method of the field returns an empty list,
        indicating that the choices are properly formed and do not contain any errors.
        This is particularly important for fields with nested choices, where a named group
        should contain a list of tuples with two elements each: a value and a human-readable name.

        """
        class Model(models.Model):
            field = models.CharField(
                max_length=10,
                choices=[
                    ["knights", [["L", "Lancelot"], ["G", "Galahad"]]],
                    ["wizards", [["T", "Tim the Enchanter"]]],
                    ["R", "Random character"],
                ],
            )

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_choices_named_group_non_pairs(self):
        """
        Tests whether a CharField with choices defined as a named group with non-pair values raises a validation error.

        The choices are defined with a nested list structure but without providing both an actual value and a human-readable name, which is the expected format for CharField choices. 

        This test case verifies that Sphinx validation correctly identifies and reports the error when such a malformed choices definition is provided.
        """
        class Model(models.Model):
            field = models.CharField(
                max_length=10,
                choices=[["knights", [["L", "Lancelot", "Du Lac"]]]],
            )

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'choices' must be a mapping of actual values to human readable "
                    "names or an iterable containing (actual value, human readable "
                    "name) tuples.",
                    obj=field,
                    id="fields.E005",
                ),
            ],
        )

    def test_choices_named_group_bad_structure(self):
        class Model(models.Model):
            field = models.CharField(
                max_length=10,
                choices=[
                    [
                        "knights",
                        [
                            ["Noble", [["G", "Galahad"]]],
                            ["Combative", [["L", "Lancelot"]]],
                        ],
                    ],
                ],
            )

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'choices' must be a mapping of actual values to human readable "
                    "names or an iterable containing (actual value, human readable "
                    "name) tuples.",
                    obj=field,
                    id="fields.E005",
                ),
            ],
        )

    def test_choices_named_group_lazy(self):
        """
        Tests that the check functionality for a model field with named group lazy choices works correctly.

        This test case verifies that the field's validation does not raise any errors when using lazy translated choices with named groups, ensuring the field's configuration is correctly validated.

        Args: None

        Returns: None
        """
        class Model(models.Model):
            field = models.CharField(
                max_length=10,
                choices=[
                    [_("knights"), [["L", _("Lancelot")], ["G", _("Galahad")]]],
                    ["R", _("Random character")],
                ],
            )

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_choices_in_max_length(self):
        class Model(models.Model):
            field = models.CharField(
                max_length=2,
                choices=[("ABC", "Value Too Long!"), ("OK", "Good")],
            )
            group = models.CharField(
                max_length=2,
                choices=[
                    ("Nested", [("OK", "Good"), ("Longer", "Longer")]),
                    ("Grouped", [("Bad", "Bad")]),
                ],
            )

        for name, choice_max_length in (("field", 3), ("group", 6)):
            with self.subTest(name):
                field = Model._meta.get_field(name)
                self.assertEqual(
                    field.check(),
                    [
                        Error(
                            "'max_length' is too small to fit the longest value "
                            "in 'choices' (%d characters)." % choice_max_length,
                            obj=field,
                            id="fields.E009",
                        ),
                    ],
                )

    def test_bad_db_index_value(self):
        """
        Tests that a CharField with an invalid db_index value raises the correct error.

        The function checks that setting db_index to a string other than 'True' or 'False' (or None), 
        which is an invalid value, results in an error being reported, specifically the 'fields.E006' error.
        """
        class Model(models.Model):
            field = models.CharField(max_length=10, db_index="bad")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'db_index' must be None, True or False.",
                    obj=field,
                    id="fields.E006",
                ),
            ],
        )

    def test_bad_validators(self):
        class Model(models.Model):
            field = models.CharField(max_length=10, validators=[True])

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "All 'validators' must be callable.",
                    hint=(
                        "validators[0] (True) isn't a function or instance of a "
                        "validator class."
                    ),
                    obj=field,
                    id="fields.E008",
                ),
            ],
        )

    @unittest.skipUnless(connection.vendor == "mysql", "Test valid only for MySQL")
    def test_too_long_char_field_under_mysql(self):
        """

        Tests the validation of a CharField with a max_length greater than 255 under MySQL.
        This test checks if the Django database validator correctly raises a warning when a CharField
        with a length greater than 255 is defined as unique, as this may not be supported by MySQL.

        The test utilizes the DatabaseValidation class from the Django MySQL backend to validate a
        model field and verifies that the expected warning is returned.

        """
        from django.db.backends.mysql.validation import DatabaseValidation

        class Model(models.Model):
            field = models.CharField(unique=True, max_length=256)

        field = Model._meta.get_field("field")
        validator = DatabaseValidation(connection=connection)
        self.assertEqual(
            validator.check_field(field),
            [
                DjangoWarning(
                    "%s may not allow unique CharFields to have a max_length > "
                    "255." % connection.display_name,
                    hint=(
                        "See: https://docs.djangoproject.com/en/%s/ref/databases/"
                        "#mysql-character-fields" % get_docs_version()
                    ),
                    obj=field,
                    id="mysql.W003",
                )
            ],
        )

    def test_db_collation(self):
        """
        Checks the validation of database collation on a CharField.

        This test case verifies that a CharField with a specified database collation
        raises the correct error if the database backend does not support collation on CharFields.
        The test ensures the field.check method returns the expected error or an empty list
        depending on the database's support for collation on CharFields.
        """
        class Model(models.Model):
            field = models.CharField(max_length=100, db_collation="anything")

        field = Model._meta.get_field("field")
        error = Error(
            "%s does not support a database collation on CharFields."
            % connection.display_name,
            id="fields.E190",
            obj=field,
        )
        expected = (
            [] if connection.features.supports_collation_on_charfield else [error]
        )
        self.assertEqual(field.check(databases=self.databases), expected)

    def test_db_collation_required_db_features(self):
        class Model(models.Model):
            field = models.CharField(max_length=100, db_collation="anything")

            class Meta:
                required_db_features = {"supports_collation_on_charfield"}

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(databases=self.databases), [])


@isolate_apps("invalid_models_tests")
class DateFieldTests(SimpleTestCase):
    maxDiff = None

    def test_auto_now_and_auto_now_add_raise_error(self):
        """
        Tests that using both `auto_now` and `auto_now_add` options on a DateTimeField raises a validation error.

        The function verifies that when these mutually exclusive options are combined, either with or without a `default` value, the expected error is raised. This ensures that the model field validation correctly enforces the restriction that only one of `auto_now`, `auto_now_add`, or `default` can be specified for a DateTimeField. 

        It covers four different scenarios, checking each for the correct error message, and confirms that the validation error is raised as expected.
        """
        class Model(models.Model):
            field0 = models.DateTimeField(auto_now=True, auto_now_add=True, default=now)
            field1 = models.DateTimeField(
                auto_now=True, auto_now_add=False, default=now
            )
            field2 = models.DateTimeField(
                auto_now=False, auto_now_add=True, default=now
            )
            field3 = models.DateTimeField(
                auto_now=True, auto_now_add=True, default=None
            )

        expected = []
        checks = []
        for i in range(4):
            field = Model._meta.get_field("field%d" % i)
            expected.append(
                Error(
                    "The options auto_now, auto_now_add, and default "
                    "are mutually exclusive. Only one of these options "
                    "may be present.",
                    obj=field,
                    id="fields.E160",
                )
            )
            checks.extend(field.check())
            self.assertEqual(checks, expected)

    def test_fix_default_value(self):
        """

        Tests that a warning is raised when a fixed default value is provided for a DateField.

        Checks that using the result of now() or now().date() as the default value for a DateField
        raises a warning, while using the now function itself does not.

        Verifies that the expected warnings are raised for the fields with fixed default values,
        and that the correct messages and hints are provided.

        """
        class Model(models.Model):
            field_dt = models.DateField(default=now())
            field_d = models.DateField(default=now().date())
            field_now = models.DateField(default=now)

        field_dt = Model._meta.get_field("field_dt")
        field_d = Model._meta.get_field("field_d")
        field_now = Model._meta.get_field("field_now")
        errors = field_dt.check()
        errors.extend(field_d.check())
        errors.extend(field_now.check())  # doesn't raise a warning
        self.assertEqual(
            errors,
            [
                DjangoWarning(
                    "Fixed default value provided.",
                    hint="It seems you set a fixed date / time / datetime "
                    "value as default for this field. This may not be "
                    "what you want. If you want to have the current date "
                    "as default, use `django.utils.timezone.now`",
                    obj=field_dt,
                    id="fields.W161",
                ),
                DjangoWarning(
                    "Fixed default value provided.",
                    hint="It seems you set a fixed date / time / datetime "
                    "value as default for this field. This may not be "
                    "what you want. If you want to have the current date "
                    "as default, use `django.utils.timezone.now`",
                    obj=field_d,
                    id="fields.W161",
                ),
            ],
        )

    @override_settings(USE_TZ=True)
    def test_fix_default_value_tz(self):
        self.test_fix_default_value()


@isolate_apps("invalid_models_tests")
class DateTimeFieldTests(SimpleTestCase):
    maxDiff = None

    def test_fix_default_value(self):
        """
        Tests the default value behavior for Django model DateTimeField instances.

        This test case creates a model with DateTimeField instances that have their default values set to different types of date/time values.
        It verifies that the check method raises the correct warnings for fields with fixed default values, providing a hint to use django.utils.timezone.now for dynamic default values.
        The test ensures that the expected warnings are generated for fields with fixed default values, helping developers avoid common pitfalls when setting default values for DateTimeField instances.
        """
        class Model(models.Model):
            field_dt = models.DateTimeField(default=now())
            field_d = models.DateTimeField(default=now().date())
            field_now = models.DateTimeField(default=now)

        field_dt = Model._meta.get_field("field_dt")
        field_d = Model._meta.get_field("field_d")
        field_now = Model._meta.get_field("field_now")
        errors = field_dt.check()
        errors.extend(field_d.check())
        errors.extend(field_now.check())  # doesn't raise a warning
        self.assertEqual(
            errors,
            [
                DjangoWarning(
                    "Fixed default value provided.",
                    hint="It seems you set a fixed date / time / datetime "
                    "value as default for this field. This may not be "
                    "what you want. If you want to have the current date "
                    "as default, use `django.utils.timezone.now`",
                    obj=field_dt,
                    id="fields.W161",
                ),
                DjangoWarning(
                    "Fixed default value provided.",
                    hint="It seems you set a fixed date / time / datetime "
                    "value as default for this field. This may not be "
                    "what you want. If you want to have the current date "
                    "as default, use `django.utils.timezone.now`",
                    obj=field_d,
                    id="fields.W161",
                ),
            ],
        )

    @override_settings(USE_TZ=True)
    def test_fix_default_value_tz(self):
        self.test_fix_default_value()


@isolate_apps("invalid_models_tests")
class DecimalFieldTests(SimpleTestCase):
    def test_required_attributes(self):
        class Model(models.Model):
            field = models.DecimalField()

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "DecimalFields must define a 'decimal_places' attribute.",
                    obj=field,
                    id="fields.E130",
                ),
                Error(
                    "DecimalFields must define a 'max_digits' attribute.",
                    obj=field,
                    id="fields.E132",
                ),
            ],
        )

    def test_negative_max_digits_and_decimal_places(self):
        """
        Tests a DecimalField with negative max_digits and decimal_places to ensure it raises validation errors.

         The function checks that the DecimalField validation correctly identifies and reports invalid input for the max_digits and decimal_places parameters.

         :return: Two expected validation error messages indicating that 'decimal_places' must be a non-negative integer and 'max_digits' must be a positive integer.
        """
        class Model(models.Model):
            field = models.DecimalField(max_digits=-1, decimal_places=-1)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'decimal_places' must be a non-negative integer.",
                    obj=field,
                    id="fields.E131",
                ),
                Error(
                    "'max_digits' must be a positive integer.",
                    obj=field,
                    id="fields.E133",
                ),
            ],
        )

    def test_bad_values_of_max_digits_and_decimal_places(self):
        class Model(models.Model):
            field = models.DecimalField(max_digits="bad", decimal_places="bad")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'decimal_places' must be a non-negative integer.",
                    obj=field,
                    id="fields.E131",
                ),
                Error(
                    "'max_digits' must be a positive integer.",
                    obj=field,
                    id="fields.E133",
                ),
            ],
        )

    def test_decimal_places_greater_than_max_digits(self):
        """

        Verify that a decimal field with decimal places greater than max digits raises an error.

        This test checks that the model validation correctly identifies and reports when the number of decimal places specified for a DecimalField exceeds the maximum number of digits allowed.

        The error is expected to be an instance of Error with the id 'fields.E134', indicating that 'max_digits' must be greater than or equal to 'decimal_places'.

        """
        class Model(models.Model):
            field = models.DecimalField(max_digits=9, decimal_places=10)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'max_digits' must be greater or equal to 'decimal_places'.",
                    obj=field,
                    id="fields.E134",
                ),
            ],
        )

    def test_valid_field(self):
        class Model(models.Model):
            field = models.DecimalField(max_digits=10, decimal_places=10)

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(), [])


@isolate_apps("invalid_models_tests")
class FileFieldTests(SimpleTestCase):
    def test_valid_default_case(self):
        class Model(models.Model):
            field = models.FileField()

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_valid_case(self):
        """
        Tests that a valid FileField in a Django model passes validation.

        This test case checks the `check` method on a FileField to ensure it returns an empty list, indicating no validation errors, for a field with a valid configuration.
        """
        class Model(models.Model):
            field = models.FileField(upload_to="somewhere")

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(), [])

    def test_primary_key(self):
        class Model(models.Model):
            field = models.FileField(primary_key=False, upload_to="somewhere")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'primary_key' is not a valid argument for a FileField.",
                    obj=field,
                    id="fields.E201",
                )
            ],
        )

    def test_upload_to_starts_with_slash(self):
        """
        Tests that a FileField's upload_to argument starting with a slash is correctly identified as an error, as Django requires relative paths for this field. 

        The test verifies that the check method on the field instance raises an error with the appropriate error code and hint when the upload_to path is absolute, ensuring that the model's field configuration is properly validated.
        """
        class Model(models.Model):
            field = models.FileField(upload_to="/somewhere")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "FileField's 'upload_to' argument must be a relative path, not "
                    "an absolute path.",
                    obj=field,
                    id="fields.E202",
                    hint="Remove the leading slash.",
                )
            ],
        )

    def test_upload_to_callable_not_checked(self):
        def callable(instance, filename):
            return "/" + filename

        class Model(models.Model):
            field = models.FileField(upload_to=callable)

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(), [])


@isolate_apps("invalid_models_tests")
class FilePathFieldTests(SimpleTestCase):
    def test_forbidden_files_and_folders(self):
        """
        Tests that a FilePathField with both 'allow_files' and 'allow_folders' set to False raises the correct error, specifically the fields.E140 error, indicating that at least one of these options must be enabled.
        """
        class Model(models.Model):
            field = models.FilePathField(allow_files=False, allow_folders=False)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "FilePathFields must have either 'allow_files' or 'allow_folders' "
                    "set to True.",
                    obj=field,
                    id="fields.E140",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class GenericIPAddressFieldTests(SimpleTestCase):
    def test_non_nullable_blank(self):
        class Model(models.Model):
            field = models.GenericIPAddressField(null=False, blank=True)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    (
                        "GenericIPAddressFields cannot have blank=True if null=False, "
                        "as blank values are stored as nulls."
                    ),
                    obj=field,
                    id="fields.E150",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class ImageFieldTests(SimpleTestCase):
    def test_pillow_installed(self):
        """
        Tests if the Pillow library is installed, which is required for using ImageField in Django models.

        Verifies that an ImageField can be used in a model without raising any errors when Pillow is installed,
        and that an appropriate error is raised when Pillow is not installed.

        Checks the field's validity and compares the expected errors with the actual errors returned by the field's check method.
        """
        try:
            from PIL import Image  # NOQA
        except ImportError:
            pillow_installed = False
        else:
            pillow_installed = True

        class Model(models.Model):
            field = models.ImageField(upload_to="somewhere")

        field = Model._meta.get_field("field")
        errors = field.check()
        expected = (
            []
            if pillow_installed
            else [
                Error(
                    "Cannot use ImageField because Pillow is not installed.",
                    hint=(
                        "Get Pillow at https://pypi.org/project/Pillow/ "
                        'or run command "python -m pip install Pillow".'
                    ),
                    obj=field,
                    id="fields.E210",
                ),
            ]
        )
        self.assertEqual(errors, expected)


@isolate_apps("invalid_models_tests")
class IntegerFieldTests(SimpleTestCase):
    def test_max_length_warning(self):
        class Model(models.Model):
            integer = models.IntegerField(max_length=2)
            biginteger = models.BigIntegerField(max_length=2)
            smallinteger = models.SmallIntegerField(max_length=2)
            positiveinteger = models.PositiveIntegerField(max_length=2)
            positivebiginteger = models.PositiveBigIntegerField(max_length=2)
            positivesmallinteger = models.PositiveSmallIntegerField(max_length=2)

        for field in Model._meta.get_fields():
            if field.auto_created:
                continue
            with self.subTest(name=field.name):
                self.assertEqual(
                    field.check(),
                    [
                        DjangoWarning(
                            "'max_length' is ignored when used with %s."
                            % field.__class__.__name__,
                            hint="Remove 'max_length' from field",
                            obj=field,
                            id="fields.W122",
                        )
                    ],
                )

    def test_non_iterable_choices(self):
        class Model(models.Model):
            field = models.IntegerField(choices=123)

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'choices' must be a mapping (e.g. a dictionary) or an iterable "
                    "(e.g. a list or tuple).",
                    obj=field,
                    id="fields.E004",
                ),
            ],
        )

    def test_non_iterable_choices_number(self):
        """An integer isn't a valid choice pair."""

        class Model(models.Model):
            field = models.IntegerField(choices=[123])

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'choices' must be a mapping of actual values to human readable "
                    "names or an iterable containing (actual value, human readable "
                    "name) tuples.",
                    obj=field,
                    id="fields.E005",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class TimeFieldTests(SimpleTestCase):
    maxDiff = None

    def test_fix_default_value(self):
        """
        Tests that using fixed datetime values or now() with or without function call as default value for TimeField and DateField models raises the correct warnings.

        This function simulates the creation of Django model fields with fixed datetime values or now() as default values and verifies that warnings are generated for these fields. The warnings are checked to ensure they are of the correct type, contain the expected hint message, and reference the correct fields.
        """
        class Model(models.Model):
            field_dt = models.TimeField(default=now())
            field_t = models.TimeField(default=now().time())
            # Timezone-aware time object (when USE_TZ=True).
            field_tz = models.TimeField(default=now().timetz())
            field_now = models.DateField(default=now)

        names = ["field_dt", "field_t", "field_tz", "field_now"]
        fields = [Model._meta.get_field(name) for name in names]
        errors = []
        for field in fields:
            errors.extend(field.check())

        self.assertEqual(
            errors,
            [
                DjangoWarning(
                    "Fixed default value provided.",
                    hint="It seems you set a fixed date / time / datetime "
                    "value as default for this field. This may not be "
                    "what you want. If you want to have the current date "
                    "as default, use `django.utils.timezone.now`",
                    obj=fields[0],
                    id="fields.W161",
                ),
                DjangoWarning(
                    "Fixed default value provided.",
                    hint="It seems you set a fixed date / time / datetime "
                    "value as default for this field. This may not be "
                    "what you want. If you want to have the current date "
                    "as default, use `django.utils.timezone.now`",
                    obj=fields[1],
                    id="fields.W161",
                ),
                DjangoWarning(
                    "Fixed default value provided.",
                    hint=(
                        "It seems you set a fixed date / time / datetime value as "
                        "default for this field. This may not be what you want. "
                        "If you want to have the current date as default, use "
                        "`django.utils.timezone.now`"
                    ),
                    obj=fields[2],
                    id="fields.W161",
                ),
                # field_now doesn't raise a warning.
            ],
        )

    @override_settings(USE_TZ=True)
    def test_fix_default_value_tz(self):
        self.test_fix_default_value()


@isolate_apps("invalid_models_tests")
class TextFieldTests(TestCase):
    @skipIfDBFeature("supports_index_on_text_field")
    def test_max_length_warning(self):
        class Model(models.Model):
            value = models.TextField(db_index=True)

        field = Model._meta.get_field("value")
        field_type = field.db_type(connection)
        self.assertEqual(
            field.check(databases=self.databases),
            [
                DjangoWarning(
                    "%s does not support a database index on %s columns."
                    % (connection.display_name, field_type),
                    hint=(
                        "An index won't be created. Silence this warning if you "
                        "don't care about it."
                    ),
                    obj=field,
                    id="fields.W162",
                )
            ],
        )

    def test_db_collation(self):
        class Model(models.Model):
            field = models.TextField(db_collation="anything")

        field = Model._meta.get_field("field")
        error = Error(
            "%s does not support a database collation on TextFields."
            % connection.display_name,
            id="fields.E190",
            obj=field,
        )
        expected = (
            [] if connection.features.supports_collation_on_textfield else [error]
        )
        self.assertEqual(field.check(databases=self.databases), expected)

    def test_db_collation_required_db_features(self):
        """
        Tests that a database operation checks for required database features when using db_collation.

        This test verifies that when a model field has a db_collation attribute set and 
        the model's Meta class specifies required_db_features, the field's check method 
        will correctly validate the availability of those features on the target database.

        The test case covers the specific scenario of using collation on a TextField, 
        ensuring that the database supports this operation before attempting it.
        """
        class Model(models.Model):
            field = models.TextField(db_collation="anything")

            class Meta:
                required_db_features = {"supports_collation_on_textfield"}

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(databases=self.databases), [])


@isolate_apps("invalid_models_tests")
class UUIDFieldTests(TestCase):
    def test_choices_named_group(self):
        """

        Tests the functionality of named groups in choices for a UUIDField.

        This test ensures that the validation of choices for a UUIDField works correctly
        when the choices are defined with named groups. It verifies that the field's
        validation returns no errors when the choices are defined correctly.

        The test case checks the model's field metadata to confirm that the check method
        returns an empty list, indicating that the field's choices are valid.

        """
        class Model(models.Model):
            field = models.UUIDField(
                choices=[
                    [
                        "knights",
                        [
                            [
                                uuid.UUID("5c859437-d061-4847-b3f7-e6b78852f8c8"),
                                "Lancelot",
                            ],
                            [
                                uuid.UUID("c7853ec1-2ea3-4359-b02d-b54e8f1bcee2"),
                                "Galahad",
                            ],
                        ],
                    ],
                    [uuid.UUID("25d405be-4895-4d50-9b2e-d6695359ce47"), "Other"],
                ],
            )

        self.assertEqual(Model._meta.get_field("field").check(), [])


@isolate_apps("invalid_models_tests")
@skipUnlessDBFeature("supports_json_field")
class JSONFieldTests(TestCase):
    def test_invalid_default(self):
        """
        Tests that a JSONField with a non-callable default value raises the correct warning.

        Checks that defining a JSONField with a default value as an instance (e.g., `{}`) instead of a callable (e.g., `dict`) triggers a Django warning,
        as this could lead to unintended shared state between all instances of the field.

        Verifies that the warning message and hint are correctly generated, advising the use of a callable default value to avoid this issue.
        """
        class Model(models.Model):
            field = models.JSONField(default={})

        self.assertEqual(
            Model._meta.get_field("field").check(),
            [
                DjangoWarning(
                    msg=(
                        "JSONField default should be a callable instead of an "
                        "instance so that it's not shared between all field "
                        "instances."
                    ),
                    hint=("Use a callable instead, e.g., use `dict` instead of `{}`."),
                    obj=Model._meta.get_field("field"),
                    id="fields.E010",
                )
            ],
        )

    def test_valid_default(self):
        """

        Tests that a valid default value is accepted for a JSONField.

        Verifies that when a JSONField is defined with a default value of an empty dictionary,
        the field's validation does not produce any errors.

        """
        class Model(models.Model):
            field = models.JSONField(default=dict)

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_valid_default_none(self):
        class Model(models.Model):
            field = models.JSONField(default=None)

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_valid_callable_default(self):
        """
        Tests that a valid callable default function is accepted for a JSONField.

        Verifies that the model field can successfully check its default value when
        it is defined by a callable function, ensuring the function runs without errors
        and produces a valid result. This confirms that the framework correctly handles
        the provided default value function for JSON fields, supporting dynamic default values. 
        """
        def callable_default():
            return {"it": "works"}

        class Model(models.Model):
            field = models.JSONField(default=callable_default)

        self.assertEqual(Model._meta.get_field("field").check(), [])


@isolate_apps("invalid_models_tests")
class DbCommentTests(TestCase):
    def test_db_comment(self):
        """

         Tests the database comment functionality on a model field.

         This test creates a model with an integer field that has a database comment.
         It then checks the field for any errors or warnings related to database comments.
         The expected result depends on whether the database backend supports comments on columns.
         If the backend supports comments, no errors or warnings are expected.
         If the backend does not support comments, a DjangoWarning is expected, indicating that the comment will be ignored.

        """
        class Model(models.Model):
            field = models.IntegerField(db_comment="Column comment")

        errors = Model._meta.get_field("field").check(databases=self.databases)
        expected = (
            []
            if connection.features.supports_comments
            else [
                DjangoWarning(
                    f"{connection.display_name} does not support comments on columns "
                    f"(db_comment).",
                    obj=Model._meta.get_field("field"),
                    id="fields.W163",
                ),
            ]
        )
        self.assertEqual(errors, expected)

    def test_db_comment_required_db_features(self):
        class Model(models.Model):
            field = models.IntegerField(db_comment="Column comment")

            class Meta:
                required_db_features = {"supports_comments"}

        errors = Model._meta.get_field("field").check(databases=self.databases)
        self.assertEqual(errors, [])


@isolate_apps("invalid_models_tests")
class InvalidDBDefaultTests(TestCase):
    def test_db_default(self):
        """
        Test that default database values with expressions (db_default) are validated correctly.

        This test case checks whether the Field class correctly identifies and reports errors
        when a default value with an expression (db_default) is used on a database that does not support it.
        The test covers both cases where the database supports expression defaults and where it does not.

        It verifies that the expected error messages are raised for databases that do not support
        expression defaults and that no errors are raised for databases that do support them.
        """
        class Model(models.Model):
            field = models.FloatField(db_default=Pi())

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)

        if connection.features.supports_expression_defaults:
            expected_errors = []
        else:
            msg = (
                f"{connection.display_name} does not support default database values "
                "with expressions (db_default)."
            )
            expected_errors = [Error(msg=msg, obj=field, id="fields.E011")]
        self.assertEqual(errors, expected_errors)

    def test_db_default_literal(self):
        """
        Tests that a model field with a db_default value of a literal does not produce any errors when checked against the database.

        This test ensures that a field's db_default value set to a literal (in this case, an integer) is valid and properly configured, 
        and that no errors are raised when validating the field against multiple databases.

        The test verifies that the field's check method returns an empty list of errors, indicating that the field's configuration is correct.

        """
        class Model(models.Model):
            field = models.IntegerField(db_default=1)

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)
        self.assertEqual(errors, [])

    def test_db_default_required_db_features(self):
        class Model(models.Model):
            field = models.FloatField(db_default=Pi())

            class Meta:
                required_db_features = {"supports_expression_defaults"}

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)
        self.assertEqual(errors, [])

    def test_db_default_expression_invalid(self):
        expression = models.F("field_name")

        class Model(models.Model):
            field = models.FloatField(db_default=expression)

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)

        if connection.features.supports_expression_defaults:
            msg = f"{expression} cannot be used in db_default."
            expected_errors = [Error(msg=msg, obj=field, id="fields.E012")]
        else:
            msg = (
                f"{connection.display_name} does not support default database values "
                "with expressions (db_default)."
            )
            expected_errors = [Error(msg=msg, obj=field, id="fields.E011")]
        self.assertEqual(errors, expected_errors)

    def test_db_default_expression_required_db_features(self):
        expression = models.F("field_name")

        class Model(models.Model):
            field = models.FloatField(db_default=expression)

            class Meta:
                required_db_features = {"supports_expression_defaults"}

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)

        if connection.features.supports_expression_defaults:
            msg = f"{expression} cannot be used in db_default."
            expected_errors = [Error(msg=msg, obj=field, id="fields.E012")]
        else:
            expected_errors = []
        self.assertEqual(errors, expected_errors)

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_db_default_combined_invalid(self):
        """

        Tests that a database default which combines expressions cannot be used.

        The validation checks enforce that the database default does not contain any
        expressions that cannot be evaluated when the field is created. 

        This test fails when it attempts to use a combined expression as a database default.

        The expected validation error is raised with a specific error message and id 'fields.E012'.

        """
        expression = models.Value(4.5) + models.F("field_name")

        class Model(models.Model):
            field = models.FloatField(db_default=expression)

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)

        msg = f"{expression} cannot be used in db_default."
        expected_error = Error(msg=msg, obj=field, id="fields.E012")
        self.assertEqual(errors, [expected_error])

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_db_default_function_arguments_invalid(self):
        """
        Otherwise sets a database default for a model field using an expression and checks that it raises an error as expected since database defaults do not support using expressions.

         Args:
             self: The test instance.

         Returns:
             None: This function does not return any value, it only checks for the expected error.

         Raises:
             Error: If the expression is used in db_default, it raises an error with message 'cannot be used in db_default', id 'fields.E012'. 

         Notes:
             The test case covers the validation of model fields to ensure they do not use expressions for database defaults. It verifies the error is correctly reported when such a case occurs.
        """
        expression = Coalesce(models.Value(4.5), models.F("field_name"))

        class Model(models.Model):
            field = models.FloatField(db_default=expression)

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)

        msg = f"{expression} cannot be used in db_default."
        expected_error = Error(msg=msg, obj=field, id="fields.E012")
        self.assertEqual(errors, [expected_error])


@isolate_apps("invalid_models_tests")
class GeneratedFieldTests(TestCase):
    def test_not_supported(self):
        """
        :::::::::::::
        Test a model field generates correct errors when GeneratedField is not supported.

        This test case checks the behavior of the GeneratedField when the database
        connection does not support stored generated columns, virtual generated columns,
        or non-persisted generated columns. It verifies that the correct errors are raised
        when the GeneratedField is defined with or without persistence, depending on the
        database capabilities. The test covers two specific error scenarios: when the
        database does not support generated fields at all, and when it does not support
        non-persisted generated fields.
        """
        db_persist = connection.features.supports_stored_generated_columns

        class Model(models.Model):
            name = models.IntegerField()
            field = models.GeneratedField(
                expression=models.F("name"),
                output_field=models.IntegerField(),
                db_persist=db_persist,
            )

        expected_errors = []
        if (
            not connection.features.supports_stored_generated_columns
            and not connection.features.supports_virtual_generated_columns
        ):
            expected_errors.append(
                Error(
                    f"{connection.display_name} does not support GeneratedFields.",
                    obj=Model._meta.get_field("field"),
                    id="fields.E220",
                )
            )
        if (
            not db_persist
            and not connection.features.supports_virtual_generated_columns
        ):
            expected_errors.append(
                Error(
                    f"{connection.display_name} does not support non-persisted "
                    "GeneratedFields.",
                    obj=Model._meta.get_field("field"),
                    id="fields.E221",
                    hint="Set db_persist=True on the field.",
                ),
            )
        self.assertEqual(
            Model._meta.get_field("field").check(databases={"default"}),
            expected_errors,
        )

    def test_not_supported_stored_required_db_features(self):
        class Model(models.Model):
            name = models.IntegerField()
            field = models.GeneratedField(
                expression=models.F("name"),
                output_field=models.IntegerField(),
                db_persist=True,
            )

            class Meta:
                required_db_features = {"supports_stored_generated_columns"}

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_not_supported_virtual_required_db_features(self):
        """

        Tests that a model with virtual generated columns and a required database feature 
        of 'supports_virtual_generated_columns' returns no errors when checked against 
        the provided databases. This ensures that the model's database requirements are 
        correctly validated. 

        The test case covers a scenario where a model uses a generated field and 
        specifies a required database feature, checking that the model validation 
        mechanism correctly handles this configuration.

        """
        class Model(models.Model):
            name = models.IntegerField()
            field = models.GeneratedField(
                expression=models.F("name"),
                output_field=models.IntegerField(),
                db_persist=False,
            )

            class Meta:
                required_db_features = {"supports_virtual_generated_columns"}

        self.assertEqual(Model.check(databases=self.databases), [])

    @skipUnlessDBFeature("supports_stored_generated_columns")
    def test_not_supported_virtual(self):
        """
        Tests the behavior of models with generated fields when the underlying database does not support non-persisted generated columns.

        Checks that the correct error is raised when a model contains a non-persisted generated field and the database does not support virtual generated columns.

        The test expects no errors when the database supports virtual generated columns and an error with a specific message and hint when it does not. The error message informs the user to set db_persist=True on the field to resolve the issue.

        Verifies that the model's meta field checks correctly identify the compatibility issue and provide useful feedback to the user.
        """
        class Model(models.Model):
            name = models.IntegerField()
            field = models.GeneratedField(
                expression=models.F("name"),
                output_field=models.IntegerField(),
                db_persist=False,
            )
            a = models.TextField()

        excepted_errors = (
            []
            if connection.features.supports_virtual_generated_columns
            else [
                Error(
                    f"{connection.display_name} does not support non-persisted "
                    "GeneratedFields.",
                    obj=Model._meta.get_field("field"),
                    id="fields.E221",
                    hint="Set db_persist=True on the field.",
                ),
            ]
        )
        self.assertEqual(
            Model._meta.get_field("field").check(databases={"default"}),
            excepted_errors,
        )

    @skipUnlessDBFeature("supports_virtual_generated_columns")
    def test_not_supported_stored(self):
        """

        Tests that a stored GeneratedField's check method correctly raises an error
        when the underlying database does not support persisted generated columns.

        This test case verifies that the checks performed on a Model with a GeneratedField
        that is marked for persistence correctly handle databases that do not support
        this feature, providing a helpful error message when the feature is not supported.

        The expected outcome depends on the capabilities of the database in use. If the
        database supports persisted generated columns, the check should pass without
        errors. If the database does not support this feature, an error should be raised
        with a message indicating that persisted generated columns are not supported and
        suggesting how to correct the issue.

        """
        class Model(models.Model):
            name = models.IntegerField()
            field = models.GeneratedField(
                expression=models.F("name"),
                output_field=models.IntegerField(),
                db_persist=True,
            )
            a = models.TextField()

        expected_errors = (
            []
            if connection.features.supports_stored_generated_columns
            else [
                Error(
                    f"{connection.display_name} does not support persisted "
                    "GeneratedFields.",
                    obj=Model._meta.get_field("field"),
                    id="fields.E222",
                    hint="Set db_persist=False on the field.",
                ),
            ]
        )
        self.assertEqual(
            Model._meta.get_field("field").check(databases={"default"}),
            expected_errors,
        )

    @skipUnlessDBFeature("supports_stored_generated_columns")
    def test_output_field_check_error(self):
        class Model(models.Model):
            value = models.DecimalField(max_digits=5, decimal_places=2)
            field = models.GeneratedField(
                expression=models.F("value") * 2,
                output_field=models.DecimalField(max_digits=-1, decimal_places=-1),
                db_persist=True,
            )

        expected_errors = [
            Error(
                "GeneratedField.output_field has errors:"
                "\n    'decimal_places' must be a non-negative integer. (fields.E131)"
                "\n    'max_digits' must be a positive integer. (fields.E133)",
                obj=Model._meta.get_field("field"),
                id="fields.E223",
            ),
        ]
        self.assertEqual(
            Model._meta.get_field("field").check(databases={"default"}),
            expected_errors,
        )

    @skipUnlessDBFeature("supports_stored_generated_columns")
    def test_output_field_charfield_unlimited_error(self):
        """

        Tests the validation of a GeneratedField with a CharField output field that has no max_length set.

        When a database does not support unlimited CharField, this test checks that a validation error is raised.
        The validation error occurs because CharFields are required to define a 'max_length' attribute.

        This test case verifies that the validation is performed correctly and the expected error is generated when the database does not support unlimited CharField.

        """
        class Model(models.Model):
            name = models.CharField(max_length=255)
            field = models.GeneratedField(
                expression=LPad("name", 7, models.Value("xy")),
                output_field=models.CharField(),
                db_persist=True,
            )

        expected_errors = (
            []
            if connection.features.supports_unlimited_charfield
            else [
                Error(
                    "GeneratedField.output_field has errors:"
                    "\n    CharFields must define a 'max_length' attribute. "
                    "(fields.E120)",
                    obj=Model._meta.get_field("field"),
                    id="fields.E223",
                ),
            ]
        )
        self.assertEqual(
            Model._meta.get_field("field").check(databases={"default"}),
            expected_errors,
        )

    @skipUnlessDBFeature("supports_stored_generated_columns")
    def test_output_field_check_warning(self):
        class Model(models.Model):
            value = models.IntegerField()
            field = models.GeneratedField(
                expression=models.F("value") * 2,
                output_field=models.IntegerField(max_length=40),
                db_persist=True,
            )

        expected_warnings = [
            DjangoWarning(
                "GeneratedField.output_field has warnings:"
                "\n    'max_length' is ignored when used with IntegerField. "
                "(fields.W122)",
                obj=Model._meta.get_field("field"),
                id="fields.W224",
            ),
        ]
        self.assertEqual(
            Model._meta.get_field("field").check(databases={"default"}),
            expected_warnings,
        )
