import unittest

from django.core.exceptions import FieldError
from django.db import IntegrityError, connection, transaction
from django.db.models import Case, CharField, Count, F, IntegerField, Max, When
from django.db.models.functions import Abs, Concat, Lower
from django.test import TestCase
from django.test.utils import register_lookup

from .models import (
    A,
    B,
    Bar,
    D,
    DataPoint,
    Foo,
    RelatedPoint,
    UniqueNumber,
    UniqueNumberChild,
)


class SimpleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating two instances of model A and associating them with multiple instances of models B and D.
        """
        cls.a1 = A.objects.create()
        cls.a2 = A.objects.create()
        for x in range(20):
            B.objects.create(a=cls.a1)
            D.objects.create(a=cls.a1)

    def test_nonempty_update(self):
        """

        Verifies that a non-empty queryset update modifies the correct number of rows.

        Tests that the update operation changes the specified field for all objects in the queryset and that the number of updated rows is accurately reported.

        """
        num_updated = self.a1.b_set.update(y=100)
        self.assertEqual(num_updated, 20)
        cnt = B.objects.filter(y=100).count()
        self.assertEqual(cnt, 20)

    def test_empty_update(self):
        """
        Verifies that updating an empty queryset results in no rows being modified, ensuring the correct count of updated rows is returned and no unintended database changes occur.
        """
        num_updated = self.a2.b_set.update(y=100)
        self.assertEqual(num_updated, 0)
        cnt = B.objects.filter(y=100).count()
        self.assertEqual(cnt, 0)

    def test_nonempty_update_with_inheritance(self):
        """
        Tests that the update method correctly updates a non-empty queryset when updating a field that affects only the base table, and verifies that the correct number of rows are updated.
        """
        num_updated = self.a1.d_set.update(y=100)
        self.assertEqual(num_updated, 20)
        cnt = D.objects.filter(y=100).count()
        self.assertEqual(cnt, 20)

    def test_empty_update_with_inheritance(self):
        """
        Tests that an update operation correctly handles an empty queryset, 
                        specifically when the update only affects the base table and no rows are modified.
        """
        num_updated = self.a2.d_set.update(y=100)
        self.assertEqual(num_updated, 0)
        cnt = D.objects.filter(y=100).count()
        self.assertEqual(cnt, 0)

    def test_foreign_key_update_with_id(self):
        """
        Update works using <field>_id for foreign keys
        """
        num_updated = self.a1.d_set.update(a_id=self.a2)
        self.assertEqual(num_updated, 20)
        self.assertEqual(self.a2.d_set.count(), 20)


class AdvancedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d0 = DataPoint.objects.create(name="d0", value="apple")
        cls.d2 = DataPoint.objects.create(name="d2", value="banana")
        cls.d3 = DataPoint.objects.create(name="d3", value="banana", is_active=False)
        cls.r1 = RelatedPoint.objects.create(name="r1", data=cls.d3)

    def test_update(self):
        """
        Tests the update functionality of DataPoint objects, verifying that filtered objects are correctly updated and returned quantities match expectations.
        """
        resp = DataPoint.objects.filter(value="apple").update(name="d1")
        self.assertEqual(resp, 1)
        resp = DataPoint.objects.filter(value="apple")
        self.assertEqual(list(resp), [self.d0])

    def test_update_multiple_objects(self):
        """
        We can update multiple objects at once.
        """
        resp = DataPoint.objects.filter(value="banana").update(value="pineapple")
        self.assertEqual(resp, 2)
        self.assertEqual(DataPoint.objects.get(name="d2").value, "pineapple")

    def test_update_fk(self):
        """
        Tests the ability to update foreign key fields in related objects, verifying that the update is successful and the correct object is referenced afterwards.
        """
        resp = RelatedPoint.objects.filter(name="r1").update(data=self.d0)
        self.assertEqual(resp, 1)
        resp = RelatedPoint.objects.filter(data__name="d0")
        self.assertEqual(list(resp), [self.r1])

    def test_update_multiple_fields(self):
        """
        Tests that updating multiple fields of a DataPoint object at once is successful, verifying the changes are correctly persisted in the database.
        """
        resp = DataPoint.objects.filter(value="apple").update(
            value="fruit", another_value="peach"
        )
        self.assertEqual(resp, 1)
        d = DataPoint.objects.get(name="d0")
        self.assertEqual(d.value, "fruit")
        self.assertEqual(d.another_value, "peach")

    def test_update_all(self):
        """
        In the rare case you want to update every instance of a model, update()
        is also a manager method.
        """
        self.assertEqual(DataPoint.objects.update(value="thing"), 3)
        resp = DataPoint.objects.values("value").distinct()
        self.assertEqual(list(resp), [{"value": "thing"}])

    def test_update_slice_fail(self):
        """
        Tests that updating a sliced query set raises a TypeError, as this operation is not supported.
        """
        method = DataPoint.objects.all()[:2].update
        msg = "Cannot update a query once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            method(another_value="another thing")

    def test_update_respects_to_field(self):
        """

        Tests that updating a foreign key field with a specified 'to_field' correctly updates the related field.

        """
        a_foo = Foo.objects.create(target="aaa")
        b_foo = Foo.objects.create(target="bbb")
        bar = Bar.objects.create(foo=a_foo)
        self.assertEqual(bar.foo_id, a_foo.target)
        bar_qs = Bar.objects.filter(pk=bar.pk)
        self.assertEqual(bar_qs[0].foo_id, a_foo.target)
        bar_qs.update(foo=b_foo)
        self.assertEqual(bar_qs[0].foo_id, b_foo.target)

    def test_update_m2m_field(self):
        msg = (
            "Cannot update model field "
            "<django.db.models.fields.related.ManyToManyField: m2m_foo> "
            "(only non-relations and foreign keys permitted)."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Bar.objects.update(m2m_foo="whatever")

    def test_update_transformed_field(self):
        """

        Tests the update functionality of a transformed field by applying the absolute value transformation to a set of integer values.

        """
        A.objects.create(x=5)
        A.objects.create(x=-6)
        with register_lookup(IntegerField, Abs):
            A.objects.update(x=F("x__abs"))
            self.assertCountEqual(A.objects.values_list("x", flat=True), [5, 6])

    def test_update_annotated_queryset(self):
        """

        Tests the update functionality of a queryset that has been annotated with additional values.
        Verifies the correct number of rows are updated in various scenarios, including 
        annotation with field values and the restriction against using aggregate functions.

        """
        # Trivial annotated update
        qs = DataPoint.objects.annotate(alias=F("value"))
        self.assertEqual(qs.update(another_value="foo"), 3)
        # Update where annotation is used for filtering
        qs = DataPoint.objects.annotate(alias=F("value")).filter(alias="apple")
        self.assertEqual(qs.update(another_value="foo"), 1)
        # Update where annotation is used in update parameters
        qs = DataPoint.objects.annotate(alias=F("value"))
        self.assertEqual(qs.update(another_value=F("alias")), 3)
        # Update where aggregation annotation is used in update parameters
        qs = DataPoint.objects.annotate(max=Max("value"))
        msg = (
            "Aggregate functions are not allowed in this query "
            "(another_value=Max(Col(update_datapoint, update.DataPoint.value)))."
        )
        with self.assertRaisesMessage(FieldError, msg):
            qs.update(another_value=F("max"))

    def test_update_annotated_multi_table_queryset(self):
        """

            Tests the functionality of updating a queryset that has been annotated and 
            involves multiple tables, verifying the correctness of update operations on 
            annotated fields across different scenarios.

        """
        # Trivial annotated update
        qs = DataPoint.objects.annotate(related_count=Count("relatedpoint"))
        self.assertEqual(qs.update(value="Foo"), 3)
        # Update where annotation is used for filtering
        qs = DataPoint.objects.annotate(related_count=Count("relatedpoint"))
        self.assertEqual(qs.filter(related_count=1).update(value="Foo"), 1)
        # Update where aggregation annotation is used in update parameters
        qs = RelatedPoint.objects.annotate(max=Max("data__value"))
        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            qs.update(name=F("max"))

    def test_update_with_joined_field_annotation(self):
        """
        Tests the restriction that joined field references cannot be used in update queries with annotations. Verifies that using such annotations results in a FieldError being raised.
        """
        msg = "Joined field references are not permitted in this query"
        with register_lookup(CharField, Lower):
            for annotation in (
                F("data__name"),
                F("data__name__lower"),
                Lower("data__name"),
                Concat("data__name", "data__value"),
            ):
                with self.subTest(annotation=annotation):
                    with self.assertRaisesMessage(FieldError, msg):
                        RelatedPoint.objects.annotate(
                            new_name=annotation,
                        ).update(name=F("new_name"))

    def test_update_ordered_by_m2m_aggregation_annotation(self):
        msg = (
            "Cannot update when ordering by an aggregate: "
            "Count(Col(update_bar_m2m_foo, update.Bar_m2m_foo.foo))"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Bar.objects.annotate(m2m_count=Count("m2m_foo")).order_by(
                "m2m_count"
            ).update(x=2)

    def test_update_ordered_by_inline_m2m_annotation(self):
        foo = Foo.objects.create(target="test")
        Bar.objects.create(foo=foo)

        Bar.objects.order_by(Abs("m2m_foo")).update(x=2)
        self.assertEqual(Bar.objects.get().x, 2)

    def test_update_ordered_by_m2m_annotation(self):
        foo = Foo.objects.create(target="test")
        Bar.objects.create(foo=foo)

        Bar.objects.annotate(abs_id=Abs("m2m_foo")).order_by("abs_id").update(x=3)
        self.assertEqual(Bar.objects.get().x, 3)

    def test_update_ordered_by_m2m_annotation_desc(self):
        foo = Foo.objects.create(target="test")
        Bar.objects.create(foo=foo)

        Bar.objects.annotate(abs_id=Abs("m2m_foo")).order_by("-abs_id").update(x=4)
        self.assertEqual(Bar.objects.get().x, 4)

    def test_update_negated_f(self):
        DataPoint.objects.update(is_active=~F("is_active"))
        self.assertCountEqual(
            DataPoint.objects.values_list("name", "is_active"),
            [("d0", False), ("d2", False), ("d3", True)],
        )
        DataPoint.objects.update(is_active=~F("is_active"))
        self.assertCountEqual(
            DataPoint.objects.values_list("name", "is_active"),
            [("d0", True), ("d2", True), ("d3", False)],
        )

    def test_update_negated_f_conditional_annotation(self):
        DataPoint.objects.annotate(
            is_d2=Case(When(name="d2", then=True), default=False)
        ).update(is_active=~F("is_d2"))
        self.assertCountEqual(
            DataPoint.objects.values_list("name", "is_active"),
            [("d0", True), ("d2", False), ("d3", True)],
        )

    def test_updating_non_conditional_field(self):
        msg = "Cannot negate non-conditional expressions."
        with self.assertRaisesMessage(TypeError, msg):
            DataPoint.objects.update(is_active=~F("name"))


@unittest.skipUnless(
    connection.vendor == "mysql",
    "UPDATE...ORDER BY syntax is supported on MySQL/MariaDB",
)
class MySQLUpdateOrderByTest(TestCase):
    """Update field with a unique constraint using an ordered queryset."""

    @classmethod
    def setUpTestData(cls):
        UniqueNumber.objects.create(number=1)
        UniqueNumber.objects.create(number=2)

    def test_order_by_update_on_unique_constraint(self):
        """

        Tests that updating a model with a unique constraint while ordering by that field works correctly.

        Verifies that updating multiple instances ordered by the unique constraint field results in the expected number of instances being updated.

        """
        tests = [
            ("-number", "id"),
            (F("number").desc(), "id"),
            (F("number") * -1, "id"),
        ]
        for ordering in tests:
            with self.subTest(ordering=ordering), transaction.atomic():
                updated = UniqueNumber.objects.order_by(*ordering).update(
                    number=F("number") + 1,
                )
                self.assertEqual(updated, 2)

    def test_order_by_update_on_unique_constraint_annotation(self):
        updated = (
            UniqueNumber.objects.annotate(number_inverse=F("number").desc())
            .order_by("number_inverse")
            .update(number=F("number") + 1)
        )
        self.assertEqual(updated, 2)

    def test_order_by_update_on_unique_constraint_annotation_desc(self):
        updated = (
            UniqueNumber.objects.annotate(number_annotation=F("number"))
            .order_by("-number_annotation")
            .update(number=F("number") + 1)
        )
        self.assertEqual(updated, 2)

    def test_order_by_update_on_parent_unique_constraint(self):
        # Ordering by inherited fields is omitted because joined fields cannot
        # be used in the ORDER BY clause.
        UniqueNumberChild.objects.create(number=3)
        UniqueNumberChild.objects.create(number=4)
        with self.assertRaises(IntegrityError):
            UniqueNumberChild.objects.order_by("number").update(
                number=F("number") + 1,
            )

    def test_order_by_update_on_related_field(self):
        # Ordering by related fields is omitted because joined fields cannot be
        # used in the ORDER BY clause.
        """
        Tests that updating a queryset ordered by a related field does not include the order in the SQL query, while still applying the update correctly.
        """
        data = DataPoint.objects.create(name="d0", value="apple")
        related = RelatedPoint.objects.create(name="r0", data=data)
        with self.assertNumQueries(1) as ctx:
            updated = RelatedPoint.objects.order_by("data__name").update(name="new")
        sql = ctx.captured_queries[0]["sql"]
        self.assertNotIn("ORDER BY", sql)
        self.assertEqual(updated, 1)
        related.refresh_from_db()
        self.assertEqual(related.name, "new")
