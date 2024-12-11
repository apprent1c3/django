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

        Tests the annotation of a queryset with a Case statement using When and default values.

        This test verifies that a queryset can be annotated with a 'selected' field based on a condition.
        The condition checks if the primary key is not in an empty list, and if true, annotates the object as 'selected', otherwise 'not selected'.
        The test asserts that the length of the annotated queryset matches the total count of objects and that all objects are annotated as 'selected'.

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

        Updates model instances based on conditional expressions.

        This function demonstrates how to use database functions to update a model's field
        with dynamic values calculated from the current field value. It applies a conditional
        update to the 'integer' field of the CaseTestModel instances, where the new value
        depends on the current 'integer' value. If the 'integer' value is 1, it increments by 1;
        if it's 2, it increments by 3; otherwise, the original value is preserved.

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

        Updates a set of model instances with an expression as a condition using a Case statement.

        The function verifies that the update is applied correctly by checking the resulting
        query set against an expected outcome. It ensures that the string field of each
        model instance is updated based on the value of its integer2 field, with specific
        values assigned when certain conditions are met.

        The conditions checked are:

        * When the integer2 field is equal to the integer field, the string field is set to 'equal'.
        * When the integer2 field is equal to the integer field plus one, the string field is set to '+1'.

        The function then validates that the updated model instances match the expected
        outcome, which includes a specific ordering and assignment of string values.

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

        Tests the update functionality of the big integer field using Django's Case expression.
        It updates the big integer field based on specific conditions applied to the integer field,
        then verifies that the resulting query set matches the expected values.

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

        Tests the update functionality of decimal fields using a conditional case statement.

        This test case updates the decimal field of a model instance based on the value of its integer field.
        It checks if the decimal field is updated correctly for specific integer values and verifies that the changes are saved to the database.

        The test case covers the following scenarios:
        - Updating the decimal field to a specific decimal value when the integer field equals 1.
        - Updating the decimal field to another specific decimal value when the integer field equals 2.
        - Leaving the decimal field unchanged when the integer field does not match any of the specified conditions.

        The test asserts that the updated values are correctly retrieved from the database and match the expected results.

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

        Tests the update functionality of CaseTestModel instances based on integer values.

        This test case checks if the email field in the database is correctly updated
        using a case statement. It verifies that the email is updated to '1@example.com'
        when the integer value is 1, '2@example.com' when the integer value is 2, and
        an empty string for all other integer values. The test asserts that the updated
        queryset matches the expected output after ordering by primary key.

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
        Tests the update of a file field in the CaseTestModel using conditional expressions.

        This test case verifies that the file field is updated correctly based on specific conditions. It checks if the update operation sets the file path to '~/1' when the integer field is 1, and to '~/2' when the integer field is 2, leaving other values unchanged.

        The test asserts that the resulting queryset, ordered by primary key, matches the expected output after the update operation. The test case ensures that the database reflects the correct changes after applying the conditional update expression. 
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
        """

         Tests updating the file path of CaseTestModel objects using a case statement.

         The function updates the file path based on the value of the integer field:
         - If integer is 1, the file path is set to '~/1'.
         - If integer is 2, the file path is set to '~/2'.
         - For all other values, the file path is set to an empty string.

         The updated query set is then compared to the expected results to ensure the update was successful.

        """
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

        Tests the update of image fields in CaseTestModel objects using a Case-When statement.

        This test updates the image fields of CaseTestModel objects based on the value of the integer field.
        The test then verifies that the image fields have been updated correctly by comparing the expected output with the actual result.

        The test case checks the following scenarios:
        - If the integer field is 1, the image field is updated to '~/1'.
        - If the integer field is 2, the image field is updated to '~/2'.
        - For all other integer field values, the image field is left unchanged.

        Note: This test requires the Pillow library to be installed.

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
        Updates a null boolean field in the database using a conditional case statement and then asserts that the updated values match the expected output.

        The function uses Django's ORM to update the null boolean field of all objects in the CaseTestModel based on the value of the integer field.
        The updated values are then compared to the expected output to verify that the update was successful.
        The expected output includes null boolean values for certain integer values, demonstrating the function's ability to handle null cases.
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
        """

        Tests the functionality of updating the time attribute in CaseTestModel objects based on the integer value.

        This test case verifies that the time attribute is correctly updated for objects with integer values of 1 and 2, and remains unchanged for objects with other integer values.

        The test checks the update operation by comparing the resulting query set with an expected list of tuples, where each tuple contains the integer and time values for a CaseTestModel object.

        """
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

         Tests the filter functionality for clients based on their registered date and account type.

         The test case verifies that clients are filtered correctly using a conditional date 
         threshold, where gold account holders are considered if they registered within the 
         last month, and platinum account holders are considered if they registered within 
         the last year.

         The test asserts that the filtered queryset matches the expected result, which is 
         a list of clients with their name and account type.

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
        """
        Tests that a Case instance can only be created with When objects as positional arguments.

        Raises a TypeError with a specific message if any positional argument is not a When object, ensuring correct usage of the Case class.

        This test helps maintain the integrity of the Case class by preventing it from being instantiated with invalid arguments, which could lead to unexpected behavior or errors down the line.
        """
        msg = "Positional arguments must all be When objects."
        with self.assertRaisesMessage(TypeError, msg):
            Case(When(Q(pk__in=[])), object())

    def test_invalid_when_constructor_args(self):
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
        msg = "An empty Q() can't be used as a When() condition."
        with self.assertRaisesMessage(ValueError, msg):
            When(Q(), then=Value(True))
