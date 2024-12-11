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
        """
        Checks the GenericForeignKey field for a missing 'content_type' field, verifying that an error is raised when it references a nonexistent field, specifically 'content_type' in the model 'TaggedItem'.
        """
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
        Tests that a GenericForeignKey with an invalid 'content_type' field raises the correct error.

        The 'content_type' field should be a ForeignKey to 'contenttypes.ContentType', but this test checks the case when it is an IntegerField instead.

        The expected error is checked to have the correct message, hint and object. The test ensures that the system correctly identifies and reports this type of configuration issue in the model.
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
        Tests that a GenericForeignKey's content_type field must point to 'contenttypes.ContentType'.

        This test case verifies that a GenericForeignKey in a model raises an error when its
        content_type field is not a ForeignKey to 'contenttypes.ContentType'. It ensures that
        the correct error message is generated, providing a hint for the user to correct the
        model definition.

        The expected error is a checks.Error with the id 'contenttypes.E004' and a hint
        indicating that the content_type field must be a ForeignKey to 'contenttypes.ContentType'.

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
        """

        Tests that a GenericForeignKey field without an 'object_id' field raises an error.

        Verifies that the model check correctly identifies the missing 'object_id' field
        when using a GenericForeignKey without a corresponding 'object_id' field.

        """
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
        """
        Checks that a field name does not end with an underscore, ensuring compliance with Django's field naming conventions.

        This test case verifies that the check is correctly triggered when a field, in this case a generic foreign key (`content_object_`), ends with an underscore, resulting in a specific error (`fields.E001`) being raised.
        """
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
        class Model(models.Model):
            content_object = GenericForeignKey()

        with mock.patch.object(GenericForeignKey, "check") as check:
            checks.run_checks(app_configs=self.apps.get_app_configs())
        check.assert_called_once_with()


@isolate_apps("contenttypes_tests")
class GenericRelationTests(SimpleTestCase):
    def test_valid_generic_relationship(self):
        """
        Tests whether a generic relationship between two models is correctly established and validated. 
        This test case verifies that the generic relation 'tags' on the 'Bookmark' model does not have any errors. 
        It utilizes a simple generic foreign key setup with 'TaggedItem' and 'Bookmark' models to check for validity. 
        A successful test indicates that the relationship is properly defined and can be used to associate 'Bookmark' instances with 'TaggedItem' instances.
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

        Tests a valid generic relationship with explicit field definitions.

        This test case verifies that a generic relationship is correctly established 
        between two models, TaggedItem and Bookmark, where the TaggedItem model 
        contains a GenericForeignKey and the Bookmark model contains a GenericRelation.
        The test checks that the relationship is properly defined with explicit fields, 
        custom_content_type and custom_object_id, and that no errors are reported when 
        the relationship is validated.

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
        Tests the validity of a self-referential generic relationship on a model.

        This test case ensures that a model can establish a generic relationship with itself, 
        allowing for flexible and dynamic associations between instances of the same model.
        It verifies that the relationship is properly defined and doesn't raise any errors.
        The test essentially checks that a model with a self-referential generic foreign key 
        passes the field validation checks without reporting any issues.
        """
        class Model(models.Model):
            rel = GenericRelation("Model")
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey("content_type", "object_id")

        self.assertEqual(Model.rel.field.check(), [])

    def test_missing_generic_foreign_key(self):
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

        Tests whether a GenericRelation field correctly raises an error when it references a model that has been swapped out.

        The test checks that when a model with a GenericRelation field is defined to point to a swappable model, an error is raised indicating that the relation needs to be updated to point to the swapped-in model.

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
        """
        Tests that a field name ending with an underscore raises a validation error.

        This test ensures that Django's model validation correctly identifies field names
        that end with an underscore, which is not allowed. The test creates a model with
        a field that has an underscore at the end of its name and checks that the
        expected error is raised when validating the model field.
        """
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
        Tests that a model with a name exceeding the maximum allowed length raises an error.

        This test case creates a model with a name longer than 100 characters and checks that 
        the appropriate error message is returned when validating model name lengths.

        The test covers the scenario where a model name is too long, ensuring that the model
        name length validation correctly identifies and reports this issue. The expected error
        message includes the model object, error id 'contenttypes.E005', and a descriptive 
        error message indicating the maximum allowed length and the actual length of the model name. 
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
        Tests that model names do not exceed the maximum allowed length by creating a model with a long name and asserting that the function to check model name lengths returns an empty list, indicating no issues with the model names.
        """
        type("A" * 100, (models.Model,), {"__module__": self.__module__})
        self.assertEqual(check_model_name_lengths(self.apps.get_app_configs()), [])
