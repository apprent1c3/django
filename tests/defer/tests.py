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
        """
        Sets up test data for the class.

        This method creates required objects in the database to be used in tests.
        It initializes one Secondary object and one Primary object with their respective attributes.
        The Primary object is linked to the Secondary object through a relationship.

        Returns:
            None

        Note:
            This method is intended to be used as a class method for setting up test data.
            The created objects are stored as class attributes for use in tests.

        """
        cls.s1 = Secondary.objects.create(first="x1", second="y1")
        cls.p1 = Primary.objects.create(name="p1", value="xx", related=cls.s1)

    def test_defer(self):
        """

        Tests the defer functionality on a queryset.

        This function checks that defer works as expected by querying the Primary model
        and deferring the loading of specific fields. It tests deferring a single field,
        deferring multiple fields, and deferring fields on related models. The tests
        verify that the deferred fields are loaded on demand and that the correct number
        of database queries are executed.

        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name")[0], 1)
        self.assert_delayed(qs.defer("name").get(pk=self.p1.pk), 1)
        self.assert_delayed(qs.defer("related__first")[0], 0)
        self.assert_delayed(qs.defer("name").defer("value")[0], 2)

    def test_only(self):
        """

        Tests the behavior of the only method in Django querysets.

        This test checks if the only method correctly delays the loading of fields 
        that are not specified. It covers various scenarios, including retrieving 
        a specific field, using the only method multiple times, and accessing 
        related objects. The test verifies that the expected number of database 
        queries are made when accessing the fetched objects.

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

        Tests the interaction between 'only' and 'defer' query methods.

        Verifies that when 'only' and 'defer' are used together on a query, the
        'defer' method takes precedence, ensuring that the specified fields are
        not immediately loaded. The test case checks this behavior by asserting
        that the delayed loading count is zero, indicating that the field has
        been successfully deferred.

        The test covers two scenarios: calling 'only' followed by 'defer', and
        calling 'defer' followed by 'only', to ensure consistent behavior in
        both cases.

        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.only("name").defer("name")[0], 0)
        self.assert_delayed(qs.defer("name").only("name")[0], 0)

    def test_defer_on_an_already_deferred_field(self):
        """
        »:param self: Test instance
            Tests that deferring a field that is already deferred does not increase the delay count.

            The test queries the Primary model, defers the 'name' field, and asserts that the delay count remains constant even when deferring the 'name' field multiple times.

            :return: None```
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name")[0], 1)
        self.assert_delayed(qs.defer("name").defer("name")[0], 1)

    def test_defer_none_to_clear_deferred_set(self):
        """
        Tests the functionality of deferring fields to None, resulting in the clearing of the deferred set.

        Deferring fields is used to optimize database queries by only loading specific fields from the database. 
        When deferring fields to None, it clears the deferred set, meaning all fields are loaded from the database. 

        This test case checks the following scenarios:
        - Deferring specific fields ('name', 'value') and verifying the correct number of fields are delayed.
        - Deferring no fields (None) and verifying no fields are delayed.
        - Deferring no fields after specifying fields to only load ('name') and verifying no fields are delayed.
        """
        qs = Primary.objects.all()
        self.assert_delayed(qs.defer("name", "value")[0], 2)
        self.assert_delayed(qs.defer(None)[0], 0)
        self.assert_delayed(qs.only("name").defer(None)[0], 0)

    def test_only_none_raises_error(self):
        msg = "Cannot pass None as an argument to only()."
        with self.assertRaisesMessage(TypeError, msg):
            Primary.objects.only(None)

    def test_defer_extra(self):
        """

        Tests the deferred loading of extra selected fields in a QuerySet.

        Verifies that the defer and extra methods can be used in combination to 
        load fields lazily, improving performance by reducing the amount of data 
        retrieved from the database. Specifically, this test case checks that 
        fields are correctly deferred when using the extra method to select 
        additional fields, regardless of the order in which these methods are 
        applied.

        The test ensures that the DeferredAttribute is created with a delay of 1, 
        indicating that the deferred field will be loaded on the next access, 
        maintaining optimal database performance.

        """
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

        Tests the retrieval of objects from the database with deferred and only fields.

        This function checks the behavior of deferred and only fields when retrieving
        objects from the Primary model. It verifies that the num_queries is as expected
        when using defer and only to limit the fields retrieved from the database.

        The test covers two scenarios:
            - Retrieval with deferred fields, checking that only the specified fields are 
              loaded from the database initially.
            - Retrieval with only fields specified, checking that only the specified 
              fields are loaded from the database.

        """
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

        Tests the behavior of the :meth:`select_related` and :meth:`only` methods 
        on a model instance, specifically when retrieving related objects.

        Verifies that the retrieved object and its related object are properly 
        delayed, and that the expected attributes are populated correctly.

        """
        obj = Primary.objects.select_related().only("related__first")[0]
        self.assert_delayed(obj, 2)
        self.assert_delayed(obj.related, 1)
        self.assertEqual(obj.related_id, self.s1.pk)
        self.assertEqual(obj.name, "p1")

    def test_defer_foreign_keys_are_deferred_and_not_traversed(self):
        # select_related() overrides defer().
        """
        Test to verify that deferred foreign keys are not traversed when using select_related.

        Checks if deferring a specific field while using select_related results in the 
        deferred field being loaded on a subsequent query, rather than being traversed 
        immediately. Confirm that only one query is executed to retrieve the primary 
        object and its related object is loaded with the correct id, without immediate 
        traversal of the deferred foreign key.
        """
        with self.assertNumQueries(1):
            obj = Primary.objects.defer("related").select_related()[0]
            self.assert_delayed(obj, 1)
            self.assertEqual(obj.related.id, self.s1.pk)

    def test_saving_object_with_deferred_field(self):
        # Saving models with deferred fields is possible (but inefficient,
        # since every field has to be retrieved first).
        """

        Tests the saving of a model object that has a deferred field.

        This test case verifies that an object can be saved successfully even when one of its fields is deferred.
        It creates an object with a related field, retrieves it with the 'value' field deferred, modifies the object,
        and then saves it. The test then asserts that the saved object's changes are properly persisted in the database.

        The test covers the scenario where a model instance is fetched with a deferred field, modified, and then saved,
        ensuring that the deferred field does not interfere with the saving process.

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
        Child.objects.create(name="c1", value="foo", related=self.s1)
        # You can defer a field on a baseclass when the subclass has no fields
        obj = Child.objects.defer("value").get(name="c1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "c1")
        self.assertEqual(obj.value, "foo")

    def test_only_baseclass_when_subclass_has_no_added_fields(self):
        # You can retrieve a single column on a base class with no fields
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
        obj = BigChild.objects.defer("value").get(name="b1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_defer_subclass(self):
        # You can defer a field on a subclass
        obj = BigChild.objects.defer("other").get(name="b1")
        self.assert_delayed(obj, 1)
        self.assertEqual(obj.name, "b1")
        self.assertEqual(obj.value, "foo")
        self.assertEqual(obj.other, "bar")

    def test_defer_subclass_both(self):
        # Deferring fields from both superclass and subclass works.
        """
        Tests deferring fields in a subclass.

        This test case verifies that deferring fields from both a parent and child model 
        works as expected. It checks that the correct number of fields are deferred when 
        retrieving an object, ensuring that the deferred fields are not loaded until 
        accessed.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the number of deferred fields does not match the expected 
            value.

        """
        obj = BigChild.objects.defer("other", "value").get(name="b1")
        self.assert_delayed(obj, 2)

    def test_only_baseclass_when_subclass_has_added_field(self):
        # You can retrieve a single field on a baseclass
        """
        ..: Tests that using the 'only' method on a base class to retrieve an object does not break when the subclass has added fields. 

            The test case verifies that the object is properly loaded with the 'only' fields 
            and that the lazy-loaded fields are accessible, even though they were not 
            explicitly requested in the 'only' method call. The test checks that the 
            object's state is correct by asserting the values of its fields.
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
        Tests that the only() method correctly loads only the specified fields for a subclass.

        Verifies that the object's fields, including those inherited from its parent class, can be accessed after loading only a subset of fields.

        Checks that the delayed loading mechanism works as expected, allowing access to fields that were not initially loaded.
        """
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
        """
        Tests the equality of a Secondary object instance with a deferred 
        version of itself, ensuring that both directions of comparison (i.e., 
        instance == deferred instance and deferred instance == instance) yield 
        the correct result, validating the proper implementation of the 
        equality method for Secondary objects.
        """
        s1 = Secondary.objects.create(first="x1", second="y1")
        s1_defer = Secondary.objects.only("pk").get(pk=s1.pk)
        self.assertEqual(s1, s1_defer)
        self.assertEqual(s1_defer, s1)

    def test_refresh_not_loading_deferred_fields(self):
        """

        Test that refreshing a model instance from the database does not load deferred fields.

        This test ensures that when an instance is refreshed from the database, it only loads
        the fields that are necessary for the current query, without loading any deferred fields.
        It also verifies that the instance's attributes are updated correctly after refreshing.

        The test case covers the following scenarios:
        - Creating a related object and a primary object with a reference to the related object
        - Creating another primary object with only a subset of fields loaded
        - Updating the primary object's attributes and saving the changes
        - Refreshing the partially loaded primary object from the database and verifying its attributes

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
        Tests the custom refresh functionality on deferred loading of related objects.

        Verifies that when a related object's attributes are updated and saved, the 
        previously loaded related object is refreshed with the new values when 
        accessed through a lazy load, ensuring data consistency and accuracy.

        The test covers the scenario where an object is initially loaded with 
        deferred loading of its related object, and then the related object's 
        attributes are updated. It checks that the refresh mechanism correctly 
        updates the related object with the new values in a single database query.
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

        Tests that deferred loading fails when attempting to defer a non-existent field.

        This function checks that attempting to defer a field that does not exist on the
        model raises the expected errors. It tests this for both direct fields and fields
        that do not exist on a related object.

        The test covers the following scenarios:

        - Attempting to defer a non-existent field on the primary model.
        - Attempting to defer a non-existent field on a related model through a direct
          relationship.
        - Attempting to defer a non-existent field on a related model through a nested
          relationship.

        Each scenario verifies that the correct error message is raised.

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

        Tests the behavior of the 'only' method when attempting to retrieve 
        non-existent fields from a model. Verifies that FieldDoesNotExist 
        or FieldError exceptions are raised with the expected error messages 
        when specifying an invalid field name, including nested field 
        references through related models. Ensures that these exceptions 
        are raised for primary and secondary fields, and for invalid related 
        fields.
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
        """
        .Tests if deferring a field and using select_related on the same field raises a FieldError.

        This test case verifies that a FieldError is raised when attempting to both defer and use select_related on the 'related' field of the Primary model at the same time, as this is an invalid query operation.

        :raises: FieldError
        """
        msg = (
            "Field Primary.related cannot be both deferred and traversed using "
            "select_related at the same time."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Primary.objects.defer("related").select_related("related")[0]

    def test_only_select_related_raises_invalid_query(self):
        """
        Tests that attempting to use both ``only`` and ``select_related`` on a related field raises an ``InvalidQuery`` with a descriptive error message. This ensures that the ORM correctly handles the conflicting field access modifiers, which cannot be both deferred (via ``only``) and traversed (via ``select_related``) simultaneously.
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
        Sets up test data for the class, creating a Secondary instance and a PrimaryOneToOne instance 
        with a related Secondary object to facilitate testing of dependent relationships.
        """
        cls.secondary = Secondary.objects.create(first="a", second="b")
        cls.primary = PrimaryOneToOne.objects.create(
            name="Bella", value="Baxter", related=cls.secondary
        )

    def test_defer_not_clear_cached_relations(self):
        """

        Tests that deferred fields do not clear cached relations.

        This test case verifies that when a model instance is retrieved with a deferred
        field, accessing a related field (via a one-to-one relationship) and then
        accessing the deferred field does not clear the cached relation. This ensures
        that subsequent accesses to the related field do not incur additional database
        queries.

        """
        obj = Secondary.objects.defer("first").get(pk=self.secondary.pk)
        with self.assertNumQueries(1):
            obj.primary_o2o
        obj.first  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.primary_o2o

    def test_only_not_clear_cached_relations(self):
        """

        Tests that relations not specifically included in the 'only' queryset are not 
        cleared from the cache after accessing another attribute.

        This test ensures that when an object is retrieved with 'only' and an attribute 
        is accessed that was not included in 'only', the resulting query is cached, and 
        subsequent accesses to the same attribute do not result in additional queries.

        """
        obj = Secondary.objects.only("first").get(pk=self.secondary.pk)
        with self.assertNumQueries(1):
            obj.primary_o2o
        obj.second  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.primary_o2o
