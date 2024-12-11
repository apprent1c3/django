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

        Sets up test data for the class.

        This class method creates test instances of model A and associated models B and D.
        It initializes two instances of model A, and then creates 20 instances of models B and D,
        each associated with the first instance of model A.

        This method is used to populate the database with test data before running tests,
        providing a consistent and predictable environment for testing.

        """
        cls.a1 = A.objects.create()
        cls.a2 = A.objects.create()
        for x in range(20):
            B.objects.create(a=cls.a1)
            D.objects.create(a=cls.a1)

    def test_nonempty_update(self):
        """
        Update changes the right number of rows for a nonempty queryset
        """
        num_updated = self.a1.b_set.update(y=100)
        self.assertEqual(num_updated, 20)
        cnt = B.objects.filter(y=100).count()
        self.assertEqual(cnt, 20)

    def test_empty_update(self):
        """
        Update changes the right number of rows for an empty queryset
        """
        num_updated = self.a2.b_set.update(y=100)
        self.assertEqual(num_updated, 0)
        cnt = B.objects.filter(y=100).count()
        self.assertEqual(cnt, 0)

    def test_nonempty_update_with_inheritance(self):
        """
        Update changes the right number of rows for an empty queryset
        when the update affects only a base table
        """
        num_updated = self.a1.d_set.update(y=100)
        self.assertEqual(num_updated, 20)
        cnt = D.objects.filter(y=100).count()
        self.assertEqual(cnt, 20)

    def test_empty_update_with_inheritance(self):
        """
        Update changes the right number of rows for an empty queryset
        when the update affects only a base table
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
        Objects are updated by first filtering the candidates into a queryset
        and then calling the update() method. It executes immediately and
        returns nothing.
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
        Foreign key fields can also be updated, although you can only update
        the object referred to, not anything inside the related object.
        """
        resp = RelatedPoint.objects.filter(name="r1").update(data=self.d0)
        self.assertEqual(resp, 1)
        resp = RelatedPoint.objects.filter(data__name="d0")
        self.assertEqual(list(resp), [self.r1])

    def test_update_multiple_fields(self):
        """
        Multiple fields can be updated at once
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
        We do not support update on already sliced query sets.
        """
        method = DataPoint.objects.all()[:2].update
        msg = "Cannot update a query once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            method(another_value="another thing")

    def test_update_respects_to_field(self):
        """
        Update of an FK field which specifies a to_field works.
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

        Tests the ability to update a model field using a transformed value.

        This test creates two instances of model A with different values for field x.
        It then registers a custom lookup for the IntegerField to apply the absolute value transformation.
        The test updates the field x to be the absolute value of its current value and verifies that the updated values are correct.

        """
        A.objects.create(x=5)
        A.objects.create(x=-6)
        with register_lookup(IntegerField, Abs):
            A.objects.update(x=F("x__abs"))
            self.assertCountEqual(A.objects.values_list("x", flat=True), [5, 6])

    def test_update_annotated_queryset(self):
        """
        Update of a queryset that's been annotated.
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
        Update of a queryset that's been annotated and involves multiple tables.
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
        Tests that updating a model instance with a joined field annotation fails as expected.

        This test case verifies that attempting to update a field of a model instance using
        an annotation that references a joined field results in a FieldError. It checks
        various annotation types, including F expressions and database function calls,
        to ensure that the error is consistently raised.

        The test covers annotations created using the following methods:
          - F expressions referencing joined fields
          - F expressions with lookahead database functions (e.g., Lower)
          - Database functions (e.g., Lower, Concat) referencing joined fields

        The expected error message indicates that joined field references are not permitted
        in the query, providing a clear indication of the issue to developers using the
        model's update method with joined field annotations.
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
        """

        Tests that updating model instances ordered by a many-to-many annotation in descending order works correctly.

        This test case verifies that when updating model instances based on an ordering applied to a many-to-many relationship annotation, the update operation is applied in the correct order. The ordering is based on the absolute value of the 'm2m_foo' relationship in descending order.

        The test creates a Foo instance and associates it with a Bar instance, then updates the Bar instance based on this ordering. It asserts that the update operation has correctly modified the instance.

        """
        foo = Foo.objects.create(target="test")
        Bar.objects.create(foo=foo)

        Bar.objects.annotate(abs_id=Abs("m2m_foo")).order_by("-abs_id").update(x=4)
        self.assertEqual(Bar.objects.get().x, 4)

    def test_update_negated_f(self):
        """

        Tests the functionality of updating DataPoint objects with negated 'is_active' status.

        This test case verifies that the 'is_active' field of DataPoint objects can be successfully toggled.
        It checks the initial state, updates the 'is_active' status to its opposite, and then asserts the new state.
        The process is repeated to ensure that the toggle functionality works in both directions.

        """
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
        """

        Tests the update of a model instance with a negated conditional annotation.

        Verifies that a conditional annotation can be used to update a field based on a condition,
        and that the update correctly negates the condition. Specifically, this test checks that
        objects with a certain condition (name='d2') are updated to have the opposite value of
        their 'is_active' field, while other objects remain unchanged.

        The test covers the scenario where a Case-When expression is used to annotate objects,
        and then an update operation is performed using the annotated field. It ensures that
        the update operation correctly applies the negation of the annotated condition.

        """
        DataPoint.objects.annotate(
            is_d2=Case(When(name="d2", then=True), default=False)
        ).update(is_active=~F("is_d2"))
        self.assertCountEqual(
            DataPoint.objects.values_list("name", "is_active"),
            [("d0", True), ("d2", False), ("d3", True)],
        )

    def test_updating_non_conditional_field(self):
        """
        Tests that updating a non-conditional field with a negation operation raises a TypeError.

        This test case ensures that attempting to negate a non-conditional expression, such as a field name, when updating a model instance results in the expected error message.

        :raises TypeError: If a non-conditional expression is negated in an update operation.
        :note: This test is designed to validate the proper handling of invalid update operations.

        """
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
        """

        Sets up test data for the class.

        This method is used to create a fixed set of test data before running tests. 
        It creates two UniqueNumber objects with numbers 1 and 2, providing a baseline 
        for testing the behavior of the class in different scenarios.

        """
        UniqueNumber.objects.create(number=1)
        UniqueNumber.objects.create(number=2)

    def test_order_by_update_on_unique_constraint(self):
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
        """

        Tests the behavior of the order_by method when used in conjunction with an update operation on a model instance annotated with a unique constraint.

        Verifies that the order_by method correctly updates the records based on the annotated field and that the update operation completes successfully, updating the expected number of records.

        The test case checks if the order_by method updates the 'number' field of two model instances by incrementing their values by 1, when ordered by the annotated 'number_inverse' field in descending order.

        The purpose of this test is to ensure the correct interaction between the order_by and update methods in the presence of annotated unique constraints, which have a significant impact on the data integrity and ordering of the records.

        """
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
        """

        Tests that an update operation on a model with a unique constraint, 
        sorted by the constrained field, raises an IntegrityError when attempting 
        to assign a duplicate value to the constrained field.

        The test case checks that an update query ordered by the unique field 
        will correctly detect and prevent the insertion of duplicate values, 
        ensuring data integrity.

        Raises:
            IntegrityError: When attempting to update the model with a duplicate value.

        """
        UniqueNumberChild.objects.create(number=3)
        UniqueNumberChild.objects.create(number=4)
        with self.assertRaises(IntegrityError):
            UniqueNumberChild.objects.order_by("number").update(
                number=F("number") + 1,
            )

    def test_order_by_update_on_related_field(self):
        # Ordering by related fields is omitted because joined fields cannot be
        # used in the ORDER BY clause.
        data = DataPoint.objects.create(name="d0", value="apple")
        related = RelatedPoint.objects.create(name="r0", data=data)
        with self.assertNumQueries(1) as ctx:
            updated = RelatedPoint.objects.order_by("data__name").update(name="new")
        sql = ctx.captured_queries[0]["sql"]
        self.assertNotIn("ORDER BY", sql)
        self.assertEqual(updated, 1)
        related.refresh_from_db()
        self.assertEqual(related.name, "new")
