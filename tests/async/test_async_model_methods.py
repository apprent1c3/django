from django.test import TestCase

from .models import SimpleModel


class AsyncModelOperationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.s1 = SimpleModel.objects.create(field=0)

    async def test_asave(self):
        self.s1.field = 10
        await self.s1.asave()
        refetched = await SimpleModel.objects.aget()
        self.assertEqual(refetched.field, 10)

    async def test_adelete(self):
        await self.s1.adelete()
        count = await SimpleModel.objects.acount()
        self.assertEqual(count, 0)

    async def test_arefresh_from_db(self):
        await SimpleModel.objects.filter(pk=self.s1.pk).aupdate(field=20)
        await self.s1.arefresh_from_db()
        self.assertEqual(self.s1.field, 20)

    async def test_arefresh_from_db_from_queryset(self):
        """

        Tests the arefresh_from_db method using a queryset to refresh an object from the database.

        This test ensures that arefresh_from_db updates the object with the latest data from the database 
        if it exists in the provided queryset. If the object does not exist in the queryset, it should 
        raise a DoesNotExist exception.

        The test first updates an existing object in the database, then attempts to refresh the object 
        from the database using a queryset that does not include the updated object, and verifies that 
        a DoesNotExist exception is raised. Finally, it refreshes the object using a queryset that 
        includes the updated object and checks that the object's data is correctly updated.

        """
        await SimpleModel.objects.filter(pk=self.s1.pk).aupdate(field=20)
        with self.assertRaises(SimpleModel.DoesNotExist):
            await self.s1.arefresh_from_db(
                from_queryset=SimpleModel.objects.filter(field=0)
            )
        await self.s1.arefresh_from_db(
            from_queryset=SimpleModel.objects.filter(field__gt=0)
        )
        self.assertEqual(self.s1.field, 20)
