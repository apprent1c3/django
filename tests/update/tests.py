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
        """
        Tests that updating a Many-To-Many field using the update method raises a FieldError.

        This test case checks that attempting to update a Many-To-Many field (m2m_foo) on model Bar using the update method will fail and raise a FieldError with a descriptive message, as only non-relations and foreign keys are permitted for bulk updates.

        The expected error message is 'Cannot update model field <django.db.models.fields.related.ManyToManyField: m2m_foo> (only non-relations and foreign keys permitted)'.
        """
        msg = (
            "Cannot update model field "
            "<django.db.models.fields.related.ManyToManyField: m2m_foo> "
            "(only non-relations and foreign keys permitted)."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Bar.objects.update(m2m_foo="whatever")

    def test_update_transformed_field(self):
        """

        Tests the update functionality of a model's field after applying a transformation lookup.

        This test case checks if a custom lookup (Absolute value) can be successfully applied 
        to a model field, and if the values in the field can be updated to their absolute values.

        It verifies that the update operation correctly transforms both positive and negative values.

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

        Tests the update functionality with field annotations that include joined fields.

        This test case verifies that the ORM raises a FieldError when attempting to update a model instance
        with an annotation that references a joined field. The test checks various annotation types,
        including F expressions and built-in database functions like Lower and Concat, to ensure that
        the error is consistently raised for all invalid annotation types.

        The test scenario involves a RelatedPoint model with a related 'data' field, which is used to
        create annotations that reference joined fields. The expected error message is \"Joined field
        references are not permitted in this query\", indicating that the ORM does not support updating
        a model instance with a joined field reference in the annotation.

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
        """

        Tests that updating a model instance raises an error when ordered by an aggregate annotation on a many-to-many field.

        This test ensures that attempting to update model instances that are ordered by an aggregate annotation, 
        such as a Count on a many-to-many field, results in a FieldError being raised.

        The error occurs because Django cannot guarantee the stability of the ordering when using aggregate annotations 
        in the ordering clause, and thus does not allow updates to be performed in this scenario.

        The expected error message is \"Cannot update when ordering by an aggregate: Count(Col(update_bar_m2m_foo, update.Bar_m2m_foo.foo))\".

        """
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

        Tests that updating model instances ordered by a many-to-many field annotation works as expected.

        Verifies that the update operation is applied to the correct instances when the queryset is ordered by
        a many-to-many field in descending order, using an annotation to compute the absolute value of the related
        object's id.

        The test case checks that the update is successful by asserting that the updated attribute matches the
        expected value.

        """
        foo = Foo.objects.create(target="test")
        Bar.objects.create(foo=foo)

        Bar.objects.annotate(abs_id=Abs("m2m_foo")).order_by("-abs_id").update(x=4)
        self.assertEqual(Bar.objects.get().x, 4)

    def test_update_negated_f(self):
        """
        Tests the update functionality of DataPoint objects with negated 'is_active' status.

        This test checks the correctness of toggling the 'is_active' field of DataPoint objects using the update method. It verifies that the 'is_active' status is correctly flipped for all DataPoint instances and that this change is persisted across multiple updates. The test cases cover scenarios where the 'is_active' status is initially True or False, ensuring that the update method behaves as expected in both cases.

        The test validates the outcome by comparing the expected and actual 'is_active' status of the DataPoint objects after each update operation, confirming that the update functionality works as intended.

        The test scenario involves the following steps:
            * Initial update: Toggles the 'is_active' status of all DataPoint objects.
            * Verification: Checks that the 'is_active' status of the DataPoint objects matches the expected values after the initial update.
            * Second update: Toggles the 'is_active' status again.
            * Final verification: Confirms that the 'is_active' status of the DataPoint objects matches the expected values after the second update.

        This test provides assurance that the update functionality with negated 'is_active' status works correctly and reliably for DataPoint objects.
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

        Tests the update functionality on a queryset with a negated F expression
        in the conditional annotation.

        This test case verifies that the is_active field of DataPoints is correctly
        updated based on the negation of a conditional annotation. The annotation
        checks if the name of a DataPoint is 'd2', and if so, sets is_d2 to True.
        The update operation then sets is_active to the negation of is_d2.

        The test asserts that the resulting DataPoints have the correct is_active
        status, with 'd2' being inactive and all other DataPoints being active.

        """
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
        """

        Tests if updating rows in the UniqueNumberChild model ordered by the 'number' field
        raises an IntegrityError when a unique constraint on the 'number' field is violated.
        The test creates multiple UniqueNumberChild objects with unique numbers and then
        attempts to update them in a way that would introduce duplicate numbers, verifying
        that the database correctly enforces the unique constraint.

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
