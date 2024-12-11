"""
Testing signals emitted on changing m2m relations.
"""

from django.db import models
from django.test import TestCase

from .models import Car, Part, Person, SportsCar


class ManyToManySignalsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up initial test data for the application.

        This method creates a set of predefined instances of cars, parts, and people to be used in tests.
        It populates the database with a selection of car models, car parts, and individuals, providing a consistent base for running tests.
        The created instances include car models such as VW, BMW, and Toyota, car parts like wheelset, doors, and engine, as well as people named Alice, Bob, Chuck, and Daisy.
        These test data instances are stored as class attributes, making them accessible throughout the test suite.
        """
        cls.vw = Car.objects.create(name="VW")
        cls.bmw = Car.objects.create(name="BMW")
        cls.toyota = Car.objects.create(name="Toyota")

        cls.wheelset = Part.objects.create(name="Wheelset")
        cls.doors = Part.objects.create(name="Doors")
        cls.engine = Part.objects.create(name="Engine")
        cls.airbag = Part.objects.create(name="Airbag")
        cls.sunroof = Part.objects.create(name="Sunroof")

        cls.alice = Person.objects.create(name="Alice")
        cls.bob = Person.objects.create(name="Bob")
        cls.chuck = Person.objects.create(name="Chuck")
        cls.daisy = Person.objects.create(name="Daisy")

    def setUp(self):
        self.m2m_changed_messages = []

    def m2m_changed_signal_receiver(self, signal, sender, **kwargs):
        message = {
            "instance": kwargs["instance"],
            "action": kwargs["action"],
            "reverse": kwargs["reverse"],
            "model": kwargs["model"],
        }
        if kwargs["pk_set"]:
            message["objects"] = list(
                kwargs["model"].objects.filter(pk__in=kwargs["pk_set"])
            )
        self.m2m_changed_messages.append(message)

    def tearDown(self):
        # disconnect all signal handlers
        models.signals.m2m_changed.disconnect(
            self.m2m_changed_signal_receiver, Car.default_parts.through
        )
        models.signals.m2m_changed.disconnect(
            self.m2m_changed_signal_receiver, Car.optional_parts.through
        )
        models.signals.m2m_changed.disconnect(
            self.m2m_changed_signal_receiver, Person.fans.through
        )
        models.signals.m2m_changed.disconnect(
            self.m2m_changed_signal_receiver, Person.friends.through
        )

    def _initialize_signal_car(self, add_default_parts_before_set_signal=False):
        """Install a listener on the two m2m relations."""
        models.signals.m2m_changed.connect(
            self.m2m_changed_signal_receiver, Car.optional_parts.through
        )
        if add_default_parts_before_set_signal:
            # adding a default part to our car - no signal listener installed
            self.vw.default_parts.add(self.sunroof)
        models.signals.m2m_changed.connect(
            self.m2m_changed_signal_receiver, Car.default_parts.through
        )

    def test_pk_set_on_repeated_add_remove(self):
        """
        m2m_changed is always fired, even for repeated calls to the same
        method, but the behavior of pk_sets differs by action.

        - For signals related to `add()`, only PKs that will actually be
          inserted are sent.
        - For `remove()` all PKs are sent, even if they will not affect the DB.
        """
        pk_sets_sent = []

        def handler(signal, sender, **kwargs):
            if kwargs["action"] in ["pre_add", "pre_remove"]:
                pk_sets_sent.append(kwargs["pk_set"])

        models.signals.m2m_changed.connect(handler, Car.default_parts.through)

        self.vw.default_parts.add(self.wheelset)
        self.vw.default_parts.add(self.wheelset)

        self.vw.default_parts.remove(self.wheelset)
        self.vw.default_parts.remove(self.wheelset)

        expected_pk_sets = [
            {self.wheelset.pk},
            set(),
            {self.wheelset.pk},
            {self.wheelset.pk},
        ]
        self.assertEqual(pk_sets_sent, expected_pk_sets)

        models.signals.m2m_changed.disconnect(handler, Car.default_parts.through)

    def test_m2m_relations_add_remove_clear(self):
        expected_messages = []

        self._initialize_signal_car(add_default_parts_before_set_signal=True)

        self.vw.default_parts.add(self.wheelset, self.doors, self.engine)
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors, self.engine, self.wheelset],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors, self.engine, self.wheelset],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

        # give the BMW and Toyota some doors as well
        self.doors.car_set.add(self.bmw, self.toyota)
        expected_messages.append(
            {
                "instance": self.doors,
                "action": "pre_add",
                "reverse": True,
                "model": Car,
                "objects": [self.bmw, self.toyota],
            }
        )
        expected_messages.append(
            {
                "instance": self.doors,
                "action": "post_add",
                "reverse": True,
                "model": Car,
                "objects": [self.bmw, self.toyota],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

    def test_m2m_relations_signals_remove_relation(self):
        """

        Tests the removal of many-to-many relations between Vehicle and Part instances via signals.

        Verifies that when a Part instance is removed from a Vehicle's default parts, 
        the 'pre_remove' and 'post_remove' signals are sent with the correct parameters, 
        including the affected Vehicle instance, the action being performed, and the Part instances being removed.

        """
        self._initialize_signal_car()
        # remove the engine from the self.vw and the airbag (which is not set
        # but is returned)
        self.vw.default_parts.remove(self.engine, self.airbag)
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.vw,
                    "action": "pre_remove",
                    "reverse": False,
                    "model": Part,
                    "objects": [self.airbag, self.engine],
                },
                {
                    "instance": self.vw,
                    "action": "post_remove",
                    "reverse": False,
                    "model": Part,
                    "objects": [self.airbag, self.engine],
                },
            ],
        )

    def test_m2m_relations_signals_give_the_self_vw_some_optional_parts(self):
        expected_messages = []

        self._initialize_signal_car()

        # give the self.vw some optional parts (second relation to same model)
        self.vw.optional_parts.add(self.airbag, self.sunroof)
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_add",
                "reverse": False,
                "model": Part,
                "objects": [self.airbag, self.sunroof],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_add",
                "reverse": False,
                "model": Part,
                "objects": [self.airbag, self.sunroof],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

        # add airbag to all the cars (even though the self.vw already has one)
        self.airbag.cars_optional.add(self.vw, self.bmw, self.toyota)
        expected_messages.append(
            {
                "instance": self.airbag,
                "action": "pre_add",
                "reverse": True,
                "model": Car,
                "objects": [self.bmw, self.toyota],
            }
        )
        expected_messages.append(
            {
                "instance": self.airbag,
                "action": "post_add",
                "reverse": True,
                "model": Car,
                "objects": [self.bmw, self.toyota],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

    def test_m2m_relations_signals_reverse_relation_with_custom_related_name(self):
        self._initialize_signal_car()
        # remove airbag from the self.vw (reverse relation with custom
        # related_name)
        self.airbag.cars_optional.remove(self.vw)
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.airbag,
                    "action": "pre_remove",
                    "reverse": True,
                    "model": Car,
                    "objects": [self.vw],
                },
                {
                    "instance": self.airbag,
                    "action": "post_remove",
                    "reverse": True,
                    "model": Car,
                    "objects": [self.vw],
                },
            ],
        )

    def test_m2m_relations_signals_clear_all_parts_of_the_self_vw(self):
        self._initialize_signal_car()
        # clear all parts of the self.vw
        self.vw.default_parts.clear()
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.vw,
                    "action": "pre_clear",
                    "reverse": False,
                    "model": Part,
                },
                {
                    "instance": self.vw,
                    "action": "post_clear",
                    "reverse": False,
                    "model": Part,
                },
            ],
        )

    def test_m2m_relations_signals_all_the_doors_off_of_cars(self):
        """
        Tests the many-to-many relation signals emitted when clearing all doors from a car.

         Verifies that the expected pre-clear and post-clear signals are sent when removing all doors associated with a car instance.

         This test case ensures that the m2m_changed messages are correctly generated, including the instance, action, reverse, and model information, for the 'pre_clear' and 'post_clear' actions.

        """
        self._initialize_signal_car()
        # take all the doors off of cars
        self.doors.car_set.clear()
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.doors,
                    "action": "pre_clear",
                    "reverse": True,
                    "model": Car,
                },
                {
                    "instance": self.doors,
                    "action": "post_clear",
                    "reverse": True,
                    "model": Car,
                },
            ],
        )

    def test_m2m_relations_signals_reverse_relation(self):
        self._initialize_signal_car()
        # take all the airbags off of cars (clear reverse relation with custom
        # related_name)
        self.airbag.cars_optional.clear()
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.airbag,
                    "action": "pre_clear",
                    "reverse": True,
                    "model": Car,
                },
                {
                    "instance": self.airbag,
                    "action": "post_clear",
                    "reverse": True,
                    "model": Car,
                },
            ],
        )

    def test_m2m_relations_signals_alternative_ways(self):
        """

        Tests the alternative ways that signals are sent for many-to-many relations.

        This test verifies that when adding or removing objects from a many-to-many relationship,
        the pre_add, post_add, pre_remove, and post_remove signals are sent as expected.
        It checks that the signal messages contain the correct instance, action, reverse,
        model, and objects, in the correct order.

        The test covers both the initial addition of an object to the relationship and
        the subsequent replacement of the related objects using the set method.

        """
        expected_messages = []

        self._initialize_signal_car()

        # alternative ways of setting relation:
        self.vw.default_parts.create(name="Windows")
        p6 = Part.objects.get(name="Windows")
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_add",
                "reverse": False,
                "model": Part,
                "objects": [p6],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_add",
                "reverse": False,
                "model": Part,
                "objects": [p6],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

        # direct assignment clears the set first, then adds
        self.vw.default_parts.set([self.wheelset, self.doors, self.engine])
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_remove",
                "reverse": False,
                "model": Part,
                "objects": [p6],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_remove",
                "reverse": False,
                "model": Part,
                "objects": [p6],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors, self.engine, self.wheelset],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors, self.engine, self.wheelset],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

    def test_m2m_relations_signals_clearing_removing(self):
        """

        Tests signal clearing and removing operations on many-to-many relations.

        This test case covers the scenario where a many-to-many relation is cleared and then 
        elements are added or removed from it, verifying that the corresponding signals are 
        sent correctly.

        It checks the pre and post signals for clear and add operations when replacing the 
        relation's elements, and the pre and post signals for remove operations when removing 
        specific elements without clearing the relation.

        The expected signals are verified to ensure that they match the actual signals sent 
        during these operations, providing confidence in the correct functioning of the 
        many-to-many relation signals.

        """
        expected_messages = []

        self._initialize_signal_car(add_default_parts_before_set_signal=True)

        # set by clearing.
        self.vw.default_parts.set([self.wheelset, self.doors, self.engine], clear=True)
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_clear",
                "reverse": False,
                "model": Part,
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_clear",
                "reverse": False,
                "model": Part,
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors, self.engine, self.wheelset],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors, self.engine, self.wheelset],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

        # set by only removing what's necessary.
        self.vw.default_parts.set([self.wheelset, self.doors], clear=False)
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "pre_remove",
                "reverse": False,
                "model": Part,
                "objects": [self.engine],
            }
        )
        expected_messages.append(
            {
                "instance": self.vw,
                "action": "post_remove",
                "reverse": False,
                "model": Part,
                "objects": [self.engine],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

    def test_m2m_relations_signals_when_inheritance(self):
        """
        Tests m2m relations signals when inheritance is involved.

        Checks the emission of pre and post add signals on both the parent and child
        models in an inheritance hierarchy, when adding related objects to a many-to-many
        field.

        Verifies that signals are sent with the correct instance, action, reverse flag,
        model, and objects, and that the expected sequence of signals is produced.

        This test case covers the following scenarios:

        - Adding a related object to a child model instance
        - Adding a child model instance to a parent model instance

        """
        expected_messages = []

        self._initialize_signal_car(add_default_parts_before_set_signal=True)

        # Signals still work when model inheritance is involved
        c4 = SportsCar.objects.create(name="Bugatti", price="1000000")
        c4b = Car.objects.get(name="Bugatti")
        c4.default_parts.set([self.doors])
        expected_messages.append(
            {
                "instance": c4,
                "action": "pre_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors],
            }
        )
        expected_messages.append(
            {
                "instance": c4,
                "action": "post_add",
                "reverse": False,
                "model": Part,
                "objects": [self.doors],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

        self.engine.car_set.add(c4)
        expected_messages.append(
            {
                "instance": self.engine,
                "action": "pre_add",
                "reverse": True,
                "model": Car,
                "objects": [c4b],
            }
        )
        expected_messages.append(
            {
                "instance": self.engine,
                "action": "post_add",
                "reverse": True,
                "model": Car,
                "objects": [c4b],
            }
        )
        self.assertEqual(self.m2m_changed_messages, expected_messages)

    def _initialize_signal_person(self):
        # Install a listener on the two m2m relations.
        """
        Initializes signal handlers for many-to-many relationships on the Person model.

        This function sets up connections between the m2m_changed signal of the Person model's fans and friends many-to-many fields and the m2m_changed_signal_receiver method.

        It enables the class to receive notifications when the relationships between a person and their fans or friends are modified, allowing for corresponding actions to be taken.

        The function is a private initializer method, intended to be called internally by the class during its setup process.
        """
        models.signals.m2m_changed.connect(
            self.m2m_changed_signal_receiver, Person.fans.through
        )
        models.signals.m2m_changed.connect(
            self.m2m_changed_signal_receiver, Person.friends.through
        )

    def test_m2m_relations_with_self_add_friends(self):
        """
        Tests the behavior of many-to-many relationships with self, specifically when adding friends to a person's friend list.

        Checks that the correct signals are sent when friends are added, including the pre-add and post-add signals, 
        and verifies that the signals contain the correct information about the instance, action, and affected objects.
        """
        self._initialize_signal_person()
        self.alice.friends.set([self.bob, self.chuck])
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.alice,
                    "action": "pre_add",
                    "reverse": False,
                    "model": Person,
                    "objects": [self.bob, self.chuck],
                },
                {
                    "instance": self.alice,
                    "action": "post_add",
                    "reverse": False,
                    "model": Person,
                    "objects": [self.bob, self.chuck],
                },
            ],
        )

    def test_m2m_relations_with_self_add_fan(self):
        self._initialize_signal_person()
        self.alice.fans.set([self.daisy])
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.alice,
                    "action": "pre_add",
                    "reverse": False,
                    "model": Person,
                    "objects": [self.daisy],
                },
                {
                    "instance": self.alice,
                    "action": "post_add",
                    "reverse": False,
                    "model": Person,
                    "objects": [self.daisy],
                },
            ],
        )

    def test_m2m_relations_with_self_add_idols(self):
        """
        Test many-to-many relations with self-referential models by adding idols to a person.

        This test case verifies the correctness of the m2m_changed signal when adding idols to a person.
        It checks if the signal is sent correctly before and after adding the idols, and if the signal
        contains the expected information about the instance, action, and affected objects.

        The test assumes that the person model has already been initialized and that the necessary
        signal handlers are in place. It sets up a scenario where a person (Chuck) adds other people
        (Alice and Bob) as their idols, and then asserts that the expected signal messages are sent.

        """
        self._initialize_signal_person()
        self.chuck.idols.set([self.alice, self.bob])
        self.assertEqual(
            self.m2m_changed_messages,
            [
                {
                    "instance": self.chuck,
                    "action": "pre_add",
                    "reverse": True,
                    "model": Person,
                    "objects": [self.alice, self.bob],
                },
                {
                    "instance": self.chuck,
                    "action": "post_add",
                    "reverse": True,
                    "model": Person,
                    "objects": [self.alice, self.bob],
                },
            ],
        )
