from django.core import checks
from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps


@isolate_apps("check_framework")
class TestDeprecatedField(SimpleTestCase):
    def test_default_details(self):
        """
        Tests that a deprecated model field triggers a warning when the model's check method is called.
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
        Tests whether a model correctly reports a deprecation warning for a field with deprecated details specified by the user.
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
        Tests that the default checks for removed model fields raises the correct error.\"\"\"
        ```python
        ```
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
        Tests that the system correctly identifies and reports removed field details specified by a user.
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
