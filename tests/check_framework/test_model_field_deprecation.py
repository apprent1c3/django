from django.core import checks
from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps


@isolate_apps("check_framework")
class TestDeprecatedField(SimpleTestCase):
    def test_default_details(self):
        """
        Tests that a deprecated model field triggers a system check warning when no deprecation details are provided.
        """
        class MyField(models.Field):
            system_check_deprecated_details = {}

        class Model(models.Model):
            name = MyField()

        model = Model()
        self.assertEqual(
            model.check(),
            [
                checks.Warning(
                    msg="MyField has been deprecated.",
                    obj=Model._meta.get_field("name"),
                    id="fields.WXXX",
                )
            ],
        )

    def test_user_specified_details(self):
        """
        Verifies that a user-specified model field correctly reports its own deprecation details through the model's system checks.
        """
        class MyField(models.Field):
            system_check_deprecated_details = {
                "msg": "This field is deprecated and will be removed soon.",
                "hint": "Use something else.",
                "id": "fields.W999",
            }

        class Model(models.Model):
            name = MyField()

        model = Model()
        self.assertEqual(
            model.check(),
            [
                checks.Warning(
                    msg="This field is deprecated and will be removed soon.",
                    hint="Use something else.",
                    obj=Model._meta.get_field("name"),
                    id="fields.W999",
                )
            ],
        )


@isolate_apps("check_framework")
class TestRemovedField(SimpleTestCase):
    def test_default_details(self):
        """
        Tests that a removed Field type raises the correct error when used in a model.\"\"\"


        However, I would recommend more specific docstring, especially because this appears to be a test function:
        \"\"\"Verifies that the system_check_removed_details check correctly reports an error when a removed field type (MyField) is used in a model.\"\"\"

        You may also want to consider including information about the expected behavior and any preconditions.
        """
        class MyField(models.Field):
            system_check_removed_details = {}

        class Model(models.Model):
            name = MyField()

        model = Model()
        self.assertEqual(
            model.check(),
            [
                checks.Error(
                    msg=(
                        "MyField has been removed except for support in historical "
                        "migrations."
                    ),
                    obj=Model._meta.get_field("name"),
                    id="fields.EXXX",
                )
            ],
        )

    def test_user_specified_details(self):
        """
        Tests that a model's check method correctly identifies and reports removed field details specified by the user.
        """
        class MyField(models.Field):
            system_check_removed_details = {
                "msg": "Support for this field is gone.",
                "hint": "Use something else.",
                "id": "fields.E999",
            }

        class Model(models.Model):
            name = MyField()

        model = Model()
        self.assertEqual(
            model.check(),
            [
                checks.Error(
                    msg="Support for this field is gone.",
                    hint="Use something else.",
                    obj=Model._meta.get_field("name"),
                    id="fields.E999",
                )
            ],
        )
