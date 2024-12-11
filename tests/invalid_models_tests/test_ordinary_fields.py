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
        Verifies that BinaryField instances accept valid default values.

        This test ensures that BinaryField instances can be instantiated with default values
        of type bytes (e.g., b'test') and None, without raising any validation errors.
        It checks the validity of these default values using the `check` method of the field,
        which should return an empty list if no errors are detected.

        The test covers two scenarios:

        - A BinaryField with a default value of type bytes (b'test')
        - A BinaryField with a default value of None

        By passing these tests, it confirms that the BinaryField class correctly handles
        these default values and does not raise any validation errors.
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
        """
        Tests that a CharField with a non-integer max_length value returns the correct error.

        Checks that the field's check method raises an error when the max_length parameter is not a positive integer, specifically when it's set to a string value. Verifies the error message is correctly formatted and contains the expected error ID 'fields.E121'.
        """
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
        Tests that model fields with choices containing lazy translations do not raise any errors during field validation.

            The test ensures that the choices defined for a model field are properly registered and validated,
            even when the choice values are wrapped in lazy translation functions.

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
        Tests validation of a CharField with choices specified as named groups containing non-pair values, verifying that it raises the correct error when the choices are not in the expected format of either a mapping of actual values to human-readable names or an iterable of (actual value, human-readable name) tuples.
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
        Checks that invalid db_index values are correctly identified and reported as errors.

        The test enforces the constraint that 'db_index' must be one of the following: None, True, or False, ensuring that any model field using an invalid 'db_index' value raises the appropriate error message.
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
        Tests whether Django's MySQL backend correctly identifies and warns about CharField instances 
        with a maximum length exceeding 255 characters when unique constraint is applied.

        This test case verifies that the database validation mechanism catches and reports potential 
        issues with MySQL's character field limitations, ensuring that developers are informed about 
        potential problems that may arise when working with unique CharFields in MySQL databases.

        The test is specific to MySQL databases and is skipped for other database vendors.
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
        """

        Checks if a model field with a db_collation attribute requires the 'supports_collation_on_charfield' database feature.

        This test ensures that the field validation correctly identifies the need for collation support on character fields when a specific collation is defined.

        """
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
        """
        Tests that the DecimalField validation correctly identifies invalid values for max_digits and decimal_places.

        Verifies that when non-integer values are assigned to max_digits and decimal_places,
        the field validation returns the expected errors, specifically 'fields.E131' for decimal_places
        and 'fields.E133' for max_digits. Ensures that the field validation accurately enforces
        the requirement that max_digits must be a positive integer and decimal_places must be
        a non-negative integer.
        """
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
        Tests that a DecimalField with more decimal places than max digits raises an error.

        This test case ensures that validation occurs when the number of decimal places
        exceeds the maximum number of digits allowed in a DecimalField. It verifies that
        an error is raised to prevent such invalid field configurations.

        The expected error is a fields.E134 error, which indicates that 'max_digits' must
        be greater than or equal to 'decimal_places' in a DecimalField.

        Validates the field's check method to guarantee that it correctly identifies
        and reports this type of configuration mistake.
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
        Tests that a valid FileField model instance does not raise any errors during validation. 
        Verifies that the check method of the field returns an empty list, indicating no validation errors.
        """
        class Model(models.Model):
            field = models.FileField(upload_to="somewhere")

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(), [])

    def test_primary_key(self):
        """
        Test that the primary_key argument is not valid for a FileField.

        Checks that a validation error is raised when attempting to set the primary_key
        argument on a FileField. This ensures that FileFields cannot be used as primary
        keys for a model, as this is not a valid configuration.

        The test verifies that the expected error message is returned when checking the
        field, confirming that the validation is correctly enforced.
        """
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

        Tests that an ImageField correctly reports an error when Pillow is not installed.

        This test case attempts to import Pillow, then defines a model with an ImageField.
        It checks the field for errors, expecting one if Pillow is not installed, and verifies
        that the expected error is raised, providing helpful instructions on how to install Pillow.

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
        class Model(models.Model):
            field = models.TextField(db_collation="anything")

            class Meta:
                required_db_features = {"supports_collation_on_textfield"}

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(databases=self.databases), [])


@isolate_apps("invalid_models_tests")
class UUIDFieldTests(TestCase):
    def test_choices_named_group(self):
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
        class Model(models.Model):
            field = models.JSONField(default=dict)

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_valid_default_none(self):
        class Model(models.Model):
            field = models.JSONField(default=None)

        self.assertEqual(Model._meta.get_field("field").check(), [])

    def test_valid_callable_default(self):
        def callable_default():
            return {"it": "works"}

        class Model(models.Model):
            field = models.JSONField(default=callable_default)

        self.assertEqual(Model._meta.get_field("field").check(), [])


@isolate_apps("invalid_models_tests")
class DbCommentTests(TestCase):
    def test_db_comment(self):
        """
        Tests the behavior of the db_comment attribute on model fields, specifically whether the underlying database supports column comments. The test checks the warnings raised when a db_comment is specified on a field but the database does not support comments on columns.
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
        """
        Tests that a model field with a database comment requires a database feature that supports comments, ensuring compatibility and preventing potential errors when using the model with different databases.
        """
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
        Tests that FloatField with a database expression default value raises the correct error on databases that do not support default database values with expressions. 
        The test creates a model with a FloatField that has a default value set to a database expression (Pi), 
        then checks the field for errors and verifies that the expected error is raised if the database does not support expression defaults.
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
        class Model(models.Model):
            field = models.IntegerField(db_default=1)

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)
        self.assertEqual(errors, [])

    def test_db_default_required_db_features(self):
        """

        Tests that a model field with a database default value expression
        and the corresponding required database features set in the model's Meta
        option is correctly validated.

        This test case verifies that a field with a FloatField and a
        database default value set to a mathematical expression (Pi) does not
        raise any errors when checked against a list of databases, given that
        the model has specified that the database must support expression defaults.

        """
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
        """
        Tests that the `db_default` argument of a model field correctly handles database expressions in terms of required database features.

        The test checks if a FloatField with a database expression as its default value is properly validated 
        across different databases. It specifically verifies that if the database supports expression defaults, 
        an error is raised because the provided expression cannot be used in `db_default`. If the database does 
        not support expression defaults, it checks that no error is raised. This ensures that the `required_db_features` 
        Meta option is correctly considered during field validation.
        """
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
        Tests that using a database function expression in a model field's db_default parameter raises the expected validation error. 

        This check ensures that the ORM correctly reports invalid usage of an expression as a default value for a database field, specifically when the expression is not a constant or a callable without arguments. 

        The test covers the case where a Coalesce expression is passed as the db_default for a FloatField, which should result in a validation error with a specific message and error code 'fields.E012'.
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

        Tests that the GeneratedField is correctly checked for support by the database.

        Verifies that a GeneratedField with or without persistence is properly validated
        against the capabilities of the underlying database. If the database does not
        support stored or virtual generated columns, or if a non-persisted field is used
        with a database that does not support virtual generated columns, an appropriate
        error is raised.

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
        Tests that a model with a generated field and required database features 
        raises no errors during model checking if the database supports virtual generated 
        columns, even if they are not persisted. This ensures that the model validation 
        correctly handles the required_db_features and db_persist settings for generated 
        fields, allowing for flexible and database-agnostic model definition.
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
        Tests the support for virtual generated columns in a database.

        This test case checks if a database supports non-persisted generated fields.
        It creates a model with a generated field that is not persisted in the database
        and verifies the expected errors are raised based on the database's capabilities.

        The test covers the scenario where a database does or does not support virtual
        generated columns, ensuring the correct error messages are generated when
        the database does not support this feature. The test helps ensure that the
        `GeneratedField` behaves as expected across different database backends.
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

        Tests that an error is raised when a CharField with unlimited length is used as the output field for a GeneratedField.

        This testcase verifies the behavior of the GeneratedField when using a CharField as its output field.
        It checks if the correct error is raised when the CharField does not have a max_length attribute defined,
        which is required for the GeneratedField to work correctly.

        The test covers the case where the database supports stored generated columns and the output field is a CharField.
        It checks the model's field validation to ensure that the error is properly reported when the CharField's max_length is not set.

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
