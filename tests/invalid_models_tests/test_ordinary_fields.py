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
        """
        Checks that AutoFields without primary_key=True raise an appropriate error, ensuring primary key constraints are properly defined in Django models.
        """
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
        Checks validity of default values for BinaryField in a Django model, ensuring no errors are raised when default values are b'test' and None.
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
        """
        Tests that a CharField without a 'max_length' attribute raises an error when checked, unless the database backend supports unlimited character fields.
        """
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
        """
        Tests that a CharField with a 'choices' attribute containing two letters raises a validation error, as it does not represent a valid choice pair.
        """

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
        """
        Tests that an iterable of iterable choices is correctly validated for a model field.
        """
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
        """
        Tests that the 'choices' attribute of a Django model field must be a mapping or an iterable of tuples, not a general iterable.

        Verifies that fields with invalid 'choices' definitions raise the expected error.
        """
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
        """
        Tests that a CharField's max_length is sufficient to hold its longest choice value, ensuring truncation does not occur when storing user input.
        """
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
        Tests the behavior of CharField with max_length greater than 255 under MySQL, 
        verifying that the correct warning is raised due to MySQL's limitations on unique character fields.
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
        Tests that a CharField raises an error when a database collation is specified if the underlying database does not support collation on CharFields.
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
        """
        Checks that the ``required_db_features`` meta attribute is properly handled when a model field has a ``db_collation`` specified, ensuring the database backend supports collation on character fields.
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
        """
        Tests that using both auto_now and auto_now_add on a DateTimeField in a model raises an error, as these options are mutually exclusive.
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
        Tests that setting fixed date/time values as field defaults raises warnings.\"\"\"
        ```
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
        Tests that setting a fixed date/time value as a default for a DateTimeField raises a warning, ensuring users are aware of potential issues with fixed defaults versus dynamic values.
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
        """
        Tests that a FileField with an upload_to callable does not trigger validation checks.
        """
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

        Checks if the Pillow library is installed and can be used with ImageField models.

        Verifies that ImageField validation correctly identifies the absence of Pillow and provides a meaningful error message.

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
        """
        Checks that the `max_length` parameter is correctly ignored and warned about when used with integer fields in a Django model.
        """
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
        """
        Checks that non-iterable choices in model fields are correctly reported as invalid, specifically for integer choices.
        """

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
        Tests that setting a fixed date/time value as the default for a Django model field generates the expected warnings.
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
        """
        Skips test if the database supports indexing on text fields, otherwise tests the warning raised when attempting to create an indexed text field on an unsupported database.\"\"\"

        or more detailed version:

        \"\"\"Tests that a warning is raised when attempting to create a database index on a text field for databases that do not support this operation. The test is skipped if the database supports indexing on text fields.
        """
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
        """
        Checks the database collation support for a TextField, ensuring an error is raised if the database does not support collation on text fields.
        """
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
        Tests that a model field with db_collation requires the corresponding database feature.
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
        """
        Tests that a JSONField with a callable default value is valid.
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
        Tests that a warning is raised when db_comment is used on a field for a database that does not support column comments.
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
        Tests that the db_comment attribute on a model field raises no errors when the 'supports_comments' database feature is required.
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
        Tests the field validation for default database values with expressions.

        Checks if the database backend supports default values with expressions.
        Verifies that an error is raised when the database does not support this feature.
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
        Tests that a database model field with a default literal value does not produce any database-specific validation errors.
        """
        class Model(models.Model):
            field = models.IntegerField(db_default=1)

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)
        self.assertEqual(errors, [])

    def test_db_default_required_db_features(self):
        """
        Tests that the database default feature is correctly validated when the field's model has required database features specified, ensuring compatibility with supported databases.
        """
        class Model(models.Model):
            field = models.FloatField(db_default=Pi())

            class Meta:
                required_db_features = {"supports_expression_defaults"}

        field = Model._meta.get_field("field")
        errors = field.check(databases=self.databases)
        self.assertEqual(errors, [])

    def test_db_default_expression_invalid(self):
        """
        Tests validation of a model field with an invalid default database expression. 

        The function verifies that Django correctly raises an error when a model field uses a database expression as its default value, which is not supported by all databases.
        """
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
        Tests that a specific database error is raised when using an expression as the default value for a field, if the database does not support expression defaults.
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
        """
        Tests that an invalid default value expression cannot be used in a model field's db_default attribute.
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
        Tests the validation of a model field's db_default attribute when using an expression that cannot be resolved to a constant value on the database side, ensuring an error is raised with the appropriate message.
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
        Tests the behavior of GeneratedFields when they are not supported by the underlying database, ensuring that proper error messages are raised in cases where the database does not support stored or virtual generated columns.
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
        """
        Tests that check database features raises no error when a model has a stored generated field that requires a database feature to be supported, but the test specifically targets non-supported features.
        """
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
        Tests that a model with a generated field and required database features raises no errors when checked against supported databases, ensuring that the 'supports_virtual_generated_columns' feature is correctly handled.
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
        Tests that a non-persisted virtual generated column raises the correct error on a database that does not support them.
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
        Tests that a model with a persisted GeneratedField raises the correct error when the database does not support stored generated columns.
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
        """

        Tests that the check method of a GeneratedField correctly identifies errors in the output field.
        Specifically, it verifies that a DecimalField with invalid max_digits and decimal_places raises validation errors.

        """
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
        Tests that a CharField used as the output field for a GeneratedField correctly reports an error when its max_length is not defined, if the database does not support unlimited character fields.
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
        """
        Tests that a check warning is raised when an unnecessary 'max_length' parameter is used with an IntegerField in a GeneratedField's output_field.
        """
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
