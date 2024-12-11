from unittest import mock

from django.core import checks
from django.core.checks import Error, Warning
from django.db import models
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import (
    isolate_apps,
    modify_settings,
    override_settings,
    override_system_checks,
)


class EmptyRouter:
    pass


@isolate_apps("check_framework", attr_name="apps")
@override_system_checks([checks.model_checks.check_all_models])
class DuplicateDBTableTests(SimpleTestCase):
    def test_collision_in_same_app(self):
        """
        Tests that the system correctly identifies and reports collisions when two models 
        in the same application use the same database table name.

        This checks the functionality of the model validation system, specifically the 
        ability to detect and handle duplicate table names across different models, 
        ensuring data integrity and preventing potential conflicts at the database level.

        The test is expected to return a specific error indicating that the database 
        table 'test_table' is being used by more than one model, thereby confirming 
        the detection of the collision and the proper functioning of the validation mechanism.

        Raises:
            Error: If the system fails to correctly identify and report the table name collision.

        """
        class Model1(models.Model):
            class Meta:
                db_table = "test_table"

        class Model2(models.Model):
            class Meta:
                db_table = "test_table"

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Error(
                    "db_table 'test_table' is used by multiple models: "
                    "check_framework.Model1, check_framework.Model2.",
                    obj="test_table",
                    id="models.E028",
                )
            ],
        )

    @override_settings(
        DATABASE_ROUTERS=["check_framework.test_model_checks.EmptyRouter"]
    )
    def test_collision_in_same_app_database_routers_installed(self):
        """

        Tests for collision detection in database table names when using DATABASE_ROUTERS.

        This test case checks that a warning is raised when two models in the same app
        attempt to use the same database table name, and DATABASE_ROUTERS are installed.
        The test verifies that the warning message accurately identifies the conflicting
        models and provides a hint to check the database routing configuration.

        The expected warning includes the names of the conflicting models and suggests
        verifying that they are correctly routed to separate databases.

        """
        class Model1(models.Model):
            class Meta:
                db_table = "test_table"

        class Model2(models.Model):
            class Meta:
                db_table = "test_table"

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Warning(
                    "db_table 'test_table' is used by multiple models: "
                    "check_framework.Model1, check_framework.Model2.",
                    hint=(
                        "You have configured settings.DATABASE_ROUTERS. Verify "
                        "that check_framework.Model1, check_framework.Model2 are "
                        "correctly routed to separate databases."
                    ),
                    obj="test_table",
                    id="models.W035",
                )
            ],
        )

    @modify_settings(INSTALLED_APPS={"append": "basic"})
    @isolate_apps("basic", "check_framework", kwarg_name="apps")
    def test_collision_across_apps(self, apps):
        """

        Tests that Django's system check framework correctly identifies and reports
        collisions between model database tables across different applications.

        Verifies that when two models from different apps share the same database table name,
        the checks system returns an error indicating the table name collision and lists the
        involved models.

        """
        class Model1(models.Model):
            class Meta:
                app_label = "basic"
                db_table = "test_table"

        class Model2(models.Model):
            class Meta:
                app_label = "check_framework"
                db_table = "test_table"

        self.assertEqual(
            checks.run_checks(app_configs=apps.get_app_configs()),
            [
                Error(
                    "db_table 'test_table' is used by multiple models: "
                    "basic.Model1, check_framework.Model2.",
                    obj="test_table",
                    id="models.E028",
                )
            ],
        )

    @modify_settings(INSTALLED_APPS={"append": "basic"})
    @override_settings(
        DATABASE_ROUTERS=["check_framework.test_model_checks.EmptyRouter"]
    )
    @isolate_apps("basic", "check_framework", kwarg_name="apps")
    def test_collision_across_apps_database_routers_installed(self, apps):
        class Model1(models.Model):
            class Meta:
                app_label = "basic"
                db_table = "test_table"

        class Model2(models.Model):
            class Meta:
                app_label = "check_framework"
                db_table = "test_table"

        self.assertEqual(
            checks.run_checks(app_configs=apps.get_app_configs()),
            [
                Warning(
                    "db_table 'test_table' is used by multiple models: "
                    "basic.Model1, check_framework.Model2.",
                    hint=(
                        "You have configured settings.DATABASE_ROUTERS. Verify "
                        "that basic.Model1, check_framework.Model2 are correctly "
                        "routed to separate databases."
                    ),
                    obj="test_table",
                    id="models.W035",
                )
            ],
        )

    def test_no_collision_for_unmanaged_models(self):
        """
        Tests that no collision errors occur when checking the database for models that are explicitly marked as unmanaged. 

        This test case creates two models: one that is unmanaged and another that is managed, both mapping to the same database table. It then runs the check system to ensure that no errors are raised due to the duplicate table mapping, confirming that the unmanaged model is properly handled and does not conflict with the managed model.
        """
        class Unmanaged(models.Model):
            class Meta:
                db_table = "test_table"
                managed = False

        class Managed(models.Model):
            class Meta:
                db_table = "test_table"

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_no_collision_for_proxy_models(self):
        class Model(models.Model):
            class Meta:
                db_table = "test_table"

        class ProxyModel(Model):
            class Meta:
                proxy = True

        self.assertEqual(Model._meta.db_table, ProxyModel._meta.db_table)
        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])


