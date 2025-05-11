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
        Test that a collision error is raised when two models in the same app use the same db_table attribute.
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
        Tests if a warning is raised when multiple models in the same app use the same database table, with a custom database router installed.
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
        Tests for database table name collision across different applications.

        Verifies that the check framework correctly identifies and reports errors
        when two models from different apps use the same database table name.
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
        Tests database collision detection across multiple applications with custom database routers. 
        Verifies that the system correctly identifies and warns about duplicate database table names used by different models in separate apps.
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
        Tests that no collision errors occur when unmanaged models are used alongside managed models with the same database table name.
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
        Verifies that creating a proxy model does not result in any database table collisions, ensuring the proxy model inherits the same table as its parent model.
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
        Tests that duplicate index names within the same model are detected and reported as an error.
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
        Checks for unique index names across models. Verifies that indexes with the same name are not defined in multiple models.
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

        Tests that checks are triggered for abstract model indexes that are not unique across all models.

        Checks if an Error E030 is raised when multiple models inherit from an abstract model
        with a non-unique index name.

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
        Tests that abstract model inheritance does not result in duplicate index names during database checks.
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
        Test that checks detect index name collisions across different applications.

        Verifies that the checks system correctly identifies and reports duplicate index names 
        across models from different apps, ensuring that each index name remains unique.

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
        Verifies that model constraint names do not collide across different applications when interpolation is used, ensuring uniqueness of constraint names in the database schema.
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
        Tests that Django raises an error when a model has multiple CheckConstraints with the same name.
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
        Tester for collision of constraint names across different models, ensuring that each constraint name is unique across all models.
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

        Verifies that a CheckConstraint with a non-unique name raises an error 
        when inherited by multiple concrete models from an abstract base model.

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
        Checks that Django's model checks do not report false positives for abstract model interpolation when using CheckConstraints in an abstract base class.
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
        Tests that checks detect and report duplicate constraint names across different apps.\"\"\"

        \"\"\" 
            This test case verifies that Django's system check can correctly identify 
            and warn about duplicate CheckConstraint names used across different django 
            applications.

            :param apps: A fixture containing the app configurations to run the checks on.
            :return: None

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
        Checks if there are no naming collisions for constraints across different applications, particularly when using string interpolation for constraint names.
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
        Tests that an AutoField primary key is correctly inherited from a parent model by a child model, ensuring no checks errors are raised.
        """
        class Parent(models.Model):
            id = models.AutoField(primary_key=True)

        class Child(Parent):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_skipped_on_model_with_invalid_app_label(self):
        """
        Tests that a model with an invalid app label is properly skipped during checks.
        """
        class Model(models.Model):
            class Meta:
                app_label = "invalid_app_label"

        self.assertEqual(Model.check(), [])

    def test_skipped_on_abstract_model(self):
        """
        Tests that the check method on an abstract model does not report any errors, as validation is skipped for abstract models.
        """
        class Abstract(models.Model):
            class Meta:
                abstract = True

        # Call .check() because abstract models are not registered.
        self.assertEqual(Abstract.check(), [])

    def test_explicit_inherited_parent_link(self):
        """
        Tests that an explicitly defined inherited parent link does not trigger any model check errors.
        """
        class Parent(models.Model):
            id = models.AutoField(primary_key=True)

        class Child(Parent):
            parent_ptr = models.OneToOneField(Parent, models.CASCADE, parent_link=True)

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_auto_created_inherited_pk(self):
        """
        Tests whether an auto-created primary key is properly inherited from a parent model by a child model, triggering a warning if the parent model lacks an explicit primary key.
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

        Tests that a warning is raised when a OneToOneField with parent_link=True is
        automatically created in an inherited model, rather than explicitly defining it.

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
        Tests that an abstract model's auto-created primary key is properly inherited by its child model, triggering a warning if the child model does not define its own primary key.
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
        Tests that the default auto field for a model is correctly set when an app is isolated.
        """
        class ModelWithPkViaAppConfig(models.Model):
            class Meta:
                app_label = "check_framework.apps.CheckPKConfig"

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [])
