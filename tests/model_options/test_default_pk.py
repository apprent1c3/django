from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.test import SimpleTestCase, override_settings
from django.test.utils import isolate_apps


class MyBigAutoField(models.BigAutoField):
    pass


@isolate_apps("model_options")
class TestDefaultPK(SimpleTestCase):
    @override_settings(DEFAULT_AUTO_FIELD="django.db.models.NonexistentAutoField")
    def test_default_auto_field_setting_nonexistent(self):
        """
        Tests that setting DEFAULT_AUTO_FIELD to a non-existent auto field module raises an ImproperlyConfigured exception.

        This test verifies that Django correctly handles an invalid DEFAULT_AUTO_FIELD setting by checking if the specified module can be imported.
        If the module does not exist, it raises an ImproperlyConfigured exception with a descriptive error message. 

        This ensures that Django provides informative error messages when encountering invalid configurations, making it easier to diagnose and fix configuration issues.

        """
        msg = (
            "DEFAULT_AUTO_FIELD refers to the module "
            "'django.db.models.NonexistentAutoField' that could not be "
            "imported."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):

            class Model(models.Model):
                pass

    @isolate_apps("model_options.apps.ModelPKNonexistentConfig")
    def test_app_default_auto_field_nonexistent(self):
        """
        Tests that attempting to use a nonexistent default auto field for a Django app raises an ImproperlyConfigured exception.

        This test case checks the behavior of Django's default auto field configuration when a non-existent module is referenced.
        It verifies that the expected error message is raised, ensuring that the application is properly handling invalid configuration.

        The test is isolated to the ModelPKNonexistentConfig app configuration to prevent interference with other tests.
        It covers a scenario where a developer might inadvertently specify a non-existent module for the default auto field, 
        providing a safeguard against potential configuration mistakes in Django applications.
        """
        msg = (
            "model_options.apps.ModelPKNonexistentConfig.default_auto_field "
            "refers to the module 'django.db.models.NonexistentAutoField' "
            "that could not be imported."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):

            class Model(models.Model):
                pass

    @override_settings(DEFAULT_AUTO_FIELD="django.db.models.TextField")
    def test_default_auto_field_setting_non_auto(self):
        """
        Tests that setting DEFAULT_AUTO_FIELD to a non-AutoField (in this case, TextField) raises a ValueError when creating a model without an explicit primary key. The error occurs because the DEFAULT_AUTO_FIELD setting specifies the default field type to use for primary keys, and this type must subclass AutoField.
        """
        msg = (
            "Primary key 'django.db.models.TextField' referred by "
            "DEFAULT_AUTO_FIELD must subclass AutoField."
        )
        with self.assertRaisesMessage(ValueError, msg):

            class Model(models.Model):
                pass

    @isolate_apps("model_options.apps.ModelPKNonAutoConfig")
    def test_app_default_auto_field_non_auto(self):
        """

        Tests whether the application's default auto field is properly set when it's not an AutoField subclass.

        When an application defines a non-AutoField primary key, this function verifies that
        the default auto field, if set, must inherit from Django's AutoField. The test ensures
        that attempting to use a non-AutoField subclass raises a ValueError with the expected
        error message.

        """
        msg = (
            "Primary key 'django.db.models.TextField' referred by "
            "model_options.apps.ModelPKNonAutoConfig.default_auto_field must "
            "subclass AutoField."
        )
        with self.assertRaisesMessage(ValueError, msg):

            class Model(models.Model):
                pass

    @override_settings(DEFAULT_AUTO_FIELD=None)
    def test_default_auto_field_setting_none(self):
        """
        Tests that attempting to use an empty DEFAULT_AUTO_FIELD setting raises an ImproperlyConfigured exception.

            This test verifies that when the DEFAULT_AUTO_FIELD setting is set to None, 
            defining a model without an explicit primary key field results in an error. 
            The expected error message indicates that the DEFAULT_AUTO_FIELD setting cannot be empty.

            Args:
                None

            Raises:
                ImproperlyConfigured: With a message indicating that DEFAULT_AUTO_FIELD must not be empty.

            Note:
                This test case ensures that Django's model introspection and validation correctly enforce 
                the requirement for a non-empty DEFAULT_AUTO_FIELD setting when creating models.

        """
        msg = "DEFAULT_AUTO_FIELD must not be empty."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):

            class Model(models.Model):
                pass

    @isolate_apps("model_options.apps.ModelPKNoneConfig")
    def test_app_default_auto_field_none(self):
        """

        Tests that the default_auto_field in a Django app is configured correctly.

        Verifies that setting default_auto_field to None in a Django app's configuration
        raises an ImproperlyConfigured exception, as this setting cannot be empty.

        This test ensures that the app's configuration is valid and properly set up,
        preventing potential errors when using the app's models.

        """
        msg = (
            "model_options.apps.ModelPKNoneConfig.default_auto_field must not "
            "be empty."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):

            class Model(models.Model):
                pass

    @isolate_apps("model_options.apps.ModelDefaultPKConfig")
    @override_settings(DEFAULT_AUTO_FIELD="django.db.models.SmallAutoField")
    def test_default_auto_field_setting(self):
        """

        Tests the usage of the DEFAULT_AUTO_FIELD setting in the model configuration.

        This test case checks if the default auto field type is correctly set to SmallAutoField
        when the DEFAULT_AUTO_FIELD setting is overridden. It verifies that the primary key
        field of a model is an instance of SmallAutoField when the setting is applied.

        The test isolates the model configuration and overrides the default auto field setting
        to ensure consistent results.

        """
        class Model(models.Model):
            pass

        self.assertIsInstance(Model._meta.pk, models.SmallAutoField)

    @override_settings(
        DEFAULT_AUTO_FIELD="model_options.test_default_pk.MyBigAutoField"
    )
    def test_default_auto_field_setting_bigautofield_subclass(self):
        """

        Tests the EFFECTIVE use of the DEFAULT_AUTO_FIELD setting when the specified field is a subclass of BigAutoField.

        Verifies that the default primary key for models is correctly set to the specified auto field class when the DEFAULT_AUTO_FIELD setting is overridden to point to a subclass of BigAutoField.

        Ensures that the primary key of a model, when not explicitly defined, defaults to the BigAutoField subclass as specified in the DEFAULT_AUTO_FIELD setting, promoting consistency and control over model primary keys.

        """
        class Model(models.Model):
            pass

        self.assertIsInstance(Model._meta.pk, MyBigAutoField)

    @isolate_apps("model_options.apps.ModelPKConfig")
    @override_settings(DEFAULT_AUTO_FIELD="django.db.models.AutoField")
    def test_app_default_auto_field(self):
        """

        Tests that the default auto field for a model in the ModelPKConfig app is set to SmallAutoField.

        This test ensures that when the DEFAULT_AUTO_FIELD setting is overridden to use AutoField, 
        models defined in the ModelPKConfig app still use SmallAutoField as their primary key field.

        """
        class Model(models.Model):
            pass

        self.assertIsInstance(Model._meta.pk, models.SmallAutoField)

    @isolate_apps("model_options.apps.ModelDefaultPKConfig")
    @override_settings(DEFAULT_AUTO_FIELD="django.db.models.SmallAutoField")
    def test_m2m_default_auto_field_setting(self):
        class M2MModel(models.Model):
            m2m = models.ManyToManyField("self")

        m2m_pk = M2MModel._meta.get_field("m2m").remote_field.through._meta.pk
        self.assertIsInstance(m2m_pk, models.SmallAutoField)

    @isolate_apps("model_options.apps.ModelPKConfig")
    @override_settings(DEFAULT_AUTO_FIELD="django.db.models.AutoField")
    def test_m2m_app_default_auto_field(self):
        """
        Tests the behavior of default auto field for many-to-many fields in a Django model.

        This test case creates a model with a many-to-many field referencing itself and checks if the primary key of the intermediate table (through model) is an instance of SmallAutoField, which is the expected default behavior when the DEFAULT_AUTO_FIELD setting is set to 'django.db.models.AutoField'.

        Verifies that the auto field for the many-to-many relationship is correctly configured and generated by Django's ORM.
        """
        class M2MModel(models.Model):
            m2m = models.ManyToManyField("self")

        m2m_pk = M2MModel._meta.get_field("m2m").remote_field.through._meta.pk
        self.assertIsInstance(m2m_pk, models.SmallAutoField)