@isolate_apps("check_framework", attr_name="apps")
@override_system_checks([checks.model_checks.check_all_models])
class IndexNameTests(SimpleTestCase):
    def test_collision_in_same_model(self):
        """
        Checks for duplicate index names in a model.

        This test verifies that a model with multiple indexes having the same name will raise a warning, 
        ensuring index name uniqueness within a model to prevent potential conflicts.
        """
        index = models.Index(fields=["id"], name="foo")

        class Model(models.Model):
            class Meta:
                indexes = [index, index]

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Error(
                    "index name 'foo' is not unique for model check_framework.Model.",
                    id="models.E029",
                ),
            ],
        )

    def test_collision_in_different_models(self):
        """

        Tests whether a check is raised when the same index name is used in different models.

        This test verifies that a unique index name is enforced across models, ensuring data integrity and preventing potential conflicts.

        """
        index = models.Index(fields=["id"], name="foo")

        class Model1(models.Model):
            class Meta:
                indexes = [index]

        class Model2(models.Model):
            class Meta:
                indexes = [index]

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Error(
                    "index name 'foo' is not unique among models: "
                    "check_framework.Model1, check_framework.Model2.",
                    id="models.E030",
                ),
            ],
        )

    def test_collision_abstract_model(self):
        class AbstractModel(models.Model):
            class Meta:
                indexes = [models.Index(fields=["id"], name="foo")]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Error(
                    "index name 'foo' is not unique among models: "
                    "check_framework.Model1, check_framework.Model2.",
                    id="models.E030",
                ),
            ],
        )

    def test_no_collision_abstract_model_interpolation(self):
        """
        Test that no collision occurs when inheriting from an abstract model with a predefined index and no additional fields in the concrete models.
        """
        class AbstractModel(models.Model):
            name = models.CharField(max_length=20)

            class Meta:
                indexes = [
                    models.Index(fields=["name"], name="%(app_label)s_%(class)s_foo")
                ]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    @modify_settings(INSTALLED_APPS={"append": "basic"})
    @isolate_apps("basic", "check_framework", kwarg_name="apps")
    def test_collision_across_apps(self, apps):
        """

        Tests that the system correctly identifies and reports collisions of index names across different applications.

        This test case verifies that when two models from separate applications have an index with the same name, the system raises an error. The error message should include the names of the models that have the conflicting index name.

        The test creates two models, one in the 'basic' application and one in the 'check_framework' application, each with an index named 'foo'. It then runs the framework's checks on the applications and asserts that the expected error is raised, confirming that the system correctly detects and reports the index name collision.

        """
        index = models.Index(fields=["id"], name="foo")

        class Model1(models.Model):
            class Meta:
                app_label = "basic"
                indexes = [index]

        class Model2(models.Model):
            class Meta:
                app_label = "check_framework"
                indexes = [index]

        self.assertEqual(
            checks.run_checks(app_configs=apps.get_app_configs()),
            [
                Error(
                    "index name 'foo' is not unique among models: basic.Model1, "
                    "check_framework.Model2.",
                    id="models.E030",
                ),
            ],
        )

    @modify_settings(INSTALLED_APPS={"append": "basic"})
    @isolate_apps("basic", "check_framework", kwarg_name="apps")
    def test_no_collision_across_apps_interpolation(self, apps):
        """

        Tests that there are no collisions across different Django apps when using interpolated names for model indices.

        This test ensures that when two models in separate apps define an index with the same name using
        interpolation (e.g. '%(app_label)s_%(class)s_foo'), Django does not raise any errors or warnings.
        Instead, the actual index names are correctly generated based on the app label and model class,
        preventing any potential naming conflicts.

        The test case involves creating two models, each in a different app, with an index defined using
        interpolation. It then runs Django's system checks to verify that no errors or warnings are raised.

        """
        index = models.Index(fields=["id"], name="%(app_label)s_%(class)s_foo")

        class Model1(models.Model):
            class Meta:
                app_label = "basic"
                constraints = [index]

        class Model2(models.Model):
            class Meta:
                app_label = "check_framework"
                constraints = [index]

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [])


