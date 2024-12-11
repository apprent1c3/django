from io import StringIO

from django.core.management import call_command

from . import PostgreSQLTestCase


class InspectDBTests(PostgreSQLTestCase):
    def assertFieldsInModel(self, model, field_outputs):
        """

        Asserts that specified fields are present in a given database model.

        This function uses Django's inspectdb command to inspect the database model
        and checks if the provided field outputs are present in the model's table.
        It is typically used in testing to verify that a model's database schema
        matches the expected field definitions.

        :param model: The name of the database model to inspect
        :param field_outputs: A list of field names or outputs to check for in the model

        """
        out = StringIO()
        call_command(
            "inspectdb",
            table_name_filter=lambda tn: tn.startswith(model),
            stdout=out,
        )
        output = out.getvalue()
        for field_output in field_outputs:
            self.assertIn(field_output, output)

    def test_range_fields(self):
        self.assertFieldsInModel(
            "postgres_tests_rangesmodel",
            [
                "ints = django.contrib.postgres.fields.IntegerRangeField(blank=True, "
                "null=True)",
                "bigints = django.contrib.postgres.fields.BigIntegerRangeField("
                "blank=True, null=True)",
                "decimals = django.contrib.postgres.fields.DecimalRangeField("
                "blank=True, null=True)",
                "timestamps = django.contrib.postgres.fields.DateTimeRangeField("
                "blank=True, null=True)",
                "dates = django.contrib.postgres.fields.DateRangeField(blank=True, "
                "null=True)",
            ],
        )
