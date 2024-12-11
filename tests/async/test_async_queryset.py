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
        """
        Tests the asynchronous iteration of SimpleModel objects.

        This test case verifies that asynchronous iteration over SimpleModel objects 
        returns the expected results in the correct order. The results are compared to 
        a predefined list of objects to ensure the asynchronous query is executed 
        correctly.

        :raises AssertionError: If the results of the asynchronous iteration do not 
                                match the expected list of objects.

        """
        results = []
        async for m in SimpleModel.objects.order_by("pk"):
            results.append(m)
        self.assertEqual(results, [self.s1, self.s2, self.s3])

    async def test_aiterator(self):
        """

        Tests the async iterator functionality for retrieving model instances.

        This test case verifies that using an async iterator to fetch model instances
        yields the expected results. It checks that the retrieved instances match the
        expected set of instances, ensuring data consistency and correctness.

        :raises AssertionError: If the retrieved instances do not match the expected set.

        """
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
        """
        Tests that the aiterator function raises a ValueError when an invalid chunk size is provided.

        The function checks that a ValueError is raised with a specific error message when the chunk size is set to a value that is not strictly positive. This ensures that the aiterator function behaves correctly and consistently when handling invalid input.

        Raises:
            ValueError: If the chunk size is not a positive integer.

        Notes:
            The test checks for chunk sizes of 0 and -1, covering the primary cases of invalid input.

        """
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
        """
        Tests the cache functionality of the acount method on a query set.

        This test case verifies that the acount method returns the correct count of objects 
        in the query set, even after the data in the database has changed, if the query set 
        has been cached due to prior iteration. It checks the count before and after 
        inserting a new object, ensuring that the cache is not updated and the count 
        remains the same as the initial iteration.
        """
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
        """
        Tests the asynchronous get functionality of the model manager.

        This test case verifies that the aget method can successfully retrieve an instance 
        from the database based on the provided field value. It checks if the retrieved 
        instance matches the expected instance, ensuring the correctness of the asynchronous 
        get operation.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the retrieved instance does not match the expected instance.

        """
        instance = await SimpleModel.objects.aget(field=1)
        self.assertEqual(instance, self.s1)

    async def test_acreate(self):
        """
        Tests the asynchronous creation of a new SimpleModel instance.

        Verifies that the acreate method successfully creates a new object and updates the count of SimpleModel instances.
        The test case checks if the expected number of instances matches the actual count after creation.
        """
        await SimpleModel.objects.acreate(field=4)
        self.assertEqual(await SimpleModel.objects.acount(), 4)

    async def test_aget_or_create(self):
        """
        Tests the asynchronous get or create functionality of the model manager.

        This test case verifies that when a specified instance does not exist, 
        it is created and the 'created' flag is set to True. It also checks 
        that the total count of instances in the database matches the expected value 
        after creation.

        The test ensures data consistency by checking the return values of 
        the 'aget_or_create' method and the 'acount' method, providing 
        confidence in the correctness of the asynchronous data access operations.
        """
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
        """
        Tests the bulk creation of model instances using the abulk_create method.

        This test creates a list of SimpleModel instances and then uses the abulk_create
        method to create them in bulk. It then asserts that the number of instances
        created matches the number of instances passed to the method.

        The test is only executed if the database feature 'has_bulk_insert' is supported.

        """
        instances = [SimpleModel(field=i) for i in range(10)]
        qs = await SimpleModel.objects.abulk_create(instances)
        self.assertEqual(len(qs), 10)

    @skipUnlessDBFeature("has_bulk_insert", "supports_update_conflicts")
    @skipIfDBFeature("supports_update_conflicts_with_target")
    @async_to_sync
    async def test_update_conflicts_unique_field_unsupported(self):
        """

        Tests the unsupported case of updating conflicts with unique fields using the bulk create method.

        This test ensures that the correct error is raised when attempting to specify unique fields that can trigger an upsert on a database backend that does not support this feature.

        :raises NotSupportedError: If the database backend does not support updating conflicts with unique fields.

        """
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

        Tests the asynchronous bulk update functionality of the model's objects.

        This test retrieves all instances of the model, modifies a specific field of each instance,
        and then uses the abulk_update method to update the instances in the database.
        Finally, it verifies that the updated values are correctly persisted and match the expected results.

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
        """
        Tests the asynchronous bulk retrieval of objects using the `ain_bulk` method.

        This method is used to fetch multiple objects from the database in a single operation.
        It returns a dictionary where the keys are the primary keys or specified field values of the objects,
        and the values are the corresponding object instances.

        The method can be used to retrieve all objects or a subset of objects by providing a list of primary keys or field values.
        An optional `field_name` parameter can be specified to use a different field as the key in the returned dictionary.
        """
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
        Tests the functionality of retrieving the earliest instance from the database based on the 'created' field.

        The test case verifies that the aearliest method correctly returns the instance with the earliest creation date when the field is specified in ascending order, 
        and the instance with the latest creation date when the field is specified in descending order (denoted by a leading minus sign).

        It ensures that the asynchronous database query works as expected, returning the correct instance in both scenarios.
        """
        instance = await SimpleModel.objects.aearliest("created")
        self.assertEqual(instance, self.s1)

        instance = await SimpleModel.objects.aearliest("-created")
        self.assertEqual(instance, self.s3)

    async def test_afirst(self):
        """

        Tests the functionality of the afirst method in retrieving the first object from a database query.

        This test case verifies that the afirst method correctly returns the first instance
        of the model that matches the specified criteria. It also checks that the method
        returns None when no instances match the filter conditions.

        Two scenarios are tested: one where the query returns a matching instance, and
        another where the query does not return any matching instances.

        """
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
        """

        Tests the functionality of the aaggregate method on the SimpleModel objects.

        This test case verifies that the aaggregate method correctly calculates the total sum of the 'field' attribute across all SimpleModel objects.

        """
        total = await SimpleModel.objects.aaggregate(total=Sum("field"))
        self.assertEqual(total, {"total": 6})

    async def test_aexists(self):
        """

        Checks the existence of asynchronous query results.

        Asynchronously checks if at least one object exists in the database that matches the given filter criteria.

        Returns:
            bool: True if at least one object exists, False otherwise.

        Example Use Cases:
            - Verifying the presence of specific data in the database before proceeding with further operations.
            - Checking if a particular condition is met in the database, such as the existence of a record with a specific field value.

        Note:
            This method returns a boolean value indicating the existence of matching records, without retrieving the actual data.

        """
        check = await SimpleModel.objects.filter(field=1).aexists()
        self.assertIs(check, True)

        check = await SimpleModel.objects.filter(field=4).aexists()
        self.assertIs(check, False)

    async def test_acontains(self):
        """
        Tests the :meth:`acontains` method of the SimpleModel query set.

        This test checks if the :meth:`acontains` method correctly returns True when the object exists in the database
        and False otherwise. The test covers two scenarios: one where the object is a direct reference to an existing database
        record, and another where the object is a mock instance with an ID that does not match any existing database record.

        :param none:
        :returns: None
        :raises: AssertionError if the :meth:`acontains` method does not return the expected result
        """
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
        """
        Tests asynchronous deletion of objects from the database.

        This test case verifies that the adelete method correctly removes objects 
        that match a specified filter condition. It checks that after deletion, 
        the remaining objects in the database match the expected set.

        The test scenario involves filtering objects based on a specific field value,
        deleting the filtered objects asynchronously, and then asserting that the 
        remaining objects in the database are as expected.

        """
        await SimpleModel.objects.filter(field=2).adelete()
        qs = [o async for o in SimpleModel.objects.all()]
        self.assertCountEqual(qs, [self.s1, self.s3])

    @skipUnlessDBFeature("supports_explaining_query_execution")
    @async_to_sync
    async def test_aexplain(self):
        """
        Tests the QuerySet.aexplain() method for retrieving query execution plans.

        This test case checks the output of the aexplain() method in various formats,
        including the default format and any additional formats supported by the
        database backend. The output is verified to be a non-empty string.

        For XML and JSON formats, the output is also checked for validity using the
        xml.etree.ElementTree and json modules, respectively.

        The test uses the SimpleModel objects to construct a query and retrieve the
        execution plan in each supported format. The results are validated and any
        errors are reported as test failures.

        The test is skipped if the database backend does not support explaining query
        execution plans.

        Args:
            None

        Returns:
            None

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
        """

        Tests the execution of a raw SQL query on the SimpleModel class.

        This test case verifies that the raw method of the SimpleModel manager can be used to
        execute a SQL query and retrieve the corresponding objects. The query used in this test
        selects all objects from the SimpleModel table where the created date matches the created
        date of a predefined object (s1).

        The test asserts that the results of the raw query match the expected object, ensuring that
        the raw method functions as expected.

        """
        sql = "SELECT id, field FROM async_simplemodel WHERE created=%s"
        qs = SimpleModel.objects.raw(sql, [self.s1.created])
        self.assertEqual([o async for o in qs], [self.s1])
