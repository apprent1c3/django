from django.db import models
from django.test import TestCase

from .models import (
    Book,
    Car,
    CustomManager,
    CustomQuerySet,
    DeconstructibleCustomManager,
    FastCarAsBase,
    FastCarAsDefault,
    FunPerson,
    OneToOneRestrictedModel,
    Person,
    PersonFromAbstract,
    PersonManager,
    PublishedBookManager,
    RelatedModel,
    RestrictedModel,
)


class CustomManagerTests(TestCase):
    custom_manager_names = [
        "custom_queryset_default_manager",
        "custom_queryset_custom_manager",
    ]

    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for testing purposes.

        This class method initializes a set of predefined test data, including books and people.
        It creates two book instances with different publication statuses and two person instances with varying characteristics.
        The test data is stored as class attributes, allowing for easy access and reuse throughout the testing process.
        The created data includes books with titles, authors, and publication statuses, as well as people with names and personalities.
        This setup enables comprehensive testing of the application's functionality and ensures consistency across tests.
        """
        cls.b1 = Book.published_objects.create(
            title="How to program", author="Rodney Dangerfield", is_published=True
        )
        cls.b2 = Book.published_objects.create(
            title="How to be smart", author="Albert Einstein", is_published=False
        )

        cls.p1 = Person.objects.create(first_name="Bugs", last_name="Bunny", fun=True)
        cls.droopy = Person.objects.create(
            first_name="Droopy", last_name="Dog", fun=False
        )

    def test_custom_manager_basic(self):
        """
        Test a custom Manager method.
        """
        self.assertQuerySetEqual(Person.objects.get_fun_people(), ["Bugs Bunny"], str)

    def test_queryset_copied_to_default(self):
        """
        The methods of a custom QuerySet are properly copied onto the
        default Manager.
        """
        for manager_name in self.custom_manager_names:
            with self.subTest(manager_name=manager_name):
                manager = getattr(Person, manager_name)

                # Public methods are copied
                manager.public_method()
                # Private methods are not copied
                with self.assertRaises(AttributeError):
                    manager._private_method()

    def test_manager_honors_queryset_only(self):
        for manager_name in self.custom_manager_names:
            with self.subTest(manager_name=manager_name):
                manager = getattr(Person, manager_name)
                # Methods with queryset_only=False are copied even if they are private.
                manager._optin_private_method()
                # Methods with queryset_only=True aren't copied even if they are public.
                msg = (
                    "%r object has no attribute 'optout_public_method'"
                    % manager.__class__.__name__
                )
                with self.assertRaisesMessage(AttributeError, msg):
                    manager.optout_public_method()

    def test_manager_use_queryset_methods(self):
        """
        Custom manager will use the queryset methods
        """
        for manager_name in self.custom_manager_names:
            with self.subTest(manager_name=manager_name):
                manager = getattr(Person, manager_name)
                queryset = manager.filter()
                self.assertQuerySetEqual(queryset, ["Bugs Bunny"], str)
                self.assertIs(queryset._filter_CustomQuerySet, True)

                # Specialized querysets inherit from our custom queryset.
                queryset = manager.values_list("first_name", flat=True).filter()
                self.assertEqual(list(queryset), ["Bugs"])
                self.assertIs(queryset._filter_CustomQuerySet, True)

                self.assertIsInstance(queryset.values(), CustomQuerySet)
                self.assertIsInstance(queryset.values().values(), CustomQuerySet)
                self.assertIsInstance(queryset.values_list().values(), CustomQuerySet)

    def test_init_args(self):
        """
        The custom manager __init__() argument has been set.
        """
        self.assertEqual(Person.custom_queryset_custom_manager.init_arg, "hello")

    def test_manager_attributes(self):
        """
        Custom manager method is only available on the manager and not on
        querysets.
        """
        Person.custom_queryset_custom_manager.manager_only()
        msg = "'CustomQuerySet' object has no attribute 'manager_only'"
        with self.assertRaisesMessage(AttributeError, msg):
            Person.custom_queryset_custom_manager.all().manager_only()

    def test_queryset_and_manager(self):
        """
        Queryset method doesn't override the custom manager method.
        """
        queryset = Person.custom_queryset_custom_manager.filter()
        self.assertQuerySetEqual(queryset, ["Bugs Bunny"], str)
        self.assertIs(queryset._filter_CustomManager, True)

    def test_related_manager(self):
        """
        The related managers extend the default manager.
        """
        self.assertIsInstance(self.droopy.books, PublishedBookManager)
        self.assertIsInstance(self.b2.authors, PersonManager)

    def test_no_objects(self):
        """
        The default manager, "objects", doesn't exist, because a custom one
        was provided.
        """
        msg = "type object 'Book' has no attribute 'objects'"
        with self.assertRaisesMessage(AttributeError, msg):
            Book.objects

    def test_filtering(self):
        """
        Custom managers respond to usual filtering methods
        """
        self.assertQuerySetEqual(
            Book.published_objects.all(),
            [
                "How to program",
            ],
            lambda b: b.title,
        )

    def test_fk_related_manager(self):
        """

        Tests the functionality of foreign key related managers.

        Verifies that the related objects are correctly retrieved and filtered 
        based on the defined managers, including the default manager and custom 
        managers for fun and boring people. The test covers both the 
        `favorite_books` manager which retrieves all people who have the book 
        as a favorite, and the `fun_people_favorite_books` and 
        `boring_people_favorite_books` managers which filter people based on 
        their 'fun' status.

        The test ensures that the related objects are correctly ordered and 
        retrieved, and that the custom managers return the expected results.

        """
        Person.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_book=self.b1
        )
        Person.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_book=self.b1
        )
        FunPerson.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_book=self.b1
        )
        FunPerson.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_book=self.b1
        )

        self.assertQuerySetEqual(
            self.b1.favorite_books.order_by("first_name").all(),
            [
                "Bugs",
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.fun_people_favorite_books.all(),
            [
                "Bugs",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.favorite_books(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.favorite_books(manager="fun_people").all(),
            [
                "Bugs",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_gfk_related_manager(self):
        Person.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_thing=self.b1
        )
        Person.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_thing=self.b1
        )
        FunPerson.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_thing=self.b1
        )
        FunPerson.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_thing=self.b1
        )

        self.assertQuerySetEqual(
            self.b1.favorite_things.all(),
            [
                "Bugs",
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.fun_people_favorite_things.all(),
            [
                "Bugs",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.favorite_things(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.favorite_things(manager="fun_people").all(),
            [
                "Bugs",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_m2m_related_manager(self):
        """

        Tests the functionality of many-to-many related managers.

        This test case verifies the correctness of adding and querying related objects 
        through multiple managers, including the default manager and custom managers 
        ('fun_people' and 'boring_people'). It ensures that the related objects are 
        properly filtered based on the 'fun' attribute, and that the results are 
        returned in the expected order.

        The test covers the following scenarios:
        - Adding authors to an object through the default 'authors' manager
        - Adding authors to an object through the 'fun_authors' manager
        - Querying authors using the default manager, ordered by first name
        - Querying authors using custom managers, ordered by first name

        """
        bugs = Person.objects.create(first_name="Bugs", last_name="Bunny", fun=True)
        self.b1.authors.add(bugs)
        droopy = Person.objects.create(first_name="Droopy", last_name="Dog", fun=False)
        self.b1.authors.add(droopy)
        bugs = FunPerson.objects.create(first_name="Bugs", last_name="Bunny", fun=True)
        self.b1.fun_authors.add(bugs)
        droopy = FunPerson.objects.create(
            first_name="Droopy", last_name="Dog", fun=False
        )
        self.b1.fun_authors.add(droopy)

        self.assertQuerySetEqual(
            self.b1.authors.order_by("first_name").all(),
            [
                "Bugs",
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.fun_authors.order_by("first_name").all(),
            [
                "Bugs",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.authors(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.authors(manager="fun_people").all(),
            [
                "Bugs",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_removal_through_default_fk_related_manager(self, bulk=True):
        """
        Tests the removal of related objects through the default foreign key related manager.

        This function checks the behavior of removing objects from a related manager, 
        both individually and in bulk. It verifies that the related objects are 
        correctly removed from the manager and that the underlying database queries 
        are executed as expected.

        Specifically, it tests the following scenarios:
        - Removing a single object from the related manager
        - Removing multiple objects from the related manager in bulk
        - Clearing all objects from the related manager

        The tests cover the case where related objects are managed through a default 
        foreign key related manager, and verifies that the results match the expected 
        outcome after each removal operation.
        """
        bugs = FunPerson.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_book=self.b1
        )
        droopy = FunPerson.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_book=self.b1
        )

        self.b1.fun_people_favorite_books.remove(droopy, bulk=bulk)
        self.assertQuerySetEqual(
            FunPerson._base_manager.filter(favorite_book=self.b1),
            [
                "Bugs",
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

        self.b1.fun_people_favorite_books.remove(bugs, bulk=bulk)
        self.assertQuerySetEqual(
            FunPerson._base_manager.filter(favorite_book=self.b1),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        bugs.favorite_book = self.b1
        bugs.save()

        self.b1.fun_people_favorite_books.clear(bulk=bulk)
        self.assertQuerySetEqual(
            FunPerson._base_manager.filter(favorite_book=self.b1),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_slow_removal_through_default_fk_related_manager(self):
        self.test_removal_through_default_fk_related_manager(bulk=False)

    def test_removal_through_specified_fk_related_manager(self, bulk=True):
        """
        Tests removal of objects from a related manager through a specified foreign key.

        This function covers scenarios where an object is removed from a related manager
        using the `remove` method and when the related manager is cleared using the `clear` method.
        The test verifies the correctness of the removal operation in both bulk and non-bulk modes.

        The test case involves creating two `Person` objects, 'Bugs' and 'Droopy', with different
        'fun' attributes, and associating them with a `Book` object. It then tests the removal of
        'Droopy' from the 'boring_people' and 'fun_people' related managers, and finally clears
        the 'fun_people' related manager.

        The function asserts that the removal and clearing operations are successful by checking
        the resulting query sets and verifying that the expected objects are removed or retained.
        """
        Person.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_book=self.b1
        )
        droopy = Person.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_book=self.b1
        )

        # The fun manager DOESN'T remove boring people.
        self.b1.favorite_books(manager="fun_people").remove(droopy, bulk=bulk)
        self.assertQuerySetEqual(
            self.b1.favorite_books(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        # The boring manager DOES remove boring people.
        self.b1.favorite_books(manager="boring_people").remove(droopy, bulk=bulk)
        self.assertQuerySetEqual(
            self.b1.favorite_books(manager="boring_people").all(),
            [],
            lambda c: c.first_name,
            ordered=False,
        )
        droopy.favorite_book = self.b1
        droopy.save()

        # The fun manager ONLY clears fun people.
        self.b1.favorite_books(manager="fun_people").clear(bulk=bulk)
        self.assertQuerySetEqual(
            self.b1.favorite_books(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.favorite_books(manager="fun_people").all(),
            [],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_slow_removal_through_specified_fk_related_manager(self):
        self.test_removal_through_specified_fk_related_manager(bulk=False)

    def test_removal_through_default_gfk_related_manager(self, bulk=True):
        """
        Tests the removal of related objects through a default Generic Foreign Key (GFK) related manager.

        This function creates test instances of FunPerson, adds them to a favorite thing, and then tests the removal
        of these instances using the remove method of the related manager. It also tests the removal of an object that
        has been reassigned to a different favorite thing.

        The test covers different removal scenarios, including removing one or multiple objects at once, and verifies
        that the changes are correctly reflected in the database.

        The `bulk` parameter determines whether the removal should be performed in bulk or not. The test is designed
        to ensure that the related manager correctly handles both bulk and non-bulk removals.

        The function uses assertions to verify that the expected results are obtained after each removal operation,
        providing a robust test of the related manager's functionality.
        """
        bugs = FunPerson.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_thing=self.b1
        )
        droopy = FunPerson.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_thing=self.b1
        )

        self.b1.fun_people_favorite_things.remove(droopy, bulk=bulk)
        self.assertQuerySetEqual(
            FunPerson._base_manager.order_by("first_name").filter(
                favorite_thing_id=self.b1.pk
            ),
            [
                "Bugs",
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

        self.b1.fun_people_favorite_things.remove(bugs, bulk=bulk)
        self.assertQuerySetEqual(
            FunPerson._base_manager.order_by("first_name").filter(
                favorite_thing_id=self.b1.pk
            ),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        bugs.favorite_book = self.b1
        bugs.save()

        self.b1.fun_people_favorite_things.clear(bulk=bulk)
        self.assertQuerySetEqual(
            FunPerson._base_manager.order_by("first_name").filter(
                favorite_thing_id=self.b1.pk
            ),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_slow_removal_through_default_gfk_related_manager(self):
        self.test_removal_through_default_gfk_related_manager(bulk=False)

    def test_removal_through_specified_gfk_related_manager(self, bulk=True):
        Person.objects.create(
            first_name="Bugs", last_name="Bunny", fun=True, favorite_thing=self.b1
        )
        droopy = Person.objects.create(
            first_name="Droopy", last_name="Dog", fun=False, favorite_thing=self.b1
        )

        # The fun manager DOESN'T remove boring people.
        self.b1.favorite_things(manager="fun_people").remove(droopy, bulk=bulk)
        self.assertQuerySetEqual(
            self.b1.favorite_things(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

        # The boring manager DOES remove boring people.
        self.b1.favorite_things(manager="boring_people").remove(droopy, bulk=bulk)
        self.assertQuerySetEqual(
            self.b1.favorite_things(manager="boring_people").all(),
            [],
            lambda c: c.first_name,
            ordered=False,
        )
        droopy.favorite_thing = self.b1
        droopy.save()

        # The fun manager ONLY clears fun people.
        self.b1.favorite_things(manager="fun_people").clear(bulk=bulk)
        self.assertQuerySetEqual(
            self.b1.favorite_things(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.favorite_things(manager="fun_people").all(),
            [],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_slow_removal_through_specified_gfk_related_manager(self):
        self.test_removal_through_specified_gfk_related_manager(bulk=False)

    def test_removal_through_default_m2m_related_manager(self):
        """

        Tests the removal of related objects through the default many-to-many related manager.

        This test case exercises the functionality of adding, removing, and clearing related objects
        using the default manager for a many-to-many relationship. It verifies that the expected
        objects are present or absent after these operations, ensuring the correctness of the removal
        and clearing functionality.

        The test scenario involves creating objects, adding them to and removing them from a many-to-many
        relationship, and validating the resulting state of the relationship.

        """
        bugs = FunPerson.objects.create(first_name="Bugs", last_name="Bunny", fun=True)
        self.b1.fun_authors.add(bugs)
        droopy = FunPerson.objects.create(
            first_name="Droopy", last_name="Dog", fun=False
        )
        self.b1.fun_authors.add(droopy)

        self.b1.fun_authors.remove(droopy)
        self.assertQuerySetEqual(
            self.b1.fun_authors.through._default_manager.all(),
            [
                "Bugs",
                "Droopy",
            ],
            lambda c: c.funperson.first_name,
            ordered=False,
        )

        self.b1.fun_authors.remove(bugs)
        self.assertQuerySetEqual(
            self.b1.fun_authors.through._default_manager.all(),
            [
                "Droopy",
            ],
            lambda c: c.funperson.first_name,
            ordered=False,
        )
        self.b1.fun_authors.add(bugs)

        self.b1.fun_authors.clear()
        self.assertQuerySetEqual(
            self.b1.fun_authors.through._default_manager.all(),
            [
                "Droopy",
            ],
            lambda c: c.funperson.first_name,
            ordered=False,
        )

    def test_removal_through_specified_m2m_related_manager(self):
        bugs = Person.objects.create(first_name="Bugs", last_name="Bunny", fun=True)
        self.b1.authors.add(bugs)
        droopy = Person.objects.create(first_name="Droopy", last_name="Dog", fun=False)
        self.b1.authors.add(droopy)

        # The fun manager DOESN'T remove boring people.
        self.b1.authors(manager="fun_people").remove(droopy)
        self.assertQuerySetEqual(
            self.b1.authors(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )

        # The boring manager DOES remove boring people.
        self.b1.authors(manager="boring_people").remove(droopy)
        self.assertQuerySetEqual(
            self.b1.authors(manager="boring_people").all(),
            [],
            lambda c: c.first_name,
            ordered=False,
        )
        self.b1.authors.add(droopy)

        # The fun manager ONLY clears fun people.
        self.b1.authors(manager="fun_people").clear()
        self.assertQuerySetEqual(
            self.b1.authors(manager="boring_people").all(),
            [
                "Droopy",
            ],
            lambda c: c.first_name,
            ordered=False,
        )
        self.assertQuerySetEqual(
            self.b1.authors(manager="fun_people").all(),
            [],
            lambda c: c.first_name,
            ordered=False,
        )

    def test_deconstruct_default(self):
        """
        ..: Tests the deconstruction of the default Django model Manager instance.

            Verifies that the deconstructed values match the expected output, ensuring
            the manager can be correctly reconstructed. The test checks that the 
            manager is not used as a queryset, its import path is correct, and it has 
            no positional or keyword arguments.
        """
        mgr = models.Manager()
        as_manager, mgr_path, qs_path, args, kwargs = mgr.deconstruct()
        self.assertFalse(as_manager)
        self.assertEqual(mgr_path, "django.db.models.manager.Manager")
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {})

    def test_deconstruct_as_manager(self):
        mgr = CustomQuerySet.as_manager()
        as_manager, mgr_path, qs_path, args, kwargs = mgr.deconstruct()
        self.assertTrue(as_manager)
        self.assertEqual(qs_path, "custom_managers.models.CustomQuerySet")

    def test_deconstruct_from_queryset(self):
        """

        Test the deconstruction of a DeconstructibleCustomManager instance from a queryset.

        This test case verifies that the deconstruct() method returns the correct manager path,
        queryset path, positional arguments, and keyword arguments. It checks the deconstruction
        with and without keyword arguments.

        The test covers the following scenarios:

        - Deconstruction with only positional arguments
        - Deconstruction with both positional and keyword arguments

        It ensures that the returned values are correctly identified as not being a manager instance,
        and that the manager path, positional arguments, and keyword arguments match the expected values.

        """
        mgr = DeconstructibleCustomManager("a", "b")
        as_manager, mgr_path, qs_path, args, kwargs = mgr.deconstruct()
        self.assertFalse(as_manager)
        self.assertEqual(
            mgr_path, "custom_managers.models.DeconstructibleCustomManager"
        )
        self.assertEqual(
            args,
            (
                "a",
                "b",
            ),
        )
        self.assertEqual(kwargs, {})

        mgr = DeconstructibleCustomManager("x", "y", c=3, d=4)
        as_manager, mgr_path, qs_path, args, kwargs = mgr.deconstruct()
        self.assertFalse(as_manager)
        self.assertEqual(
            mgr_path, "custom_managers.models.DeconstructibleCustomManager"
        )
        self.assertEqual(
            args,
            (
                "x",
                "y",
            ),
        )
        self.assertEqual(kwargs, {"c": 3, "d": 4})

    def test_deconstruct_from_queryset_failing(self):
        """

        Tests whether deconstructing a custom manager instance fails as expected when the manager class was dynamically generated with 'from_queryset()' but does not inherit from the base custom manager class.

        The test verifies that the deconstruct method raises a ValueError with a specific error message, indicating that the manager class could not be found in the django.db.models.manager module. This ensures that the correct exception is raised when a dynamically generated manager class is not properly defined.

        """
        mgr = CustomManager("arg")
        msg = (
            "Could not find manager BaseCustomManagerFromCustomQuerySet in "
            "django.db.models.manager.\n"
            "Please note that you need to inherit from managers you "
            "dynamically generated with 'from_queryset()'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            mgr.deconstruct()

    def test_abstract_model_with_custom_manager_name(self):
        """
        A custom manager may be defined on an abstract model.
        It will be inherited by the abstract model's children.
        """
        PersonFromAbstract.abstract_persons.create(objects="Test")
        self.assertQuerySetEqual(
            PersonFromAbstract.abstract_persons.all(),
            ["Test"],
            lambda c: c.objects,
        )


class TestCars(TestCase):
    def test_managers(self):
        # Each model class gets a "_default_manager" attribute, which is a
        # reference to the first manager defined in the class.
        """
        .. method:: test_managers(self)

           Tests the custom model managers for the Car model.

           This test creates instances of Cars with different attributes and then 
           verifies that the custom managers return the correct results. It checks 
           the default manager, a custom manager named 'cars', and a custom manager 
           'fast_cars' that filters cars based on their top speed. The test also 
           checks the behavior of custom managers when used as the default manager 
           for a model, with both a custom manager named 'cars' for the 
           FastCarAsDefault model and a custom base manager named '_base_manager' 
           for the FastCarAsBase model.
        """
        Car.cars.create(name="Corvette", mileage=21, top_speed=180)
        Car.cars.create(name="Neon", mileage=31, top_speed=100)

        self.assertQuerySetEqual(
            Car._default_manager.order_by("name"),
            [
                "Corvette",
                "Neon",
            ],
            lambda c: c.name,
        )
        self.assertQuerySetEqual(
            Car.cars.order_by("name"),
            [
                "Corvette",
                "Neon",
            ],
            lambda c: c.name,
        )
        # alternate manager
        self.assertQuerySetEqual(
            Car.fast_cars.all(),
            [
                "Corvette",
            ],
            lambda c: c.name,
        )
        # explicit default manager
        self.assertQuerySetEqual(
            FastCarAsDefault.cars.order_by("name"),
            [
                "Corvette",
                "Neon",
            ],
            lambda c: c.name,
        )
        self.assertQuerySetEqual(
            FastCarAsDefault._default_manager.all(),
            [
                "Corvette",
            ],
            lambda c: c.name,
        )
        # explicit base manager
        self.assertQuerySetEqual(
            FastCarAsBase.cars.order_by("name"),
            [
                "Corvette",
                "Neon",
            ],
            lambda c: c.name,
        )
        self.assertQuerySetEqual(
            FastCarAsBase._base_manager.all(),
            [
                "Corvette",
            ],
            lambda c: c.name,
        )


class CustomManagersRegressTestCase(TestCase):
    def test_filtered_default_manager(self):
        """Even though the default manager filters out some records,
        we must still be able to save (particularly, save by updating
        existing records) those filtered instances. This is a
        regression test for #8990, #9527"""
        related = RelatedModel.objects.create(name="xyzzy")
        obj = RestrictedModel.objects.create(name="hidden", related=related)
        obj.name = "still hidden"
        obj.save()

        # If the hidden object wasn't seen during the save process,
        # there would now be two objects in the database.
        self.assertEqual(RestrictedModel.plain_manager.count(), 1)

    def test_refresh_from_db_when_default_manager_filters(self):
        """
        Model.refresh_from_db() works for instances hidden by the default
        manager.
        """
        book = Book._base_manager.create(is_published=False)
        Book._base_manager.filter(pk=book.pk).update(title="Hi")
        book.refresh_from_db()
        self.assertEqual(book.title, "Hi")

    def test_save_clears_annotations_from_base_manager(self):
        """Model.save() clears annotations from the base manager."""
        self.assertEqual(Book._meta.base_manager.name, "annotated_objects")
        book = Book.annotated_objects.create(title="Hunting")
        Person.objects.create(
            first_name="Bugs",
            last_name="Bunny",
            fun=True,
            favorite_book=book,
            favorite_thing_id=1,
        )
        book = Book.annotated_objects.first()
        self.assertEqual(book.favorite_avg, 1)  # Annotation from the manager.
        book.title = "New Hunting"
        # save() fails if annotations that involve related fields aren't
        # cleared before the update query.
        book.save()
        self.assertEqual(Book.annotated_objects.first().title, "New Hunting")

    def test_delete_related_on_filtered_manager(self):
        """Deleting related objects should also not be distracted by a
        restricted manager on the related object. This is a regression
        test for #2698."""
        related = RelatedModel.objects.create(name="xyzzy")

        for name, public in (("one", True), ("two", False), ("three", False)):
            RestrictedModel.objects.create(name=name, is_public=public, related=related)

        obj = RelatedModel.objects.get(name="xyzzy")
        obj.delete()

        # All of the RestrictedModel instances should have been
        # deleted, since they *all* pointed to the RelatedModel. If
        # the default manager is used, only the public one will be
        # deleted.
        self.assertEqual(len(RestrictedModel.plain_manager.all()), 0)

    def test_delete_one_to_one_manager(self):
        # The same test case as the last one, but for one-to-one
        # models, which are implemented slightly different internally,
        # so it's a different code path.
        obj = RelatedModel.objects.create(name="xyzzy")
        OneToOneRestrictedModel.objects.create(name="foo", is_public=False, related=obj)
        obj = RelatedModel.objects.get(name="xyzzy")
        obj.delete()
        self.assertEqual(len(OneToOneRestrictedModel.plain_manager.all()), 0)

    def test_queryset_with_custom_init(self):
        """
        BaseManager.get_queryset() should use kwargs rather than args to allow
        custom kwargs (#24911).
        """
        qs_custom = Person.custom_init_queryset_manager.all()
        qs_default = Person.objects.all()
        self.assertQuerySetEqual(qs_custom, qs_default)
