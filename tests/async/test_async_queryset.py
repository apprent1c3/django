import json
import xml.etree.ElementTree
from datetime import datetime

from asgiref.sync import async_to_sync, sync_to_async

from django.db import NotSupportedError, connection
from django.db.models import Prefetch, Sum
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature

from .models import RelatedModel, SimpleModel


class AsyncQuerySetTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.s1 = SimpleModel.objects.create(
            field=1,
            created=datetime(2022, 1, 1, 0, 0, 0),
        )
        cls.s2 = SimpleModel.objects.create(
            field=2,
            created=datetime(2022, 1, 1, 0, 0, 1),
        )
        cls.s3 = SimpleModel.objects.create(
            field=3,
            created=datetime(2022, 1, 1, 0, 0, 2),
        )
        cls.r1 = RelatedModel.objects.create(simple=cls.s1)
        cls.r2 = RelatedModel.objects.create(simple=cls.s2)
        cls.r3 = RelatedModel.objects.create(simple=cls.s3)

    @staticmethod
    def _get_db_feature(connection_, feature_name):
        # Wrapper to avoid accessing connection attributes until inside
        # coroutine function. Connection access is thread sensitive and cannot
        # be passed across sync/async boundaries.
        return getattr(connection_.features, feature_name)

    async def test_async_iteration(self):
        results = []
        async for m in SimpleModel.objects.order_by("pk"):
            results.append(m)
        self.assertEqual(results, [self.s1, self.s2, self.s3])

    async def test_aiterator(self):
        qs = SimpleModel.objects.aiterator()
        results = []
        async for m in qs:
            results.append(m)
        self.assertCountEqual(results, [self.s1, self.s2, self.s3])

    async def test_aiterator_prefetch_related(self):
        results = []
        async for s in SimpleModel.objects.prefetch_related(
            Prefetch("relatedmodel_set", to_attr="prefetched_relatedmodel")
        ).aiterator():
            results.append(s.prefetched_relatedmodel)
        self.assertCountEqual(results, [[self.r1], [self.r2], [self.r3]])

    async def test_aiterator_invalid_chunk_size(self):
        msg = "Chunk size must be strictly positive."
        for size in [0, -1]:
            qs = SimpleModel.objects.aiterator(chunk_size=size)
            with self.subTest(size=size), self.assertRaisesMessage(ValueError, msg):
                async for m in qs:
                    pass

    async def test_acount(self):
        count = await SimpleModel.objects.acount()
        self.assertEqual(count, 3)

    async def test_acount_cached_result(self):
        qs = SimpleModel.objects.all()
        # Evaluate the queryset to populate the query cache.
        [x async for x in qs]
        count = await qs.acount()
        self.assertEqual(count, 3)

        await sync_to_async(SimpleModel.objects.create)(
            field=4,
            created=datetime(2022, 1, 1, 0, 0, 0),
        )
        # The query cache is used.
        count = await qs.acount()
        self.assertEqual(count, 3)

    async def test_aget(self):
        instance = await SimpleModel.objects.aget(field=1)
        self.assertEqual(instance, self.s1)

    async def test_acreate(self):
        await SimpleModel.objects.acreate(field=4)
        self.assertEqual(await SimpleModel.objects.acount(), 4)

    async def test_aget_or_create(self):
        instance, created = await SimpleModel.objects.aget_or_create(field=4)
        self.assertEqual(await SimpleModel.objects.acount(), 4)
        self.assertIs(created, True)

    async def test_aupdate_or_create(self):
        instance, created = await SimpleModel.objects.aupdate_or_create(
            id=self.s1.id, defaults={"field": 2}
        )
        self.assertEqual(instance, self.s1)
        self.assertEqual(instance.field, 2)
        self.assertIs(created, False)
        instance, created = await SimpleModel.objects.aupdate_or_create(field=4)
        self.assertEqual(await SimpleModel.objects.acount(), 4)
        self.assertIs(created, True)
        instance, created = await SimpleModel.objects.aupdate_or_create(
            field=5, defaults={"field": 7}, create_defaults={"field": 6}
        )
        self.assertEqual(await SimpleModel.objects.acount(), 5)
        self.assertIs(created, True)
        self.assertEqual(instance.field, 6)

    @skipUnlessDBFeature("has_bulk_insert")
    @async_to_sync
    async def test_abulk_create(self):
        instances = [SimpleModel(field=i) for i in range(10)]
        qs = await SimpleModel.objects.abulk_create(instances)
        self.assertEqual(len(qs), 10)

    @skipUnlessDBFeature("has_bulk_insert", "supports_update_conflicts")
    @skipIfDBFeature("supports_update_conflicts_with_target")
    @async_to_sync
    async def test_update_conflicts_unique_field_unsupported(self):
        msg = (
            "This database backend does not support updating conflicts with specifying "
            "unique fields that can trigger the upsert."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            await SimpleModel.objects.abulk_create(
                [SimpleModel(field=1), SimpleModel(field=2)],
                update_conflicts=True,
                update_fields=["field"],
                unique_fields=["created"],
            )

    async def test_abulk_update(self):
        """

        Test the bulk update functionality of the asynchronous model manager.

        This test case verifies that multiple model instances can be updated in bulk
        using the :meth:`abulk_update` method. It checks that the ``field`` attribute
        of each instance is correctly updated and persists the changes to the database.

        The test performs the following steps:
            1. Retrieves all instances of the model.
            2. Modifies the ``field`` attribute of each instance.
            3. Updates the modified instances in bulk.
            4. Verifies that the updated values are correctly stored in the database.

        """
        instances = SimpleModel.objects.all()
        async for instance in instances:
            instance.field = instance.field * 10

        await SimpleModel.objects.abulk_update(instances, ["field"])

        qs = [(o.pk, o.field) async for o in SimpleModel.objects.all()]
        self.assertCountEqual(
            qs,
            [(self.s1.pk, 10), (self.s2.pk, 20), (self.s3.pk, 30)],
        )

    async def test_ain_bulk(self):
        res = await SimpleModel.objects.ain_bulk()
        self.assertEqual(
            res,
            {self.s1.pk: self.s1, self.s2.pk: self.s2, self.s3.pk: self.s3},
        )

        res = await SimpleModel.objects.ain_bulk([self.s2.pk])
        self.assertEqual(res, {self.s2.pk: self.s2})

        res = await SimpleModel.objects.ain_bulk([self.s2.pk], field_name="id")
        self.assertEqual(res, {self.s2.pk: self.s2})

    async def test_alatest(self):
        instance = await SimpleModel.objects.alatest("created")
        self.assertEqual(instance, self.s3)

        instance = await SimpleModel.objects.alatest("-created")
        self.assertEqual(instance, self.s1)

    async def test_aearliest(self):
        """
        Tests the functionality of retrieving the earliest or latest instance of a model based on a specified field.

        This test case checks the correctness of the `aearliest` method by comparing the retrieved instances with the expected ones. It verifies that the method returns the correct instance when sorting by a field in ascending or descending order.

        The test covers two scenarios: retrieving the earliest instance (based on the 'created' field) and retrieving the latest instance (based on the '-created' field), ensuring the method behaves as expected in both cases.
        """
        instance = await SimpleModel.objects.aearliest("created")
        self.assertEqual(instance, self.s1)

        instance = await SimpleModel.objects.aearliest("-created")
        self.assertEqual(instance, self.s3)

    async def test_afirst(self):
        instance = await SimpleModel.objects.afirst()
        self.assertEqual(instance, self.s1)

        instance = await SimpleModel.objects.filter(field=4).afirst()
        self.assertIsNone(instance)

    async def test_alast(self):
        instance = await SimpleModel.objects.alast()
        self.assertEqual(instance, self.s3)

        instance = await SimpleModel.objects.filter(field=4).alast()
        self.assertIsNone(instance)

    async def test_aaggregate(self):
        total = await SimpleModel.objects.aaggregate(total=Sum("field"))
        self.assertEqual(total, {"total": 6})

    async def test_aexists(self):
        """
        Checks the existence of objects in the database that match a given filter.

        This method uses an asynchronous query to determine if at least one object
        exists in the database that satisfies the specified conditions. It returns
        True if such an object exists, and False otherwise.

        The result of this method can be used to verify the presence or absence of
        specific data in the database, allowing for more informed decisions or
        actions to be taken in the application.

        Args:
            None

        Returns:
            bool: True if at least one object matching the filter exists, False otherwise

        Note:
            This method is asynchronous and should be used within an async context.
        """
        check = await SimpleModel.objects.filter(field=1).aexists()
        self.assertIs(check, True)

        check = await SimpleModel.objects.filter(field=4).aexists()
        self.assertIs(check, False)

    async def test_acontains(self):
        check = await SimpleModel.objects.acontains(self.s1)
        self.assertIs(check, True)
        # Unsaved instances are not allowed, so use an ID known not to exist.
        check = await SimpleModel.objects.acontains(
            SimpleModel(id=self.s3.id + 1, field=4)
        )
        self.assertIs(check, False)

    async def test_aupdate(self):
        await SimpleModel.objects.aupdate(field=99)
        qs = [o async for o in SimpleModel.objects.all()]
        values = [instance.field for instance in qs]
        self.assertEqual(set(values), {99})

    async def test_adelete(self):
        await SimpleModel.objects.filter(field=2).adelete()
        qs = [o async for o in SimpleModel.objects.all()]
        self.assertCountEqual(qs, [self.s1, self.s3])

    @skipUnlessDBFeature("supports_explaining_query_execution")
    @async_to_sync
    async def test_aexplain(self):
        """
        Tests the QuerySet.aexplain() method to ensure it returns a valid explanation of query execution.

        The test checks the method's output in various formats, including the default format and all formats supported by the database.
        It verifies that the result is a non-empty string and, when applicable, that it is valid XML or JSON.

        :raises AssertionError: If the explanation result is invalid or empty, or if the result is not a string.
        :raises SkipTest: If the database does not support explaining query execution.

        """
        supported_formats = await sync_to_async(self._get_db_feature)(
            connection, "supported_explain_formats"
        )
        all_formats = (None, *supported_formats)
        for format_ in all_formats:
            with self.subTest(format=format_):
                # TODO: Check the captured query when async versions of
                # self.assertNumQueries/CaptureQueriesContext context
                # processors are available.
                result = await SimpleModel.objects.filter(field=1).aexplain(
                    format=format_
                )
                self.assertIsInstance(result, str)
                self.assertTrue(result)
                if not format_:
                    continue
                if format_.lower() == "xml":
                    try:
                        xml.etree.ElementTree.fromstring(result)
                    except xml.etree.ElementTree.ParseError as e:
                        self.fail(f"QuerySet.aexplain() result is not valid XML: {e}")
                elif format_.lower() == "json":
                    try:
                        json.loads(result)
                    except json.JSONDecodeError as e:
                        self.fail(f"QuerySet.aexplain() result is not valid JSON: {e}")

    async def test_raw(self):
        sql = "SELECT id, field FROM async_simplemodel WHERE created=%s"
        qs = SimpleModel.objects.raw(sql, [self.s1.created])
        self.assertEqual([o async for o in qs], [self.s1])
