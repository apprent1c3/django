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
        """
        Tests the asynchronous refresh of a model instance from the database.

        This test case verifies that the :meth:`arefresh_from_db` method updates the
        instance's fields with the latest values from the database. It modifies a model
        instance in the database and then checks if the instance's fields are correctly
        updated after calling :meth:`arefresh_from_db`.

        """
        await SimpleModel.objects.filter(pk=self.s1.pk).aupdate(field=20)
        await self.s1.arefresh_from_db()
        self.assertEqual(self.s1.field, 20)

    async def test_arefresh_from_db_from_queryset(self):
        await SimpleModel.objects.filter(pk=self.s1.pk).aupdate(field=20)
        with self.assertRaises(SimpleModel.DoesNotExist):
            await self.s1.arefresh_from_db(
                from_queryset=SimpleModel.objects.filter(field=0)
            )
        await self.s1.arefresh_from_db(
            from_queryset=SimpleModel.objects.filter(field__gt=0)
        )
        self.assertEqual(self.s1.field, 20)
