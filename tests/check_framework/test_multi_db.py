from unittest import mock

from django.db import connections, models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps, override_settings


class TestRouter:
    """
    Routes to the 'other' database if the model name starts with 'Other'.
    """

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == ("other" if model_name.startswith("other") else "default")


@override_settings(DATABASE_ROUTERS=[TestRouter()])
@isolate_apps("check_framework")
class TestMultiDBChecks(SimpleTestCase):
    def _patch_check_field_on(self, db):
        return mock.patch.object(connections[db].validation, "check_field")

    def test_checks_called_on_the_default_database(self):
        """
        .\"\"\"
        Verifies that model checks are performed on the default database.

        This test case ensures that when a model instance's check method is called,
        it invokes the check_field_on method specifically for the default database,
        leaving other databases unaffected.

        :param None:
        :returns: None
        :raises: AssertionError if the check_field_on method is not called on the default database

        """
        class Model(models.Model):
            field = models.CharField(max_length=100)

        model = Model()
        with self._patch_check_field_on("default") as mock_check_field_default:
            with self._patch_check_field_on("other") as mock_check_field_other:
                model.check(databases={"default", "other"})
                self.assertTrue(mock_check_field_default.called)
                self.assertFalse(mock_check_field_other.called)

    def test_checks_called_on_the_other_database(self):
        """

        Tests that model checks are called on the other database.

        This test case verifies that when a model instance is checked, the checks are
        performed on the specified database ('other' in this case), rather than the
        default database. It ensures that the check_field method is called on the
        'other' database and not on the 'default' database.

        The test creates a model instance and patches the check_field method on both
        'default' and 'other' databases. It then calls the check method on the model
        instance, specifying both databases, and asserts that the check_field method
        was called on the 'other' database and not on the 'default' database.

        """
        class OtherModel(models.Model):
            field = models.CharField(max_length=100)

        model = OtherModel()
        with self._patch_check_field_on("other") as mock_check_field_other:
            with self._patch_check_field_on("default") as mock_check_field_default:
                model.check(databases={"default", "other"})
                self.assertTrue(mock_check_field_other.called)
                self.assertFalse(mock_check_field_default.called)
