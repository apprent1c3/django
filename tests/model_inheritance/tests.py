from operator import attrgetter

from django.core.exceptions import FieldError, ValidationError
from django.db import connection, models
from django.db.models.query_utils import DeferredAttribute
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext, isolate_apps

from .models import (
    Base,
    Chef,
    CommonChild,
    CommonInfo,
    CustomSupplier,
    GrandChild,
    GrandParent,
    ItalianRestaurant,
    ItalianRestaurantCommonParent,
    MixinModel,
    Parent,
    ParkingLot,
    Place,
    Post,
    Restaurant,
    Student,
    SubBase,
    Supplier,
    Title,
    Worker,
)


class ModelInheritanceTests(TestCase):
    def test_abstract(self):
        # The Student and Worker models both have 'name' and 'age' fields on
        # them and inherit the __str__() method, just as with normal Python
        # subclassing. This is useful if you want to factor out common
        # information for programming purposes, but still completely
        # independent separate models at the database level.
        w1 = Worker.objects.create(name="Fred", age=35, job="Quarry worker")
        Worker.objects.create(name="Barney", age=34, job="Quarry worker")

        s = Student.objects.create(name="Pebbles", age=5, school_class="1B")

        self.assertEqual(str(w1), "Worker Fred")
        self.assertEqual(str(s), "Student Pebbles")

        # The children inherit the Meta class of their parents (if they don't
        # specify their own).
        self.assertSequenceEqual(
            Worker.objects.values("name"),
            [
                {"name": "Barney"},
                {"name": "Fred"},
            ],
        )

        # Since Student does not subclass CommonInfo's Meta, it has the effect
        # of completely overriding it. So ordering by name doesn't take place
        # for Students.
        self.assertEqual(Student._meta.ordering, [])

        # However, the CommonInfo class cannot be used as a normal model (it
        # doesn't exist as a model).
        with self.assertRaisesMessage(
            AttributeError, "'CommonInfo' has no attribute 'objects'"
        ):
            CommonInfo.objects.all()

    def test_reverse_relation_for_different_hierarchy_tree(self):
        # Even though p.supplier for a Place 'p' (a parent of a Supplier), a
        # Restaurant object cannot access that reverse relation, since it's not
        # part of the Place-Supplier Hierarchy.
        self.assertSequenceEqual(Place.objects.filter(supplier__name="foo"), [])
        msg = (
            "Cannot resolve keyword 'supplier' into field. Choices are: "
            "address, chef, chef_id, id, italianrestaurant, lot, name, "
            "place_ptr, place_ptr_id, provider, rating, serves_hot_dogs, serves_pizza"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Restaurant.objects.filter(supplier__name="foo")

    def test_model_with_distinct_accessors(self):
        # The Post model has distinct accessors for the Comment and Link models.
        post = Post.objects.create(title="Lorem Ipsum")
        post.attached_comment_set.create(content="Save $ on V1agr@", is_spam=True)
        post.attached_link_set.create(
            content="The web framework for perfections with deadlines.",
            url="http://www.djangoproject.com/",
        )

        # The Post model doesn't have an attribute called
        # 'attached_%(class)s_set'.
        msg = "'Post' object has no attribute 'attached_%(class)s_set'"
        with self.assertRaisesMessage(AttributeError, msg):
            getattr(post, "attached_%(class)s_set")

    def test_model_with_distinct_related_query_name(self):
        self.assertSequenceEqual(
            Post.objects.filter(attached_model_inheritance_comments__is_spam=True), []
        )

        # The Post model doesn't have a related query accessor based on
        # related_name (attached_comment_set).
        msg = "Cannot resolve keyword 'attached_comment_set' into field."
        with self.assertRaisesMessage(FieldError, msg):
            Post.objects.filter(attached_comment_set__is_spam=True)

    def test_meta_fields_and_ordering(self):
        # Make sure Restaurant and ItalianRestaurant have the right fields in
        # the right order.
        self.assertEqual(
            [f.name for f in Restaurant._meta.fields],
            [
                "id",
                "name",
                "address",
                "place_ptr",
                "rating",
                "serves_hot_dogs",
                "serves_pizza",
                "chef",
            ],
        )
        self.assertEqual(
            [f.name for f in ItalianRestaurant._meta.fields],
            [
                "id",
                "name",
                "address",
                "place_ptr",
                "rating",
                "serves_hot_dogs",
                "serves_pizza",
                "chef",
                "restaurant_ptr",
                "serves_gnocchi",
            ],
        )
        self.assertEqual(Restaurant._meta.ordering, ["-rating"])

    def test_custompk_m2m(self):
        b = Base.objects.create()
        b.titles.add(Title.objects.create(title="foof"))
        s = SubBase.objects.create(sub_id=b.id)
        b = Base.objects.get(pk=s.id)
        self.assertNotEqual(b.pk, s.pk)
        # Low-level test for related_val
        self.assertEqual(s.titles.related_val, (s.id,))
        # Higher level test for correct query values (title foof not
        # accidentally found).
        self.assertSequenceEqual(s.titles.all(), [])

    def test_create_diamond_mti_default_pk(self):
        # 1 INSERT for each base.
        with self.assertNumQueries(4):
            common_child = CommonChild.objects.create()
        # 3 SELECTs for the parents, 1 UPDATE for the child.
        with self.assertNumQueries(4):
            common_child.save()

    def test_create_diamond_mti_common_parent(self):
        with self.assertNumQueries(4):
            italian_restaurant_child = ItalianRestaurantCommonParent.objects.create(
                name="Ristorante Miron",
                address="1234 W. Ash",
            )

        self.assertEqual(
            italian_restaurant_child.italianrestaurant_ptr.place_ptr,
            italian_restaurant_child.place_ptr_two,
        )
        self.assertEqual(
            italian_restaurant_child.italianrestaurant_ptr.restaurant_ptr,
            italian_restaurant_child.restaurant_ptr,
        )
        self.assertEqual(
            italian_restaurant_child.restaurant_ptr.place_ptr,
            italian_restaurant_child.place_ptr_two,
        )
        self.assertEqual(italian_restaurant_child.name, "Ristorante Miron")
        self.assertEqual(italian_restaurant_child.address, "1234 W. Ash")

    def test_update_parent_filtering(self):
        """
        Updating a field of a model subclass doesn't issue an UPDATE
        query constrained by an inner query (#10399).
        """
        supplier = Supplier.objects.create(
            name="Central market",
            address="610 some street",
        )
        # Capture the expected query in a database agnostic way
        with CaptureQueriesContext(connection) as captured_queries:
            Place.objects.filter(pk=supplier.pk).update(name=supplier.name)
        expected_sql = captured_queries[0]["sql"]
        # Capture the queries executed when a subclassed model instance is saved.
        with CaptureQueriesContext(connection) as captured_queries:
            supplier.save(update_fields=("name",))
        for query in captured_queries:
            sql = query["sql"]
            if "UPDATE" in sql:
                self.assertEqual(expected_sql, sql)

    def test_create_child_no_update(self):
        """Creating a child with non-abstract parents only issues INSERTs."""

        def a():
            GrandChild.objects.create(
                email="grand_parent@example.com",
                first_name="grand",
                last_name="parent",
            )

        def b():
            GrandChild().save()

        for i, test in enumerate([a, b]):
            with (
                self.subTest(i=i),
                self.assertNumQueries(4),
                CaptureQueriesContext(connection) as queries,
            ):
                test()
                for query in queries:
                    sql = query["sql"]
                    self.assertIn("INSERT INTO", sql, sql)

    def test_create_copy_with_inherited_m2m(self):
        """

        Tests that a new supplier instance created as a copy of an existing supplier
        inherits the many-to-many relationship with customers.

        This test case verifies that when a supplier is duplicated, its associated customers
        are properly transferred to the new supplier instance, ensuring data consistency.

        """
        restaurant = Restaurant.objects.create()
        supplier = CustomSupplier.objects.create(
            name="Central market", address="944 W. Fullerton"
        )
        supplier.customers.set([restaurant])
        old_customers = supplier.customers.all()
        supplier.pk = None
        supplier.id = None
        supplier._state.adding = True
        supplier.save()
        supplier.customers.set(old_customers)
        supplier = Supplier.objects.get(pk=supplier.pk)
        self.assertCountEqual(supplier.customers.all(), old_customers)
        self.assertSequenceEqual(supplier.customers.all(), [restaurant])

    def test_eq(self):
        # Equality doesn't transfer in multitable inheritance.
        """

        Tests the equality of Place and Restaurant objects.

        Verifies that instances of Place and Restaurant are not considered equal, 
        even if they have the same id. This check ensures that the equality 
        comparison correctly distinguishes between these two distinct classes.

        """
        self.assertNotEqual(Place(id=1), Restaurant(id=1))
        self.assertNotEqual(Restaurant(id=1), Place(id=1))

    def test_mixin_init(self):
        """

        Tests the initialization of the MixinModel class.

        Verifies that upon creation, the instance attribute 'other_attr' is correctly set to its expected initial value.

        """
        m = MixinModel()
        self.assertEqual(m.other_attr, 1)

    @isolate_apps("model_inheritance")
    def test_abstract_parent_link(self):
        class A(models.Model):
            pass

        class B(A):
            a = models.OneToOneField("A", parent_link=True, on_delete=models.CASCADE)

            class Meta:
                abstract = True

        class C(B):
            pass

        self.assertIs(C._meta.parents[A], C._meta.get_field("a"))

    @isolate_apps("model_inheritance")
    def test_init_subclass(self):
        saved_kwargs = {}

        class A(models.Model):
            def __init_subclass__(cls, **kwargs):
                """

                Initializes a subclass, updating the saved keyword arguments.

                This method is automatically called when a subclass is created, allowing for
                the registration of additional keyword arguments. The provided keyword arguments
                are stored for later use, extending the functionality of the base class.

                :param cls: The subclass being initialized.
                :param **kwargs: Keyword arguments to update and store.

                """
                super().__init_subclass__()
                saved_kwargs.update(kwargs)

        kwargs = {"x": 1, "y": 2, "z": 3}

        class B(A, **kwargs):
            pass

        self.assertEqual(saved_kwargs, kwargs)

    @isolate_apps("model_inheritance")
    def test_set_name(self):
        """
        Tests that the __set_name__ method is correctly called when a class attribute is set.

        This test verifies that the __set_name__ method is invoked with the correct owner and name when an instance of a class is created, specifically in the context of Django model inheritance.

        The test checks that the __set_name__ method is called with the class as the owner and the attribute name as the name, and that the method is only called once, as indicated by the 'called' attribute being initially None and then set to the expected values.

        The test case covers the scenario where a class attribute is defined with a custom descriptor class that implements the __set_name__ method, which is a common pattern in Django model inheritance. The test ensures that the descriptor is properly initialized and that the __set_name__ method is called as expected.
        """
        class ClassAttr:
            called = None

            def __set_name__(self_, owner, name):
                """

                Called when an instance of this object is assigned to a container.

                This method is part of the descriptor protocol in Python, allowing the object
                to track its ownership and name within the container. It records the owner
                and name of the attribute as a tuple, marking the instance as called.

                :param self_: The instance being assigned.
                :param owner: The class or object owning the attribute.
                :param name: The name of the attribute.

                """
                self.assertIsNone(self_.called)
                self_.called = (owner, name)

        class A(models.Model):
            attr = ClassAttr()

        self.assertEqual(A.attr.called, (A, "attr"))

    def test_inherited_ordering_pk_desc(self):
        p1 = Parent.objects.create(first_name="Joe", email="joe@email.com")
        p2 = Parent.objects.create(first_name="Jon", email="jon@email.com")
        expected_order_by_sql = "ORDER BY %s.%s DESC" % (
            connection.ops.quote_name(Parent._meta.db_table),
            connection.ops.quote_name(Parent._meta.get_field("grandparent_ptr").column),
        )
        qs = Parent.objects.all()
        self.assertSequenceEqual(qs, [p2, p1])
        self.assertIn(expected_order_by_sql, str(qs.query))

    def test_queryset_class_getitem(self):
        self.assertIs(models.QuerySet[Post], models.QuerySet)
        self.assertIs(models.QuerySet[Post, Post], models.QuerySet)
        self.assertIs(models.QuerySet[Post, int, str], models.QuerySet)

    def test_shadow_parent_attribute_with_field(self):
        class ScalarParent(models.Model):
            foo = 1

        class ScalarOverride(ScalarParent):
            foo = models.IntegerField()

        self.assertEqual(type(ScalarOverride.foo), DeferredAttribute)

    def test_shadow_parent_property_with_field(self):
        class PropertyParent(models.Model):
            @property
            def foo(self):
                pass

        class PropertyOverride(PropertyParent):
            foo = models.IntegerField()

        self.assertEqual(type(PropertyOverride.foo), DeferredAttribute)

    def test_shadow_parent_method_with_field(self):
        class MethodParent(models.Model):
            def foo(self):
                pass

        class MethodOverride(MethodParent):
            foo = models.IntegerField()

        self.assertEqual(type(MethodOverride.foo), DeferredAttribute)


class ModelInheritanceDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.restaurant = Restaurant.objects.create(
            name="Demon Dogs",
            address="944 W. Fullerton",
            serves_hot_dogs=True,
            serves_pizza=False,
            rating=2,
        )

        chef = Chef.objects.create(name="Albert")
        cls.italian_restaurant = ItalianRestaurant.objects.create(
            name="Ristorante Miron",
            address="1234 W. Ash",
            serves_hot_dogs=False,
            serves_pizza=False,
            serves_gnocchi=True,
            rating=4,
            chef=chef,
        )

    def test_filter_inherited_model(self):
        self.assertQuerySetEqual(
            ItalianRestaurant.objects.filter(address="1234 W. Ash"),
            [
                "Ristorante Miron",
            ],
            attrgetter("name"),
        )

    def test_update_inherited_model(self):
        """
        Tests the update functionality of a model that inherits from another model.

        Verifies that changes made to an instance of the inheriting model are persisted to the database and can be retrieved correctly.
        The test specifically checks that updating an attribute, in this case the address, results in the correct data being stored and retrieved.
        The expected outcome is that the updated instance is returned when querying the database with the new attribute value.
        """
        self.italian_restaurant.address = "1234 W. Elm"
        self.italian_restaurant.save()
        self.assertQuerySetEqual(
            ItalianRestaurant.objects.filter(address="1234 W. Elm"),
            [
                "Ristorante Miron",
            ],
            attrgetter("name"),
        )

    def test_parent_fields_available_for_filtering_in_child_model(self):
        # Parent fields can be used directly in filters on the child model.
        """

        Verify that fields from parent models are accessible for filtering in child models.

        This test checks if attributes defined in a parent model can be used as filters when querying a child model.
        It ensures that the relationship between parent and child models allows for proper filtering based on parent fields.

        """
        self.assertQuerySetEqual(
            Restaurant.objects.filter(name="Demon Dogs"),
            [
                "Demon Dogs",
            ],
            attrgetter("name"),
        )
        self.assertQuerySetEqual(
            ItalianRestaurant.objects.filter(address="1234 W. Ash"),
            [
                "Ristorante Miron",
            ],
            attrgetter("name"),
        )

    def test_filter_on_parent_returns_object_of_parent_type(self):
        # Filters against the parent model return objects of the parent's type.
        p = Place.objects.get(name="Demon Dogs")
        self.assertIs(type(p), Place)

    def test_parent_child_one_to_one_link(self):
        # Since the parent and child are linked by an automatically created
        # OneToOneField, you can get from the parent to the child by using the
        # child's name.
        """
        Tests one-to-one relationships between parent and child objects in the database, specifically between Places and Restaurants, as well as between Restaurants and their specialized types like ItalianRestaurants. 

        The function verifies that the associations between these objects are correctly established, ensuring that each object can be retrieved from its parent or child object, and that these relationships are consistent across different types of restaurants. 

        This test case covers scenarios where a Place is linked to a Restaurant, and a Restaurant is linked to its specific type, in this case, an ItalianRestaurant, validating the integrity of these one-to-one links.
        """
        self.assertEqual(
            Place.objects.get(name="Demon Dogs").restaurant,
            Restaurant.objects.get(name="Demon Dogs"),
        )
        self.assertEqual(
            Place.objects.get(name="Ristorante Miron").restaurant.italianrestaurant,
            ItalianRestaurant.objects.get(name="Ristorante Miron"),
        )
        self.assertEqual(
            Restaurant.objects.get(name="Ristorante Miron").italianrestaurant,
            ItalianRestaurant.objects.get(name="Ristorante Miron"),
        )

    def test_parent_child_one_to_one_link_on_nonrelated_objects(self):
        # This won't work because the Demon Dogs restaurant is not an Italian
        # restaurant.
        """

        Tests that a One-To-One link between parent and child objects raises a DoesNotExist exception 
        when attempting to access the child object on a parent object that does not have a related child object.

        This test ensures that the ItalianRestaurant child object cannot be accessed on a Place object 
        that is not related to an ItalianRestaurant, specifically verifying that the link between 
        non-related objects is properly handled.

        """
        with self.assertRaises(ItalianRestaurant.DoesNotExist):
            Place.objects.get(name="Demon Dogs").restaurant.italianrestaurant

    def test_inherited_does_not_exist_exception(self):
        # An ItalianRestaurant which does not exist is also a Place which does
        # not exist.
        with self.assertRaises(Place.DoesNotExist):
            ItalianRestaurant.objects.get(name="The Noodle Void")

    def test_inherited_multiple_objects_returned_exception(self):
        # MultipleObjectsReturned is also inherited.
        with self.assertRaises(Place.MultipleObjectsReturned):
            Restaurant.objects.get()

    def test_related_objects_for_inherited_models(self):
        # Related objects work just as they normally do.
        s1 = Supplier.objects.create(name="Joe's Chickens", address="123 Sesame St")
        s1.customers.set([self.restaurant, self.italian_restaurant])
        s2 = Supplier.objects.create(name="Luigi's Pasta", address="456 Sesame St")
        s2.customers.set([self.italian_restaurant])

        # This won't work because the Place we select is not a Restaurant (it's
        # a Supplier).
        p = Place.objects.get(name="Joe's Chickens")
        with self.assertRaises(Restaurant.DoesNotExist):
            p.restaurant

        self.assertEqual(p.supplier, s1)
        self.assertQuerySetEqual(
            self.italian_restaurant.provider.order_by("-name"),
            ["Luigi's Pasta", "Joe's Chickens"],
            attrgetter("name"),
        )
        self.assertQuerySetEqual(
            Restaurant.objects.filter(provider__name__contains="Chickens"),
            [
                "Ristorante Miron",
                "Demon Dogs",
            ],
            attrgetter("name"),
        )
        self.assertQuerySetEqual(
            ItalianRestaurant.objects.filter(provider__name__contains="Chickens"),
            [
                "Ristorante Miron",
            ],
            attrgetter("name"),
        )

        ParkingLot.objects.create(name="Main St", address="111 Main St", main_site=s1)
        ParkingLot.objects.create(
            name="Well Lit", address="124 Sesame St", main_site=self.italian_restaurant
        )

        self.assertEqual(
            Restaurant.objects.get(lot__name="Well Lit").name, "Ristorante Miron"
        )

    def test_update_works_on_parent_and_child_models_at_once(self):
        # The update() command can update fields in parent and child classes at
        # once (although it executed multiple SQL queries to do so).
        """
        Tests that the update method can modify both parent and child models simultaneously, verifying the successful update of a Restaurant object's attributes. 

        The function checks that a single row is updated when filtering by specific conditions, and then asserts that the updated object's attributes match the expected values, ensuring that the update operation is correctly applied.
        """
        rows = Restaurant.objects.filter(
            serves_hot_dogs=True, name__contains="D"
        ).update(name="Demon Puppies", serves_hot_dogs=False)
        self.assertEqual(rows, 1)

        r1 = Restaurant.objects.get(pk=self.restaurant.pk)
        self.assertFalse(r1.serves_hot_dogs)
        self.assertEqual(r1.name, "Demon Puppies")

    def test_values_works_on_parent_model_fields(self):
        # The values() command also works on fields from parent models.
        self.assertSequenceEqual(
            ItalianRestaurant.objects.values("name", "rating"),
            [
                {"rating": 4, "name": "Ristorante Miron"},
            ],
        )

    def test_select_related_works_on_parent_model_fields(self):
        # select_related works with fields from the parent object as if they
        # were a normal part of the model.
        self.assertNumQueries(2, lambda: ItalianRestaurant.objects.all()[0].chef)
        self.assertNumQueries(
            1, lambda: ItalianRestaurant.objects.select_related("chef")[0].chef
        )

    def test_select_related_defer(self):
        """
        #23370 - Should be able to defer child fields when using
        select_related() from parent to child.
        """
        qs = (
            Restaurant.objects.select_related("italianrestaurant")
            .defer("italianrestaurant__serves_gnocchi")
            .order_by("rating")
        )

        # The field was actually deferred
        with self.assertNumQueries(2):
            objs = list(qs.all())
            self.assertTrue(objs[1].italianrestaurant.serves_gnocchi)

        # Model fields where assigned correct values
        self.assertEqual(qs[0].name, "Demon Dogs")
        self.assertEqual(qs[0].rating, 2)
        self.assertEqual(qs[1].italianrestaurant.name, "Ristorante Miron")
        self.assertEqual(qs[1].italianrestaurant.rating, 4)

    def test_parent_cache_reuse(self):
        """
        Tests the caching behavior of the parent relationship in the object hierarchy.

        This test creates a place and a grandchild object, then traverses the object hierarchy
        from the grandparent to the grandchild, verifying that the place attribute is correctly
        reused from the cache, reducing the number of database queries.

        The test checks that the first query to the grandparent's place attribute results in a
        single database query, and subsequent queries to the place attribute of the parent,
        child, and grandchild objects do not result in additional queries, demonstrating the
        correct caching of the parent relationship.
        """
        place = Place.objects.create()
        GrandChild.objects.create(place=place)
        grand_parent = GrandParent.objects.latest("pk")
        with self.assertNumQueries(1):
            self.assertEqual(grand_parent.place, place)
        parent = grand_parent.parent
        with self.assertNumQueries(0):
            self.assertEqual(parent.place, place)
        child = parent.child
        with self.assertNumQueries(0):
            self.assertEqual(child.place, place)
        grandchild = child.grandchild
        with self.assertNumQueries(0):
            self.assertEqual(grandchild.place, place)

    def test_update_query_counts(self):
        """
        Update queries do not generate unnecessary queries (#18304).
        """
        with self.assertNumQueries(3):
            self.italian_restaurant.save()

    def test_filter_inherited_on_null(self):
        # Refs #12567
        Supplier.objects.create(
            name="Central market",
            address="610 some street",
        )
        self.assertQuerySetEqual(
            Place.objects.filter(supplier__isnull=False),
            [
                "Central market",
            ],
            attrgetter("name"),
        )
        self.assertQuerySetEqual(
            Place.objects.filter(supplier__isnull=True).order_by("name"),
            [
                "Demon Dogs",
                "Ristorante Miron",
            ],
            attrgetter("name"),
        )

    def test_exclude_inherited_on_null(self):
        # Refs #12567
        Supplier.objects.create(
            name="Central market",
            address="610 some street",
        )
        self.assertQuerySetEqual(
            Place.objects.exclude(supplier__isnull=False).order_by("name"),
            [
                "Demon Dogs",
                "Ristorante Miron",
            ],
            attrgetter("name"),
        )
        self.assertQuerySetEqual(
            Place.objects.exclude(supplier__isnull=True),
            [
                "Central market",
            ],
            attrgetter("name"),
        )


@isolate_apps("model_inheritance", "model_inheritance.tests")
class InheritanceSameModelNameTests(SimpleTestCase):
    def test_abstract_fk_related_name(self):
        related_name = "%(app_label)s_%(class)s_references"

        class Referenced(models.Model):
            class Meta:
                app_label = "model_inheritance"

        class AbstractReferent(models.Model):
            reference = models.ForeignKey(
                Referenced, models.CASCADE, related_name=related_name
            )

            class Meta:
                app_label = "model_inheritance"
                abstract = True

        class Referent(AbstractReferent):
            class Meta:
                app_label = "model_inheritance"

        LocalReferent = Referent

        class Referent(AbstractReferent):
            class Meta:
                app_label = "tests"

        ForeignReferent = Referent

        self.assertFalse(hasattr(Referenced, related_name))
        self.assertIs(
            Referenced.model_inheritance_referent_references.field.model, LocalReferent
        )
        self.assertIs(Referenced.tests_referent_references.field.model, ForeignReferent)


class InheritanceUniqueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grand_parent = GrandParent.objects.create(
            email="grand_parent@example.com",
            first_name="grand",
            last_name="parent",
        )

    def test_unique(self):
        """

        Tests the validation of a GrandChild instance with a unique email address.

        Verifies that attempting to validate a GrandChild with an email address that already
        exists in the system raises a ValidationError with an informative error message.

        This test ensures that the data integrity of the GrandChild instances is maintained,
        preventing duplicate email addresses from being created.

        """
        grand_child = GrandChild(
            email=self.grand_parent.email,
            first_name="grand",
            last_name="child",
        )
        msg = "Grand parent with this Email already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            grand_child.validate_unique()

    def test_unique_together(self):
        """
        Tests the uniqueness constraint on a GrandChild instance with respect to its grand parent's first and last name.

        The function attempts to create a GrandChild object with a first and last name that already exists for a grand parent, 
        then checks that a ValidationError is raised with the expected error message, ensuring that the unique_together 
        constraint is properly enforced.
        """
        grand_child = GrandChild(
            email="grand_child@example.com",
            first_name=self.grand_parent.first_name,
            last_name=self.grand_parent.last_name,
        )
        msg = "Grand parent with this First name and Last name already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            grand_child.validate_unique()
