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
        Tests adding a check constraint to ensure integer range values fall within a specific range.

        Verifies the constraint is applied correctly, checking that values inside the range are allowed and values outside the range trigger an IntegrityError
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
        """
        Tests whether the CheckConstraint correctly validates an array field to contain a specific value, raising a ValidationError if the constraint is not met.
        """
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
        Checks that the CheckConstraint for array length is enforced correctly, 
        raising a ValidationError when the array length is not equal to 1.
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
        """
        Tests the creation and enforcement of a date range check constraint.

        Verifies that a constraint is added to the database, and that it prevents 
        the creation of objects with invalid date ranges, while allowing valid ranges.
        """
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
        Tests the addition of a database check constraint to ensure a datetime range contains another range, and verifies its enforcement on model instance creation.
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
        constraint = CheckConstraint(
            condition=Q(ints__contains=(1, 5)),
            name="ints_contains",
        )
        msg = f"Constraint “{constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(RangesModel, RangesModel(ints=(6, 10)))

    def test_check_constraint_range_lower_upper(self):
        """

        Checks if a check constraint with a range condition, enforcing lower and upper bounds, correctly validates or raises an exception when given valid or invalid input.

        The constraint requires that the 'ints' field starts with a value greater than or equal to 0 and ends with a value less than or equal to 99.

        """
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
        """

        Test the creation and removal of a unique constraint with a specific operator class.

        This function ensures that a unique constraint can be successfully added and removed 
        from a database table, and that the operator class is correctly assigned and queried.

        """
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
        """
        Tests that a unique constraint with multiple columns and custom opclasses is properly added to the database schema and its opclasses are correctly registered.
        """
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
        """
        Tests the addition of a partial unique constraint with a specific operator class to the database schema.
        """
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
        """
        Tests the inclusion of columns in a unique constraint with a specific operator class, verifying that the correct operator class is used for the index created on the specified field.
        """
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
        """
        Tests the addition and removal of a unique constraint with a custom operator class.

        Verifies that the constraint is correctly applied to the database table and enforces uniqueness
        with case-insensitive comparisons, and that it can be successfully removed after use.
        """
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
        """
        afforded by this method ensures data consistency by checking 
         Scenes against the predefined unique Lowercase constraint 
         enforcing the same scene name to have same case.
        """
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
        msg = "The expressions must be a list of 2-tuples."
        for expressions in (["foo"], [("foo")], [("foo_1", "foo_2", "foo_3")]):
            with self.subTest(expressions), self.assertRaisesMessage(ValueError, msg):
                ExclusionConstraint(
                    index_type="GIST",
                    name="exclude_invalid_expressions",
                    expressions=expressions,
                )

    def test_empty_expressions(self):
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
        Tests the check mechanism for exclusion constraints in database models.

        Checks that exclusion constraints referencing nonexistent fields or joined fields raise the expected validation errors.
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
        Tests the proper string representation of an ExclusionConstraint, covering various cases including different operator types, condition, deferrability, included fields, and custom error messages.
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
        Tests the equality of ExclusionConstraint objects based on their attributes, ensuring that constraints are considered equal when they have the same name, expressions, condition, and deferred behavior, and not equal when any of these attributes differ.
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
        """
        Tests the deconstruction of an ExclusionConstraint instance.

        Verifies that the deconstruct method correctly returns the path, arguments, and keyword arguments necessary to reconstruct the constraint.

        """
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
        """
        Tests the deconstruction of an ExclusionConstraint instance with a specific index type, verifying that the constraint is correctly broken down into its constituent parts for serialization or other purposes.
        """
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
        """
        Tests the deconstruction of an ExclusionConstraint instance to ensure it correctly breaks down into its constituent parts, including path, arguments, and keyword arguments.
        """
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
        """

        Tests the deconstruction of a deferrable ExclusionConstraint.

        Verifies that the deconstruct method correctly breaks down the constraint
        into its path, arguments, and keyword arguments.

        """
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
        Tests the deconstruction of an ExclusionConstraint into its constituent parts, verifying that the correct path, arguments, and keyword arguments are returned.
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
        """
        Tests the functionality of a database constraint that enforces a specific condition on hotel reservations, namely that two reservations with overlapping date ranges cannot exist for the same room.
        """
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
        """
        Test that an exclusion constraint using a custom operator class correctly prevents overlapping date ranges for reservations.
        """
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
        Tests the creation, application, and removal of an exclusion constraint on a model's range field.

        This function ensures that the exclusion constraint prevents the creation of adjacent ranges,
        while allowing non-adjacent ranges to be created, and verifies the constraint is successfully added and removed from the database schema.
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
        """
        Tests the validation of an exclusion constraint checking for adjacent ranges.

        This test covers different scenarios of range overlap, ensuring that a ValidationError is raised when the ranges are adjacent and the error code and message are correctly set. It also verifies that the constraint passes when the ranges are not adjacent or when the field is excluded from validation.
        """
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
        """
        Validate an ExclusionConstraint with a custom error code and condition, ensuring that a range does not overlap with another range under certain conditions.
        """
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
        """
        Checks that an exclusion constraint with a parameterized expression can be successfully added to the database schema.
        """
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
        """
        Tests adding an exclusion constraint with key transformation to the HotelReservation model.
        """
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
        Tests the addition of an exclusion constraint to a model's database table, 
        specifically checking that the constraint is successfully applied when the first index is equal.\"\"\"

        or 

        \"\"\"Verifies that an exclusion constraint is correctly added to a model's database table, 
        testing the constraint's behavior for the 'first index equal' case.
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
        """
        Tests that adding an exclusion constraint for adjacent ranges works correctly when deferred, specifically that it prevents overlapping ranges from being created initially, and allows them after the constraint is deferred.
        """
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
        """
        Tests the creation and implication of an exclusion constraint on adjacent ranges that is deferrable and has a condition.

        Verifies that the constraint is applied when the condition is met, and that it does not prevent the creation of non-adjacent ranges when the condition is not met or when the constraint is deferred.

        Ensures that attempting to insert an adjacent range when the constraint is not deferred results in an IntegrityError, and that the constraint can be deferred to allow for the creation of adjacent ranges under specific conditions.
        """
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
        """
        Tests the addition of an exclusion constraint to prevent adjacent ranges in the 'ints' field of a model, ensuring that overlapping ranges are rejected while non-adjacent ranges are allowed.
        """
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
        Tests adding an exclusion constraint with SP-GiST index to a model, ensuring it prevents adjacent ranges from being inserted.
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
        Tests the creation of an exclusion constraint with a gist index and include condition on the RangesModel's ints field, ensuring it is successfully added to the database.
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
        """
        Tests adding an SP-GiST exclusion constraint with an include condition to a model's table, verifying its creation and presence in the database schema.\"\"\"
        ```
        """
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
        Tests the creation of a deferrable exclusion constraint with a GIST index and included fields, specifically for adjacent ranges on integer fields, ensuring it is properly added to the database schema.
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
        """
        Test that an exclusion constraint with an sp-GiST index and deferred deferral can be added to a model.
        """
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
        """
        .. method:: test_range_adjacent_opclass

           Tests the addition and removal of an exclusion constraint named \"ints_adjacent_opclass\" 
           on the 'ints' field of the RangesModel. The constraint ensures that ranges in the 'ints' 
           field do not overlap. The test verifies the constraint's effectiveness by attempting 
           to create overlapping ranges, which should raise an IntegrityError.
        """
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
        """
        Tests adding an exclusion constraint with an adjacent operator class condition to a model's database table.
        """
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
        """
        Tests the creation of a deferrable exclusion constraint for adjacent ranges in the database.

            Verifies that the constraint does not initially exist, creates it with the
            specified name and adjacent_to operator, and then checks that it has been
            successfully added to the database table.
        """
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
        """
        Tests adding an exclusion constraint to a model with a GiST index, verifying inclusion of a specific field.
        """
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
        """
        Tests the addition of an exclusion constraint with an SP-GiST opclass to a model, 
        verifying that it successfully includes specified columns and is properly added to the database.
        """
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
        Tests the addition of an exclusion constraint to prevent equal room casting.\"\"\"

         \"\"\"This function checks that a specific constraint is not initially present in the Room database table.
         It then creates an exclusion constraint for equal room casting and adds it to the Room table, 
         verifying that the constraint has been successfully added.
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
        """
        Test creation of a database table with an exclusion constraint using Django's ORM.

        Verifies that a table can be successfully created with an exclusion constraint that enforces equality on a specified field.

        """
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
