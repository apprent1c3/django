import datetime
import unittest

from django.apps.registry import Apps
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from .models import (
    CustomPKModel,
    FlexibleDatePost,
    ModelToValidate,
    Post,
    UniqueErrorsModel,
    UniqueFieldsModel,
    UniqueForDateModel,
    UniqueFuncConstraintModel,
    UniqueTogetherModel,
)


class GetUniqueCheckTests(unittest.TestCase):
    def test_unique_fields_get_collected(self):
        """

        Tests that unique fields defined in the model get collected correctly.

        This function verifies that all unique fields across the model are properly
        identified and returned by the `_get_unique_checks` method. The test checks
        that both the fields defined as unique and those that are implicitly unique
        (e.g., primary key) are included in the result.

        The expected output is a tuple containing two lists: the first list contains
        tuples with the model class and a tuple of unique field names, and the second
        list is empty (reserved for future use).

        The test ensures that the model's unique fields are accurately detected and
        collected, allowing for proper validation and checking of unique constraints.

        """
        m = UniqueFieldsModel()
        self.assertEqual(
            (
                [
                    (UniqueFieldsModel, ("id",)),
                    (UniqueFieldsModel, ("unique_charfield",)),
                    (UniqueFieldsModel, ("unique_integerfield",)),
                ],
                [],
            ),
            m._get_unique_checks(),
        )

    def test_unique_together_gets_picked_up_and_converted_to_tuple(self):
        """
        Tests that the unique_together constraints defined on a model are properly 
        detected and converted into a tuple format.

        Verifies that the _get_unique_checks method returns a list of tuples, where each 
        tuple contains the model class and a tuple of field names that are subject to 
        unique together constraints. This ensures that the model's unique together 
        constraints are correctly identified and formatted for use in database operations.

        The test case checks for multiple unique together constraints and a default 
        constraint on the 'id' field, confirming that all constraints are correctly 
        picked up and converted to the expected tuple format.
        """
        m = UniqueTogetherModel()
        self.assertEqual(
            (
                [
                    (UniqueTogetherModel, ("ifield", "cfield")),
                    (UniqueTogetherModel, ("ifield", "efield")),
                    (UniqueTogetherModel, ("id",)),
                ],
                [],
            ),
            m._get_unique_checks(),
        )

    def test_unique_together_normalization(self):
        """
        Test the Meta.unique_together normalization with different sorts of
        objects.
        """
        data = {
            "2-tuple": (("foo", "bar"), (("foo", "bar"),)),
            "list": (["foo", "bar"], (("foo", "bar"),)),
            "already normalized": (
                (("foo", "bar"), ("bar", "baz")),
                (("foo", "bar"), ("bar", "baz")),
            ),
            "set": (
                {("foo", "bar"), ("bar", "baz")},  # Ref #21469
                (("foo", "bar"), ("bar", "baz")),
            ),
        }

        for unique_together, normalized in data.values():

            class M(models.Model):
                foo = models.IntegerField()
                bar = models.IntegerField()
                baz = models.IntegerField()

                Meta = type(
                    "Meta", (), {"unique_together": unique_together, "apps": Apps()}
                )

            checks, _ = M()._get_unique_checks()
            for t in normalized:
                check = (M, t)
                self.assertIn(check, checks)

    def test_primary_key_is_considered_unique(self):
        m = CustomPKModel()
        self.assertEqual(
            ([(CustomPKModel, ("my_pk_field",))], []), m._get_unique_checks()
        )

    def test_unique_for_date_gets_picked_up(self):
        """
        Tests that the unique_for_date metadata is correctly picked up and utilized in the _get_unique_checks method.

        This test case verifies that the unique_for_date constraints are properly identified and returned as part of the unique checks for the model. The expected output includes both the unique_together constraint and the unique_for_date constraints, which cover various date-related fields and ordering rules.

        The returned value is a tuple containing two lists: the first list includes the unique_together constraints, and the second list includes the unique_for_date constraints. Each constraint is represented as a tuple containing the model class and the relevant field names or ordering rules.

        By passing this test, the _get_unique_checks method is verified to correctly collect and return all unique constraints for the model, ensuring data integrity and proper validation for date-related fields.
        """
        m = UniqueForDateModel()
        self.assertEqual(
            (
                [(UniqueForDateModel, ("id",))],
                [
                    (UniqueForDateModel, "date", "count", "start_date"),
                    (UniqueForDateModel, "year", "count", "end_date"),
                    (UniqueForDateModel, "month", "order", "end_date"),
                ],
            ),
            m._get_unique_checks(),
        )

    def test_unique_for_date_exclusion(self):
        m = UniqueForDateModel()
        self.assertEqual(
            (
                [(UniqueForDateModel, ("id",))],
                [
                    (UniqueForDateModel, "year", "count", "end_date"),
                    (UniqueForDateModel, "month", "order", "end_date"),
                ],
            ),
            m._get_unique_checks(exclude="start_date"),
        )

    def test_func_unique_constraint_ignored(self):
        m = UniqueFuncConstraintModel()
        self.assertEqual(
            m._get_unique_checks(),
            ([(UniqueFuncConstraintModel, ("id",))], []),
        )


