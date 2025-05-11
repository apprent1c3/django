from django.core.exceptions import FieldDoesNotExist, FieldError
from django.test import SimpleTestCase, TestCase

from .models import (
    BigChild,
    Child,
    ChildProxy,
    Primary,
    PrimaryOneToOne,
    RefreshPrimaryProxy,
    Secondary,
    ShadowChild,
)


class AssertionMixin:
    def assert_delayed(self, obj, num):
        """
        Instances with deferred fields look the same as normal instances when
        we examine attribute values. Therefore, this method returns the number
        of deferred fields on returned instances.
        """
        count = len(obj.get_deferred_fields())
        self.assertEqual(count, num)


class DeferTests(AssertionMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.s1 = Secondary.objects.create(first="x1", second="y1")
        cls.p1 = Primary.objects.create(name="p1", value="xx", related=cls.s1)

    def test_defer(self):
        """
        Tests the deferred loading of model fields, verifying that the correct number of database queries are delayed.
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name")[0], 1)
        self.assert_delayed(qs.defer("name").get(pk=self.p1.pk), 1)
        self.assert_delayed(qs.defer("related__first")[0], 0)
        self.assert_delayed(qs.defer("name").defer("value")[0], 2)

    def test_only(self):
        """
        Tests the behavior of the :meth:`assert_delayed` method with :meth:`QuerySet.only` for various query scenarios, ensuring expected delays are enforced when accessing related objects and specific fields.
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.only("name")[0], 2)
        self.assert_delayed(qs.only("name").get(pk=self.p1.pk), 2)
        self.assert_delayed(qs.only("name").only("value")[0], 2)
        self.assert_delayed(qs.only("related__first")[0], 2)
        # Using 'pk' with only() should result in 3 deferred fields, namely all
        # of them except the model's primary key see #15494
        self.assert_delayed(qs.only("pk")[0], 3)
        # You can use 'pk' with reverse foreign key lookups.
        # The related_id is always set even if it's not fetched from the DB,
        # so pk and related_id are not deferred.
        self.assert_delayed(self.s1.primary_set.only("pk")[0], 2)

    def test_defer_only_chaining(self):
        """
        Verifies the correct behavior of combining only and defer methods in querysets, testing that the resulting query fetches the expected number of fields lazily.
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.only("name", "value").defer("name")[0], 2)
        self.assert_delayed(qs.defer("name").only("value", "name")[0], 2)
        self.assert_delayed(qs.defer("name").only("name").only("value")[0], 2)
        self.assert_delayed(qs.defer("name").only("value")[0], 2)
        self.assert_delayed(qs.only("name").defer("value")[0], 2)
        self.assert_delayed(qs.only("name").defer("name").defer("value")[0], 1)
        self.assert_delayed(qs.only("name").defer("name", "value")[0], 1)

    def test_defer_only_clear(self):
        qs = Primary.objects.all()
        self.assert_delayed(qs.only("name").defer("name")[0], 0)
        self.assert_delayed(qs.defer("name").only("name")[0], 0)

    def test_defer_on_an_already_deferred_field(self):
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name")[0], 1)
        self.assert_delayed(qs.defer("name").defer("name")[0], 1)

    def test_defer_none_to_clear_deferred_set(self):
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name", "value")[0], 2)
        self.assert_delayed(qs.defer(None)[0], 0)
        self.assert_delayed(qs.only("name").defer(None)[0], 0)

    def test_only_none_raises_error(self):
        msg = "Cannot pass None as an argument to only()."
        with self.assertRaisesMessage(TypeError, msg):
            Primary.objects.only(None)

    def test_defer_extra(self):
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name").extra(select={"a": 1})[0], 1)
        self.assert_delayed(qs.extra(select={"a": 1}).defer("name")[0], 1)

    def test_defer_values_does_not_defer(self):
        # User values() won't defer anything (you get the full list of
        # dictionaries back), but it still works.
        self.assertEqual(
            Primary.objects.defer("name").values()[0],
            {
                "id": self.p1.id,
                "name": "p1",
                "value": "xx",
                "related_id": self.s1.id,
            },
        )

    def test_only_values_does_not_defer(self):
        self.assertEqual(
            Primary.objects.only("name").values()[0],
            {
                "id": self.p1.id,
                "name": "p1",
                "value": "xx",
                "related_id": self.s1.id,
            },
        )

    def test_get(self):
        # Using defer() and only() with get() is also valid.
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name").get(pk=self.p1.pk), 1)
        self.assert_delayed(qs.only("name").get(pk=self.p1.pk), 2)

    def test_defer_with_select_related(self):
        obj = Primary.objects.select_related().defer(
            "related__first", "related__second"
        )[0]
        self.assert_delayed(obj.related, 2)
        self.assert_delayed(obj, 0)

    def test_only_with_select_related(self):
        """
        Verifies the correct initialization of an object with select_related and only methods, 
        checking for proper loading of related objects and attributes.
        """
        obj = Primary.objects.select_related().only("related__first")[0]
        self.assert_delayed(obj, 2)
        self.assert_delayed(obj.related, 1)
        self.assertEqual(obj.related_id, self.s1.pk)
        self.assertEqual(obj.name, "p1")

    def test_defer_foreign_keys_are_deferred_and_not_traversed(self):
        # select_related() overrides defer().
        with self.assertNumQueries(1):
            obj = Primary.objects.defer("related").select_related()[0]
            self.assert_delayed(obj, 1)
            self.assertEqual(obj.related.id, self.s1.pk)

    def test_saving_object_with_deferred_field(self):
        # Saving models with deferred fields is possible (but inefficient,
        # since every field has to be retrieved first).
        """
        Tests that an object with a deferred field can be saved after modification, 
        without affecting the deferred field, and that the changes are correctly persisted.
        """
        Primary.objects.create(name="p2", value="xy", related=self.s1)
        obj = Primary.objects.defer("value").get(name="p2")
        obj.name = "a new name"
        obj.save()
        self.assertQuerySetEqual(
            Primary.objects.all(),
            [
                "p1",
                "a new name",
            ],
            lambda p: p.name,
            ordered=False,
        )

    def test_defer_baseclass_when_subclass_has_no_added_fields(self):
        # Regression for #10572 - A subclass with no extra fields can defer
        # fields from the base class
        """

        Tests that deferring fields in a base class does not break when a subclass has no additional fields.

        Verifies that a deferred field can still be loaded correctly from the database when accessed on an instance of the subclass.

        """
        Child.objects.create(name="c1", value="foo", related=self.s1)
        # You can defer a field on a baseclass when the subclass has no fields
        obj = Child.objects.defer("value").get(name="c1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "c1")
        self.assertEqual(obj.value, "foo")

    def test_only_baseclass_when_subclass_has_no_added_fields(self):
        # You can retrieve a single column on a base class with no fields
        """
        Tests that only the base class fields are loaded when a subclass has no additional fields, 
        verifying delayed loading and field values for the child object.
        """
        Child.objects.create(name="c1", value="foo", related=self.s1)
        obj = Child.objects.only("name").get(name="c1")
        # on an inherited model, its PK is also fetched, hence '3' deferred fields.
        self.assert_delayed(obj, 3)
        self.assertEqual(obj.name, "c1")
        self.assertEqual(obj.value, "foo")

    def test_defer_of_overridden_scalar(self):
        ShadowChild.objects.create()
        obj = ShadowChild.objects.defer("name").get()
        self.assertEqual(obj.name, "adonis")

    def test_defer_fk_attname(self):
        primary = Primary.objects.defer("related_id").get()
        with self.assertNumQueries(1):
            self.assertEqual(primary.related_id, self.p1.related_id)


class BigChildDeferTests(AssertionMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.s1 = Secondary.objects.create(first="x1", second="y1")
        BigChild.objects.create(name="b1", value="foo", related=cls.s1, other="bar")

    def test_defer_baseclass_when_subclass_has_added_field(self):
        # You can defer a field on a baseclass
        """
        Tests that a model's base class fields are deferred when a subclass has additional fields, ensuring only the requested fields are loaded from the database.
        """
        obj = BigChild.objects.defer("value").get(name="b1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_defer_subclass(self):
        # You can defer a field on a subclass
        """
        Tests deferring of fields in a subclassed model, verifying that the deferred fields are properly loaded and accessible.
        """
        obj = BigChild.objects.defer("other").get(name="b1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_defer_subclass_both(self):
        # Deferring fields from both superclass and subclass works.
        obj = BigChild.objects.defer("other", "value").get(name="b1")
        self.assert_delayed(obj, 2)

    def test_only_baseclass_when_subclass_has_added_field(self):
        # You can retrieve a single field on a baseclass
        """
        Tests the behavior of only loading base class fields when retrieving a subclass instance that has added fields, verifying that the delayed loading of added fields works as expected.
        """
        obj = BigChild.objects.only("name").get(name="b1")
        # when inherited model, its PK is also fetched, hence '4' deferred fields.
        self.assert_delayed(obj, 4)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_only_subclass(self):
        # You can retrieve a single field on a subclass
        """
        Tests that only a subclass instance is retrieved with specified field values, 
        verifying lazy loading and field values match the expected results.
        """
        obj = BigChild.objects.only("other").get(name="b1")
        self.assert_delayed(obj, 4)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")


class TestDefer2(AssertionMixin, TestCase):
    def test_defer_proxy(self):
        """
        Tests the behavior of select_related and only methods on a proxy model, ensuring that related objects are properly fetched and attributes are accessible as expected.
        """
        related = Secondary.objects.create(first="x1", second="x2")
        ChildProxy.objects.create(name="p1", value="xx", related=related)
        children = ChildProxy.objects.select_related().only("id", "name")
        self.assertEqual(len(children), 1)
        child = children[0]
        self.assert_delayed(child, 2)
        self.assertEqual(child.name, "p1")
        self.assertEqual(child.value, "xx")

    def test_defer_inheritance_pk_chaining(self):
        """
        Tests that the primary key of a parent model is correctly chained and reused when 
        an inherited model is fetched from the database, to avoid unnecessary database queries.
        """
        s1 = Secondary.objects.create(first="x1", second="y1")
        bc = BigChild.objects.create(name="b1", value="foo", related=s1, other="bar")
        bc_deferred = BigChild.objects.only("name").get(pk=bc.pk)
        with self.assertNumQueries(0):
            bc_deferred.id
        self.assertEqual(bc_deferred.pk, bc_deferred.id)

    def test_eq(self):
        s1 = Secondary.objects.create(first="x1", second="y1")
        s1_defer = Secondary.objects.only("pk").get(pk=s1.pk)
        self.assertEqual(s1, s1_defer)
        self.assertEqual(s1_defer, s1)

    def test_refresh_not_loading_deferred_fields(self):
        """
        Tests that deferred fields on a model instance are loaded when accessed after a refresh from the database, without loading all fields at once, while respecting the minimum number of database queries necessary for such an operation.
        """
        s = Secondary.objects.create()
        rf = Primary.objects.create(name="foo", value="bar", related=s)
        rf2 = Primary.objects.only("related", "value").get()
        rf.name = "new foo"
        rf.value = "new bar"
        rf.save()
        with self.assertNumQueries(1):
            rf2.refresh_from_db()
            self.assertEqual(rf2.value, "new bar")
        with self.assertNumQueries(1):
            self.assertEqual(rf2.name, "new foo")

    def test_custom_refresh_on_deferred_loading(self):
        """
        Tests that custom refresh functionality works correctly when primary proxy objects are loaded deferredly, 
        ensuring that the related primary objects are updated automatically when the secondary objects are changed.
        """
        s = Secondary.objects.create()
        rf = RefreshPrimaryProxy.objects.create(name="foo", value="bar", related=s)
        rf2 = RefreshPrimaryProxy.objects.only("related").get()
        rf.name = "new foo"
        rf.value = "new bar"
        rf.save()
        with self.assertNumQueries(1):
            # Customized refresh_from_db() reloads all deferred fields on
            # access of any of them.
            self.assertEqual(rf2.name, "new foo")
            self.assertEqual(rf2.value, "new bar")


class InvalidDeferTests(SimpleTestCase):
    def test_invalid_defer(self):
        """
        Tests the behavior of the defer method when given an invalid field name.

        Verifies that the correct exceptions (FieldDoesNotExist and FieldError) are raised
        when attempting to defer a non-existent field, including cases where the field
        name is provided as a string with a related object or nested field notation.
        """
        msg = "Primary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.defer("missing"))
        with self.assertRaisesMessage(FieldError, "missing"):
            list(Primary.objects.defer("value__missing"))
        msg = "Secondary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.defer("related__missing"))

    def test_invalid_only(self):
        """
        Tests that attempting to use the \"only\" method on a model instance with a field that does not exist raises the correct exceptions.
        """
        msg = "Primary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.only("missing"))
        with self.assertRaisesMessage(FieldError, "missing"):
            list(Primary.objects.only("value__missing"))
        msg = "Secondary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.only("related__missing"))

    def test_defer_select_related_raises_invalid_query(self):
        msg = (
            "Field Primary.related cannot be both deferred and traversed using "
            "select_related at the same time."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Primary.objects.defer("related").select_related("related")[0]

    def test_only_select_related_raises_invalid_query(self):
        msg = (
            "Field Primary.related cannot be both deferred and traversed using "
            "select_related at the same time."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Primary.objects.only("name").select_related("related")[0]


class DeferredRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.secondary = Secondary.objects.create(first="a", second="b")
        cls.primary = PrimaryOneToOne.objects.create(
            name="Bella", value="Baxter", related=cls.secondary
        )

    def test_defer_not_clear_cached_relations(self):
        """
        Tests that deferring a field does not clear cached relations.\"\"\"
        ```
        """
        obj = Secondary.objects.defer("first").get(pk=self.secondary.pk)
        with self.assertNumQueries(1):
            obj.primary_o2o
        obj.first  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.primary_o2o

    def test_only_not_clear_cached_relations(self):
        """
        Tests that Django's `only` method correctly loads and caches relation attributes, 
        demonstrating that a subsequent access to the same relation does not result in an additional database query.
        """
        obj = Secondary.objects.only("first").get(pk=self.secondary.pk)
        with self.assertNumQueries(1):
            obj.primary_o2o
        obj.second  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.primary_o2o
