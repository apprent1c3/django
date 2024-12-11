from django.test import TestCase

from .models import ManyToManyModel, RelatedModel, SimpleModel


class AsyncRelatedManagersOperationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for ManyToManyModel and SimpleModel instances.

        This method creates and assigns test data to class attributes, including two ManyToManyModel instances and one SimpleModel instance.
        The second ManyToManyModel instance is associated with the created SimpleModel instance.
        The test data is intended to be used in subsequent tests, allowing for the evaluation of relationships between these models.
        """
        cls.mtm1 = ManyToManyModel.objects.create()
        cls.s1 = SimpleModel.objects.create(field=0)
        cls.mtm2 = ManyToManyModel.objects.create()
        cls.mtm2.simples.set([cls.s1])

    async def test_acreate(self):
        """
        Tests the asynchronous creation of a simple object.

        This test case verifies that a new simple object can be created with the specified field value
        and then successfully retrieved. The test checks that the field value of the newly created
        object matches the expected value, ensuring that the creation and retrieval operations are
        functioning as expected.
        """
        await self.mtm1.simples.acreate(field=2)
        new_simple = await self.mtm1.simples.aget()
        self.assertEqual(new_simple.field, 2)

    async def test_acreate_reverse(self):
        await self.s1.relatedmodel_set.acreate()
        new_relatedmodel = await self.s1.relatedmodel_set.aget()
        self.assertEqual(new_relatedmodel.simple, self.s1)

    async def test_aget_or_create(self):
        """

        Fetches or creates a related object, and returns the object along with a boolean indicating whether it was created.

        This method provides a way to retrieve an existing related object, or create a new one if it doesn't exist, in a single asynchronous operation.
        It can also be used to fetch an existing object by its ID, allowing for additional defaults to be specified for a related many-to-many relationship.

        The method returns a tuple containing the fetched or created object and a boolean value, where:
        - The object is the related instance that was either retrieved or created.
        - The boolean value is True if the object was created, and False if it was fetched from the database.

        Additionally, when used to fetch an existing object, this method can accept defaults for a many-to-many relationship, specified through the 'through_defaults' parameter.
        However, these defaults do not affect the existing object's attributes, and are only used when creating new many-to-many relationships.

        """
        new_simple, created = await self.mtm1.simples.aget_or_create(field=2)
        self.assertIs(created, True)
        self.assertEqual(await self.mtm1.simples.acount(), 1)
        self.assertEqual(new_simple.field, 2)
        new_simple, created = await self.mtm1.simples.aget_or_create(
            id=new_simple.id, through_defaults={"field": 3}
        )
        self.assertIs(created, False)
        self.assertEqual(await self.mtm1.simples.acount(), 1)
        self.assertEqual(new_simple.field, 2)

    async def test_aget_or_create_reverse(self):
        """

        Tests the asynchronous get or create functionality for reverse relationships.

        This test ensures that a new related model instance is created when one does not exist,
        and that the instance is correctly associated with the parent model.
        It also verifies that the correct count of related instances is returned.

        """
        new_relatedmodel, created = await self.s1.relatedmodel_set.aget_or_create()
        self.assertIs(created, True)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 1)
        self.assertEqual(new_relatedmodel.simple, self.s1)

    async def test_aupdate_or_create(self):
        """

        Create or update a simple object in a many-to-many relationship.

        This function attempts to get or create an object that matches the given keywords.
        If an object with matching keywords already exists, the function updates it with the given defaults.
        If no matching object exists, the function creates a new one with the keyword values and additional create defaults.

        The function returns a tuple containing the created or updated object and a boolean indicating whether the object was created.

        Parameters can include:
        - Keyword arguments (e.g., field) to match existing objects.
        - id: to match an object by its id.
        - defaults: a dictionary of fields and values to update the existing object with.
        - create_defaults: a dictionary of fields and values to initialize a new object with.

        Returns:
            tuple: A tuple containing the created or updated object and a boolean indicating whether the object was created.

        """
        new_simple, created = await self.mtm1.simples.aupdate_or_create(field=2)
        self.assertIs(created, True)
        self.assertEqual(await self.mtm1.simples.acount(), 1)
        self.assertEqual(new_simple.field, 2)
        new_simple1, created = await self.mtm1.simples.aupdate_or_create(
            id=new_simple.id, defaults={"field": 3}
        )
        self.assertIs(created, False)
        self.assertEqual(new_simple1.field, 3)

        new_simple2, created = await self.mtm1.simples.aupdate_or_create(
            field=4, defaults={"field": 6}, create_defaults={"field": 5}
        )
        self.assertIs(created, True)
        self.assertEqual(new_simple2.field, 5)
        self.assertEqual(await self.mtm1.simples.acount(), 2)

    async def test_aupdate_or_create_reverse(self):
        """
        Tests the asynchronous update or creation of a related model instance, 
        ensuring a new instance is created and its relationship to the parent model is correctly established.

        The function validates that the creation of the related model instance is successful, 
        and that it is correctly linked to the parent model, with the expected count of related instances.

        It checks for the correct creation status, count of related instances, and the correct linking of the new instance to the parent model.
        """
        new_relatedmodel, created = await self.s1.relatedmodel_set.aupdate_or_create()
        self.assertIs(created, True)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 1)
        self.assertEqual(new_relatedmodel.simple, self.s1)

    async def test_aadd(self):
        """
        Tests the asynchronous addition of an element using the 'aadd' method and verifies its retrieval using the 'aget' method. 

        This test case ensures that an element can be successfully added to the collection and then accurately retrieved, validating the functionality of the asynchronous addition operation.
        """
        await self.mtm1.simples.aadd(self.s1)
        self.assertEqual(await self.mtm1.simples.aget(), self.s1)

    async def test_aadd_reverse(self):
        r1 = await RelatedModel.objects.acreate()
        await self.s1.relatedmodel_set.aadd(r1, bulk=False)
        self.assertEqual(await self.s1.relatedmodel_set.aget(), r1)

    async def test_aremove(self):
        """
        Tests the removal of an item from the collection using the aremove method.

        This test case verifies that the aremove method correctly decreases the count of items 
        in the collection after removing a specified item. It checks the initial count, 
        removes an item, and then checks the updated count to ensure it has been reduced 
        by one, confirming the successful removal of the item.
        """
        self.assertEqual(await self.mtm2.simples.acount(), 1)
        await self.mtm2.simples.aremove(self.s1)
        self.assertEqual(await self.mtm2.simples.acount(), 0)

    async def test_aremove_reverse(self):
        """

        Tests the removal of a related object from a model instance in reverse.

        This test case verifies that the aremove method correctly detaches a related object 
        from the model instance and updates the relationship count accordingly. 

        It creates a related object, confirms the initial relationship count, removes the 
        related object using aremove, and then asserts that the relationship count has 
        been updated to reflect the removal.

        """
        r1 = await RelatedModel.objects.acreate(simple=self.s1)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 1)
        await self.s1.relatedmodel_set.aremove(r1)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 0)

    async def test_aset(self):
        await self.mtm1.simples.aset([self.s1])
        self.assertEqual(await self.mtm1.simples.aget(), self.s1)
        await self.mtm1.simples.aset([])
        self.assertEqual(await self.mtm1.simples.acount(), 0)
        await self.mtm1.simples.aset([self.s1], clear=True)
        self.assertEqual(await self.mtm1.simples.aget(), self.s1)

    async def test_aset_reverse(self):
        """
        Tests the asynchronous set operation on a related model set.

        Verifies that a related model can be added to and removed from the set, 
        and that the set operations are correctly reflected in the database. 

        Specifically, this test covers the following scenarios:

        * Adding a related model to the set
        * Removing all related models from the set
        * Adding a related model to the set with a clear operation and without bulk mode
        """
        r1 = await RelatedModel.objects.acreate()
        await self.s1.relatedmodel_set.aset([r1])
        self.assertEqual(await self.s1.relatedmodel_set.aget(), r1)
        await self.s1.relatedmodel_set.aset([])
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 0)
        await self.s1.relatedmodel_set.aset([r1], bulk=False, clear=True)
        self.assertEqual(await self.s1.relatedmodel_set.aget(), r1)

    async def test_aclear(self):
        self.assertEqual(await self.mtm2.simples.acount(), 1)
        await self.mtm2.simples.aclear()
        self.assertEqual(await self.mtm2.simples.acount(), 0)

    async def test_aclear_reverse(self):
        await RelatedModel.objects.acreate(simple=self.s1)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 1)
        await self.s1.relatedmodel_set.aclear(bulk=False)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 0)
