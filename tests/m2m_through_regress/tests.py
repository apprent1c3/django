from io import StringIO

from django.contrib.auth.models import User
from django.core import management
from django.test import TestCase

from .models import Car, CarDriver, Driver, Group, Membership, Person, UserMembership


class M2MThroughTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Setup test data for the application.

        This class method creates a set of predefined test data, including persons, groups, users, and their respective memberships.
        The test data includes two persons (Bob and Jim), two groups (Rock and Roll), and two users (frank and jane).
        Additionally, membership relationships are established between persons and groups, as well as between users and groups, with some memberships having an associated price.

        The created test data can be used as a foundation for writing test cases, allowing for a consistent and reliable testing environment.
        The test data is created as class attributes, making it accessible throughout the test suite.
        """
        cls.bob = Person.objects.create(name="Bob")
        cls.jim = Person.objects.create(name="Jim")

        cls.rock = Group.objects.create(name="Rock")
        cls.roll = Group.objects.create(name="Roll")

        cls.frank = User.objects.create_user("frank", "frank@example.com", "password")
        cls.jane = User.objects.create_user("jane", "jane@example.com", "password")

        # normal intermediate model
        cls.bob_rock = Membership.objects.create(person=cls.bob, group=cls.rock)
        cls.bob_roll = Membership.objects.create(
            person=cls.bob, group=cls.roll, price=50
        )
        cls.jim_rock = Membership.objects.create(
            person=cls.jim, group=cls.rock, price=50
        )

        # intermediate model with custom id column
        cls.frank_rock = UserMembership.objects.create(user=cls.frank, group=cls.rock)
        cls.frank_roll = UserMembership.objects.create(user=cls.frank, group=cls.roll)
        cls.jane_rock = UserMembership.objects.create(user=cls.jane, group=cls.rock)

    def test_retrieve_reverse_m2m_items(self):
        self.assertCountEqual(self.bob.group_set.all(), [self.rock, self.roll])

    def test_retrieve_forward_m2m_items(self):
        self.assertSequenceEqual(self.roll.members.all(), [self.bob])

    def test_retrieve_reverse_m2m_items_via_custom_id_intermediary(self):
        self.assertCountEqual(self.frank.group_set.all(), [self.rock, self.roll])

    def test_retrieve_forward_m2m_items_via_custom_id_intermediary(self):
        self.assertSequenceEqual(self.roll.user_members.all(), [self.frank])

    def test_join_trimming_forwards(self):
        """
        Too many copies of the intermediate table aren't involved when doing a
        join (#8046, #8254).
        """
        self.assertSequenceEqual(
            self.rock.members.filter(membership__price=50),
            [self.jim],
        )

    def test_join_trimming_reverse(self):
        self.assertSequenceEqual(
            self.bob.group_set.filter(membership__price=50),
            [self.roll],
        )


class M2MThroughSerializationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bob = Person.objects.create(name="Bob")
        cls.roll = Group.objects.create(name="Roll")
        cls.bob_roll = Membership.objects.create(person=cls.bob, group=cls.roll)

    def test_serialization(self):
        "m2m-through models aren't serialized as m2m fields. Refs #8134"
        pks = {
            "p_pk": self.bob.pk,
            "g_pk": self.roll.pk,
            "m_pk": self.bob_roll.pk,
            "app_label": "m2m_through_regress",
        }

        out = StringIO()
        management.call_command(
            "dumpdata", "m2m_through_regress", format="json", stdout=out
        )
        self.assertJSONEqual(
            out.getvalue().strip(),
            '[{"pk": %(m_pk)s, "model": "m2m_through_regress.membership", '
            '"fields": {"person": %(p_pk)s, "price": 100, "group": %(g_pk)s}}, '
            '{"pk": %(p_pk)s, "model": "m2m_through_regress.person", '
            '"fields": {"name": "Bob"}}, '
            '{"pk": %(g_pk)s, "model": "m2m_through_regress.group", '
            '"fields": {"name": "Roll"}}]' % pks,
        )

        out = StringIO()
        management.call_command(
            "dumpdata", "m2m_through_regress", format="xml", indent=2, stdout=out
        )
        self.assertXMLEqual(
            out.getvalue().strip(),
            """
<?xml version="1.0" encoding="utf-8"?>
<django-objects version="1.0">
  <object pk="%(m_pk)s" model="%(app_label)s.membership">
    <field to="%(app_label)s.person" name="person" rel="ManyToOneRel">%(p_pk)s</field>
    <field to="%(app_label)s.group" name="group" rel="ManyToOneRel">%(g_pk)s</field>
    <field type="IntegerField" name="price">100</field>
  </object>
  <object pk="%(p_pk)s" model="%(app_label)s.person">
    <field type="CharField" name="name">Bob</field>
  </object>
  <object pk="%(g_pk)s" model="%(app_label)s.group">
    <field type="CharField" name="name">Roll</field>
  </object>
</django-objects>
        """.strip()
            % pks,
        )


class ToFieldThroughTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the test class.

        This method creates test instances of cars and drivers, and establishes relationships between them.
        It creates a car with a driver, as well as additional unused cars and drivers for testing purposes.
        The test data is stored as class attributes for use in test methods.

        """
        cls.car = Car.objects.create(make="Toyota")
        cls.driver = Driver.objects.create(name="Ryan Briscoe")
        CarDriver.objects.create(car=cls.car, driver=cls.driver)
        # We are testing if wrong objects get deleted due to using wrong
        # field value in m2m queries. So, it is essential that the pk
        # numberings do not match.
        # Create one intentionally unused driver to mix up the autonumbering
        cls.unused_driver = Driver.objects.create(name="Barney Gumble")
        # And two intentionally unused cars.
        cls.unused_car1 = Car.objects.create(make="Trabant")
        cls.unused_car2 = Car.objects.create(make="Wartburg")

    def test_to_field(self):
        self.assertSequenceEqual(self.car.drivers.all(), [self.driver])

    def test_to_field_reverse(self):
        self.assertSequenceEqual(self.driver.car_set.all(), [self.car])

    def test_to_field_clear_reverse(self):
        self.driver.car_set.clear()
        self.assertSequenceEqual(self.driver.car_set.all(), [])

    def test_to_field_clear(self):
        """

        Tests that the to_field 'drivers' is cleared successfully.

        This method verifies that after clearing the drivers attribute,
        it returns an empty sequence of drivers, confirming the successful removal of all drivers.

        """
        self.car.drivers.clear()
        self.assertSequenceEqual(self.car.drivers.all(), [])

    # Low level tests for _add_items and _remove_items. We test these methods
    # because .add/.remove aren't available for m2m fields with through, but
    # through is the only way to set to_field currently. We do want to make
    # sure these methods are ready if the ability to use .add or .remove with
    # to_field relations is added some day.
    def test_add(self):
        """

        Tests the addition of a driver to a car's drivers collection.

        Checks that the function successfully adds a new driver to the existing list of drivers.
        It first verifies the initial state of the drivers collection and then adds a new driver.
        Finally, it asserts that the updated collection contains both the original and new drivers.

        """
        self.assertSequenceEqual(self.car.drivers.all(), [self.driver])
        # Yikes - barney is going to drive...
        self.car.drivers._add_items("car", "driver", self.unused_driver)
        self.assertSequenceEqual(
            self.car.drivers.all(),
            [self.unused_driver, self.driver],
        )

    def test_m2m_relations_unusable_on_null_to_field(self):
        nullcar = Car(make=None)
        msg = (
            '"<Car: None>" needs to have a value for field "make" before this '
            "many-to-many relationship can be used."
        )
        with self.assertRaisesMessage(ValueError, msg):
            nullcar.drivers.all()

    def test_m2m_relations_unusable_on_null_pk_obj(self):
        """
        Tests that attempting to access a many-to-many relation on an object without a primary key value raises a ValueError, as objects must have a primary key value before their many-to-many relationships can be used.
        """
        msg = (
            "'Car' instance needs to have a primary key value before a "
            "many-to-many relationship can be used."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Car(make="Ford").drivers.all()

    def test_add_related_null(self):
        """

        Tests that adding a related object with a null value to a car's drivers raises a ValueError.

        The test verifies that an attempt to add a driver with a null name to a car's drivers
        results in an error message indicating that the value for the \"driver\" field is None.

        """
        nulldriver = Driver.objects.create(name=None)
        msg = 'Cannot add "<Driver: None>": the value for field "driver" is None'
        with self.assertRaisesMessage(ValueError, msg):
            self.car.drivers._add_items("car", "driver", nulldriver)

    def test_add_reverse(self):
        car2 = Car.objects.create(make="Honda")
        self.assertCountEqual(self.driver.car_set.all(), [self.car])
        self.driver.car_set._add_items("driver", "car", car2)
        self.assertCountEqual(self.driver.car_set.all(), [self.car, car2])

    def test_add_null_reverse(self):
        """
        Tests that adding a Car object with a null 'make' field to a driver's car set raises a ValueError.

        This function verifies that the _add_items method correctly handles attempts to add a Car object with a missing 'make' field, 
        ensuring data integrity by rejecting such additions and providing a meaningful error message instead.
        """
        nullcar = Car.objects.create(make=None)
        msg = 'Cannot add "<Car: None>": the value for field "car" is None'
        with self.assertRaisesMessage(ValueError, msg):
            self.driver.car_set._add_items("driver", "car", nullcar)

    def test_add_null_reverse_related(self):
        """
        Tests the behavior of adding a reverse related object to a many-to-many relationship 
        when the parent object has a null field.

        Verifies that attempting to add a related object to an instance of Driver that 
        has a null 'name' field raises a ValueError with a specific error message, as 
        the 'name' field is required before the relationship can be used.
        """
        nulldriver = Driver.objects.create(name=None)
        msg = (
            '"<Driver: None>" needs to have a value for field "name" before '
            "this many-to-many relationship can be used."
        )
        with self.assertRaisesMessage(ValueError, msg):
            nulldriver.car_set._add_items("driver", "car", self.car)

    def test_remove(self):
        """

        Test removal of a driver from a car.

        Verifies that the driver can be successfully removed from the car's list of drivers.
        The test checks the initial state of the car's drivers, removes the driver, and then
        assures that the driver is no longer in the list.

        """
        self.assertSequenceEqual(self.car.drivers.all(), [self.driver])
        self.car.drivers._remove_items("car", "driver", self.driver)
        self.assertSequenceEqual(self.car.drivers.all(), [])

    def test_remove_reverse(self):
        """
        Tests the removal of a car from a driver's car set in reverse, verifying that the car is successfully removed and the resulting set is empty.
        """
        self.assertSequenceEqual(self.driver.car_set.all(), [self.car])
        self.driver.car_set._remove_items("driver", "car", self.car)
        self.assertSequenceEqual(self.driver.car_set.all(), [])


class ThroughLoadDataTestCase(TestCase):
    fixtures = ["m2m_through"]

    def test_sequence_creation(self):
        """
        Sequences on an m2m_through are created for the through model, not a
        phantom auto-generated m2m table (#11107).
        """
        out = StringIO()
        management.call_command(
            "dumpdata", "m2m_through_regress", format="json", stdout=out
        )
        self.assertJSONEqual(
            out.getvalue().strip(),
            '[{"pk": 1, "model": "m2m_through_regress.usermembership", '
            '"fields": {"price": 100, "group": 1, "user": 1}}, '
            '{"pk": 1, "model": "m2m_through_regress.person", '
            '"fields": {"name": "Guido"}}, '
            '{"pk": 1, "model": "m2m_through_regress.group", '
            '"fields": {"name": "Python Core Group"}}]',
        )