@isolate_apps("check_framework", attr_name="apps")
@override_system_checks([checks.model_checks.check_all_models])
@skipUnlessDBFeature("supports_table_check_constraints")
class ConstraintNameTests(TestCase):
    def test_collision_in_same_model(self):
        """

        Tests that a collision occurs when two CheckConstraints in the same model have the same name.

        This function verifies that the checks system correctly identifies and reports a naming conflict 
        between two CheckConstraints defined in a single model. It ensures that the error message is 
        triggered when the check_constraints command is run, indicating that the constraint name 'foo' 
        is not unique for the model.

        """
        class Model(models.Model):
            class Meta:
                constraints = [
                    models.CheckConstraint(condition=models.Q(id__gt=0), name="foo"),
                    models.CheckConstraint(condition=models.Q(id__lt=100), name="foo"),
                ]

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Error(
                    "constraint name 'foo' is not unique for model "
                    "check_framework.Model.",
                    id="models.E031",
                ),
            ],
        )

    def test_collision_in_different_models(self):
        """

        Tests that Django raises a validation error when a CheckConstraint with a 
        non-unique name is defined across multiple models.

        This test ensures that the framework correctly identifies and reports 
        constraint name collisions, helping prevent potential data inconsistencies 
        and errors.

        """
        constraint = models.CheckConstraint(condition=models.Q(id__gt=0), name="foo")

        class Model1(models.Model):
            class Meta:
                constraints = [constraint]

        class Model2(models.Model):
            class Meta:
                constraints = [constraint]

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Error(
                    "constraint name 'foo' is not unique among models: "
                    "check_framework.Model1, check_framework.Model2.",
                    id="models.E032",
                ),
            ],
        )

    def test_collision_abstract_model(self):
        class AbstractModel(models.Model):
            class Meta:
                constraints = [
                    models.CheckConstraint(condition=models.Q(id__gt=0), name="foo")
                ]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Error(
                    "constraint name 'foo' is not unique among models: "
                    "check_framework.Model1, check_framework.Model2.",
                    id="models.E032",
                ),
            ],
        )

    def test_no_collision_abstract_model_interpolation(self):
        """

        Tests that abstract model interpolation does not cause collisions when 
        multiple concrete models inherit from the same abstract model with 
        database constraints.

        This test case verifies that the checks system correctly handles 
        inherited constraints from abstract models, ensuring that the constraints 
        are properly interpolated and do not conflict with each other.

        """
        class AbstractModel(models.Model):
            class Meta:
                constraints = [
                    models.CheckConstraint(
                        condition=models.Q(id__gt=0), name="%(app_label)s_%(class)s_foo"
                    ),
                ]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    @modify_settings(INSTALLED_APPS={"append": "basic"})
    @isolate_apps("basic", "check_framework", kwarg_name="apps")
    def test_collision_across_apps(self, apps):
        constraint = models.CheckConstraint(condition=models.Q(id__gt=0), name="foo")

        class Model1(models.Model):
            class Meta:
                app_label = "basic"
                constraints = [constraint]

        class Model2(models.Model):
            class Meta:
                app_label = "check_framework"
                constraints = [constraint]

        self.assertEqual(
            checks.run_checks(app_configs=apps.get_app_configs()),
            [
                Error(
                    "constraint name 'foo' is not unique among models: "
                    "basic.Model1, check_framework.Model2.",
                    id="models.E032",
                ),
            ],
        )

    @modify_settings(INSTALLED_APPS={"append": "basic"})
    @isolate_apps("basic", "check_framework", kwarg_name="apps")
    def test_no_collision_across_apps_interpolation(self, apps):
        constraint = models.CheckConstraint(
            condition=models.Q(id__gt=0), name="%(app_label)s_%(class)s_foo"
        )

        class Model1(models.Model):
            class Meta:
                app_label = "basic"
                constraints = [constraint]

        class Model2(models.Model):
            class Meta:
                app_label = "check_framework"
                constraints = [constraint]

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [])


def mocked_is_overridden(self, setting):
    # Force treating DEFAULT_AUTO_FIELD = 'django.db.models.AutoField' as a not
    # overridden setting.
    return (
        setting != "DEFAULT_AUTO_FIELD"
        or self.DEFAULT_AUTO_FIELD != "django.db.models.AutoField"
    )


