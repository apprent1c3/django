import datetime
from unittest import mock

from django.contrib.postgres.indexes import OpClass
from django.core.checks import Error
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import (
    CASCADE,
    CharField,
    CheckConstraint,
    DateField,
    Deferrable,
    F,
    ForeignKey,
    Func,
    IntegerField,
    Model,
    Q,
    UniqueConstraint,
)
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Left, Lower
from django.test import skipUnlessDBFeature
from django.test.utils import isolate_apps
from django.utils import timezone

from . import PostgreSQLTestCase
from .models import HotelReservation, IntegerArrayModel, RangesModel, Room, Scene

try:
    from django.contrib.postgres.constraints import ExclusionConstraint
    from django.contrib.postgres.fields import (
        DateTimeRangeField,
        RangeBoundary,
        RangeOperators,
    )
    from django.db.backends.postgresql.psycopg_any import DateRange, NumericRange
except ImportError:
    pass


class SchemaTests(PostgreSQLTestCase):
    get_opclass_query = """
        SELECT opcname, c.relname FROM pg_opclass AS oc
        JOIN pg_index as i on oc.oid = ANY(i.indclass)
        JOIN pg_class as c on c.oid = i.indexrelid
        WHERE c.relname = %s
    """

    def get_constraints(self, table):
        """Get the constraints on the table using a new cursor."""
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table)

    def test_check_constraint_range_value(self):
        """
        Tests the application of a check constraint to ensure a range value falls within a specified range.

        Checks that the constraint is not initially present in the database, then adds it and verifies its presence.
        Subsequently, attempts to create an instance with a range value outside the allowed range, expecting an IntegrityError to be raised.
        Finally, creates an instance with a range value within the allowed range to demonstrate the constraint's effectiveness.
        """
        constraint_name = "ints_between"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = CheckConstraint(
            condition=Q(ints__contained_by=NumericRange(10, 30)),
            name=constraint_name,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        with self.assertRaises(IntegrityError), transaction.atomic():
            RangesModel.objects.create(ints=(20, 50))
        RangesModel.objects.create(ints=(10, 30))

    def test_check_constraint_array_contains(self):
        constraint = CheckConstraint(
            condition=Q(field__contains=[1]),
            name="array_contains",
        )
        msg = f"Constraint “{constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(IntegerArrayModel, IntegerArrayModel())
        constraint.validate(IntegerArrayModel, IntegerArrayModel(field=[1]))

    def test_check_constraint_array_length(self):
        """

        Tests the validation of a check constraint that verifies the length of an array field.

        The function creates a check constraint that requires the length of a specific field to be 1.
        It then attempts to validate this constraint against an instance of IntegerArrayModel 
        with an invalid field length, expecting a ValidationError to be raised with a specific message.
        Finally, it validates the constraint against a model instance with a valid field length, 
        ensuring that no error is raised.

        Args:
            None

        Returns:
            None

        Raises:
            ValidationError: If the check constraint is violated.

        """
        constraint = CheckConstraint(
            condition=Q(field__len=1),
            name="array_length",
        )
        msg = f"Constraint “{constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(IntegerArrayModel, IntegerArrayModel())
        constraint.validate(IntegerArrayModel, IntegerArrayModel(field=[1]))

    def test_check_constraint_daterange_contains(self):
        constraint_name = "dates_contains"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = CheckConstraint(
            condition=Q(dates__contains=F("dates_inner")),
            name=constraint_name,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        date_1 = datetime.date(2016, 1, 1)
        date_2 = datetime.date(2016, 1, 4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RangesModel.objects.create(
                dates=(date_1, date_2),
                dates_inner=(date_1, date_2.replace(day=5)),
            )
        RangesModel.objects.create(
            dates=(date_1, date_2),
            dates_inner=(date_1, date_2),
        )

    def test_check_constraint_datetimerange_contains(self):
        """

        Tests the 'timestamps_contains' check constraint on the RangesModel.

        This test checks that a check constraint, which enforces the condition that 
        'timestamps_inner' must be contained within 'timestamps', is correctly applied 
        to the model. The test first verifies that the constraint does not initially 
        exist, then adds it, and checks that it is enforced by attempting to create 
        invalid data and ensuring that an IntegrityError is raised.

        The check constraint is tested with two scenarios: one where the 'timestamps_inner' 
        range is contained within the 'timestamps' range, and one where it is not, to 
        verify that the constraint correctly allows or rejects data based on this condition.

        """
        constraint_name = "timestamps_contains"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = CheckConstraint(
            condition=Q(timestamps__contains=F("timestamps_inner")),
            name=constraint_name,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        datetime_1 = datetime.datetime(2016, 1, 1)
        datetime_2 = datetime.datetime(2016, 1, 2, 12)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RangesModel.objects.create(
                timestamps=(datetime_1, datetime_2),
                timestamps_inner=(datetime_1, datetime_2.replace(hour=13)),
            )
        RangesModel.objects.create(
            timestamps=(datetime_1, datetime_2),
            timestamps_inner=(datetime_1, datetime_2),
        )

    def test_check_constraint_range_contains(self):
        """

        Tests that the CheckConstraint validator correctly identifies when a given range does not contain the specified integers.

        This function creates a CheckConstraint with a condition that checks if a range of integers contains the numbers 1 and 5. It then attempts to validate a model instance where the range of integers does not include these numbers, verifying that a ValidationError is raised with the expected error message.

        """
        constraint = CheckConstraint(
            condition=Q(ints__contains=(1, 5)),
            name="ints_contains",
        )
        msg = f"Constraint “{constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(RangesModel, RangesModel(ints=(6, 10)))

    def test_check_constraint_range_lower_upper(self):
        constraint = CheckConstraint(
            condition=Q(ints__startswith__gte=0) & Q(ints__endswith__lte=99),
            name="ints_range_lower_upper",
        )
        msg = f"Constraint “{constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(RangesModel, RangesModel(ints=(-1, 20)))
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(RangesModel, RangesModel(ints=(0, 100)))
        constraint.validate(RangesModel, RangesModel(ints=(0, 99)))

    def test_check_constraint_range_lower_with_nulls(self):
        """

        Check that a range of integers adheres to a specified constraint, 
        either allowing null values and non-negative integers or strictly non-negative integers.

        The test covers two scenarios: 
        1. 'ints_optional_positive_range': Validates that the range of integers 
           can be null or contain values that start with a non-negative integer.
        2. 'ints_positive_range': Validates that the range of integers strictly 
           contains values that start with a non-negative integer.

        """
        constraint = CheckConstraint(
            condition=Q(ints__isnull=True) | Q(ints__startswith__gte=0),
            name="ints_optional_positive_range",
        )
        constraint.validate(RangesModel, RangesModel())
        constraint = CheckConstraint(
            condition=Q(ints__startswith__gte=0),
            name="ints_positive_range",
        )
        constraint.validate(RangesModel, RangesModel())

    def test_opclass(self):
        constraint = UniqueConstraint(
            name="test_opclass",
            fields=["scene"],
            opclasses=["varchar_pattern_ops"],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Scene, constraint)
        self.assertIn(constraint.name, self.get_constraints(Scene._meta.db_table))
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [constraint.name])
            self.assertEqual(
                cursor.fetchall(),
                [("varchar_pattern_ops", constraint.name)],
            )
        # Drop the constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Scene, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(Scene._meta.db_table))

    def test_opclass_multiple_columns(self):
        constraint = UniqueConstraint(
            name="test_opclass_multiple",
            fields=["scene", "setting"],
            opclasses=["varchar_pattern_ops", "text_pattern_ops"],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Scene, constraint)
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [constraint.name])
            expected_opclasses = (
                ("varchar_pattern_ops", constraint.name),
                ("text_pattern_ops", constraint.name),
            )
            self.assertCountEqual(cursor.fetchall(), expected_opclasses)

    def test_opclass_partial(self):
        constraint = UniqueConstraint(
            name="test_opclass_partial",
            fields=["scene"],
            opclasses=["varchar_pattern_ops"],
            condition=Q(setting__contains="Sir Bedemir's Castle"),
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Scene, constraint)
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [constraint.name])
            self.assertCountEqual(
                cursor.fetchall(),
                [("varchar_pattern_ops", constraint.name)],
            )

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_opclass_include(self):
        constraint = UniqueConstraint(
            name="test_opclass_include",
            fields=["scene"],
            opclasses=["varchar_pattern_ops"],
            include=["setting"],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Scene, constraint)
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [constraint.name])
            self.assertCountEqual(
                cursor.fetchall(),
                [("varchar_pattern_ops", constraint.name)],
            )

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_opclass_func(self):
        constraint = UniqueConstraint(
            OpClass(Lower("scene"), name="text_pattern_ops"),
            name="test_opclass_func",
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Scene, constraint)
        constraints = self.get_constraints(Scene._meta.db_table)
        self.assertIs(constraints[constraint.name]["unique"], True)
        self.assertIn(constraint.name, constraints)
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [constraint.name])
            self.assertEqual(
                cursor.fetchall(),
                [("text_pattern_ops", constraint.name)],
            )
        Scene.objects.create(scene="Scene 10", setting="The dark forest of Ewing")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Scene.objects.create(scene="ScEnE 10", setting="Sir Bedemir's Castle")
        Scene.objects.create(scene="Scene 5", setting="Sir Bedemir's Castle")
        # Drop the constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Scene, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(Scene._meta.db_table))
        Scene.objects.create(scene="ScEnE 10", setting="Sir Bedemir's Castle")

    def test_opclass_func_validate_constraints(self):
        constraint_name = "test_opclass_func_validate_constraints"
        constraint = UniqueConstraint(
            OpClass(Lower("scene"), name="text_pattern_ops"),
            name="test_opclass_func_validate_constraints",
        )
        Scene.objects.create(scene="First scene")
        # Non-unique scene.
        msg = f"Constraint “{constraint_name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(Scene, Scene(scene="first Scene"))
        constraint.validate(Scene, Scene(scene="second Scene"))