class PerformUniqueChecksTest(TestCase):
    def test_primary_key_unique_check_not_performed_when_adding_and_pk_not_specified(
        self,
    ):
        # Regression test for #12560
        """

        Tests that the uniqueness check for primary keys is not performed when adding a new instance 
        and the primary key is not explicitly specified.

        This test case verifies the behaviour of the full_clean method when a model instance is created 
        with a specified value only for fields other than the primary key, ensuring the absence of a 
        database query to check for primary key uniqueness.

        """
        with self.assertNumQueries(0):
            mtv = ModelToValidate(number=10, name="Some Name")
            setattr(mtv, "_adding", True)
            mtv.full_clean()

    def test_primary_key_unique_check_performed_when_adding_and_pk_specified(self):
        # Regression test for #12560
        """
        Tests that a primary key uniqueness check is performed when adding a new instance and a primary key is specified.

        This test ensures that the model's validation correctly checks for uniqueness of the primary key when creating a new instance with a predefined primary key value. The test verifies that only one database query is executed during the validation process, confirming that the uniqueness check is performed efficiently.

        The test case covers a scenario where a new instance of the ModelToValidate is created with a specified primary key, and then the full_clean method is called to trigger the validation process. The test checks that the primary key uniqueness validation is correctly performed during this process.
        """
        with self.assertNumQueries(1):
            mtv = ModelToValidate(number=10, name="Some Name", id=123)
            setattr(mtv, "_adding", True)
            mtv.full_clean()

    def test_primary_key_unique_check_not_performed_when_not_adding(self):
        # Regression test for #12132
        """

        Checks that primary key uniqueness validation is not performed when the model instance is not being added.

        This test ensures that the full_clean() method does not trigger a database query to check for primary key uniqueness when the model instance is not being inserted into the database. 

        """
        with self.assertNumQueries(0):
            mtv = ModelToValidate(number=10, name="Some Name")
            mtv.full_clean()

    def test_unique_for_date(self):
        """

        Tests the uniqueness constraints for the Post model fields based on the posted date.

        Verifies that the title, slug, and subtitle fields must be unique for the posted date, 
        year, and month respectively, and that a posted date is required.

        The test cases cover various scenarios, including:

        - Creating a post with a title that already exists for the same posted date.
        - Creating a post with a slug that already exists for the same posted year.
        - Creating a post with a subtitle that already exists for the same posted month.
        - Creating a post without a posted date.

        Each test case checks for the appropriate validation error message.

        """
        Post.objects.create(
            title="Django 1.0 is released",
            slug="Django 1.0",
            subtitle="Finally",
            posted=datetime.date(2008, 9, 3),
        )
        p = Post(title="Django 1.0 is released", posted=datetime.date(2008, 9, 3))
        with self.assertRaises(ValidationError) as cm:
            p.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {"title": ["Title must be unique for Posted date."]},
        )

        # Should work without errors
        p = Post(title="Work on Django 1.1 begins", posted=datetime.date(2008, 9, 3))
        p.full_clean()

        # Should work without errors
        p = Post(title="Django 1.0 is released", posted=datetime.datetime(2008, 9, 4))
        p.full_clean()

        p = Post(slug="Django 1.0", posted=datetime.datetime(2008, 1, 1))
        with self.assertRaises(ValidationError) as cm:
            p.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {"slug": ["Slug must be unique for Posted year."]},
        )

        p = Post(subtitle="Finally", posted=datetime.datetime(2008, 9, 30))
        with self.assertRaises(ValidationError) as cm:
            p.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {"subtitle": ["Subtitle must be unique for Posted month."]},
        )

        p = Post(title="Django 1.0 is released")
        with self.assertRaises(ValidationError) as cm:
            p.full_clean()
        self.assertEqual(
            cm.exception.message_dict, {"posted": ["This field cannot be null."]}
        )

    def test_unique_for_date_with_nullable_date(self):
        """
        unique_for_date/year/month checks shouldn't trigger when the
        associated DateField is None.
        """
        FlexibleDatePost.objects.create(
            title="Django 1.0 is released",
            slug="Django 1.0",
            subtitle="Finally",
            posted=datetime.date(2008, 9, 3),
        )
        p = FlexibleDatePost(title="Django 1.0 is released")
        p.full_clean()

        p = FlexibleDatePost(slug="Django 1.0")
        p.full_clean()

        p = FlexibleDatePost(subtitle="Finally")
        p.full_clean()

    def test_unique_errors(self):
        """

        Tests the validation of unique constraints on the UniqueErrorsModel.

        Checks that attempting to create a model instance with a duplicate name or number
        raises a ValidationError with the expected custom error messages. The function
        verifies the error messages for both duplicate name and duplicate number scenarios,
        ensuring that the model's unique constraints are correctly enforced.

        """
        UniqueErrorsModel.objects.create(name="Some Name", no=10)
        m = UniqueErrorsModel(name="Some Name", no=11)
        with self.assertRaises(ValidationError) as cm:
            m.full_clean()
        self.assertEqual(
            cm.exception.message_dict, {"name": ["Custom unique name message."]}
        )

        m = UniqueErrorsModel(name="Some Other Name", no=10)
        with self.assertRaises(ValidationError) as cm:
            m.full_clean()
        self.assertEqual(
            cm.exception.message_dict, {"no": ["Custom unique number message."]}
        )