@mock.patch("django.conf.UserSettingsHolder.is_overridden", mocked_is_overridden)
@override_settings(DEFAULT_AUTO_FIELD="django.db.models.AutoField")
@isolate_apps("check_framework.apps.CheckDefaultPKConfig", attr_name="apps")
@override_system_checks([checks.model_checks.check_all_models])
class ModelDefaultAutoFieldTests(SimpleTestCase):
    msg = (
        "Auto-created primary key used when not defining a primary key type, "
        "by default 'django.db.models.AutoField'."
    )
    hint = (
        "Configure the DEFAULT_AUTO_FIELD setting or the "
        "CheckDefaultPKConfig.default_auto_field attribute to point to a "
        "subclass of AutoField, e.g. 'django.db.models.BigAutoField'."
    )

    def test_auto_created_pk(self):
        class Model(models.Model):
            pass

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Warning(self.msg, hint=self.hint, obj=Model, id="models.W042"),
            ],
        )

    def test_explicit_inherited_pk(self):
        """
        Tests that explicitly defining a primary key in a parent model results in no errors when running model checks on a child model that inherits from it.

        This test case ensures that the child model correctly inherits the primary key from its parent and that the model validation checks pass without any issues.

        :raises: AssertionError if model checks fail
        """
        class Parent(models.Model):
            id = models.AutoField(primary_key=True)

        class Child(Parent):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_skipped_on_model_with_invalid_app_label(self):
        class Model(models.Model):
            class Meta:
                app_label = "invalid_app_label"

        self.assertEqual(Model.check(), [])

    def test_skipped_on_abstract_model(self):
        class Abstract(models.Model):
            class Meta:
                abstract = True

        # Call .check() because abstract models are not registered.
        self.assertEqual(Abstract.check(), [])

    def test_explicit_inherited_parent_link(self):
        class Parent(models.Model):
            id = models.AutoField(primary_key=True)

        class Child(Parent):
            parent_ptr = models.OneToOneField(Parent, models.CASCADE, parent_link=True)

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_auto_created_inherited_pk(self):
        class Parent(models.Model):
            pass

        class Child(Parent):
            pass

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Warning(self.msg, hint=self.hint, obj=Parent, id="models.W042"),
            ],
        )

    def test_auto_created_inherited_parent_link(self):
        """
        Tests the automatic creation of inherited parent links when a child model inherits from a parent model.

        Checks that a warning is raised when a child model defines its own parent link, as Django automatically creates a parent link for inherited models.
        The test verifies that the warning is correctly raised with the expected message, hint, and object reference to the parent model.
        This ensures that Django's model inheritance behavior is correctly validated and reported during system checks.
        """
        class Parent(models.Model):
            pass

        class Child(Parent):
            parent_ptr = models.OneToOneField(Parent, models.CASCADE, parent_link=True)

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Warning(self.msg, hint=self.hint, obj=Parent, id="models.W042"),
            ],
        )

    def test_auto_created_pk_inherited_abstract_parent(self):
        """

        Tests that a warning is raised when an abstract parent model does not explicitly define a primary key field,
        and Django automatically creates one, which is then inherited by its child models.

        The test case creates an abstract parent model and a child model that inherits from it.
        It then checks that running model checks raises the expected warning (models.W042) due to the auto-created primary key.

        """
        class Parent(models.Model):
            class Meta:
                abstract = True

        class Child(Parent):
            pass

        self.assertEqual(
            checks.run_checks(app_configs=self.apps.get_app_configs()),
            [
                Warning(self.msg, hint=self.hint, obj=Child, id="models.W042"),
            ],
        )

    @override_settings(DEFAULT_AUTO_FIELD="django.db.models.BigAutoField")
    def test_default_auto_field_setting(self):
        """

        Test the default auto field setting in Django models.

        Verifies that the default auto field setting is correctly applied when creating a model.
        It checks if the model passes the system checks without raising any errors.

        This test ensures that the model configuration is valid and the auto field is properly defined,
        without explicitly specifying the auto field type in the model definition.

        """
        class Model(models.Model):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_explicit_pk(self):
        """
        Tests that a model with an explicit primary key definition passes model checks.

        This test case verifies that a model with a primary key explicitly defined using the
        BigAutoField does not raise any errors when running model checks. The test creates a
        model with an explicit primary key and then runs model checks to ensure that no
        checks fail.

        :raises AssertionError: If model checks fail for the model with an explicit primary key

        """
        class Model(models.Model):
            id = models.BigAutoField(primary_key=True)

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    @isolate_apps("check_framework.apps.CheckPKConfig", kwarg_name="apps")
    def test_app_default_auto_field(self, apps):
        """
        Test the default auto field functionality in a model.

        This test case ensures that the default auto field is correctly applied to a model when the model is defined with an app_label that corresponds to a specific application configuration.

        It verifies that the framework's checks do not report any errors when the model is created with the default auto field and the given application configuration. 

        Parameters
        ----------
        apps : dict
            A dictionary containing the application configurations to be used for testing.

        Returns
        -------
        None 

        Raises
        ------
        AssertionError
            If the framework's checks report any errors.
        """
        class ModelWithPkViaAppConfig(models.Model):
            class Meta:
                app_label = "check_framework.apps.CheckPKConfig"

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [])
