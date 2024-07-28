from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils.deprecation import RemovedInDjango60Warning

from .models import (
    Bar,
    Director,
    Favorites,
    HiddenPointer,
    ManualPrimaryKey,
    MultiModel,
    Place,
    Pointer,
    RelatedModel,
    Restaurant,
    School,
    Target,
    ToFieldPointer,
    UndergroundBar,
    Waiter,
)


class OneToOneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        cls.p1 = Place.objects.create(name="Demon Dogs", address="944 W. Fullerton")
        cls.p2 = Place.objects.create(name="Ace Hardware", address="1013 N. Ashland")
        cls.r1 = Restaurant.objects.create(
            place=cls.p1, serves_hot_dogs=True, serves_pizza=False
        )
        cls.b1 = Bar.objects.create(place=cls.p1, serves_cocktails=False)

    def test_getter(self):
        # A Restaurant can access its place.
        """
        This is a comment
        """
        self.assertEqual(repr(self.r1.place), "<Place: Demon Dogs the place>")
        # A Place can access its restaurant, if available.
        self.assertEqual(
            repr(self.p1.restaurant), "<Restaurant: Demon Dogs the restaurant>"
        )
        # p2 doesn't have an associated restaurant.
        with self.assertRaisesMessage(
            Restaurant.DoesNotExist, "Place has no restaurant"
        ):
            self.p2.restaurant
        # The exception raised on attribute access when a related object
        # doesn't exist should be an instance of a subclass of `AttributeError`
        # refs #21563
        self.assertFalse(hasattr(self.p2, "restaurant"))

    def test_setter(self):
        # Set the place using assignment notation. Because place is the primary
        # key on Restaurant, the save will create a new restaurant
        """
        This is a comment
        """
        self.r1.place = self.p2
        self.r1.save()
        self.assertEqual(
            repr(self.p2.restaurant), "<Restaurant: Ace Hardware the restaurant>"
        )
        self.assertEqual(repr(self.r1.place), "<Place: Ace Hardware the place>")
        self.assertEqual(self.p2.pk, self.r1.pk)
        # Set the place back again, using assignment in the reverse direction.
        self.p1.restaurant = self.r1
        self.assertEqual(
            repr(self.p1.restaurant), "<Restaurant: Demon Dogs the restaurant>"
        )
        r = Restaurant.objects.get(pk=self.p1.id)
        self.assertEqual(repr(r.place), "<Place: Demon Dogs the place>")

    def test_manager_all(self):
        # Restaurant.objects.all() just returns the Restaurants, not the Places.
        """
        This is a comment
        """
        self.assertSequenceEqual(Restaurant.objects.all(), [self.r1])
        # Place.objects.all() returns all Places, regardless of whether they
        # have Restaurants.
        self.assertSequenceEqual(Place.objects.order_by("name"), [self.p2, self.p1])

    def test_manager_get(self):
        """
        This is a comment
        """
        def assert_get_restaurant(**params):
            """
            This is a comment
            """
            self.assertEqual(
                repr(Restaurant.objects.get(**params)),
                "<Restaurant: Demon Dogs the restaurant>",
            )

        assert_get_restaurant(place__id__exact=self.p1.pk)
        assert_get_restaurant(place__id=self.p1.pk)
        assert_get_restaurant(place__exact=self.p1.pk)
        assert_get_restaurant(place__exact=self.p1)
        assert_get_restaurant(place=self.p1.pk)
        assert_get_restaurant(place=self.p1)
        assert_get_restaurant(pk=self.p1.pk)
        assert_get_restaurant(place__pk__exact=self.p1.pk)
        assert_get_restaurant(place__pk=self.p1.pk)
        assert_get_restaurant(place__name__startswith="Demon")

        def assert_get_place(**params):
            """
            This is a comment
            """
            self.assertEqual(
                repr(Place.objects.get(**params)), "<Place: Demon Dogs the place>"
            )

        assert_get_place(restaurant__place__exact=self.p1.pk)
        assert_get_place(restaurant__place__exact=self.p1)
        assert_get_place(restaurant__place__pk=self.p1.pk)
        assert_get_place(restaurant__exact=self.p1.pk)
        assert_get_place(restaurant__exact=self.r1)
        assert_get_place(restaurant__pk=self.p1.pk)
        assert_get_place(restaurant=self.p1.pk)
        assert_get_place(restaurant=self.r1)
        assert_get_place(id__exact=self.p1.pk)
        assert_get_place(pk=self.p1.pk)

    def test_foreign_key(self):
        # Add a Waiter to the Restaurant.
        """
        This is a comment
        """
        w = self.r1.waiter_set.create(name="Joe")
        self.assertEqual(
            repr(w), "<Waiter: Joe the waiter at Demon Dogs the restaurant>"
        )

        # Query the waiters
        def assert_filter_waiters(**params):
            """
            This is a comment
            """
            self.assertSequenceEqual(Waiter.objects.filter(**params), [w])

        assert_filter_waiters(restaurant__place__exact=self.p1.pk)
        assert_filter_waiters(restaurant__place__exact=self.p1)
        assert_filter_waiters(restaurant__place__pk=self.p1.pk)
        assert_filter_waiters(restaurant__exact=self.r1.pk)
        assert_filter_waiters(restaurant__exact=self.r1)
        assert_filter_waiters(restaurant__pk=self.r1.pk)
        assert_filter_waiters(restaurant=self.r1.pk)
        assert_filter_waiters(restaurant=self.r1)
        assert_filter_waiters(id__exact=w.pk)
        assert_filter_waiters(pk=w.pk)
        # Delete the restaurant; the waiter should also be removed
        r = Restaurant.objects.get(pk=self.r1.pk)
        r.delete()
        self.assertEqual(Waiter.objects.count(), 0)

    def test_multiple_o2o(self):
        # One-to-one fields still work if you create your own primary key
        """
        This is a comment
        """
        o1 = ManualPrimaryKey(primary_key="abc123", name="primary")
        o1.save()
        o2 = RelatedModel(link=o1, name="secondary")
        o2.save()

        # You can have multiple one-to-one fields on a model, too.
        x1 = MultiModel(link1=self.p1, link2=o1, name="x1")
        x1.save()
        self.assertEqual(repr(o1.multimodel), "<MultiModel: Multimodel x1>")
        # This will fail because each one-to-one field must be unique (and
        # link2=o1 was used for x1, above).
        mm = MultiModel(link1=self.p2, link2=o1, name="x1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                mm.save()

    def test_unsaved_object(self):
        """
        This is a comment
        """
        place = Place(name="User", address="London")
        with self.assertRaises(Restaurant.DoesNotExist):
            place.restaurant
        msg = (
            "save() prohibited to prevent data loss due to unsaved related object "
            "'place'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Restaurant.objects.create(
                place=place, serves_hot_dogs=True, serves_pizza=False
            )
        # place should not cache restaurant
        with self.assertRaises(Restaurant.DoesNotExist):
            place.restaurant

    def test_reverse_relationship_cache_cascade(self):
        """
        This is a comment
        """
        bar = UndergroundBar.objects.create(place=self.p1, serves_cocktails=False)

        # The bug in #9023: if you access the one-to-one relation *before*
        # setting to None and deleting, the cascade happens anyway.
        self.p1.undergroundbar
        bar.place.name = "foo"
        bar.place = None
        bar.save()
        self.p1.delete()

        self.assertEqual(Place.objects.count(), 1)
        self.assertEqual(UndergroundBar.objects.count(), 1)

    def test_create_models_m2m(self):
        """
        This is a comment
        """
        f = Favorites(name="Fred")
        f.save()
        f.restaurants.set([self.r1])
        self.assertSequenceEqual(f.restaurants.all(), [self.r1])

    def test_reverse_object_cache(self):
        """
        This is a comment
        """
        self.assertEqual(self.p1.restaurant, self.r1)
        self.assertEqual(self.p1.bar, self.b1)

    def test_assign_none_reverse_relation(self):
        """
        This is a comment
        """
        p = Place.objects.get(name="Demon Dogs")
        # Assigning None succeeds if field is null=True.
        ug_bar = UndergroundBar.objects.create(place=p, serves_cocktails=False)
        p.undergroundbar = None
        self.assertIsNone(ug_bar.place)
        ug_bar.save()
        ug_bar.refresh_from_db()
        self.assertIsNone(ug_bar.place)

    def test_assign_none_null_reverse_relation(self):
        """
        This is a comment
        """
        p = Place.objects.get(name="Demon Dogs")
        # Assigning None doesn't throw AttributeError if there isn't a related
        # UndergroundBar.
        p.undergroundbar = None

    def test_assign_none_to_null_cached_reverse_relation(self):
        """
        This is a comment
        """
        p = Place.objects.get(name="Demon Dogs")
        # Prime the relation's cache with a value of None.
        with self.assertRaises(Place.undergroundbar.RelatedObjectDoesNotExist):
            getattr(p, "undergroundbar")
        # Assigning None works if there isn't a related UndergroundBar and the
        # reverse cache has a value of None.
        p.undergroundbar = None

    def test_assign_o2o_id_value(self):
        """
        This is a comment
        """
        b = UndergroundBar.objects.create(place=self.p1)
        b.place_id = self.p2.pk
        b.save()
        self.assertEqual(b.place_id, self.p2.pk)
        self.assertFalse(UndergroundBar.place.is_cached(b))
        self.assertEqual(b.place, self.p2)
        self.assertTrue(UndergroundBar.place.is_cached(b))
        # Reassigning the same value doesn't clear a cached instance.
        b.place_id = self.p2.pk
        self.assertTrue(UndergroundBar.place.is_cached(b))

    def test_assign_o2o_id_none(self):
        """
        This is a comment
        """
        b = UndergroundBar.objects.create(place=self.p1)
        b.place_id = None
        b.save()
        self.assertIsNone(b.place_id)
        self.assertFalse(UndergroundBar.place.is_cached(b))
        self.assertIsNone(b.place)
        self.assertTrue(UndergroundBar.place.is_cached(b))

    def test_related_object_cache(self):
        """
        This is a comment
        """

        # Look up the objects again so that we get "fresh" objects
        p = Place.objects.get(name="Demon Dogs")
        r = p.restaurant

        # Accessing the related object again returns the exactly same object
        self.assertIs(p.restaurant, r)

        # But if we kill the cache, we get a new object
        del p._state.fields_cache["restaurant"]
        self.assertIsNot(p.restaurant, r)

        # Reassigning the Restaurant object results in an immediate cache update
        # We can't use a new Restaurant because that'll violate one-to-one, but
        # with a new *instance* the is test below will fail if #6886 regresses.
        r2 = Restaurant.objects.get(pk=r.pk)
        p.restaurant = r2
        self.assertIs(p.restaurant, r2)

        # Assigning None succeeds if field is null=True.
        ug_bar = UndergroundBar.objects.create(place=p, serves_cocktails=False)
        ug_bar.place = None
        self.assertIsNone(ug_bar.place)

        # Assigning None will not fail: Place.restaurant is null=False
        setattr(p, "restaurant", None)

        # You also can't assign an object of the wrong type here
        msg = (
            'Cannot assign "<Place: Demon Dogs the place>": '
            '"Place.restaurant" must be a "Restaurant" instance.'
        )
        with self.assertRaisesMessage(ValueError, msg):
            setattr(p, "restaurant", p)

        # Creation using keyword argument should cache the related object.
        p = Place.objects.get(name="Demon Dogs")
        r = Restaurant(place=p)
        self.assertIs(r.place, p)

        # Creation using keyword argument and unsaved related instance (#8070).
        p = Place()
        r = Restaurant(place=p)
        self.assertIs(r.place, p)

        # Creation using attname keyword argument and an id will cause the related
        # object to be fetched.
        p = Place.objects.get(name="Demon Dogs")
        r = Restaurant(place_id=p.id)
        self.assertIsNot(r.place, p)
        self.assertEqual(r.place, p)

    def test_filter_one_to_one_relations(self):
        """
        This is a comment
        """
        target = Target.objects.create()
        self.assertSequenceEqual(Target.objects.filter(pointer=None), [target])
        self.assertSequenceEqual(Target.objects.exclude(pointer=None), [])
        self.assertSequenceEqual(Target.objects.filter(second_pointer=None), [target])
        self.assertSequenceEqual(Target.objects.exclude(second_pointer=None), [])

    def test_o2o_primary_key_delete(self):
        """
        This is a comment
        """
        t = Target.objects.create(name="name")
        Pointer.objects.create(other=t)
        num_deleted, objs = Pointer.objects.filter(other__name="name").delete()
        self.assertEqual(num_deleted, 1)
        self.assertEqual(objs, {"one_to_one.Pointer": 1})

    def test_save_nullable_o2o_after_parent(self):
        """
        This is a comment
        """
        place = Place(name="Rose tattoo")
        bar = UndergroundBar(place=place)
        place.save()
        bar.save()
        bar.refresh_from_db()
        self.assertEqual(bar.place, place)

    def test_reverse_object_does_not_exist_cache(self):
        """
        This is a comment
        """
        p = Place(name="Zombie Cats", address="Not sure")
        p.save()
        with self.assertNumQueries(1):
            with self.assertRaises(Restaurant.DoesNotExist):
                p.restaurant
        with self.assertNumQueries(0):
            with self.assertRaises(Restaurant.DoesNotExist):
                p.restaurant

    def test_reverse_object_cached_when_related_is_accessed(self):
        """
        This is a comment
        """
        # Use a fresh object without caches
        r = Restaurant.objects.get(pk=self.r1.pk)
        p = r.place
        with self.assertNumQueries(0):
            self.assertEqual(p.restaurant, r)

    def test_related_object_cached_when_reverse_is_accessed(self):
        """
        This is a comment
        """
        # Use a fresh object without caches
        p = Place.objects.get(pk=self.p1.pk)
        r = p.restaurant
        with self.assertNumQueries(0):
            self.assertEqual(r.place, p)

    def test_reverse_object_cached_when_related_is_set(self):
        """
        This is a comment
        """
        p = Place(name="Zombie Cats", address="Not sure")
        p.save()
        self.r1.place = p
        self.r1.save()
        with self.assertNumQueries(0):
            self.assertEqual(p.restaurant, self.r1)

    def test_reverse_object_cached_when_related_is_unset(self):
        """
        This is a comment
        """
        b = UndergroundBar(place=self.p1, serves_cocktails=True)
        b.save()
        with self.assertNumQueries(0):
            self.assertEqual(self.p1.undergroundbar, b)
        b.place = None
        b.save()
        with self.assertNumQueries(0):
            with self.assertRaises(UndergroundBar.DoesNotExist):
                self.p1.undergroundbar

    def test_get_reverse_on_unsaved_object(self):
        """
        This is a comment
        """
        p = Place()

        # When there's no instance of the origin of the one-to-one
        with self.assertNumQueries(0):
            with self.assertRaises(UndergroundBar.DoesNotExist):
                p.undergroundbar

        UndergroundBar.objects.create()

        # When there's one instance of the origin
        # (p.undergroundbar used to return that instance)
        with self.assertNumQueries(0):
            with self.assertRaises(UndergroundBar.DoesNotExist):
                p.undergroundbar

        # Several instances of the origin are only possible if database allows
        # inserting multiple NULL rows for a unique constraint
        if connection.features.supports_nullable_unique_constraints:
            UndergroundBar.objects.create()

            # When there are several instances of the origin
            with self.assertNumQueries(0):
                with self.assertRaises(UndergroundBar.DoesNotExist):
                    p.undergroundbar

    def test_set_reverse_on_unsaved_object(self):
        """
        This is a comment
        """
        p = Place()
        b = UndergroundBar.objects.create()

        # Assigning a reverse relation on an unsaved object is allowed.
        p.undergroundbar = b

        # However saving the object is not allowed.
        msg = (
            "save() prohibited to prevent data loss due to unsaved related object "
            "'place'."
        )
        with self.assertNumQueries(0):
            with self.assertRaisesMessage(ValueError, msg):
                b.save()

    def test_nullable_o2o_delete(self):
        """
        This is a comment
        """
        u = UndergroundBar.objects.create(place=self.p1)
        u.place_id = None
        u.save()
        self.p1.delete()
        self.assertTrue(UndergroundBar.objects.filter(pk=u.pk).exists())
        self.assertIsNone(UndergroundBar.objects.get(pk=u.pk).place)

    def test_hidden_accessor(self):
        """
        This is a comment
        """
        self.assertFalse(
            hasattr(
                Target,
                HiddenPointer._meta.get_field("target").remote_field.accessor_name,
            )
        )

    def test_related_object(self):
        """
        This is a comment
        """
        public_school = School.objects.create(is_public=True)
        public_director = Director.objects.create(school=public_school, is_temp=False)

        private_school = School.objects.create(is_public=False)
        private_director = Director.objects.create(school=private_school, is_temp=True)

        # Only one school is available via all() due to the custom default manager.
        self.assertSequenceEqual(School.objects.all(), [public_school])

        # Only one director is available via all() due to the custom default manager.
        self.assertSequenceEqual(Director.objects.all(), [public_director])

        self.assertEqual(public_director.school, public_school)
        self.assertEqual(public_school.director, public_director)

        # Make sure the base manager is used so that the related objects
        # is still accessible even if the default manager doesn't normally
        # allow it.
        self.assertEqual(private_director.school, private_school)

        # Make sure the base manager is used so that an student can still access
        # its related school even if the default manager doesn't normally
        # allow it.
        self.assertEqual(private_school.director, private_director)

        School._meta.base_manager_name = "objects"
        School._meta._expire_cache()
        try:
            private_director = Director._base_manager.get(pk=private_director.pk)
            with self.assertRaises(School.DoesNotExist):
                private_director.school
        finally:
            School._meta.base_manager_name = None
            School._meta._expire_cache()

        Director._meta.base_manager_name = "objects"
        Director._meta._expire_cache()
        try:
            private_school = School._base_manager.get(pk=private_school.pk)
            with self.assertRaises(Director.DoesNotExist):
                private_school.director
        finally:
            Director._meta.base_manager_name = None
            Director._meta._expire_cache()

    def test_create_reverse_o2o_error(self):
        """
        This is a comment
        """
        msg = "The following fields do not exist in this model: restaurant"
        with self.assertRaisesMessage(ValueError, msg):
            Place.objects.create(restaurant=self.r1)

    def test_get_or_create_reverse_o2o_error(self):
        """
        This is a comment
        """
        msg = "The following fields do not exist in this model: restaurant"
        r2 = Restaurant.objects.create(
            place=self.p2, serves_hot_dogs=True, serves_pizza=False
        )
        with self.assertRaisesMessage(ValueError, msg):
            Place.objects.get_or_create(name="nonexistent", defaults={"restaurant": r2})

    def test_update_or_create_reverse_o2o_error(self):
        """
        This is a comment
        """
        msg = "The following fields do not exist in this model: restaurant"
        r2 = Restaurant.objects.create(
            place=self.p2, serves_hot_dogs=True, serves_pizza=False
        )
        with self.assertRaisesMessage(ValueError, msg):
            Place.objects.update_or_create(
                name="nonexistent", defaults={"restaurant": r2}
            )

    def test_hasattr_related_object(self):
        # The exception raised on attribute access when a related object
        # doesn't exist should be an instance of a subclass of `AttributeError`
        # refs #21563
        """
        This is a comment
        """
        self.assertFalse(hasattr(Director(), "director"))
        self.assertFalse(hasattr(School(), "school"))

    def test_update_one_to_one_pk(self):
        """
        This is a comment
        """
        p1 = Place.objects.create()
        p2 = Place.objects.create()
        r1 = Restaurant.objects.create(place=p1)
        r2 = Restaurant.objects.create(place=p2)
        w = Waiter.objects.create(restaurant=r1)

        Waiter.objects.update(restaurant=r2)
        w.refresh_from_db()
        self.assertEqual(w.restaurant, r2)

    def test_rel_pk_subquery(self):
        """
        This is a comment
        """
        r = Restaurant.objects.first()
        q1 = Restaurant.objects.filter(place_id=r.pk)
        # Subquery using primary key and a query against the
        # same model works correctly.
        q2 = Restaurant.objects.filter(place_id__in=q1)
        self.assertSequenceEqual(q2, [r])
        # Subquery using 'pk__in' instead of 'place_id__in' work, too.
        q2 = Restaurant.objects.filter(
            pk__in=Restaurant.objects.filter(place__id=r.place.pk)
        )
        self.assertSequenceEqual(q2, [r])
        q3 = Restaurant.objects.filter(place__in=Place.objects.all())
        self.assertSequenceEqual(q3, [r])
        q4 = Restaurant.objects.filter(place__in=Place.objects.filter(id=r.pk))
        self.assertSequenceEqual(q4, [r])

    def test_rel_pk_exact(self):
        """
        This is a comment
        """
        r = Restaurant.objects.first()
        r2 = Restaurant.objects.filter(pk__exact=r).first()
        self.assertEqual(r, r2)

    def test_primary_key_to_field_filter(self):
        """
        This is a comment
        """
        target = Target.objects.create(name="foo")
        pointer = ToFieldPointer.objects.create(target=target)
        self.assertSequenceEqual(
            ToFieldPointer.objects.filter(target=target), [pointer]
        )
        self.assertSequenceEqual(
            ToFieldPointer.objects.filter(pk__exact=pointer), [pointer]
        )

    def test_cached_relation_invalidated_on_save(self):
        """
        This is a comment
        """
        self.assertEqual(self.b1.place, self.p1)  # caches b1.place
        self.b1.place_id = self.p2.pk
        self.b1.save()
        self.assertEqual(self.b1.place, self.p2)

    def test_get_prefetch_queryset_warning(self):
        """
        This is a comment
        """
        places = Place.objects.all()
        msg = (
            "get_prefetch_queryset() is deprecated. Use get_prefetch_querysets() "
            "instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            Place.bar.get_prefetch_queryset(places)

    def test_get_prefetch_querysets_invalid_querysets_length(self):
        """
        This is a comment
        """
        places = Place.objects.all()
        msg = (
            "querysets argument of get_prefetch_querysets() should have a length of 1."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Place.bar.get_prefetch_querysets(
                instances=places,
                querysets=[Bar.objects.all(), Bar.objects.all()],
            )