class ExclusionConstraintTests(PostgreSQLTestCase):
    def get_constraints(self, table):
        """Get the constraints on the table using a new cursor."""
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table)

    def test_invalid_condition(self):
        msg = "ExclusionConstraint.condition must be a Q instance."
        with self.assertRaisesMessage(ValueError, msg):
            ExclusionConstraint(
                index_type="GIST",
                name="exclude_invalid_condition",
                expressions=[(F("datespan"), RangeOperators.OVERLAPS)],
                condition=F("invalid"),
            )

    def test_invalid_index_type(self):
        msg = "Exclusion constraints only support GiST or SP-GiST indexes."
        with self.assertRaisesMessage(ValueError, msg):
            ExclusionConstraint(
                index_type="gin",
                name="exclude_invalid_index_type",
                expressions=[(F("datespan"), RangeOperators.OVERLAPS)],
            )

    def test_invalid_expressions(self):
        """
        Tests the ExclusionConstraint class to ensure it raises a ValueError when initialized with invalid expressions.
        The function checks for expressions that are not lists of 2-tuples, covering cases where the input is a list with single elements or tuples with more than two elements.
        It verifies the error message to ensure it correctly indicates that expressions must be a list of 2-tuples.
        """
        msg = "The expressions must be a list of 2-tuples."
        for expressions in (["foo"], [("foo")], [("foo_1", "foo_2", "foo_3")]):
            with self.subTest(expressions), self.assertRaisesMessage(ValueError, msg):
                ExclusionConstraint(
                    index_type="GIST",
                    name="exclude_invalid_expressions",
                    expressions=expressions,
                )

    def test_empty_expressions(self):
        """
        #: Tests that providing empty or no expressions to the ExclusionConstraint results in a ValueError.
        #: 
        #: Verifies that an ExclusionConstraint cannot be created without at least one expression, 
        #: ensuring the validity of the constraint definition.
        #: 
        #: :raises ValueError: If no expressions or an empty list is provided.
        """
        msg = "At least one expression is required to define an exclusion constraint."
        for empty_expressions in (None, []):
            with (
                self.subTest(empty_expressions),
                self.assertRaisesMessage(ValueError, msg),
            ):
                ExclusionConstraint(
                    index_type="GIST",
                    name="exclude_empty_expressions",
                    expressions=empty_expressions,
                )

    def test_invalid_deferrable(self):
        msg = "ExclusionConstraint.deferrable must be a Deferrable instance."
        with self.assertRaisesMessage(ValueError, msg):
            ExclusionConstraint(
                name="exclude_invalid_deferrable",
                expressions=[(F("datespan"), RangeOperators.OVERLAPS)],
                deferrable="invalid",
            )

    def test_invalid_include_type(self):
        msg = "ExclusionConstraint.include must be a list or tuple."
        with self.assertRaisesMessage(ValueError, msg):
            ExclusionConstraint(
                name="exclude_invalid_include",
                expressions=[(F("datespan"), RangeOperators.OVERLAPS)],
                include="invalid",
            )

    @isolate_apps("postgres_tests")
    def test_check(self):
        """

        Tests the functionality of model constraints checking.

        Verifies that the check method correctly identifies and reports errors
        in the model's constraints, specifically when referencing nonexistent fields
        or joined fields. Ensures that the method returns the expected error messages.

        """
        class Author(Model):
            name = CharField(max_length=255)
            alias = CharField(max_length=255)

            class Meta:
                app_label = "postgres_tests"

        class Book(Model):
            title = CharField(max_length=255)
            published_date = DateField()
            author = ForeignKey(Author, CASCADE)

            class Meta:
                app_label = "postgres_tests"
                constraints = [
                    ExclusionConstraint(
                        name="exclude_check",
                        expressions=[
                            (F("title"), RangeOperators.EQUAL),
                            (F("published_date__year"), RangeOperators.EQUAL),
                            ("published_date__month", RangeOperators.EQUAL),
                            (F("author__name"), RangeOperators.EQUAL),
                            ("author__alias", RangeOperators.EQUAL),
                            ("nonexistent", RangeOperators.EQUAL),
                        ],
                    )
                ]

        self.assertCountEqual(
            Book.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to the nonexistent field 'nonexistent'.",
                    obj=Book,
                    id="models.E012",
                ),
                Error(
                    "'constraints' refers to the joined field 'author__alias'.",
                    obj=Book,
                    id="models.E041",
                ),
                Error(
                    "'constraints' refers to the joined field 'author__name'.",
                    obj=Book,
                    id="models.E041",
                ),
            ],
        )

    def test_repr(self):
        """
        Tests the string representation of ExclusionConstraint objects with various settings.

            The function creates ExclusionConstraint instances with different attributes, such as name, expressions, condition, index type, deferrability, included fields, and custom error messages.
            For each constraint, it verifies that the repr() method returns a string that correctly reflects the attributes and settings of the constraint.
            The expected repr() strings are compared to the actual output of repr(constraint) to ensure that the representation is accurate and consistent.
            The test cases cover a range of scenarios, including different operator types, index types, and error handling configurations, to ensure that the repr() method works correctly in various situations.
        """
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                (F("datespan"), RangeOperators.OVERLAPS),
                (F("room"), RangeOperators.EQUAL),
            ],
        )
        self.assertEqual(
            repr(constraint),
            "<ExclusionConstraint: index_type='GIST' expressions=["
            "(F(datespan), '&&'), (F(room), '=')] name='exclude_overlapping'>",
        )
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[(F("datespan"), RangeOperators.ADJACENT_TO)],
            condition=Q(cancelled=False),
            index_type="SPGiST",
        )
        self.assertEqual(
            repr(constraint),
            "<ExclusionConstraint: index_type='SPGiST' expressions=["
            "(F(datespan), '-|-')] name='exclude_overlapping' "
            "condition=(AND: ('cancelled', False))>",
        )
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[(F("datespan"), RangeOperators.ADJACENT_TO)],
            deferrable=Deferrable.IMMEDIATE,
        )
        self.assertEqual(
            repr(constraint),
            "<ExclusionConstraint: index_type='GIST' expressions=["
            "(F(datespan), '-|-')] name='exclude_overlapping' "
            "deferrable=Deferrable.IMMEDIATE>",
        )
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[(F("datespan"), RangeOperators.ADJACENT_TO)],
            include=["cancelled", "room"],
        )
        self.assertEqual(
            repr(constraint),
            "<ExclusionConstraint: index_type='GIST' expressions=["
            "(F(datespan), '-|-')] name='exclude_overlapping' "
            "include=('cancelled', 'room')>",
        )
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                (OpClass("datespan", name="range_ops"), RangeOperators.ADJACENT_TO),
            ],
        )
        self.assertEqual(
            repr(constraint),
            "<ExclusionConstraint: index_type='GIST' expressions=["
            "(OpClass(F(datespan), name=range_ops), '-|-')] "
            "name='exclude_overlapping'>",
        )
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[(F("datespan"), RangeOperators.ADJACENT_TO)],
            violation_error_message="Overlapping must be excluded",
        )
        self.assertEqual(
            repr(constraint),
            "<ExclusionConstraint: index_type='GIST' expressions=["
            "(F(datespan), '-|-')] name='exclude_overlapping' "
            "violation_error_message='Overlapping must be excluded'>",
        )
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[(F("datespan"), RangeOperators.ADJACENT_TO)],
            violation_error_code="overlapping_must_be_excluded",
        )
        self.assertEqual(
            repr(constraint),
            "<ExclusionConstraint: index_type='GIST' expressions=["
            "(F(datespan), '-|-')] name='exclude_overlapping' "
            "violation_error_code='overlapping_must_be_excluded'>",
        )

    def test_eq(self):
        """
        Tests the equality of ExclusionConstraint instances.

        This test case verifies that the equality of ExclusionConstraint objects is correctly determined based on their attributes.
        It checks the equality of constraints with different attribute combinations, such as expressions, conditions, deferrability, and include/exclude parameters.
        Additionally, it tests the equality of constraints with custom violation error messages and codes.
        The test case ensures that the equality comparison is correctly implemented and handles various scenarios as expected.
        """
        constraint_1 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                (F("datespan"), RangeOperators.OVERLAPS),
                (F("room"), RangeOperators.EQUAL),
            ],
            condition=Q(cancelled=False),
        )
        constraint_2 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
        )
        constraint_3 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[("datespan", RangeOperators.OVERLAPS)],
            condition=Q(cancelled=False),
        )
        constraint_4 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
            deferrable=Deferrable.DEFERRED,
        )
        constraint_5 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
            deferrable=Deferrable.IMMEDIATE,
        )
        constraint_6 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
            deferrable=Deferrable.IMMEDIATE,
            include=["cancelled"],
        )
        constraint_7 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
            include=["cancelled"],
        )
        constraint_10 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                (F("datespan"), RangeOperators.OVERLAPS),
                (F("room"), RangeOperators.EQUAL),
            ],
            condition=Q(cancelled=False),
            violation_error_message="custom error",
        )
        constraint_11 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                (F("datespan"), RangeOperators.OVERLAPS),
                (F("room"), RangeOperators.EQUAL),
            ],
            condition=Q(cancelled=False),
            violation_error_message="other custom error",
        )
        constraint_12 = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                (F("datespan"), RangeOperators.OVERLAPS),
                (F("room"), RangeOperators.EQUAL),
            ],
            condition=Q(cancelled=False),
            violation_error_code="custom_code",
            violation_error_message="other custom error",
        )
        self.assertEqual(constraint_1, constraint_1)
        self.assertEqual(constraint_1, mock.ANY)
        self.assertNotEqual(constraint_1, constraint_2)
        self.assertNotEqual(constraint_1, constraint_3)
        self.assertNotEqual(constraint_1, constraint_4)
        self.assertNotEqual(constraint_1, constraint_10)
        self.assertNotEqual(constraint_2, constraint_3)
        self.assertNotEqual(constraint_2, constraint_4)
        self.assertNotEqual(constraint_2, constraint_7)
        self.assertNotEqual(constraint_4, constraint_5)
        self.assertNotEqual(constraint_5, constraint_6)
        self.assertNotEqual(constraint_1, object())
        self.assertNotEqual(constraint_10, constraint_11)
        self.assertNotEqual(constraint_11, constraint_12)
        self.assertEqual(constraint_10, constraint_10)
        self.assertEqual(constraint_12, constraint_12)

    def test_deconstruct(self):
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(
            path, "django.contrib.postgres.constraints.ExclusionConstraint"
        )
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "name": "exclude_overlapping",
                "expressions": [
                    ("datespan", RangeOperators.OVERLAPS),
                    ("room", RangeOperators.EQUAL),
                ],
            },
        )

    def test_deconstruct_index_type(self):
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            index_type="SPGIST",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(
            path, "django.contrib.postgres.constraints.ExclusionConstraint"
        )
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "name": "exclude_overlapping",
                "index_type": "SPGIST",
                "expressions": [
                    ("datespan", RangeOperators.OVERLAPS),
                    ("room", RangeOperators.EQUAL),
                ],
            },
        )

    def test_deconstruct_condition(self):
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[
                ("datespan", RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
            condition=Q(cancelled=False),
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(
            path, "django.contrib.postgres.constraints.ExclusionConstraint"
        )
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "name": "exclude_overlapping",
                "expressions": [
                    ("datespan", RangeOperators.OVERLAPS),
                    ("room", RangeOperators.EQUAL),
                ],
                "condition": Q(cancelled=False),
            },
        )

    def test_deconstruct_deferrable(self):
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[("datespan", RangeOperators.OVERLAPS)],
            deferrable=Deferrable.DEFERRED,
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(
            path, "django.contrib.postgres.constraints.ExclusionConstraint"
        )
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "name": "exclude_overlapping",
                "expressions": [("datespan", RangeOperators.OVERLAPS)],
                "deferrable": Deferrable.DEFERRED,
            },
        )

    def test_deconstruct_include(self):
        """

        Tests the deconstruction of an ExclusionConstraint instance.

        The deconstruct method is used to serialize the constraint into a tuple containing 
        the path to the constraint class, its positional arguments, and keyword arguments. 
        This test verifies that the deconstruction process correctly captures the constraint's 
        name, expressions, and included fields.

        It ensures that the deconstructed constraint can be accurately reconstructed, 
        which is crucial for serializing and deserializing database constraints.

        """
        constraint = ExclusionConstraint(
            name="exclude_overlapping",
            expressions=[("datespan", RangeOperators.OVERLAPS)],
            include=["cancelled", "room"],
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(
            path, "django.contrib.postgres.constraints.ExclusionConstraint"
        )
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "name": "exclude_overlapping",
                "expressions": [("datespan", RangeOperators.OVERLAPS)],
                "include": ("cancelled", "room"),
            },
        )

    def _test_range_overlaps(self, constraint):
        # Create exclusion constraint.
        self.assertNotIn(
            constraint.name, self.get_constraints(HotelReservation._meta.db_table)
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(HotelReservation, constraint)
        self.assertIn(
            constraint.name, self.get_constraints(HotelReservation._meta.db_table)
        )
        # Add initial reservations.
        room101 = Room.objects.create(number=101)
        room102 = Room.objects.create(number=102)
        datetimes = [
            timezone.datetime(2018, 6, 20),
            timezone.datetime(2018, 6, 24),
            timezone.datetime(2018, 6, 26),
            timezone.datetime(2018, 6, 28),
            timezone.datetime(2018, 6, 29),
        ]
        reservation = HotelReservation.objects.create(
            datespan=DateRange(datetimes[0].date(), datetimes[1].date()),
            start=datetimes[0],
            end=datetimes[1],
            room=room102,
        )
        constraint.validate(HotelReservation, reservation)
        HotelReservation.objects.create(
            datespan=DateRange(datetimes[1].date(), datetimes[3].date()),
            start=datetimes[1],
            end=datetimes[3],
            room=room102,
        )
        HotelReservation.objects.create(
            datespan=DateRange(datetimes[3].date(), datetimes[4].date()),
            start=datetimes[3],
            end=datetimes[4],
            room=room102,
            cancelled=True,
        )
        # Overlap dates.
        with self.assertRaises(IntegrityError), transaction.atomic():
            reservation = HotelReservation(
                datespan=(datetimes[1].date(), datetimes[2].date()),
                start=datetimes[1],
                end=datetimes[2],
                room=room102,
            )
            msg = f"Constraint “{constraint.name}” is violated."
            with self.assertRaisesMessage(ValidationError, msg):
                constraint.validate(HotelReservation, reservation)
            reservation.save()
        # Valid range.
        other_valid_reservations = [
            # Other room.
            HotelReservation(
                datespan=(datetimes[1].date(), datetimes[2].date()),
                start=datetimes[1],
                end=datetimes[2],
                room=room101,
            ),
            # Cancelled reservation.
            HotelReservation(
                datespan=(datetimes[1].date(), datetimes[1].date()),
                start=datetimes[1],
                end=datetimes[2],
                room=room102,
                cancelled=True,
            ),
            # Other adjacent dates.
            HotelReservation(
                datespan=(datetimes[3].date(), datetimes[4].date()),
                start=datetimes[3],
                end=datetimes[4],
                room=room102,
            ),
        ]
        for reservation in other_valid_reservations:
            constraint.validate(HotelReservation, reservation)
        HotelReservation.objects.bulk_create(other_valid_reservations)
        # Excluded fields.
        constraint.validate(
            HotelReservation,
            HotelReservation(
                datespan=(datetimes[1].date(), datetimes[2].date()),
                start=datetimes[1],
                end=datetimes[2],
                room=room102,
            ),
            exclude={"room"},
        )
        constraint.validate(
            HotelReservation,
            HotelReservation(
                datespan=(datetimes[1].date(), datetimes[2].date()),
                start=datetimes[1],
                end=datetimes[2],
                room=room102,
            ),
            exclude={"datespan", "start", "end", "room"},
        )

    def test_range_overlaps_custom(self):
        class TsTzRange(Func):
            function = "TSTZRANGE"
            output_field = DateTimeRangeField()

        constraint = ExclusionConstraint(
            name="exclude_overlapping_reservations_custom_opclass",
            expressions=[
                (
                    OpClass(TsTzRange("start", "end", RangeBoundary()), "range_ops"),
                    RangeOperators.OVERLAPS,
                ),
                (OpClass("room", "gist_int4_ops"), RangeOperators.EQUAL),
            ],
            condition=Q(cancelled=False),
        )
        self._test_range_overlaps(constraint)

    def test_range_overlaps(self):
        constraint = ExclusionConstraint(
            name="exclude_overlapping_reservations",
            expressions=[
                (F("datespan"), RangeOperators.OVERLAPS),
                ("room", RangeOperators.EQUAL),
            ],
            condition=Q(cancelled=False),
        )
        self._test_range_overlaps(constraint)

    def test_range_adjacent(self):
        """
        Checks the functionality of an exclusion constraint on adjacent integer ranges.

        Test the creation, enforcement, and removal of an exclusion constraint named 'ints_adjacent' 
        on a model's 'ints' field. The constraint ensures that integer ranges do not overlap with 
        adjacent ranges. The test case verifies that the constraint is correctly added and removed, 
        and that it prevents the creation of overlapping ranges while allowing non-overlapping ranges 
        to be created successfully.
        """
        constraint_name = "ints_adjacent"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        RangesModel.objects.create(ints=(20, 50))
        with self.assertRaises(IntegrityError), transaction.atomic():
            RangesModel.objects.create(ints=(10, 20))
        RangesModel.objects.create(ints=(10, 19))
        RangesModel.objects.create(ints=(51, 60))
        # Drop the constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(RangesModel, constraint)
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )

    def test_validate_range_adjacent(self):
        constraint = ExclusionConstraint(
            name="ints_adjacent",
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            violation_error_code="custom_code",
            violation_error_message="Custom error message.",
        )
        range_obj = RangesModel.objects.create(ints=(20, 50))
        constraint.validate(RangesModel, range_obj)
        msg = "Custom error message."
        with self.assertRaisesMessage(ValidationError, msg) as cm:
            constraint.validate(RangesModel, RangesModel(ints=(10, 20)))
        self.assertEqual(cm.exception.code, "custom_code")
        constraint.validate(RangesModel, RangesModel(ints=(10, 19)))
        constraint.validate(RangesModel, RangesModel(ints=(51, 60)))
        constraint.validate(RangesModel, RangesModel(ints=(10, 20)), exclude={"ints"})

    def test_validate_with_custom_code_and_condition(self):
        constraint = ExclusionConstraint(
            name="ints_adjacent",
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            violation_error_code="custom_code",
            condition=Q(ints__lt=(100, 200)),
        )
        range_obj = RangesModel.objects.create(ints=(20, 50))
        constraint.validate(RangesModel, range_obj)
        with self.assertRaises(ValidationError) as cm:
            constraint.validate(RangesModel, RangesModel(ints=(10, 20)))
        self.assertEqual(cm.exception.code, "custom_code")

    def test_expressions_with_params(self):
        constraint_name = "scene_left_equal"
        self.assertNotIn(constraint_name, self.get_constraints(Scene._meta.db_table))
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[(Left("scene", 4), RangeOperators.EQUAL)],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Scene, constraint)
        self.assertIn(constraint_name, self.get_constraints(Scene._meta.db_table))

    def test_expressions_with_key_transform(self):
        constraint_name = "exclude_overlapping_reservations_smoking"
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[
                (F("datespan"), RangeOperators.OVERLAPS),
                (KeyTextTransform("smoking", "requirements"), RangeOperators.EQUAL),
            ],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(HotelReservation, constraint)
        self.assertIn(
            constraint_name,
            self.get_constraints(HotelReservation._meta.db_table),
        )

    def test_index_transform(self):
        """


        Test that an index transformation is successfully applied to the database.

        This test adds an exclusion constraint to the IntegerArrayModel table, 
        specifying that the first element of the array field must be unique.
        The constraint is then verified to be present in the database.

        The test case covers the application of a specific exclusion constraint, 
        ensuring that the indexing transformation is correctly translated into 
        a database constraint.


        """
        constraint_name = "first_index_equal"
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("field__0", RangeOperators.EQUAL)],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(IntegerArrayModel, constraint)
        self.assertIn(
            constraint_name,
            self.get_constraints(IntegerArrayModel._meta.db_table),
        )

    def test_range_adjacent_initially_deferred(self):
        constraint_name = "ints_adjacent_deferred"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            deferrable=Deferrable.DEFERRED,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        RangesModel.objects.create(ints=(20, 50))
        adjacent_range = RangesModel.objects.create(ints=(10, 20))
        # Constraint behavior can be changed with SET CONSTRAINTS.
        with self.assertRaises(IntegrityError):
            with transaction.atomic(), connection.cursor() as cursor:
                quoted_name = connection.ops.quote_name(constraint_name)
                cursor.execute("SET CONSTRAINTS %s IMMEDIATE" % quoted_name)
        # Remove adjacent range before the end of transaction.
        adjacent_range.delete()
        RangesModel.objects.create(ints=(10, 19))
        RangesModel.objects.create(ints=(51, 60))

    def test_range_adjacent_initially_deferred_with_condition(self):
        constraint_name = "ints_adjacent_deferred_with_condition"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            condition=Q(ints__lt=(100, 200)),
            deferrable=Deferrable.DEFERRED,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        RangesModel.objects.create(ints=(20, 50))
        adjacent_range = RangesModel.objects.create(ints=(10, 20))
        # Constraint behavior can be changed with SET CONSTRAINTS.
        with self.assertRaises(IntegrityError):
            with transaction.atomic(), connection.cursor() as cursor:
                quoted_name = connection.ops.quote_name(constraint_name)
                cursor.execute(f"SET CONSTRAINTS {quoted_name} IMMEDIATE")
        # Remove adjacent range before the end of transaction.
        adjacent_range.delete()
        RangesModel.objects.create(ints=(10, 19))
        RangesModel.objects.create(ints=(51, 60))
        # Add adjacent range that doesn't match the condition.
        RangesModel.objects.create(ints=(200, 500))
        adjacent_range = RangesModel.objects.create(ints=(100, 200))
        # Constraint behavior can be changed with SET CONSTRAINTS.
        with transaction.atomic(), connection.cursor() as cursor:
            quoted_name = connection.ops.quote_name(constraint_name)
            cursor.execute(f"SET CONSTRAINTS {quoted_name} IMMEDIATE")

    def test_range_adjacent_gist_include(self):
        constraint_name = "ints_adjacent_gist_include"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            index_type="gist",
            include=["decimals", "ints"],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        RangesModel.objects.create(ints=(20, 50))
        with self.assertRaises(IntegrityError), transaction.atomic():
            RangesModel.objects.create(ints=(10, 20))
        RangesModel.objects.create(ints=(10, 19))
        RangesModel.objects.create(ints=(51, 60))

    def test_range_adjacent_spgist_include(self):
        """
        Tests the creation and functionality of an exclusion constraint on a range field using a SP-GiST index, 
        including specific fields in the constraint. 

        The test checks that the constraint is successfully added to the database table, 
        and that it prevents the insertion of overlapping ranges while allowing non-overlapping ranges.
        """
        constraint_name = "ints_adjacent_spgist_include"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            index_type="spgist",
            include=["decimals", "ints"],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))
        RangesModel.objects.create(ints=(20, 50))
        with self.assertRaises(IntegrityError), transaction.atomic():
            RangesModel.objects.create(ints=(10, 20))
        RangesModel.objects.create(ints=(10, 19))
        RangesModel.objects.create(ints=(51, 60))

    def test_range_adjacent_gist_include_condition(self):
        """

        Test that an exclusion constraint with an adjacent gist include condition can be successfully added to a model.

        The test verifies that the constraint does not initially exist on the model, then creates and adds the constraint.
        The added constraint uses the gist index type, includes a 'decimals' column, and applies to rows with id greater than or equal to 100.
        After adding the constraint, the test checks that the constraint name is present in the model's database table constraints.

        :raises AssertionError: If the constraint is not successfully added to the model.

        """
        constraint_name = "ints_adjacent_gist_include_condition"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            index_type="gist",
            include=["decimals"],
            condition=Q(id__gte=100),
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_adjacent_spgist_include_condition(self):
        constraint_name = "ints_adjacent_spgist_include_condition"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            index_type="spgist",
            include=["decimals"],
            condition=Q(id__gte=100),
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_adjacent_gist_include_deferrable(self):
        """
        Tests the addition of a deferrable exclusion constraint with a GIST index to a model.

        This test ensures that an exclusion constraint can be successfully added to a model with
        a GIST index on a range field, and that the constraint includes a specific field.
        The constraint is set to be deferrable, meaning that it will not be checked until the end of
        a transaction. The test verifies that the constraint does not exist before it is added,
        and then checks that it has been successfully added to the model's database table.

        The test uses a model with a range field, and adds an exclusion constraint with the following properties:
        - Name: ints_adjacent_gist_include_deferrable
        - Type: GIST index
        - Expression: ints field with an \"adjacent to\" range operator
        - Included field: decimals field
        - Deferrability: Deferred, meaning that constraint checks will be delayed until the end of a transaction
        """
        constraint_name = "ints_adjacent_gist_include_deferrable"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            index_type="gist",
            include=["decimals"],
            deferrable=Deferrable.DEFERRED,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_adjacent_spgist_include_deferrable(self):
        constraint_name = "ints_adjacent_spgist_include_deferrable"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[("ints", RangeOperators.ADJACENT_TO)],
            index_type="spgist",
            include=["decimals"],
            deferrable=Deferrable.DEFERRED,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_adjacent_opclass(self):
        constraint_name = "ints_adjacent_opclass"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[
                (OpClass("ints", name="range_ops"), RangeOperators.ADJACENT_TO),
            ],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        constraints = self.get_constraints(RangesModel._meta.db_table)
        self.assertIn(constraint_name, constraints)
        with editor.connection.cursor() as cursor:
            cursor.execute(SchemaTests.get_opclass_query, [constraint_name])
            self.assertEqual(
                cursor.fetchall(),
                [("range_ops", constraint_name)],
            )
        RangesModel.objects.create(ints=(20, 50))
        with self.assertRaises(IntegrityError), transaction.atomic():
            RangesModel.objects.create(ints=(10, 20))
        RangesModel.objects.create(ints=(10, 19))
        RangesModel.objects.create(ints=(51, 60))
        # Drop the constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(RangesModel, constraint)
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )

    def test_range_adjacent_opclass_condition(self):
        constraint_name = "ints_adjacent_opclass_condition"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[
                (OpClass("ints", name="range_ops"), RangeOperators.ADJACENT_TO),
            ],
            condition=Q(id__gte=100),
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_adjacent_opclass_deferrable(self):
        constraint_name = "ints_adjacent_opclass_deferrable"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[
                (OpClass("ints", name="range_ops"), RangeOperators.ADJACENT_TO),
            ],
            deferrable=Deferrable.DEFERRED,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_adjacent_gist_opclass_include(self):
        constraint_name = "ints_adjacent_gist_opclass_include"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[
                (OpClass("ints", name="range_ops"), RangeOperators.ADJACENT_TO),
            ],
            index_type="gist",
            include=["decimals"],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_adjacent_spgist_opclass_include(self):
        constraint_name = "ints_adjacent_spgist_opclass_include"
        self.assertNotIn(
            constraint_name, self.get_constraints(RangesModel._meta.db_table)
        )
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[
                (OpClass("ints", name="range_ops"), RangeOperators.ADJACENT_TO),
            ],
            index_type="spgist",
            include=["decimals"],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(RangesModel, constraint)
        self.assertIn(constraint_name, self.get_constraints(RangesModel._meta.db_table))

    def test_range_equal_cast(self):
        """
        Tests that an exclusion constraint with a range equal operator can be added to the Room model. 

        The constraint is created with a specific name and definition, then added to the database using a schema editor. 
        The test verifies that the constraint does not initially exist, is successfully added, and then exists in the database after addition.
        """
        constraint_name = "exclusion_equal_room_cast"
        self.assertNotIn(constraint_name, self.get_constraints(Room._meta.db_table))
        constraint = ExclusionConstraint(
            name=constraint_name,
            expressions=[(Cast("number", IntegerField()), RangeOperators.EQUAL)],
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Room, constraint)
        self.assertIn(constraint_name, self.get_constraints(Room._meta.db_table))

    @isolate_apps("postgres_tests")
    def test_table_create(self):
        constraint_name = "exclusion_equal_number_tc"

        class ModelWithExclusionConstraint(Model):
            number = IntegerField()

            class Meta:
                app_label = "postgres_tests"
                constraints = [
                    ExclusionConstraint(
                        name=constraint_name,
                        expressions=[("number", RangeOperators.EQUAL)],
                    )
                ]

        with connection.schema_editor() as editor:
            editor.create_model(ModelWithExclusionConstraint)
        self.assertIn(
            constraint_name,
            self.get_constraints(ModelWithExclusionConstraint._meta.db_table),
        )
