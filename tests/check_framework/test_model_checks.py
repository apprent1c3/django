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
        Tests that the system correctly detects and reports collisions when two models within the same application are assigned the same database table name.
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
        Tests that database table collisions between models in the same app are detected when database routers are installed.
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
        Tests the detection of database table collisions across different Django apps.

        Verifies that the system correctly identifies and reports errors when multiple models
        from different apps attempt to use the same database table name.
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
        """

        Tests that the checks framework correctly identifies and reports database table name collisions
        across different Django applications when using database routers.

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
        Tests that no collision errors are raised when an unmanaged model is defined with the same database table as a managed model.
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
        """
        Checks that a proxy model does not introduce any naming collisions, specifically verifying that it shares the same database table as its parent model and passes all model checks.
        """
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
        Checks for duplicate index names in the same model.
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
        Tests that a collision error is raised when two models share the same index name.
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
        """
        Tests that the ORM checks correctly identify identical index names across models that inherit from an abstract model.
        """
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
        Verifies that abstract model interpolation does not result in naming collisions between indexes.
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

        Verifies that checks are run correctly to detect index name collisions across different Django applications.

        Checks that the system raises an error when two models from separate apps have an index with the same name.

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
        Verifies that index names do not collide across apps when using string interpolation in model constraints.

        Tests that models from different apps using the same index name pattern do not result in name conflicts.

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
        Tests that Django correctly detects and reports a collision when multiple constraints in the same model have the same name.
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
        Tests that a CheckConstraint with the same name is not reusable across multiple models, ensuring that constraint names are unique among all models.\"\"\"

         \"\"\"Checks that running model checks raises an error when a constraint name is duplicated.
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
        """
        Tests that the check framework raises an error when an abstract model defines a constraint with a non-unique name that is shared by its concrete subclasses.
        """
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
        Tests that the model check system correctly handles abstract model interpolation, ensuring that no duplicate constraint names are generated when multiple models inherit from the same abstract base model with a constraint.
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
        """

        Tests that a CheckConstraint name collision across two separate apps raises the correct error.

        The test verifies that Django correctly identifies and reports duplicate constraint names 
        when they are defined in different applications.

        """
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
        """
        Test that CheckConstraint names do not collide across different apps when using string interpolation.
        """
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
        Tests that an explicit primary key on a parent model is inherited by its child model.
        """
        class Parent(models.Model):
            id = models.AutoField(primary_key=True)

        class Child(Parent):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_skipped_on_model_with_invalid_app_label(self):
        """
        Tests that the Model.check() method correctly handles models with invalid app labels and does not raise any issues.
        """
        class Model(models.Model):
            class Meta:
                app_label = "invalid_app_label"

        self.assertEqual(Model.check(), [])

    def test_skipped_on_abstract_model(self):
        """
        Verifies that checks are skipped for abstract models, ensuring that no errors are raised when checking abstract model definitions.
        """
        class Abstract(models.Model):
            class Meta:
                abstract = True

        # Call .check() because abstract models are not registered.
        self.assertEqual(Abstract.check(), [])

    def test_explicit_inherited_parent_link(self):
        """
        Checks that a model with an explicit inherited parent link does not produce any errors during system checks.
        """
        class Parent(models.Model):
            id = models.AutoField(primary_key=True)

        class Child(Parent):
            parent_ptr = models.OneToOneField(Parent, models.CASCADE, parent_link=True)

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_auto_created_inherited_pk(self):
        """
        Tests that a warning is raised when a parent model has an auto-created primary key that is not defined explicitly, and an inherited child model does not override the primary key field.
        """
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
        Checks that a parent link field is not automatically created when a model inherits from a parent model that has an auto-created parent link.
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
        Tests that an abstract model's auto-created primary key is properly inherited by its child models, verifying a warning is raised during system checks.
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
        class Model(models.Model):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_explicit_pk(self):
        class Model(models.Model):
            id = models.BigAutoField(primary_key=True)

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    @isolate_apps("check_framework.apps.CheckPKConfig", kwarg_name="apps")
    def test_app_default_auto_field(self, apps):
        """
        Tests the auto field configuration for a default primary key in a Django model when using a custom app configuration.
        """
        class ModelWithPkViaAppConfig(models.Model):
            class Meta:
                app_label = "check_framework.apps.CheckPKConfig"

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [])
