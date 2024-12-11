from django.test import TestCase

from .models import Flea, House, Person, Pet, Room


class UUIDPrefetchRelated(TestCase):
    def test_prefetch_related_from_uuid_model(self):
        Pet.objects.create(name="Fifi").people.add(
            Person.objects.create(name="Ellen"),
            Person.objects.create(name="George"),
        )

        with self.assertNumQueries(2):
            pet = Pet.objects.prefetch_related("people").get(name="Fifi")
        with self.assertNumQueries(0):
            self.assertEqual(2, len(pet.people.all()))

    def test_prefetch_related_to_uuid_model(self):
        Person.objects.create(name="Bella").pets.add(
            Pet.objects.create(name="Socks"),
            Pet.objects.create(name="Coffee"),
        )

        with self.assertNumQueries(2):
            person = Person.objects.prefetch_related("pets").get(name="Bella")
        with self.assertNumQueries(0):
            self.assertEqual(2, len(person.pets.all()))

    def test_prefetch_related_from_uuid_model_to_uuid_model(self):
        fleas = [Flea.objects.create() for i in range(3)]
        Pet.objects.create(name="Fifi").fleas_hosted.add(*fleas)
        Pet.objects.create(name="Bobo").fleas_hosted.add(*fleas)

        with self.assertNumQueries(2):
            pet = Pet.objects.prefetch_related("fleas_hosted").get(name="Fifi")
        with self.assertNumQueries(0):
            self.assertEqual(3, len(pet.fleas_hosted.all()))

        with self.assertNumQueries(2):
            flea = Flea.objects.prefetch_related("pets_visited").get(pk=fleas[0].pk)
        with self.assertNumQueries(0):
            self.assertEqual(2, len(flea.pets_visited.all()))

    def test_prefetch_related_from_uuid_model_to_uuid_model_with_values_flat(self):
        """
        Tests the behavior of prefetching related objects between two models using UUIDs, specifically from a Pet to its hosted Fleas. 
        This test case verifies that the prefetch_related method successfully retrieves related objects (in this case, Fleas) from the Pet model, 
        when the related object relationship is established via a UUID-based foreign key. 
        The test creates a Pet instance with associated people and then checks that the prefetched related Fleas are correctly retrieved and their IDs match the expected IDs.
        """
        pet = Pet.objects.create(name="Fifi")
        pet.people.add(
            Person.objects.create(name="Ellen"),
            Person.objects.create(name="George"),
        )
        self.assertSequenceEqual(
            Pet.objects.prefetch_related("fleas_hosted").values_list("id", flat=True),
            [pet.id],
        )


class UUIDPrefetchRelatedLookups(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the application, creating a complete scenario with a house, room, fleas, pet, and person.
        This includes establishing relationships between these entities, such as a person owning a house and a pet, and the pet hosting fleas.
        The resulting test data provides a comprehensive setup for testing various features and interactions within the application.

        """
        house = House.objects.create(name="Redwood", address="Arcata")
        room = Room.objects.create(name="Racoon", house=house)
        fleas = [Flea.objects.create(current_room=room) for i in range(3)]
        pet = Pet.objects.create(name="Spooky")
        pet.fleas_hosted.add(*fleas)
        person = Person.objects.create(name="Bob")
        person.houses.add(house)
        person.pets.add(pet)
        person.fleas_hosted.add(*fleas)

    def test_from_uuid_pk_lookup_uuid_pk_integer_pk(self):
        # From uuid-pk model, prefetch <uuid-pk model>.<integer-pk model>:
        with self.assertNumQueries(4):
            spooky = Pet.objects.prefetch_related(
                "fleas_hosted__current_room__house"
            ).get(name="Spooky")
        with self.assertNumQueries(0):
            self.assertEqual("Racoon", spooky.fleas_hosted.all()[0].current_room.name)

    def test_from_uuid_pk_lookup_integer_pk2_uuid_pk2(self):
        # From uuid-pk model, prefetch
        # <integer-pk model>.<integer-pk model>.<uuid-pk model>.<uuid-pk model>:
        """

        Tests the lookup of a UUID primary key using an integer primary key.

        This test case verifies that when using Django's ORM, a `UUID` primary key can be retrieved 
        using an `Integer` primary key with minimal database queries. It exercises the `prefetch_related` 
        method to reduce the number of database queries.

        The test checks that the number of database queries is minimized after the initial prefetch, 
        and that the related objects can be accessed without triggering additional queries.

        Verifies the correctness of the lookup and the efficiency of the query retrieval process.

        """
        with self.assertNumQueries(5):
            spooky = Pet.objects.prefetch_related("people__houses__rooms__fleas").get(
                name="Spooky"
            )
        with self.assertNumQueries(0):
            self.assertEqual(
                3,
                len(spooky.people.all()[0].houses.all()[0].rooms.all()[0].fleas.all()),
            )

    def test_from_integer_pk_lookup_uuid_pk_integer_pk(self):
        # From integer-pk model, prefetch <uuid-pk model>.<integer-pk model>:
        """
        Tests the optimization of integer primary key lookup in combination with UUID primary key.

        This test case verifies that using prefetch_related on a model with integer primary key 
        involving a UUID primary key lookup results in efficient database queries. It checks that 
        after an initial query to retrieve a Room object, subsequent accesses to its related 
        objects do not trigger additional database queries. The test ensures that the 
        prefetch_related method correctly fetches all necessary related objects, allowing for 
        fast and efficient data retrieval.

        The test covers the scenario where a Room object is retrieved by its name and then its 
        related Flea objects, and subsequently the People who visited those Flea objects, are 
        accessed without causing additional database queries. The expected outcome is that the 
        test passes without generating extra queries after the initial Room object retrieval.
        """
        with self.assertNumQueries(3):
            racoon = Room.objects.prefetch_related("fleas__people_visited").get(
                name="Racoon"
            )
        with self.assertNumQueries(0):
            self.assertEqual("Bob", racoon.fleas.all()[0].people_visited.all()[0].name)

    def test_from_integer_pk_lookup_integer_pk_uuid_pk(self):
        # From integer-pk model, prefetch <integer-pk model>.<uuid-pk model>:
        """

        Tests the lookup of a model instance using an integer primary key and UUID primary key.

        This test case retrieves a 'House' instance with the name 'Redwood' from the database, 
        prefetching related 'rooms' and their associated 'fleas' in a single query. 
        It then verifies that the number of 'fleas' in the first 'room' can be accessed without 
        issuing any additional database queries, ensuring the efficacy of the prefetching operation.

        """
        with self.assertNumQueries(3):
            redwood = House.objects.prefetch_related("rooms__fleas").get(name="Redwood")
        with self.assertNumQueries(0):
            self.assertEqual(3, len(redwood.rooms.all()[0].fleas.all()))

    def test_from_integer_pk_lookup_integer_pk_uuid_pk_uuid_pk(self):
        # From integer-pk model, prefetch
        # <integer-pk model>.<uuid-pk model>.<uuid-pk model>:
        """
        Tests the lookup of a foreign key relationship starting from an integer primary key 
        and traversing through related model instances, ending at a UUID primary key, 
        all while utilizing prefetch related optimization to minimize database queries.
        """
        with self.assertNumQueries(4):
            redwood = House.objects.prefetch_related("rooms__fleas__pets_visited").get(
                name="Redwood"
            )
        with self.assertNumQueries(0):
            self.assertEqual(
                "Spooky",
                redwood.rooms.all()[0].fleas.all()[0].pets_visited.all()[0].name,
            )
