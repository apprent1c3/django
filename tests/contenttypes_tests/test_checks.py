from unittest import mock

from django.contrib.contenttypes.checks import check_model_name_lengths
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core import checks
from django.db import models
from django.test import SimpleTestCase, override_settings
from django.test.utils import isolate_apps


@isolate_apps("contenttypes_tests", attr_name="apps")
class GenericForeignKeyTests(SimpleTestCase):
    databases = "__all__"

    def test_missing_content_type_field(self):
        class TaggedItem(models.Model):
            # no content_type field
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey()

        expected = [
            checks.Error(
                "The GenericForeignKey content type references the nonexistent "
                "field 'TaggedItem.content_type'.",
                obj=TaggedItem.content_object,
                id="contenttypes.E002",
            )
        ]
        self.assertEqual(TaggedItem.content_object.check(), expected)

    def test_invalid_content_type_field(self):
        """

        Tests the case where the content_type field in a GenericForeignKey is not a ForeignKey to 'contenttypes.ContentType'.

        This test checks that a proper error is raised when the content_type field is defined as an IntegerField instead of a ForeignKey to ContentType, 
        as required by the GenericForeignKey.

        The test validates that the check returns an error message indicating the problem with the content_type field and provides a hint for the correct implementation.

        """
        class Model(models.Model):
            content_type = models.IntegerField()  # should be ForeignKey
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey("content_type", "object_id")

        self.assertEqual(
            Model.content_object.check(),
            [
                checks.Error(
                    "'Model.content_type' is not a ForeignKey.",
                    hint=(
                        "GenericForeignKeys must use a ForeignKey to "
                        "'contenttypes.ContentType' as the 'content_type' field."
                    ),
                    obj=Model.content_object,
                    id="contenttypes.E003",
                )
            ],
        )

    def test_content_type_field_pointing_to_wrong_model(self):
        """

        .. function:: test_content_type_field_pointing_to_wrong_model

            Tests that GenericForeignKey's content_type field must point to a model that is a subclass of contenttypes.ContentType.

            Verifies the integrity of GenericForeignKey relationships by checking if the content_type field is correctly defined as a ForeignKey to contenttypes.ContentType.

            The test checks for a specific error (contenttypes.E004) that occurs when the content_type field is not a ForeignKey to contenttypes.ContentType, ensuring that the GenericForeignKey is properly configured.

        """
        class Model(models.Model):
            content_type = models.ForeignKey(
                "self", models.CASCADE
            )  # should point to ContentType
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey("content_type", "object_id")

        self.assertEqual(
            Model.content_object.check(),
            [
                checks.Error(
                    "'Model.content_type' is not a ForeignKey to "
                    "'contenttypes.ContentType'.",
                    hint=(
                        "GenericForeignKeys must use a ForeignKey to "
                        "'contenttypes.ContentType' as the 'content_type' field."
                    ),
                    obj=Model.content_object,
                    id="contenttypes.E004",
                )
            ],
        )

    def test_missing_object_id_field(self):
        class TaggedItem(models.Model):
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            # missing object_id field
            content_object = GenericForeignKey()

        self.assertEqual(
            TaggedItem.content_object.check(),
            [
                checks.Error(
                    "The GenericForeignKey object ID references the nonexistent "
                    "field 'object_id'.",
                    obj=TaggedItem.content_object,
                    id="contenttypes.E001",
                )
            ],
        )

    def test_field_name_ending_with_underscore(self):
        class Model(models.Model):
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()
            content_object_ = GenericForeignKey("content_type", "object_id")

        self.assertEqual(
            Model.content_object_.check(),
            [
                checks.Error(
                    "Field names must not end with an underscore.",
                    obj=Model.content_object_,
                    id="fields.E001",
                )
            ],
        )

    @override_settings(
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "contenttypes_tests",
        ]
    )
    def test_generic_foreign_key_checks_are_performed(self):
        """

        Tests that checks are performed on GenericForeignKey fields.

        Verifies that the check method of a GenericForeignKey is called when running
        system checks. This ensures that any issues with GenericForeignKey fields are
        identified and reported, allowing developers to correct problems before they
        cause issues in production.

        The test uses a simple model with a GenericForeignKey to exercise the checks
        system, simulating the checking process to confirm that the expected validation
        occurs.

        """
        class Model(models.Model):
            content_object = GenericForeignKey()

        with mock.patch.object(GenericForeignKey, "check") as check:
            checks.run_checks(app_configs=self.apps.get_app_configs())
        check.assert_called_once_with()


