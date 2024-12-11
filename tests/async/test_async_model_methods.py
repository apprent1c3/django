from django.test import TestCase

from .models import SimpleModel


class AsyncModelOperationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.s1 = SimpleModel.objects.create(field=0)

    async def test_asave(self):
        """

        Tests the asynchronous save functionality of a model instance.

        Verifies that changes made to a model instance's fields are persisted to the database
        when the asave method is called. This is done by modifying an instance's field, saving it,
        refetching the instance from the database, and asserting that the changes are reflected.

        """
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
        Tests that arefresh_from_db method updates the object's attributes with the latest values from the database.

        This test case checks if the arefresh_from_db method correctly refreshes an object's field by comparing its value after an asynchronous update operation with the expected value.

        It verifies that after updating a model instance in the database, calling arefresh_from_db on the instance will synchronise its attributes with the new values stored in the database.
        """
        await SimpleModel.objects.filter(pk=self.s1.pk).aupdate(field=20)
        await self.s1.arefresh_from_db()
        self.assertEqual(self.s1.field, 20)

    async def test_arefresh_from_db_from_queryset(self):
        """
        Tests the behavior of the `arefresh_from_db` method when used with a queryset.

        This test checks that the method refreshes the object's state from the database when the provided queryset contains the object, 
        and raises a `DoesNotExist` exception when the queryset does not contain the object.

        It verifies that the object's attributes are updated correctly after a successful refresh.
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
