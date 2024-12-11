from django.test import TestCase

from .models import ManyToManyModel, RelatedModel, SimpleModel


class AsyncRelatedManagersOperationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mtm1 = ManyToManyModel.objects.create()
        cls.s1 = SimpleModel.objects.create(field=0)
        cls.mtm2 = ManyToManyModel.objects.create()
        cls.mtm2.simples.set([cls.s1])

    async def test_acreate(self):
        await self.mtm1.simples.acreate(field=2)
        new_simple = await self.mtm1.simples.aget()
        self.assertEqual(new_simple.field, 2)

    async def test_acreate_reverse(self):
        await self.s1.relatedmodel_set.acreate()
        new_relatedmodel = await self.s1.relatedmodel_set.aget()
        self.assertEqual(new_relatedmodel.simple, self.s1)

    async def test_aget_or_create(self):
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

        Tests the asynchronous get or create operation on a reverse relationship.

        Verifies that a new related model instance is created and associated with the source instance,
        and that the resulting instance and count are as expected.

        The test case ensures the following:

        * A new related model instance is created and the created flag is set to True.
        * The count of related model instances is incremented to 1 after creation.
        * The newly created related model instance is correctly associated with the source instance.

        This test covers the functionality of the asynchronous get or create operation
        on a reverse relationship, ensuring that it behaves as expected in a concurrent environment.

        """
        new_relatedmodel, created = await self.s1.relatedmodel_set.aget_or_create()
        self.assertIs(created, True)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 1)
        self.assertEqual(new_relatedmodel.simple, self.s1)

    async def test_aupdate_or_create(self):
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

        Tests the asynchronous update or creation of a related model instance in the opposite direction of the relationship.

        Verifies that a new related model instance is created and associated with the main model instance, and that the correct count of related instances is returned.

        """
        new_relatedmodel, created = await self.s1.relatedmodel_set.aupdate_or_create()
        self.assertIs(created, True)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 1)
        self.assertEqual(new_relatedmodel.simple, self.s1)

    async def test_aadd(self):
        await self.mtm1.simples.aadd(self.s1)
        self.assertEqual(await self.mtm1.simples.aget(), self.s1)

    async def test_aadd_reverse(self):
        r1 = await RelatedModel.objects.acreate()
        await self.s1.relatedmodel_set.aadd(r1, bulk=False)
        self.assertEqual(await self.s1.relatedmodel_set.aget(), r1)

    async def test_aremove(self):
        self.assertEqual(await self.mtm2.simples.acount(), 1)
        await self.mtm2.simples.aremove(self.s1)
        self.assertEqual(await self.mtm2.simples.acount(), 0)

    async def test_aremove_reverse(self):
        r1 = await RelatedModel.objects.acreate(simple=self.s1)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 1)
        await self.s1.relatedmodel_set.aremove(r1)
        self.assertEqual(await self.s1.relatedmodel_set.acount(), 0)

    async def test_aset(self):
        """
        Tests the functionality of setting and getting values asynchronously.

        This test case covers the following scenarios:
        - Setting a single value and verifying it is retrieved correctly
        - Setting an empty list and checking the count of values is zero
        - Setting a single value with the clear option and verifying it is retrieved correctly

        Verifies that the asynchronous set and get operations work as expected, including the ability to clear existing values
        """
        await self.mtm1.simples.aset([self.s1])
        self.assertEqual(await self.mtm1.simples.aget(), self.s1)
        await self.mtm1.simples.aset([])
        self.assertEqual(await self.mtm1.simples.acount(), 0)
        await self.mtm1.simples.aset([self.s1], clear=True)
        self.assertEqual(await self.mtm1.simples.aget(), self.s1)

    async def test_aset_reverse(self):
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
