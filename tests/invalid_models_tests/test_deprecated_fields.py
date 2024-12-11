from unittest import skipUnless

from django.core import checks
from django.db import connection, models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps


@isolate_apps("invalid_models_tests")
class DeprecatedFieldsTests(SimpleTestCase):
    def test_IPAddressField_deprecated(self):
        class IPAddressModel(models.Model):
            ip = models.IPAddressField()

        model = IPAddressModel()
        self.assertEqual(
            model.check(),
            [
                checks.Error(
                    "IPAddressField has been removed except for support in "
                    "historical migrations.",
                    hint="Use GenericIPAddressField instead.",
                    obj=IPAddressModel._meta.get_field("ip"),
                    id="fields.E900",
                )
            ],
        )

    def test_CommaSeparatedIntegerField_deprecated(self):
        """
        Tests the deprecated CommaSeparatedIntegerField in a model to ensure it raises the correct deprecation error.

        The test checks if using CommaSeparatedIntegerField in a model field triggers a warning about its deprecation, 
        with a suggestion to replace it with a CharField that uses a comma-separated integer list validator.
        """
        class CommaSeparatedIntegerModel(models.Model):
            csi = models.CommaSeparatedIntegerField(max_length=64)

        model = CommaSeparatedIntegerModel()
        self.assertEqual(
            model.check(),
            [
                checks.Error(
                    "CommaSeparatedIntegerField is removed except for support in "
                    "historical migrations.",
                    hint=(
                        "Use "
                        "CharField(validators=[validate_comma_separated_integer_list]) "
                        "instead."
                    ),
                    obj=CommaSeparatedIntegerModel._meta.get_field("csi"),
                    id="fields.E901",
                )
            ],
        )

    def test_nullbooleanfield_deprecated(self):
        """
        Tests the deprecation of NullBooleanField.

        This test case checks that using a NullBooleanField in a model triggers a deprecation error.
        The error suggests replacing NullBooleanField with BooleanField(null=True, blank=True) for equivalent functionality.

        The test verifies that the check method returns an error with the expected message and hint,
        indicating that NullBooleanField is no longer supported except for historical migration purposes.
        """
        class NullBooleanFieldModel(models.Model):
            nb = models.NullBooleanField()

        model = NullBooleanFieldModel()
        self.assertEqual(
            model.check(),
            [
                checks.Error(
                    "NullBooleanField is removed except for support in historical "
                    "migrations.",
                    hint="Use BooleanField(null=True, blank=True) instead.",
                    obj=NullBooleanFieldModel._meta.get_field("nb"),
                    id="fields.E903",
                ),
            ],
        )

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL specific SQL")
    def test_postgres_jsonfield_deprecated(self):
        """

        Tests the deprecation of PostgreSQL's JSONField.

        This test case verifies that using the deprecated JSONField from django.contrib.postgres.fields
        triggers a warning, recommending the use of django.db.models.JSONField instead.
        It checks the model validation and ensures that the expected error is raised.

        """
        from django.contrib.postgres.fields import JSONField

        class PostgresJSONFieldModel(models.Model):
            field = JSONField()

        self.assertEqual(
            PostgresJSONFieldModel.check(),
            [
                checks.Error(
                    "django.contrib.postgres.fields.JSONField is removed except "
                    "for support in historical migrations.",
                    hint="Use django.db.models.JSONField instead.",
                    obj=PostgresJSONFieldModel._meta.get_field("field"),
                    id="fields.E904",
                ),
            ],
        )

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL specific SQL")
    def test_postgres_ci_fields_deprecated(self):
        from django.contrib.postgres.fields import (
            ArrayField,
            CICharField,
            CIEmailField,
            CITextField,
        )

        class PostgresCIFieldsModel(models.Model):
            ci_char = CICharField(max_length=255)
            ci_email = CIEmailField()
            ci_text = CITextField()
            array_ci_text = ArrayField(CITextField())

        self.assertEqual(
            PostgresCIFieldsModel.check(),
            [
                checks.Error(
                    "django.contrib.postgres.fields.CICharField is removed except for "
                    "support in historical migrations.",
                    hint=(
                        'Use CharField(db_collation="…") with a case-insensitive '
                        "non-deterministic collation instead."
                    ),
                    obj=PostgresCIFieldsModel._meta.get_field("ci_char"),
                    id="fields.E905",
                ),
                checks.Error(
                    "django.contrib.postgres.fields.CIEmailField is removed except for "
                    "support in historical migrations.",
                    hint=(
                        'Use EmailField(db_collation="…") with a case-insensitive '
                        "non-deterministic collation instead."
                    ),
                    obj=PostgresCIFieldsModel._meta.get_field("ci_email"),
                    id="fields.E906",
                ),
                checks.Error(
                    "django.contrib.postgres.fields.CITextField is removed except for "
                    "support in historical migrations.",
                    hint=(
                        'Use TextField(db_collation="…") with a case-insensitive '
                        "non-deterministic collation instead."
                    ),
                    obj=PostgresCIFieldsModel._meta.get_field("ci_text"),
                    id="fields.E907",
                ),
                checks.Error(
                    "Base field for array has errors:\n"
                    "    django.contrib.postgres.fields.CITextField is removed except "
                    "for support in historical migrations. (fields.E907)",
                    obj=PostgresCIFieldsModel._meta.get_field("array_ci_text"),
                    id="postgres.E001",
                ),
            ],
        )