@isolate_apps("contenttypes_tests")
class GenericRelationTests(SimpleTestCase):
    def test_valid_generic_relationship(self):
        """
        Tests the functionality of generic relationships in Django models.

        This test case verifies that a generic relation is correctly set up between a Bookmark model and a TaggedItem model.
        It checks if the generic relationship is valid by calling the check method on the tags field of the Bookmark model.
        The test passes if no errors are reported, indicating a properly defined generic relationship.
        """
        class TaggedItem(models.Model):
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey()

        class Bookmark(models.Model):
            tags = GenericRelation("TaggedItem")

        self.assertEqual(Bookmark.tags.field.check(), [])

    def test_valid_generic_relationship_with_explicit_fields(self):
        """
        Tests the validity of a generic relationship between two models, `TaggedItem` and `Bookmark`, 
        where the `TaggedItem` model contains explicit fields for the content type and object ID, 
        and the `Bookmark` model contains a generic relation to `TaggedItem` using these fields.
        The test verifies that the generic relationship is correctly defined and does not produce any errors.
        """
        class TaggedItem(models.Model):
            custom_content_type = models.ForeignKey(ContentType, models.CASCADE)
            custom_object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey(
                "custom_content_type", "custom_object_id"
            )

        class Bookmark(models.Model):
            tags = GenericRelation(
                "TaggedItem",
                content_type_field="custom_content_type",
                object_id_field="custom_object_id",
            )

        self.assertEqual(Bookmark.tags.field.check(), [])

    def test_pointing_to_missing_model(self):
        class Model(models.Model):
            rel = GenericRelation("MissingModel")

        self.assertEqual(
            Model.rel.field.check(),
            [
                checks.Error(
                    "Field defines a relation with model 'MissingModel', "
                    "which is either not installed, or is abstract.",
                    obj=Model.rel.field,
                    id="fields.E300",
                )
            ],
        )

    def test_valid_self_referential_generic_relationship(self):
        """

        Checks the validity of a self-referential generic relationship.

        This test case verifies that a generic relation pointing to the same model
        can be created and validated without any errors. It ensures that the check
        method on the GenericRelation field returns an empty list, indicating no validation
        errors.

        """
        class Model(models.Model):
            rel = GenericRelation("Model")
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey("content_type", "object_id")

        self.assertEqual(Model.rel.field.check(), [])

    def test_missing_generic_foreign_key(self):
        """
        )
        Checks for a missing GenericForeignKey in a model using GenericRelation.

        The GenericRelation in the tested model (Bookmark) should have a corresponding
        GenericForeignKey in the related model (TaggedItem). This test case verifies
        that a constraint error is raised when the GenericForeignKey is not defined
        in the related model.

        Args:
            None

        Returns:
            None

        Raises:
            checks.Error: If the GenericRelation is not paired with a GenericForeignKey.

        """
        class TaggedItem(models.Model):
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()

        class Bookmark(models.Model):
            tags = GenericRelation("TaggedItem")

        self.assertEqual(
            Bookmark.tags.field.check(),
            [
                checks.Error(
                    "The GenericRelation defines a relation with the model "
                    "'contenttypes_tests.TaggedItem', but that model does not have a "
                    "GenericForeignKey.",
                    obj=Bookmark.tags.field,
                    id="contenttypes.E004",
                )
            ],
        )

    @override_settings(TEST_SWAPPED_MODEL="contenttypes_tests.Replacement")
    def test_pointing_to_swapped_model(self):
        """

        Tests that a GenericRelation in a model correctly raises an error when pointing to a swappable model that has been swapped out.

        This test case verifies that when a model's GenericRelation is defined with a swappable model and that model is swapped out in the test settings, the model's field check correctly identifies the issue and provides a hint to update the relation to point to the swapped model.

        The expected error message is checked to ensure it matches the expected error, which includes a message describing the problem and a hint to update the relation.

        """
        class Replacement(models.Model):
            pass

        class SwappedModel(models.Model):
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey()

            class Meta:
                swappable = "TEST_SWAPPED_MODEL"

        class Model(models.Model):
            rel = GenericRelation("SwappedModel")

        self.assertEqual(
            Model.rel.field.check(),
            [
                checks.Error(
                    "Field defines a relation with the model "
                    "'contenttypes_tests.SwappedModel', "
                    "which has been swapped out.",
                    hint=(
                        "Update the relation to point at 'settings.TEST_SWAPPED_MODEL'."
                    ),
                    obj=Model.rel.field,
                    id="fields.E301",
                )
            ],
        )

    def test_field_name_ending_with_underscore(self):
        class TaggedItem(models.Model):
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey()

        class InvalidBookmark(models.Model):
            tags_ = GenericRelation("TaggedItem")

        self.assertEqual(
            InvalidBookmark.tags_.field.check(),
            [
                checks.Error(
                    "Field names must not end with an underscore.",
                    obj=InvalidBookmark.tags_.field,
                    id="fields.E001",
                )
            ],
        )


@isolate_apps("contenttypes_tests", attr_name="apps")
class ModelCheckTests(SimpleTestCase):
    def test_model_name_too_long(self):
        """
        Checks if a model name exceeds the maximum length of 100 characters.

        This test case verifies that the model name length validation correctly identifies models with names longer than 100 characters.
        It ensures that the check returns an error with the expected message and object reference when a model name is too long.

        The test case creates a test model with a name that exceeds the maximum length and then checks the result of the model name length validation.
        The expected output is an error message indicating that the model name must be at most 100 characters, along with the object reference and error ID 'contenttypes.E005'.
        """
        model = type("A" * 101, (models.Model,), {"__module__": self.__module__})
        self.assertEqual(
            check_model_name_lengths(self.apps.get_app_configs()),
            [
                checks.Error(
                    "Model names must be at most 100 characters (got 101).",
                    obj=model,
                    id="contenttypes.E005",
                )
            ],
        )

    def test_model_name_max_length(self):
        """
        Tests that model name with maximum length does not raise any errors.

        Checks if a model with a name consisting of 100 characters ('A' repeated 100 times)
        is successfully created and validated, ensuring that the model name length check
        function returns an empty list, indicating no issues with the model names.

        """
        type("A" * 100, (models.Model,), {"__module__": self.__module__})
        self.assertEqual(check_model_name_lengths(self.apps.get_app_configs()), [])
