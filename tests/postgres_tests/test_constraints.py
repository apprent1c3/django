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
        Checks that a check constraint ensuring a numeric range value falls within a specified range is correctly enforced on a database model.
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
        #: Tests that the CheckConstraint for an array containing a specific value correctly raises a ValidationError when the constraint is violated and passes when it is not.
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
        Tests that a CheckConstraint for validating the length of an array field correctly raises a ValidationError when the length is invalid.
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
        Tests the addition of a check constraint to ensure that a date range contains another date range, and verifies that violating this constraint raises an IntegrityError.
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
        Tests the functionality of a check constraint that verifies if the 'timestamps_inner' range is contained within the 'timestamps' range in the RangesModel table.
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

        Tests the CheckConstraint to ensure it correctly enforces the lower and upper range bounds on the 'ints' field.

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
        Tests the creation and removal of a unique constraint with a custom operator class on the Scene model's database table. Verifies that the constraint is successfully added, its operator class is correctly set, and that it is properly removed.
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
        Tests the creation of a unique constraint with multiple columns and operator classes, verifying that the constraint is correctly applied with the specified operator classes.
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
        Tests adding a partial unique constraint with a specific operator class to the Scene model. 

        The constraint is specifically created for the 'scene' field with the 'varchar_pattern_ops' operator class and a condition that filters by the 'setting' field containing \"Sir Bedemir's Castle\". The test then verifies that the correct operator class is applied to the constraint.
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
        Tests the inclusion of an opclass with a covering index, specifically verifying that a unique constraint with an opclass is correctly applied to a model.
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
        Tests the creation and removal of a unique constraint on a model field using a specific operator class, ensuring that the constraint correctly enforces uniqueness in a case-insensitive manner.
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
        Tests the validation of a unique OpClass constraint.

        Verifies that the UniqueConstraint is correctly applied to a Scene object,
        ensuring that duplicate values in a specific OpClass do not pass validation.
        (
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
        Tests model validation for exclusion constraints to ensure correct error messages are generated when constraints refer to nonexistent or joined fields.
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
        Tests the string representation of an ExclusionConstraint instance.

        Verifies that the repr function correctly formats the constraint's attributes,
        including index type, expressions, name, condition, deferrable, include, and error messages.
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
        Tests the equality of ExclusionConstraint instances based on their attributes.
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
        Tests the deconstruction of an ExclusionConstraint instance into its constituent parts, ensuring correct path, arguments, and keyword arguments are returned.
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
        Tests the deconstruction of an ExclusionConstraint instance, verifying that it correctly decomposes into its constituent parts, including path, arguments, and keyword arguments.
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
        Tests that an ExclusionConstraint can be correctly deconstructed into its path, args, and kwargs components, ensuring accurate serialization and deserialization of the constraint's parameters.
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
        Tests that an ExclusionConstraint with a deferred deferrability can be properly deconstructed, ensuring that its path and constructor arguments are correctly extracted.
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
        Tests the deconstruction of an ExclusionConstraint instance with include parameters, verifying that it correctly breaks down into its constituent path and keyword arguments.
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
        Verifies the behavior of a database constraint for overlapping date ranges in hotel reservations.

        Checks that the constraint prevents reservations with overlapping dates for the same room, 
        while allowing valid reservations for different rooms or with non-overlapping dates. 

        Also tests edge cases, such as cancelled reservations and partial overlap exclusions.
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
        Tests the exclusion constraint for overlapping date ranges with a custom operator class, ensuring that reservations with the same room do not overlap when they are not cancelled.
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
        Tests the application of an exclusion constraint to prevent adjacent integer ranges.

        Verifies that adding and removing the exclusion constraint correctly enforces the 
        adjacency rule, allowing or blocking the creation of models with adjacent integer ranges 
        based on the presence or absence of the constraint.
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

            Tests the validation of the ExclusionConstraint for adjacent range values.

            Verifies that the constraint raises a ValidationError with a custom error code and message
            when the range is adjacent to an existing range, and that it passes when the range is not adjacent.

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
        Tests that the ExclusionConstraint validation raises a ValidationError with a custom code when the range condition is met and the adjacent range is found, and that the constraint's custom error code is used in the raised exception.
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
        Tests adding an exclusion constraint to the database table for Scene model with a specified name and Left expression parameter. Verifies that the constraint is successfully added by checking its presence in the database table before and after the addition.
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
        Tests adding an exclusion constraint to the HotelReservation model with key transform, 
        verifying that the constraint is successfully added to the database schema.
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
        Verifies that an exclusion constraint can be successfully added to a model with an integer array field, ensuring the first element of the field equals a specified value.
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
        Tests if an exclusion constraint with deferred checking allows for the creation of adjacent ranges initially, 
        but raises an IntegrityError when the constraint is set to immediate checking, and ensures the constraint is properly added and removed.
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
        Tests the creation and enforcement of an exclusion constraint on adjacent integer ranges, 
        where the constraint is deferred and conditionally applied to ranges with integers less than (100, 200).
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
        Tests that adjacent range exclusion constraints are correctly applied to a model.

        Verifies that a range with adjacent bounds raises an IntegrityError when created, 
        while non-adjacent ranges are allowed. Ensures the constraint is properly added to 
        the database and respected by the model.
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
        Tests the creation and enforcement of an exclusion constraint with an SP-GiST index that includes adjacent ranges for integer fields, ensuring data integrity by preventing overlapping ranges.
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
        Tests the creation of an exclusion constraint with an adjacent gist include condition on the RangesModel table. Verifies that the constraint is successfully added by checking its presence before and after creation.
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
        Tests that adding an exclusion constraint to a model with an adjacent range condition and specified include values works as expected.
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

        Tests the creation of a deferrable GIST exclusion constraint with an include clause on a range field, ensuring it is successfully added to the model's database table.

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
        Tests the creation of an exclusion constraint on the RangesModel with an adjacent SP-GiST index that includes a column and is deferrable.
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
        Tests the creation and removal of an exclusion constraint for adjacent range operations on the RangesModel's 'ints' field, verifying that adjacent ranges cannot be inserted while the constraint is active.
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
        Tests the creation and existence of an exclusion constraint with an adjacent operator class condition on the RangesModel table, verifying its addition and presence in the database.
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

        Tests that an exclusion constraint with an adjacent operator class and deferrable validation can be added to a model.

        Verifies that the constraint is initially absent, then adds it and checks that it has been successfully created.

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
        Tests the creation of a GIST exclusion constraint with range adjacent operation and included columns.
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
        Tests the functionality of adding an exclusion constraint with a specific opclass and include clause to a model's table, ensuring the constraint is correctly applied to the database.
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

        Tests that an exclusion constraint with an equal range casting to an integer can be added to the Room model.

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
        Tests the creation of a table with an exclusion constraint in a PostgreSQL database.

        Verifies that a model with an exclusion constraint can be created successfully and that the constraint is properly installed in the database schema.
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
