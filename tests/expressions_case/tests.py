import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from operator import attrgetter, itemgetter
from uuid import UUID

from django.core.exceptions import FieldError
from django.db import connection
from django.db.models import (
    BinaryField,
    BooleanField,
    Case,
    Count,
    DecimalField,
    F,
    GenericIPAddressField,
    IntegerField,
    Max,
    Min,
    Q,
    Sum,
    TextField,
    Value,
    When,
)
from django.test import SimpleTestCase, TestCase

from .models import CaseTestModel, Client, FKCaseTestModel, O2OCaseTestModel

try:
    from PIL import Image
except ImportError:
    Image = None


class CaseExpressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the test cases.

        This method creates a set of objects in the database, including CaseTestModel,
        O2OCaseTestModel, and FKCaseTestModel instances. The objects are created with
        specific attribute values to support various test scenarios.

        The method also initializes a class attribute ``group_by_fields``, which is a
        list of field names from the CaseTestModel that can be used in group by
        queries. The list excludes fields that are relations or auto-created, and also
        excludes large object fields (LOBs) if the database backend does not support
        grouping by LOBs.

        """
        o = CaseTestModel.objects.create(integer=1, integer2=1, string="1")
        O2OCaseTestModel.objects.create(o2o=o, integer=1)
        FKCaseTestModel.objects.create(fk=o, integer=1)

        o = CaseTestModel.objects.create(integer=2, integer2=3, string="2")
        O2OCaseTestModel.objects.create(o2o=o, integer=2)
        FKCaseTestModel.objects.create(fk=o, integer=2)
        FKCaseTestModel.objects.create(fk=o, integer=3)

        o = CaseTestModel.objects.create(integer=3, integer2=4, string="3")
        O2OCaseTestModel.objects.create(o2o=o, integer=3)
        FKCaseTestModel.objects.create(fk=o, integer=3)
        FKCaseTestModel.objects.create(fk=o, integer=4)

        o = CaseTestModel.objects.create(integer=2, integer2=2, string="2")
        O2OCaseTestModel.objects.create(o2o=o, integer=2)
        FKCaseTestModel.objects.create(fk=o, integer=2)
        FKCaseTestModel.objects.create(fk=o, integer=3)

        o = CaseTestModel.objects.create(integer=3, integer2=4, string="3")
        O2OCaseTestModel.objects.create(o2o=o, integer=3)
        FKCaseTestModel.objects.create(fk=o, integer=3)
        FKCaseTestModel.objects.create(fk=o, integer=4)

        o = CaseTestModel.objects.create(integer=3, integer2=3, string="3")
        O2OCaseTestModel.objects.create(o2o=o, integer=3)
        FKCaseTestModel.objects.create(fk=o, integer=3)
        FKCaseTestModel.objects.create(fk=o, integer=4)

        o = CaseTestModel.objects.create(integer=4, integer2=5, string="4")
        O2OCaseTestModel.objects.create(o2o=o, integer=1)
        FKCaseTestModel.objects.create(fk=o, integer=5)

        cls.group_by_fields = [
            f.name
            for f in CaseTestModel._meta.get_fields()
            if not (f.is_relation and f.auto_created)
            and (
                connection.features.allows_group_by_lob
                or not isinstance(f, (BinaryField, TextField))
            )
        ]

    def test_annotate(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                test=Case(
                    When(integer=1, then=Value("one")),
                    When(integer=2, then=Value("two")),
                    default=Value("other"),
                )
            ).order_by("pk"),
            [
                (1, "one"),
                (2, "two"),
                (3, "other"),
                (2, "two"),
                (3, "other"),
                (3, "other"),
                (4, "other"),
            ],
            transform=attrgetter("integer", "test"),
        )

    def test_annotate_without_default(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                test=Case(
                    When(integer=1, then=1),
                    When(integer=2, then=2),
                )
            ).order_by("pk"),
            [(1, 1), (2, 2), (3, None), (2, 2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "test"),
        )

    def test_annotate_with_expression_as_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f_test=Case(
                    When(integer=1, then=F("integer") + 1),
                    When(integer=2, then=F("integer") + 3),
                    default="integer",
                )
            ).order_by("pk"),
            [(1, 2), (2, 5), (3, 3), (2, 5), (3, 3), (3, 3), (4, 4)],
            transform=attrgetter("integer", "f_test"),
        )

    def test_annotate_with_expression_as_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f_test=Case(
                    When(integer2=F("integer"), then=Value("equal")),
                    When(integer2=F("integer") + 1, then=Value("+1")),
                )
            ).order_by("pk"),
            [
                (1, "equal"),
                (2, "+1"),
                (3, "+1"),
                (2, "equal"),
                (3, "+1"),
                (3, "equal"),
                (4, "+1"),
            ],
            transform=attrgetter("integer", "f_test"),
        )

    def test_annotate_with_join_in_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                join_test=Case(
                    When(integer=1, then=F("o2o_rel__integer") + 1),
                    When(integer=2, then=F("o2o_rel__integer") + 3),
                    default="o2o_rel__integer",
                )
            ).order_by("pk"),
            [(1, 2), (2, 5), (3, 3), (2, 5), (3, 3), (3, 3), (4, 1)],
            transform=attrgetter("integer", "join_test"),
        )

    def test_annotate_with_in_clause(self):
        """

        Tests the annotation functionality using the 'in' clause.

        This test verifies that a queryset of CaseTestModel instances can be annotated with a Sum aggregation
        using a Case statement, where the condition checks for existence in a foreign key relationship.

        The annotation calculates a value named 'in_test', which sums the 'integer' values from the foreign key
        relation 'fk_rel' only if the related object is present in a given queryset 'fk_rels'.

        The test asserts that the annotated queryset matches the expected results when ordered by primary key.

        """
        fk_rels = FKCaseTestModel.objects.filter(integer__in=[5])
        self.assertQuerySetEqual(
            CaseTestModel.objects.only("pk", "integer")
            .annotate(
                in_test=Sum(
                    Case(
                        When(fk_rel__in=fk_rels, then=F("fk_rel__integer")),
                        default=Value(0),
                    )
                )
            )
            .order_by("pk"),
            [(1, 0), (2, 0), (3, 0), (2, 0), (3, 0), (3, 0), (4, 5)],
            transform=attrgetter("integer", "in_test"),
        )

    def test_annotate_with_join_in_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                join_test=Case(
                    When(integer2=F("o2o_rel__integer"), then=Value("equal")),
                    When(integer2=F("o2o_rel__integer") + 1, then=Value("+1")),
                    default=Value("other"),
                )
            ).order_by("pk"),
            [
                (1, "equal"),
                (2, "+1"),
                (3, "+1"),
                (2, "equal"),
                (3, "+1"),
                (3, "equal"),
                (4, "other"),
            ],
            transform=attrgetter("integer", "join_test"),
        )

    def test_annotate_with_join_in_predicate(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                join_test=Case(
                    When(o2o_rel__integer=1, then=Value("one")),
                    When(o2o_rel__integer=2, then=Value("two")),
                    When(o2o_rel__integer=3, then=Value("three")),
                    default=Value("other"),
                )
            ).order_by("pk"),
            [
                (1, "one"),
                (2, "two"),
                (3, "three"),
                (2, "two"),
                (3, "three"),
                (3, "three"),
                (4, "one"),
            ],
            transform=attrgetter("integer", "join_test"),
        )

    def test_annotate_with_annotation_in_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f_plus_1=F("integer") + 1,
                f_plus_3=F("integer") + 3,
            )
            .annotate(
                f_test=Case(
                    When(integer=1, then="f_plus_1"),
                    When(integer=2, then="f_plus_3"),
                    default="integer",
                ),
            )
            .order_by("pk"),
            [(1, 2), (2, 5), (3, 3), (2, 5), (3, 3), (3, 3), (4, 4)],
            transform=attrgetter("integer", "f_test"),
        )

    def test_annotate_with_annotation_in_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f_plus_1=F("integer") + 1,
            )
            .annotate(
                f_test=Case(
                    When(integer2=F("integer"), then=Value("equal")),
                    When(integer2=F("f_plus_1"), then=Value("+1")),
                ),
            )
            .order_by("pk"),
            [
                (1, "equal"),
                (2, "+1"),
                (3, "+1"),
                (2, "equal"),
                (3, "+1"),
                (3, "equal"),
                (4, "+1"),
            ],
            transform=attrgetter("integer", "f_test"),
        )

    def test_annotate_with_annotation_in_predicate(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f_minus_2=F("integer") - 2,
            )
            .annotate(
                test=Case(
                    When(f_minus_2=-1, then=Value("negative one")),
                    When(f_minus_2=0, then=Value("zero")),
                    When(f_minus_2=1, then=Value("one")),
                    default=Value("other"),
                ),
            )
            .order_by("pk"),
            [
                (1, "negative one"),
                (2, "zero"),
                (3, "one"),
                (2, "zero"),
                (3, "one"),
                (3, "one"),
                (4, "other"),
            ],
            transform=attrgetter("integer", "test"),
        )

    def test_annotate_with_aggregation_in_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.values(*self.group_by_fields)
            .annotate(
                min=Min("fk_rel__integer"),
                max=Max("fk_rel__integer"),
            )
            .annotate(
                test=Case(
                    When(integer=2, then="min"),
                    When(integer=3, then="max"),
                ),
            )
            .order_by("pk"),
            [
                (1, None, 1, 1),
                (2, 2, 2, 3),
                (3, 4, 3, 4),
                (2, 2, 2, 3),
                (3, 4, 3, 4),
                (3, 4, 3, 4),
                (4, None, 5, 5),
            ],
            transform=itemgetter("integer", "test", "min", "max"),
        )

    def test_annotate_with_aggregation_in_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.values(*self.group_by_fields)
            .annotate(
                min=Min("fk_rel__integer"),
                max=Max("fk_rel__integer"),
            )
            .annotate(
                test=Case(
                    When(integer2=F("min"), then=Value("min")),
                    When(integer2=F("max"), then=Value("max")),
                ),
            )
            .order_by("pk"),
            [
                (1, 1, "min"),
                (2, 3, "max"),
                (3, 4, "max"),
                (2, 2, "min"),
                (3, 4, "max"),
                (3, 3, "min"),
                (4, 5, "min"),
            ],
            transform=itemgetter("integer", "integer2", "test"),
        )

    def test_annotate_with_aggregation_in_predicate(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.values(*self.group_by_fields)
            .annotate(
                max=Max("fk_rel__integer"),
            )
            .annotate(
                test=Case(
                    When(max=3, then=Value("max = 3")),
                    When(max=4, then=Value("max = 4")),
                    default=Value(""),
                ),
            )
            .order_by("pk"),
            [
                (1, 1, ""),
                (2, 3, "max = 3"),
                (3, 4, "max = 4"),
                (2, 3, "max = 3"),
                (3, 4, "max = 4"),
                (3, 4, "max = 4"),
                (4, 5, ""),
            ],
            transform=itemgetter("integer", "max", "test"),
        )

    def test_annotate_exclude(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                test=Case(
                    When(integer=1, then=Value("one")),
                    When(integer=2, then=Value("two")),
                    default=Value("other"),
                )
            )
            .exclude(test="other")
            .order_by("pk"),
            [(1, "one"), (2, "two"), (2, "two")],
            transform=attrgetter("integer", "test"),
        )

    def test_annotate_filter_decimal(self):
        """
        Tests the annotation and filtering of Decimal fields using the Case function.

        Verifies that when using the Case function to annotate a queryset with a Decimal value,
        we can correctly filter the queryset using both integer and Decimal values for comparison.

        Ensures that the filtering logic works as expected when annotating fields with the Case function,
        allowing for precise data selection and retrieval based on complex conditions.
        """
        obj = CaseTestModel.objects.create(integer=0, decimal=Decimal("1"))
        qs = CaseTestModel.objects.annotate(
            x=Case(When(integer=0, then=F("decimal"))),
            y=Case(When(integer=0, then=Value(Decimal("1")))),
        )
        self.assertSequenceEqual(qs.filter(Q(x=1) & Q(x=Decimal("1"))), [obj])
        self.assertSequenceEqual(qs.filter(Q(y=1) & Q(y=Decimal("1"))), [obj])

    def test_annotate_values_not_in_order_by(self):
        self.assertEqual(
            list(
                CaseTestModel.objects.annotate(
                    test=Case(
                        When(integer=1, then=Value("one")),
                        When(integer=2, then=Value("two")),
                        When(integer=3, then=Value("three")),
                        default=Value("other"),
                    )
                )
                .order_by("test")
                .values_list("integer", flat=True)
            ),
            [1, 4, 3, 3, 3, 2, 2],
        )

    def test_annotate_with_empty_when(self):
        """

        Tests the annotation of a queryset with a conditional case statement when the filter list is empty.

        The test checks that the annotation is applied correctly to all objects in the queryset, 
        resulting in all objects being marked as 'not selected' when the filter list is empty.

        The test verifies that the length of the annotated queryset matches the original queryset 
        length, ensuring that no objects are filtered out during the annotation process.

        """
        objects = CaseTestModel.objects.annotate(
            selected=Case(
                When(pk__in=[], then=Value("selected")),
                default=Value("not selected"),
            )
        )
        self.assertEqual(len(objects), CaseTestModel.objects.count())
        self.assertTrue(all(obj.selected == "not selected" for obj in objects))

    def test_annotate_with_full_when(self):
        """
        Tests the annotation of model objects using a Case statement with a full When condition.

        Verifies that all objects in the queryset are annotated correctly, regardless of their primary key. 
        The function checks that the annotation is applied to all objects and that the length of the annotated 
        queryset matches the total count of objects in the model, confirming the annotation does not filter any objects.

        The annotation sets the 'selected' field to 'selected' for all objects, since the When condition 
        is always true due to the empty list in the Q object. This allows for a basic test of the 
        annotation mechanism without depending on specific object data.
        """
        objects = CaseTestModel.objects.annotate(
            selected=Case(
                When(~Q(pk__in=[]), then=Value("selected")),
                default=Value("not selected"),
            )
        )
        self.assertEqual(len(objects), CaseTestModel.objects.count())
        self.assertTrue(all(obj.selected == "selected" for obj in objects))

    def test_combined_expression(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                test=Case(
                    When(integer=1, then=2),
                    When(integer=2, then=1),
                    default=3,
                )
                + 1,
            ).order_by("pk"),
            [(1, 3), (2, 2), (3, 4), (2, 2), (3, 4), (3, 4), (4, 4)],
            transform=attrgetter("integer", "test"),
        )

    def test_in_subquery(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                pk__in=CaseTestModel.objects.annotate(
                    test=Case(
                        When(integer=F("integer2"), then="pk"),
                        When(integer=4, then="pk"),
                    ),
                ).values("test")
            ).order_by("pk"),
            [(1, 1), (2, 2), (3, 3), (4, 5)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_condition_with_lookups(self):
        """

        Tests the application of condition with lookups using Django's Case annotation.

        This test case verifies that the Case annotation can correctly apply different conditions
        based on the values of model fields, and that the resulting annotated field returns the
        expected boolean values.

        """
        qs = CaseTestModel.objects.annotate(
            test=Case(
                When(Q(integer2=1), string="2", then=Value(False)),
                When(Q(integer2=1), string="1", then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        self.assertIs(qs.get(integer=1).test, True)

    def test_case_reuse(self):
        """

         Tests the reuse of a Case object within a Django ORM query.

         This test verifies that a Case object can be reused within an annotation and 
         ordering operation, ensuring that the results match the expected output. The 
         test case covers the usage of a Case object with a specific condition and 
         default value, and verifies that the resulting query set is correctly ordered 
         and annotated.

        """
        SOME_CASE = Case(
            When(pk=0, then=Value("0")),
            default=Value("1"),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(somecase=SOME_CASE).order_by("pk"),
            CaseTestModel.objects.annotate(somecase=SOME_CASE)
            .order_by("pk")
            .values_list("pk", "somecase"),
            lambda x: (x.pk, x.somecase),
        )

    def test_aggregate(self):
        self.assertEqual(
            CaseTestModel.objects.aggregate(
                one=Sum(
                    Case(
                        When(integer=1, then=1),
                    )
                ),
                two=Sum(
                    Case(
                        When(integer=2, then=1),
                    )
                ),
                three=Sum(
                    Case(
                        When(integer=3, then=1),
                    )
                ),
                four=Sum(
                    Case(
                        When(integer=4, then=1),
                    )
                ),
            ),
            {"one": 1, "two": 2, "three": 3, "four": 1},
        )

    def test_aggregate_with_expression_as_value(self):
        self.assertEqual(
            CaseTestModel.objects.aggregate(
                one=Sum(Case(When(integer=1, then="integer"))),
                two=Sum(Case(When(integer=2, then=F("integer") - 1))),
                three=Sum(Case(When(integer=3, then=F("integer") + 1))),
            ),
            {"one": 1, "two": 2, "three": 12},
        )

    def test_aggregate_with_expression_as_condition(self):
        self.assertEqual(
            CaseTestModel.objects.aggregate(
                equal=Sum(
                    Case(
                        When(integer2=F("integer"), then=1),
                    )
                ),
                plus_one=Sum(
                    Case(
                        When(integer2=F("integer") + 1, then=1),
                    )
                ),
            ),
            {"equal": 3, "plus_one": 4},
        )

    def test_filter(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                integer2=Case(
                    When(integer=2, then=3),
                    When(integer=3, then=4),
                    default=1,
                )
            ).order_by("pk"),
            [(1, 1), (2, 3), (3, 4), (3, 4)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_without_default(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                integer2=Case(
                    When(integer=2, then=3),
                    When(integer=3, then=4),
                )
            ).order_by("pk"),
            [(2, 3), (3, 4), (3, 4)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_expression_as_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                integer2=Case(
                    When(integer=2, then=F("integer") + 1),
                    When(integer=3, then=F("integer")),
                    default="integer",
                )
            ).order_by("pk"),
            [(1, 1), (2, 3), (3, 3)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_expression_as_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                string=Case(
                    When(integer2=F("integer"), then=Value("2")),
                    When(integer2=F("integer") + 1, then=Value("3")),
                )
            ).order_by("pk"),
            [(3, 4, "3"), (2, 2, "2"), (3, 4, "3")],
            transform=attrgetter("integer", "integer2", "string"),
        )

    def test_filter_with_join_in_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                integer2=Case(
                    When(integer=2, then=F("o2o_rel__integer") + 1),
                    When(integer=3, then=F("o2o_rel__integer")),
                    default="o2o_rel__integer",
                )
            ).order_by("pk"),
            [(1, 1), (2, 3), (3, 3)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_join_in_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                integer=Case(
                    When(integer2=F("o2o_rel__integer") + 1, then=2),
                    When(integer2=F("o2o_rel__integer"), then=3),
                )
            ).order_by("pk"),
            [(2, 3), (3, 3)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_join_in_predicate(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(
                integer2=Case(
                    When(o2o_rel__integer=1, then=1),
                    When(o2o_rel__integer=2, then=3),
                    When(o2o_rel__integer=3, then=4),
                )
            ).order_by("pk"),
            [(1, 1), (2, 3), (3, 4), (3, 4)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_annotation_in_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f=F("integer"),
                f_plus_1=F("integer") + 1,
            )
            .filter(
                integer2=Case(
                    When(integer=2, then="f_plus_1"),
                    When(integer=3, then="f"),
                ),
            )
            .order_by("pk"),
            [(2, 3), (3, 3)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_annotation_in_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f_plus_1=F("integer") + 1,
            )
            .filter(
                integer=Case(
                    When(integer2=F("integer"), then=2),
                    When(integer2=F("f_plus_1"), then=3),
                ),
            )
            .order_by("pk"),
            [(3, 4), (2, 2), (3, 4)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_annotation_in_predicate(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                f_plus_1=F("integer") + 1,
            )
            .filter(
                integer2=Case(
                    When(f_plus_1=3, then=3),
                    When(f_plus_1=4, then=4),
                    default=1,
                ),
            )
            .order_by("pk"),
            [(1, 1), (2, 3), (3, 4), (3, 4)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_filter_with_aggregation_in_value(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.values(*self.group_by_fields)
            .annotate(
                min=Min("fk_rel__integer"),
                max=Max("fk_rel__integer"),
            )
            .filter(
                integer2=Case(
                    When(integer=2, then="min"),
                    When(integer=3, then="max"),
                ),
            )
            .order_by("pk"),
            [(3, 4, 3, 4), (2, 2, 2, 3), (3, 4, 3, 4)],
            transform=itemgetter("integer", "integer2", "min", "max"),
        )

    def test_filter_with_aggregation_in_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.values(*self.group_by_fields)
            .annotate(
                min=Min("fk_rel__integer"),
                max=Max("fk_rel__integer"),
            )
            .filter(
                integer=Case(
                    When(integer2=F("min"), then=2),
                    When(integer2=F("max"), then=3),
                ),
            )
            .order_by("pk"),
            [(3, 4, 3, 4), (2, 2, 2, 3), (3, 4, 3, 4)],
            transform=itemgetter("integer", "integer2", "min", "max"),
        )

    def test_filter_with_aggregation_in_predicate(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.values(*self.group_by_fields)
            .annotate(
                max=Max("fk_rel__integer"),
            )
            .filter(
                integer=Case(
                    When(max=3, then=2),
                    When(max=4, then=3),
                ),
            )
            .order_by("pk"),
            [(2, 3, 3), (3, 4, 4), (2, 2, 3), (3, 4, 4), (3, 3, 4)],
            transform=itemgetter("integer", "integer2", "max"),
        )

    def test_update(self):
        """
        Tests the update functionality of the CaseTestModel using conditional expressions.

        This test updates all objects in the CaseTestModel database table to set the 'string' field based on the 'integer' field.
        The update is performed using a case statement, where 'integer' values of 1 and 2 are mapped to 'one' and 'two' respectively,
        and all other values are set to 'other'. The test then asserts that the updated queryset matches the expected results,
        ordered by the primary key of the objects.

        This test ensures that the update function is working correctly with conditional statements and validates the data integrity
        after the update operation.
        """
        CaseTestModel.objects.update(
            string=Case(
                When(integer=1, then=Value("one")),
                When(integer=2, then=Value("two")),
                default=Value("other"),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, "one"),
                (2, "two"),
                (3, "other"),
                (2, "two"),
                (3, "other"),
                (3, "other"),
                (4, "other"),
            ],
            transform=attrgetter("integer", "string"),
        )

    def test_update_without_default(self):
        CaseTestModel.objects.update(
            integer2=Case(
                When(integer=1, then=1),
                When(integer=2, then=2),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, 1), (2, 2), (3, None), (2, 2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "integer2"),
        )

    def test_update_with_expression_as_value(self):
        """

        Updates a set of model objects using a case expression as the value.

        This function tests the ability to update a model field with a dynamic value
        based on conditions specified in a case expression. It checks if the update
        operation correctly applies the conditional logic and updates the model objects
        accordingly.

        The case expression used in this function includes multiple conditions and a default
        value, allowing for a flexible and dynamic update process.

        The function also verifies that the updated objects match the expected results,
        providing a way to ensure the correctness of the update operation.

        """
        CaseTestModel.objects.update(
            integer=Case(
                When(integer=1, then=F("integer") + 1),
                When(integer=2, then=F("integer") + 3),
                default="integer",
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [("1", 2), ("2", 5), ("3", 3), ("2", 5), ("3", 3), ("3", 3), ("4", 4)],
            transform=attrgetter("string", "integer"),
        )

    def test_update_with_expression_as_condition(self):
        """

        Updates a model's field using a conditional expression and verifies the result.

        This function tests the functionality of updating a model's field based on specific conditions using a Case expression.
        It creates a Case statement with When conditions that check the value of the 'integer2' field and update the 'string' field accordingly.
        The conditions include checking for equality and a value one greater than the 'integer2' field.
        The function then asserts that the updated queryset matches the expected results, ordered by the primary key.

        The test covers different scenarios to ensure the conditional update works as expected.

        """
        CaseTestModel.objects.update(
            string=Case(
                When(integer2=F("integer"), then=Value("equal")),
                When(integer2=F("integer") + 1, then=Value("+1")),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, "equal"),
                (2, "+1"),
                (3, "+1"),
                (2, "equal"),
                (3, "+1"),
                (3, "equal"),
                (4, "+1"),
            ],
            transform=attrgetter("integer", "string"),
        )

    def test_update_with_join_in_condition_raise_field_error(self):
        """
        Tests that an update query with a join in the condition raises a FieldError.

        When attempting to update a model's field using a Case expression that references a joined field,
        this function checks that the expected FieldError exception is raised with the correct error message.

        The test verifies that the ORM correctly restricts the use of joined field references in this type of query,
        ensuring data integrity and preventing potential errors due to ambiguous or incorrect joins.
        """
        with self.assertRaisesMessage(
            FieldError, "Joined field references are not permitted in this query"
        ):
            CaseTestModel.objects.update(
                integer=Case(
                    When(integer2=F("o2o_rel__integer") + 1, then=2),
                    When(integer2=F("o2o_rel__integer"), then=3),
                ),
            )

    def test_update_with_join_in_predicate_raise_field_error(self):
        """
        Tests that an update query with a join in the predicate raises a FieldError.

        When attempting to perform an update on a model using a Case statement that references a joined field,
        this function verifies that the expected error message is raised.

        The error is triggered because joined field references are not allowed in this type of query.

        :raises: FieldError with the message 'Joined field references are not permitted in this query'
        """
        with self.assertRaisesMessage(
            FieldError, "Joined field references are not permitted in this query"
        ):
            CaseTestModel.objects.update(
                string=Case(
                    When(o2o_rel__integer=1, then=Value("one")),
                    When(o2o_rel__integer=2, then=Value("two")),
                    When(o2o_rel__integer=3, then=Value("three")),
                    default=Value("other"),
                ),
            )

    def test_update_big_integer(self):
        """

        Updates a model's big integer field using a Case expression and verifies the result.

        This function tests the functionality of updating a big integer field in a model
        instance using conditional logic based on the value of another field.

        It checks that the update operation correctly applies the specified conditions and
        modifies the big integer field as expected, while leaving other values unchanged.

        """
        CaseTestModel.objects.update(
            big_integer=Case(
                When(integer=1, then=1),
                When(integer=2, then=2),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, 1), (2, 2), (3, None), (2, 2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "big_integer"),
        )

    def test_update_binary(self):
        """

        Updates a database model using a binary case statement and checks the query results.

        This function tests the ability to update a model using a Case statement with binary data.
        It updates the binary field of a model based on the value of an integer field, then verifies
        that the updated values match the expected results.

        The test covers different cases, including when the integer field has values that match the
        conditions in the Case statement, as well as when the integer field has values that do not
        match any of the conditions, resulting in a default binary value being applied.

        """
        CaseTestModel.objects.update(
            binary=Case(
                When(integer=1, then=b"one"),
                When(integer=2, then=b"two"),
                default=b"",
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, b"one"),
                (2, b"two"),
                (3, b""),
                (2, b"two"),
                (3, b""),
                (3, b""),
                (4, b""),
            ],
            transform=lambda o: (o.integer, bytes(o.binary)),
        )

    def test_update_boolean(self):
        CaseTestModel.objects.update(
            boolean=Case(
                When(integer=1, then=True),
                When(integer=2, then=True),
                default=False,
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, True),
                (2, True),
                (3, False),
                (2, True),
                (3, False),
                (3, False),
                (4, False),
            ],
            transform=attrgetter("integer", "boolean"),
        )

    def test_update_date(self):
        CaseTestModel.objects.update(
            date=Case(
                When(integer=1, then=date(2015, 1, 1)),
                When(integer=2, then=date(2015, 1, 2)),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, date(2015, 1, 1)),
                (2, date(2015, 1, 2)),
                (3, None),
                (2, date(2015, 1, 2)),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "date"),
        )

    def test_update_date_time(self):
        """

        Updates the date_time field of the CaseTestModel instances based on the value of the integer field.

        This function tests the update functionality by setting the date_time to January 1, 2015, for instances where the integer is 1, and to January 2, 2015, for instances where the integer is 2. The update is then verified by checking the resulting queryset.

        The test covers cases where the integer value is 1, 2, or other values, and verifies that the corresponding date_time values are correctly updated or remain unchanged.

        """
        CaseTestModel.objects.update(
            date_time=Case(
                When(integer=1, then=datetime(2015, 1, 1)),
                When(integer=2, then=datetime(2015, 1, 2)),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, datetime(2015, 1, 1)),
                (2, datetime(2015, 1, 2)),
                (3, None),
                (2, datetime(2015, 1, 2)),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "date_time"),
        )

    def test_update_decimal(self):
        """

        Tests updating decimal fields in a model using Django's Case expressions.

        This test case verifies that updating decimal fields with specific conditions
        (using When expressions) results in the expected values.

        It checks the outcome of updating decimal fields for different integer values,
        ensuring that the decimal values are correctly updated based on the conditions.

        The test asserts that the updated queryset matches the expected results, 
        which include updated decimal values for specific integer values and unchanged 
        values for others.

        """
        CaseTestModel.objects.update(
            decimal=Case(
                When(integer=1, then=Decimal("1.1")),
                When(
                    integer=2, then=Value(Decimal("2.2"), output_field=DecimalField())
                ),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, Decimal("1.1")),
                (2, Decimal("2.2")),
                (3, None),
                (2, Decimal("2.2")),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "decimal"),
        )

    def test_update_duration(self):
        """

        Tests the update functionality with a Case statement to set duration based on integer value.

        The test updates a queryset of CaseTestModel objects, setting the duration field using a conditional Case statement.
        The condition checks the integer field, setting duration to 1 day if integer is 1 and 2 days if integer is 2.
        The test then verifies the updated queryset matches the expected output, ensuring the duration field is correctly updated for each object.

        """
        CaseTestModel.objects.update(
            duration=Case(
                When(integer=1, then=timedelta(1)),
                When(integer=2, then=timedelta(2)),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, timedelta(1)),
                (2, timedelta(2)),
                (3, None),
                (2, timedelta(2)),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "duration"),
        )

    def test_update_email(self):
        """

        Updates the email field of CaseTestModel instances using a conditional case statement.

        The update operation sets the email based on the value of the integer field:
        - If the integer field is 1, the email is set to '1@example.com'.
        - If the integer field is 2, the email is set to '2@example.com'.
        - For all other integer values, the email is set to an empty string.

        This function tests the correctness of the update query by comparing the resulting queryset with an expected list of tuples containing the integer and email values for each instance, ordered by primary key.

        """
        CaseTestModel.objects.update(
            email=Case(
                When(integer=1, then=Value("1@example.com")),
                When(integer=2, then=Value("2@example.com")),
                default=Value(""),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, "1@example.com"),
                (2, "2@example.com"),
                (3, ""),
                (2, "2@example.com"),
                (3, ""),
                (3, ""),
                (4, ""),
            ],
            transform=attrgetter("integer", "email"),
        )

    def test_update_file(self):
        """

        Update test case to verify that the file field in CaseTestModel is updated correctly using Case When SQL expressions.

        This test updates the file field with specific values based on the integer value in each object.
        It then checks the resulting queryset to ensure that the expected values are returned.

        The test covers the following scenarios:
        - Updating the file field with a specific value when the integer is 1
        - Updating the file field with a different value when the integer is 2
        - Leaving the file field empty when the integer is not 1 or 2

        """
        CaseTestModel.objects.update(
            file=Case(
                When(integer=1, then=Value("~/1")),
                When(integer=2, then=Value("~/2")),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, "~/1"), (2, "~/2"), (3, ""), (2, "~/2"), (3, ""), (3, ""), (4, "")],
            transform=lambda o: (o.integer, str(o.file)),
        )

    def test_update_file_path(self):
        CaseTestModel.objects.update(
            file_path=Case(
                When(integer=1, then=Value("~/1")),
                When(integer=2, then=Value("~/2")),
                default=Value(""),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, "~/1"), (2, "~/2"), (3, ""), (2, "~/2"), (3, ""), (3, ""), (4, "")],
            transform=attrgetter("integer", "file_path"),
        )

    def test_update_float(self):
        """

        Tests the update of a float field in a model using a Case statement.

        The function updates the float field of a set of objects based on the value of their integer field.
        It then asserts that the updated values match the expected results.

        The test covers cases where the integer field has specific values (1 and 2) and verifies that the float field is updated accordingly.
        It also checks that objects with other integer values remain unchanged.

        This test ensures that the Case statement is correctly applied to the model's float field.

        """
        CaseTestModel.objects.update(
            float=Case(
                When(integer=1, then=1.1),
                When(integer=2, then=2.2),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, 1.1), (2, 2.2), (3, None), (2, 2.2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "float"),
        )

    @unittest.skipUnless(Image, "Pillow not installed")
    def test_update_image(self):
        """

        Tests the update functionality of images in the CaseTestModel using conditional statements.

        This test case skips execution if the Pillow library is not installed.

        The test updates the images in the database based on specific conditions, and then verifies that the updated images match the expected values.
        The conditions used for updating the images are based on the 'integer' field, where:
        - integer value 1 sets the image to '~/1'
        - integer value 2 sets the image to '~/2'
        - all other integer values leave the image unchanged

        The test asserts that the updated queryset matches the expected output, ensuring the update functionality works as expected.

        """
        CaseTestModel.objects.update(
            image=Case(
                When(integer=1, then=Value("~/1")),
                When(integer=2, then=Value("~/2")),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, "~/1"), (2, "~/2"), (3, ""), (2, "~/2"), (3, ""), (3, ""), (4, "")],
            transform=lambda o: (o.integer, str(o.image)),
        )

    def test_update_generic_ip_address(self):
        """

        Updates a set of records in the database with generic IP addresses based on a specific condition.

        This function tests the update functionality using a conditional statement to assign IP addresses to records.
        It checks if the 'integer' field is 1 and assigns '1.1.1.1' or if it's 2 and assigns '2.2.2.2'.
        The function then verifies that the update operation has produced the expected results by comparing the updated records with the expected output.

        The test case covers the update of records with conditional logic and verifies the correctness of the results.

        """
        CaseTestModel.objects.update(
            generic_ip_address=Case(
                When(integer=1, then=Value("1.1.1.1")),
                When(integer=2, then=Value("2.2.2.2")),
                output_field=GenericIPAddressField(),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, "1.1.1.1"),
                (2, "2.2.2.2"),
                (3, None),
                (2, "2.2.2.2"),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "generic_ip_address"),
        )

    def test_update_null_boolean(self):
        """
        Tests the update of a null boolean field in the database using a case statement.

        The test verifies that the null boolean field is correctly updated based on the value of the integer field.
        It checks that the values are updated as expected and that the order of the queryset is maintained.
        The test case covers both True and False values, as well as the case where the null boolean field remains unchanged (None).
        """
        CaseTestModel.objects.update(
            null_boolean=Case(
                When(integer=1, then=True),
                When(integer=2, then=False),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, True),
                (2, False),
                (3, None),
                (2, False),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "null_boolean"),
        )

    def test_update_positive_big_integer(self):
        """

        Test that the update of positive_big_integer field using Case When works correctly.

        This test updates the positive_big_integer field in the CaseTestModel database table using a Case/When statement to set specific values based on conditions.

        It then checks if the updated values are correct by comparing the refreshed queryset with expected output, verifying that the update was successful and accurate.

        The test case covers various scenarios, including updating existing values and handling null cases.

        """
        CaseTestModel.objects.update(
            positive_big_integer=Case(
                When(integer=1, then=1),
                When(integer=2, then=2),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, 1), (2, 2), (3, None), (2, 2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "positive_big_integer"),
        )

    def test_update_positive_integer(self):
        CaseTestModel.objects.update(
            positive_integer=Case(
                When(integer=1, then=1),
                When(integer=2, then=2),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, 1), (2, 2), (3, None), (2, 2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "positive_integer"),
        )

    def test_update_positive_small_integer(self):
        CaseTestModel.objects.update(
            positive_small_integer=Case(
                When(integer=1, then=1),
                When(integer=2, then=2),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, 1), (2, 2), (3, None), (2, 2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "positive_small_integer"),
        )

    def test_update_slug(self):
        CaseTestModel.objects.update(
            slug=Case(
                When(integer=1, then=Value("1")),
                When(integer=2, then=Value("2")),
                default=Value(""),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, "1"), (2, "2"), (3, ""), (2, "2"), (3, ""), (3, ""), (4, "")],
            transform=attrgetter("integer", "slug"),
        )

    def test_update_small_integer(self):
        CaseTestModel.objects.update(
            small_integer=Case(
                When(integer=1, then=1),
                When(integer=2, then=2),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, 1), (2, 2), (3, None), (2, 2), (3, None), (3, None), (4, None)],
            transform=attrgetter("integer", "small_integer"),
        )

    def test_update_string(self):
        CaseTestModel.objects.filter(string__in=["1", "2"]).update(
            string=Case(
                When(integer=1, then=Value("1")),
                When(integer=2, then=Value("2")),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(string__in=["1", "2"]).order_by("pk"),
            [(1, "1"), (2, "2"), (2, "2")],
            transform=attrgetter("integer", "string"),
        )

    def test_update_text(self):
        CaseTestModel.objects.update(
            text=Case(
                When(integer=1, then=Value("1")),
                When(integer=2, then=Value("2")),
                default=Value(""),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [(1, "1"), (2, "2"), (3, ""), (2, "2"), (3, ""), (3, ""), (4, "")],
            transform=attrgetter("integer", "text"),
        )

    def test_update_time(self):
        CaseTestModel.objects.update(
            time=Case(
                When(integer=1, then=time(1)),
                When(integer=2, then=time(2)),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, time(1)),
                (2, time(2)),
                (3, None),
                (2, time(2)),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "time"),
        )

    def test_update_url(self):
        """

        Tests the update of URLs for CaseTestModel instances using conditional logic.

        This test case verifies that the URLs are updated correctly based on the integer value of each instance.
        Specifically, it checks that instances with an integer value of 1 are assigned the URL 'http://1.example.com/',
        instances with an integer value of 2 are assigned the URL 'http://2.example.com/', and all other instances are assigned an empty URL.

        The test ensures that the updated URLs are correctly reflected in the database and can be retrieved in the correct order.

        """
        CaseTestModel.objects.update(
            url=Case(
                When(integer=1, then=Value("http://1.example.com/")),
                When(integer=2, then=Value("http://2.example.com/")),
                default=Value(""),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, "http://1.example.com/"),
                (2, "http://2.example.com/"),
                (3, ""),
                (2, "http://2.example.com/"),
                (3, ""),
                (3, ""),
                (4, ""),
            ],
            transform=attrgetter("integer", "url"),
        )

    def test_update_uuid(self):
        CaseTestModel.objects.update(
            uuid=Case(
                When(integer=1, then=UUID("11111111111111111111111111111111")),
                When(integer=2, then=UUID("22222222222222222222222222222222")),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, UUID("11111111111111111111111111111111")),
                (2, UUID("22222222222222222222222222222222")),
                (3, None),
                (2, UUID("22222222222222222222222222222222")),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "uuid"),
        )

    def test_update_fk(self):
        """
        Tests updating a foreign key field using a Case expression.

        This test case verifies that the foreign key field in the CaseTestModel can be
        successfully updated using a conditional Case statement. The test checks if the
        foreign key field is correctly set for specific integer values, ensuring that the
        update operation is working as expected.

        The test covers the scenario where the foreign key field is updated for a subset
        of objects in the database, and verifies that the updated values match the
        expected results. The test also checks that objects not matched by the Case
        expression are not updated.

        The test outcome is validated by comparing the updated query set with the
        expected results, ensuring that the foreign key field has been correctly updated
        for the specified objects.
        """
        obj1, obj2 = CaseTestModel.objects.all()[:2]

        CaseTestModel.objects.update(
            fk=Case(
                When(integer=1, then=obj1.pk),
                When(integer=2, then=obj2.pk),
            ),
        )
        self.assertQuerySetEqual(
            CaseTestModel.objects.order_by("pk"),
            [
                (1, obj1.pk),
                (2, obj2.pk),
                (3, None),
                (2, obj2.pk),
                (3, None),
                (3, None),
                (4, None),
            ],
            transform=attrgetter("integer", "fk_id"),
        )

    def test_lookup_in_condition(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                test=Case(
                    When(integer__lt=2, then=Value("less than 2")),
                    When(integer__gt=2, then=Value("greater than 2")),
                    default=Value("equal to 2"),
                ),
            ).order_by("pk"),
            [
                (1, "less than 2"),
                (2, "equal to 2"),
                (3, "greater than 2"),
                (2, "equal to 2"),
                (3, "greater than 2"),
                (3, "greater than 2"),
                (4, "greater than 2"),
            ],
            transform=attrgetter("integer", "test"),
        )

    def test_lookup_different_fields(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                test=Case(
                    When(integer=2, integer2=3, then=Value("when")),
                    default=Value("default"),
                ),
            ).order_by("pk"),
            [
                (1, 1, "default"),
                (2, 3, "when"),
                (3, 4, "default"),
                (2, 2, "default"),
                (3, 4, "default"),
                (3, 3, "default"),
                (4, 5, "default"),
            ],
            transform=attrgetter("integer", "integer2", "test"),
        )

    def test_combined_q_object(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.annotate(
                test=Case(
                    When(Q(integer=2) | Q(integer2=3), then=Value("when")),
                    default=Value("default"),
                ),
            ).order_by("pk"),
            [
                (1, 1, "default"),
                (2, 3, "when"),
                (3, 4, "default"),
                (2, 2, "when"),
                (3, 4, "default"),
                (3, 3, "when"),
                (4, 5, "default"),
            ],
            transform=attrgetter("integer", "integer2", "test"),
        )

    def test_order_by_conditional_implicit(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(integer__lte=2)
            .annotate(
                test=Case(
                    When(integer=1, then=2),
                    When(integer=2, then=1),
                    default=3,
                )
            )
            .order_by("test", "pk"),
            [(2, 1), (2, 1), (1, 2)],
            transform=attrgetter("integer", "test"),
        )

    def test_order_by_conditional_explicit(self):
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(integer__lte=2)
            .annotate(
                test=Case(
                    When(integer=1, then=2),
                    When(integer=2, then=1),
                    default=3,
                )
            )
            .order_by(F("test").asc(), "pk"),
            [(2, 1), (2, 1), (1, 2)],
            transform=attrgetter("integer", "test"),
        )

    def test_join_promotion(self):
        """

        Tests the usage of conditional expressions in Django's ORM, specifically the Case statement, 
        in conjunction with the annotate method to add calculated fields to a queryset.

        The function creates an instance of CaseTestModel, then proceeds to test two different scenarios: 
        1. when a foreign key relation is matched, 
        2. when a foreign key relation is null.

        It verifies that the Case statement correctly evaluates the conditions and returns the expected values 
        for the annotated field 'foo'. The tests cover both the 'then' and 'default' branches of the Case statement.

        """
        o = CaseTestModel.objects.create(integer=1, integer2=1, string="1")
        # Testing that:
        # 1. There isn't any object on the remote side of the fk_rel
        #    relation. If the query used inner joins, then the join to fk_rel
        #    would remove o from the results. So, in effect we are testing that
        #    we are promoting the fk_rel join to a left outer join here.
        # 2. The default value of 3 is generated for the case expression.
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(pk=o.pk).annotate(
                foo=Case(
                    When(fk_rel__pk=1, then=2),
                    default=3,
                ),
            ),
            [(o, 3)],
            lambda x: (x, x.foo),
        )
        # Now 2 should be generated, as the fk_rel is null.
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(pk=o.pk).annotate(
                foo=Case(
                    When(fk_rel__isnull=True, then=2),
                    default=3,
                ),
            ),
            [(o, 2)],
            lambda x: (x, x.foo),
        )

    def test_join_promotion_multiple_annotations(self):
        """

        Tests the join promotion of multiple annotations in a QuerySet.

        This test case ensures that multiple annotations can be applied to a QuerySet, 
        and that the correct values are returned based on the conditions specified in the 
        Case statements. The test covers two scenarios: when the foreign key relation 
        is present and when it is null.

        The function first creates a test model instance, then applies two sets of 
        annotations to the instance's QuerySet. The first set checks for the presence 
        of a foreign key relation, and the second set checks for the absence of a 
        foreign key relation. The function then verifies that the annotated values 
        match the expected results.

        """
        o = CaseTestModel.objects.create(integer=1, integer2=1, string="1")
        # Testing that:
        # 1. There isn't any object on the remote side of the fk_rel
        #    relation. If the query used inner joins, then the join to fk_rel
        #    would remove o from the results. So, in effect we are testing that
        #    we are promoting the fk_rel join to a left outer join here.
        # 2. The default value of 3 is generated for the case expression.
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(pk=o.pk).annotate(
                foo=Case(
                    When(fk_rel__pk=1, then=2),
                    default=3,
                ),
                bar=Case(
                    When(fk_rel__pk=1, then=4),
                    default=5,
                ),
            ),
            [(o, 3, 5)],
            lambda x: (x, x.foo, x.bar),
        )
        # Now 2 should be generated, as the fk_rel is null.
        self.assertQuerySetEqual(
            CaseTestModel.objects.filter(pk=o.pk).annotate(
                foo=Case(
                    When(fk_rel__isnull=True, then=2),
                    default=3,
                ),
                bar=Case(
                    When(fk_rel__isnull=True, then=4),
                    default=5,
                ),
            ),
            [(o, 2, 4)],
            lambda x: (x, x.foo, x.bar),
        )

    def test_m2m_exclude(self):
        CaseTestModel.objects.create(integer=10, integer2=1, string="1")
        qs = (
            CaseTestModel.objects.values_list("id", "integer")
            .annotate(
                cnt=Sum(
                    Case(When(~Q(fk_rel__integer=1), then=1), default=2),
                ),
            )
            .order_by("integer")
        )
        # The first o has 2 as its fk_rel__integer=1, thus it hits the
        # default=2 case. The other ones have 2 as the result as they have 2
        # fk_rel objects, except for integer=4 and integer=10 (created above).
        # The integer=4 case has one integer, thus the result is 1, and
        # integer=10 doesn't have any and this too generates 1 (instead of 0)
        # as ~Q() also matches nulls.
        self.assertQuerySetEqual(
            qs,
            [(1, 2), (2, 2), (2, 2), (3, 2), (3, 2), (3, 2), (4, 1), (10, 1)],
            lambda x: x[1:],
        )

    def test_m2m_reuse(self):
        """

        Tests the reuse of joins in many-to-many relationships.

        This test case creates a test model instance and then queries the database to 
        calculate aggregated values based on certain conditions in the related model. 
        It verifies that the generated SQL query uses an optimal number of joins and 
        that the results match the expected values. The test focuses on ensuring that 
        the Django ORM is able to correctly reuse joins when performing multiple 
        aggregations on a single related model. 

        It checks that the generated SQL query joins the related table only once, 
        regardless of the number of aggregations. The results are then compared to 
        the expected output, verifying that the aggregations are calculated correctly.

        """
        CaseTestModel.objects.create(integer=10, integer2=1, string="1")
        # Need to use values before annotate so that Oracle will not group
        # by fields it isn't capable of grouping by.
        qs = (
            CaseTestModel.objects.values_list("id", "integer")
            .annotate(
                cnt=Sum(
                    Case(When(~Q(fk_rel__integer=1), then=1), default=2),
                ),
            )
            .annotate(
                cnt2=Sum(
                    Case(When(~Q(fk_rel__integer=1), then=1), default=2),
                ),
            )
            .order_by("integer")
        )
        self.assertEqual(str(qs.query).count(" JOIN "), 1)
        self.assertQuerySetEqual(
            qs,
            [
                (1, 2, 2),
                (2, 2, 2),
                (2, 2, 2),
                (3, 2, 2),
                (3, 2, 2),
                (3, 2, 2),
                (4, 1, 1),
                (10, 1, 1),
            ],
            lambda x: x[1:],
        )

    def test_aggregation_empty_cases(self):
        tests = [
            # Empty cases and default.
            (Case(output_field=IntegerField()), None),
            # Empty cases and a constant default.
            (Case(default=Value("empty")), "empty"),
            # Empty cases and column in the default.
            (Case(default=F("url")), ""),
        ]
        for case, value in tests:
            with self.subTest(case=case):
                self.assertQuerySetEqual(
                    CaseTestModel.objects.values("string")
                    .annotate(
                        case=case,
                        integer_sum=Sum("integer"),
                    )
                    .order_by("string"),
                    [
                        ("1", value, 1),
                        ("2", value, 4),
                        ("3", value, 9),
                        ("4", value, 4),
                    ],
                    transform=itemgetter("string", "case", "integer_sum"),
                )


class CaseDocumentationExamples(TestCase):
    @classmethod
    def setUpTestData(cls):
        Client.objects.create(
            name="Jane Doe",
            account_type=Client.REGULAR,
            registered_on=date.today() - timedelta(days=36),
        )
        Client.objects.create(
            name="James Smith",
            account_type=Client.GOLD,
            registered_on=date.today() - timedelta(days=5),
        )
        Client.objects.create(
            name="Jack Black",
            account_type=Client.PLATINUM,
            registered_on=date.today() - timedelta(days=10 * 365),
        )

    def test_simple_example(self):
        self.assertQuerySetEqual(
            Client.objects.annotate(
                discount=Case(
                    When(account_type=Client.GOLD, then=Value("5%")),
                    When(account_type=Client.PLATINUM, then=Value("10%")),
                    default=Value("0%"),
                ),
            ).order_by("pk"),
            [("Jane Doe", "0%"), ("James Smith", "5%"), ("Jack Black", "10%")],
            transform=attrgetter("name", "discount"),
        )

    def test_lookup_example(self):
        """
        )test_lookup_example(self):
            \"\"\"
            Tests the ability to dynamically apply discounts to clients based on their registration date.

            This test case verifies that clients who have been registered for more than a year receive a 10% discount,
            those registered within the last month receive a 5% discount, and all others receive a 0% discount.
            The test ensures that the discounts are applied correctly and the results are returned in the correct order.

        """
        a_month_ago = date.today() - timedelta(days=30)
        a_year_ago = date.today() - timedelta(days=365)
        self.assertQuerySetEqual(
            Client.objects.annotate(
                discount=Case(
                    When(registered_on__lte=a_year_ago, then=Value("10%")),
                    When(registered_on__lte=a_month_ago, then=Value("5%")),
                    default=Value("0%"),
                ),
            ).order_by("pk"),
            [("Jane Doe", "5%"), ("James Smith", "0%"), ("Jack Black", "10%")],
            transform=attrgetter("name", "discount"),
        )

    def test_conditional_update_example(self):
        a_month_ago = date.today() - timedelta(days=30)
        a_year_ago = date.today() - timedelta(days=365)
        Client.objects.update(
            account_type=Case(
                When(registered_on__lte=a_year_ago, then=Value(Client.PLATINUM)),
                When(registered_on__lte=a_month_ago, then=Value(Client.GOLD)),
                default=Value(Client.REGULAR),
            ),
        )
        self.assertQuerySetEqual(
            Client.objects.order_by("pk"),
            [("Jane Doe", "G"), ("James Smith", "R"), ("Jack Black", "P")],
            transform=attrgetter("name", "account_type"),
        )

    def test_conditional_aggregation_example(self):
        """

        Tests the conditional aggregation functionality for client accounts.

        Verifies that the aggregation of client objects by account type (regular, gold, platinum) 
        produces the expected results. The test creates sample client objects with different 
        account types and checks the aggregated counts using both the Count aggregation 
        with a filter and the Sum aggregation with a Case statement.

        The test outcome ensures that the conditional aggregation accurately reflects the 
        number of clients assigned to each account type.

        """
        Client.objects.create(
            name="Jean Grey",
            account_type=Client.REGULAR,
            registered_on=date.today(),
        )
        Client.objects.create(
            name="James Bond",
            account_type=Client.PLATINUM,
            registered_on=date.today(),
        )
        Client.objects.create(
            name="Jane Porter",
            account_type=Client.PLATINUM,
            registered_on=date.today(),
        )
        self.assertEqual(
            Client.objects.aggregate(
                regular=Count("pk", filter=Q(account_type=Client.REGULAR)),
                gold=Count("pk", filter=Q(account_type=Client.GOLD)),
                platinum=Count("pk", filter=Q(account_type=Client.PLATINUM)),
            ),
            {"regular": 2, "gold": 1, "platinum": 3},
        )
        # This was the example before the filter argument was added.
        self.assertEqual(
            Client.objects.aggregate(
                regular=Sum(
                    Case(
                        When(account_type=Client.REGULAR, then=1),
                    )
                ),
                gold=Sum(
                    Case(
                        When(account_type=Client.GOLD, then=1),
                    )
                ),
                platinum=Sum(
                    Case(
                        When(account_type=Client.PLATINUM, then=1),
                    )
                ),
            ),
            {"regular": 2, "gold": 1, "platinum": 3},
        )

    def test_filter_example(self):
        """

        Filter clients based on their registered date and account type.

        Tests the database query to retrieve clients who meet specific registration date criteria,
        depending on their account type. Clients with a 'GOLD' account type are considered if they registered
        within the last month, while clients with a 'PLATINUM' account type are considered if they registered
        within the last year. The query result is then compared to the expected output.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the query result does not match the expected output.

        """
        a_month_ago = date.today() - timedelta(days=30)
        a_year_ago = date.today() - timedelta(days=365)
        self.assertQuerySetEqual(
            Client.objects.filter(
                registered_on__lte=Case(
                    When(account_type=Client.GOLD, then=a_month_ago),
                    When(account_type=Client.PLATINUM, then=a_year_ago),
                ),
            ),
            [("Jack Black", "P")],
            transform=attrgetter("name", "account_type"),
        )

    def test_hash(self):
        expression_1 = Case(
            When(account_type__in=[Client.REGULAR, Client.GOLD], then=1),
            default=2,
            output_field=IntegerField(),
        )
        expression_2 = Case(
            When(account_type__in=(Client.REGULAR, Client.GOLD), then=1),
            default=2,
            output_field=IntegerField(),
        )
        expression_3 = Case(
            When(account_type__in=[Client.REGULAR, Client.GOLD], then=1), default=2
        )
        expression_4 = Case(
            When(account_type__in=[Client.PLATINUM, Client.GOLD], then=2), default=1
        )
        self.assertEqual(hash(expression_1), hash(expression_2))
        self.assertNotEqual(hash(expression_2), hash(expression_3))
        self.assertNotEqual(hash(expression_1), hash(expression_4))
        self.assertNotEqual(hash(expression_3), hash(expression_4))


class CaseWhenTests(SimpleTestCase):
    def test_only_when_arguments(self):
        msg = "Positional arguments must all be When objects."
        with self.assertRaisesMessage(TypeError, msg):
            Case(When(Q(pk__in=[])), object())

    def test_invalid_when_constructor_args(self):
        """
        Tests that the When class constructor raises a TypeError when an invalid condition is provided.

        The When class must be initialized with a valid condition, which can be a Q object, a boolean expression, or lookups.
        This test ensures that providing an invalid condition, such as an arbitrary object, a Value object, or no condition at all,
        results in a TypeError with a descriptive error message indicating the supported condition types.
        """
        msg = (
            "When() supports a Q object, a boolean expression, or lookups as "
            "a condition."
        )
        with self.assertRaisesMessage(TypeError, msg):
            When(condition=object())
        with self.assertRaisesMessage(TypeError, msg):
            When(condition=Value(1))
        with self.assertRaisesMessage(TypeError, msg):
            When(Value(1), string="1")
        with self.assertRaisesMessage(TypeError, msg):
            When()

    def test_empty_q_object(self):
        """
        Tests that an empty Q object cannot be used as a condition in a When clause.

        This test ensures that attempting to use an empty Q object as a condition raises a ValueError with a meaningful error message, preventing incorrect usage of the When function.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError: If an empty Q object is used as a condition in the When clause.

        Note:
            This test is designed to validate the correct behavior of the When function when given invalid input, ensuring that it rejects empty Q objects and provides a clear error message instead.
        """
        msg = "An empty Q() can't be used as a When() condition."
        with self.assertRaisesMessage(ValueError, msg):
            When(Q(), then=Value(True))
