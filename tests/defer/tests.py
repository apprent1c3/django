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
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name")[0], 1)
        self.assert_delayed(qs.defer("name").get(pk=self.p1.pk), 1)
        self.assert_delayed(qs.defer("related__first")[0], 0)
        self.assert_delayed(qs.defer("name").defer("value")[0], 2)

    def test_only(self):
        """

        Tests the behavior of the :meth:`only` method on querysets.

        This function verifies that the :meth:`only` method correctly delays the loading of 
        fields until they are actually accessed. It checks various scenarios, including 
        loading only specific fields, loading related objects, and chaining multiple 
        :meth:`only` calls. The test covers both direct queryset operations and 
        reverse relations.

        The test cases cover a range of field types, including simple fields like 'name' 
        and 'value', as well as foreign keys and primary keys. It also checks that the 
        expected number of database queries are executed in each case.

        This test is useful for ensuring that the :meth:`only` method behaves correctly 
        and efficiently in different scenarios, which can help improve the performance 
        of database queries in the application.

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
        Tests the interaction between the `only()` and `defer()` methods in querysets, 
        verifying the correct application of deferred loading when chaining these methods 
        in different orders and combinations. 
        The test checks that the expected number of database queries is performed 
        when retrieving specific attributes of a `Primary` object from the database.
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
        """
        Tests that using defer() and only() methods together correctly clears the deferred fields.

        Verifies that deferring a field and then selecting only that field, as well as the inverse, both result in no fields being deferred. This ensures that the defer() and only() methods interact as expected, and that the resulting query has the correct fields loaded.
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.only("name").defer("name")[0], 0)
        self.assert_delayed(qs.defer("name").only("name")[0], 0)

    def test_defer_on_an_already_deferred_field(self):
        """
        Tests that deferring a field that has already been deferred does not result in additional database queries.

        Verifies that deferring the 'name' field on a queryset, and then deferring the 'name' field again, 
        only results in a single database query for the deferred field.
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name")[0], 1)
        self.assert_delayed(qs.defer("name").defer("name")[0], 1)

    def test_defer_none_to_clear_deferred_set(self):
        """
        Tests that deferring None clears the deferred field set in a QuerySet. 

        This checks three scenarios: 
        - deferring specific fields ('name', 'value') and verifying the deferred fields count,
        - deferring None which should clear any previously deferred fields, 
        - and combining only() and defer(None) to ensure the deferred field set is reset in this case as well.
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name", "value")[0], 2)
        self.assert_delayed(qs.defer(None)[0], 0)
        self.assert_delayed(qs.only("name").defer(None)[0], 0)

    def test_only_none_raises_error(self):
        """
        Tests that passing None as an argument to the only method raises a TypeError.

        The only method is expected to accept one or more field names, but passing None
        is not a valid input. This test case verifies that attempting to do so results
        in a TypeError with a descriptive error message. 
        """
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
        """

        Tests the behavior of the get method with deferred and only fields.

        This test ensures that the get method correctly handles deferred and only fields,
        verifying the number of database queries made in each case.

        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name").get(pk=self.p1.pk), 1)
        self.assert_delayed(qs.only("name").get(pk=self.p1.pk), 2)

    def test_defer_with_select_related(self):
        """

        Tests the use of defer with select_related to delay loading of certain fields.

        This test case verifies that when using select_related to load related objects,
        defer can be used to exclude specific fields from the initial load, and instead
        load them on demand. The test checks that the related object and its deferred
        fields are loaded only when accessed, and that the main object's fields are
        loaded immediately.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the deferred loading of fields does not behave as expected.

        """
        obj = Primary.objects.select_related().defer(
            "related__first", "related__second"
        )[0]
        self.assert_delayed(obj.related, 2)
        self.assert_delayed(obj, 0)

    def test_only_with_select_related(self):
        obj = Primary.objects.select_related().only("related__first")[0]
        self.assert_delayed(obj, 2)
        self.assert_delayed(obj.related, 1)
        self.assertEqual(obj.related_id, self.s1.pk)
        self.assertEqual(obj.name, "p1")

    def test_defer_foreign_keys_are_deferred_and_not_traversed(self):
        # select_related() overrides defer().
        """
        Test that deferring foreign keys results in deferred loading and no unnecessary traversal.

        This test case verifies that when a foreign key field is deferred, the related object 
        is not loaded immediately, reducing the number of database queries. It also checks 
        that the deferred field can still be accessed and its value is correct when loaded.

        The test confirms that deferring foreign keys and using select_related() together 
        does not cause the deferred field to be traversed, thus optimizing database queries.
        """
        with self.assertNumQueries(1):
            obj = Primary.objects.defer("related").select_related()[0]
            self.assert_delayed(obj, 1)
            self.assertEqual(obj.related.id, self.s1.pk)

    def test_saving_object_with_deferred_field(self):
        # Saving models with deferred fields is possible (but inefficient,
        # since every field has to be retrieved first).
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

        Tests that when a subclass has no additional fields, the base class fields are deferred correctly.
        Verifies that deferred fields are loaded upon access and that non-deferred fields are available immediately.

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
        Tests that only base class fields are loaded when a subclass has no additional fields.

        This test verifies the behavior of the :meth:`only` method when applied to a subclass.
        It ensures that only the specified base class fields are loaded, and that the delayed
        loading of other fields works as expected.

        The test creates a :class:`Child` object, loads it with only the 'name' field, and then
        verifies that the 'name' field is accessible, while other fields are loaded on demand.
        """
        Child.objects.create(name="c1", value="foo", related=self.s1)
        obj = Child.objects.only("name").get(name="c1")
        # on an inherited model, its PK is also fetched, hence '3' deferred fields.
        self.assert_delayed(obj, 3)
        self.assertEqual(obj.name, "c1")
        self.assertEqual(obj.value, "foo")

    def test_defer_of_overridden_scalar(self):
        """

        Tests the defer functionality on a scalar field that has been overridden in a model.

        Verifies that deferring the loading of a field does not affect its ability to be overridden
        with a custom value. In this case, it checks that the 'name' field of a ShadowChild object
        is correctly overridden despite being deferred during retrieval from the database.

        """
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
        obj = BigChild.objects.defer("value").get(name="b1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_defer_subclass(self):
        # You can defer a field on a subclass
        """

        Tests that deferring a field in a subclassed model works as expected.

        Verifies that the deferred field is loaded only once and that its value is correct.
        Also checks that the non-deferred fields are loaded immediately and have the expected values.

        """
        obj = BigChild.objects.defer("other").get(name="b1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_defer_subclass_both(self):
        # Deferring fields from both superclass and subclass works.
        """
        Tests the deferring of fields on a subclass instance when both parent and child fields are deferred.

        This test case verifies that when deferring fields on a subclass instance,
        the deferred fields are loaded correctly and the correct number of database
        query delays are triggered.

        The test focuses on a scenario where both the parent and child classes have
        fields that are deferred, ensuring that the deferring mechanism works as
        expected in a hierarchical model setup.

        The expected outcome is that the object's deferred fields are not loaded
        immediately, resulting in the specified number of database query delays.
        """
        obj = BigChild.objects.defer("other", "value").get(name="b1")
        self.assert_delayed(obj, 2)

    def test_only_baseclass_when_subclass_has_added_field(self):
        # You can retrieve a single field on a baseclass
        obj = BigChild.objects.only("name").get(name="b1")
        # when inherited model, its PK is also fetched, hence '4' deferred fields.
        self.assert_delayed(obj, 4)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_only_subclass(self):
        # You can retrieve a single field on a subclass
        obj = BigChild.objects.only("other").get(name="b1")
        self.assert_delayed(obj, 4)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")


class TestDefer2(AssertionMixin, TestCase):
    def test_defer_proxy(self):
        """
        Ensure select_related together with only on a proxy model behaves
        as expected. See #17876.
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
        When an inherited model is fetched from the DB, its PK is also fetched.
        When getting the PK of the parent model it is useful to use the already
        fetched parent model PK if it happens to be available.
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

        Tests that refresh_from_db only loads deferred fields when they are accessed,
        even after the model instance has been refreshed.

        This test case creates a Primary model instance with a related Secondary instance,
        then fetches the Primary instance again with deferred loading of some fields.
        It updates the original Primary instance and saves the changes.
        The test then refreshes the fetched Primary instance from the database and checks
        that the refreshed instance has the updated values, while also verifying that the
        deferred fields are loaded only when accessed, resulting in the expected number of
        database queries.

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
        Tests whether the primary data is refreshed correctly after updating a related object 
        when using deferred loading on a RefreshPrimaryProxy instance.

        This test case verifies that changes made to the primary data are reflected in a 
        RefreshPrimaryProxy instance that was loaded with only the related object, demonstrating
        that the refresh mechanism works as expected in this scenario.

        The test checks that the updated values are correctly retrieved in a single database query,
        ensuring the refresh process is efficient and effective.
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
        msg = "Primary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.defer("missing"))
        with self.assertRaisesMessage(FieldError, "missing"):
            list(Primary.objects.defer("value__missing"))
        msg = "Secondary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.defer("related__missing"))

    def test_invalid_only(self):
        msg = "Primary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.only("missing"))
        with self.assertRaisesMessage(FieldError, "missing"):
            list(Primary.objects.only("value__missing"))
        msg = "Secondary has no field named 'missing'"
        with self.assertRaisesMessage(FieldDoesNotExist, msg):
            list(Primary.objects.only("related__missing"))

    def test_defer_select_related_raises_invalid_query(self):
        """
        Tests that an Invalid Query error is raised when attempting to use select_related on a field that has been deferred.

        This test case verifies that the ORM correctly handles the contradiction between deferring a field and trying to fetch it using select_related, ensuring that an informative error message is provided to the user.

        The expected error message indicates that a field cannot be both deferred and traversed using select_related at the same time, helping to prevent ambiguous or conflicting query settings.
        """
        msg = (
            "Field Primary.related cannot be both deferred and traversed using "
            "select_related at the same time."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Primary.objects.defer("related").select_related("related")[0]

    def test_only_select_related_raises_invalid_query(self):
        """

        Test that using select_related and only together on a model instance with a related field raises a FieldError.

        Checks that an attempt to query a model while both deferring certain fields and using select_related on related fields results in an error, 
        as this is an invalid combination of query parameters.

        The expected error message indicates that a field cannot be both deferred and traversed using select_related simultaneously.

        """
        msg = (
            "Field Primary.related cannot be both deferred and traversed using "
            "select_related at the same time."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Primary.objects.only("name").select_related("related")[0]


class DeferredRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the class.

        This method creates and stores instance-level test data, setting up a primary and secondary object for use in subsequent tests.
        The secondary object and a primary object with a one-to-one relationship to the secondary object are created and stored as class attributes.

        """
        cls.secondary = Secondary.objects.create(first="a", second="b")
        cls.primary = PrimaryOneToOne.objects.create(
            name="Bella", value="Baxter", related=cls.secondary
        )

    def test_defer_not_clear_cached_relations(self):
        """
        Tests that deferred fields do not interfere with caching of related objects.

        This test ensures that when a related object is accessed after deferring a field,
        it is fetched from the cache instead of making a new database query. The test
        verifies that the related object is loaded with a single query, and subsequent
        accesses to the same related object do not trigger additional queries, even if
        the deferred field is accessed in between.
        """
        obj = Secondary.objects.defer("first").get(pk=self.secondary.pk)
        with self.assertNumQueries(1):
            obj.primary_o2o
        obj.first  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.primary_o2o

    def test_only_not_clear_cached_relations(self):
        obj = Secondary.objects.only("first").get(pk=self.secondary.pk)
        with self.assertNumQueries(1):
            obj.primary_o2o
        obj.second  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.primary_o2o
