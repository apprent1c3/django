import datetime

from django.db import connection
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from .models import DumbCategory, NonIntegerPKReturningModel, ReturningModel


@skipUnlessDBFeature("can_return_columns_from_insert")
class ReturningValuesTests(TestCase):
    def test_insert_returning(self):
        with CaptureQueriesContext(connection) as captured_queries:
            DumbCategory.objects.create()
        self.assertIn(
            "RETURNING %s.%s"
            % (
                connection.ops.quote_name(DumbCategory._meta.db_table),
                connection.ops.quote_name(DumbCategory._meta.get_field("id").column),
            ),
            captured_queries[-1]["sql"],
        )

    def test_insert_returning_non_integer(self):
        """
        Tests that a non-integer primary key model instance returns a datetime object when created.

        This test verifies that the \"created\" attribute of a NonIntegerPKReturningModel instance
        is set to a datetime object after the instance is created. It checks that the \"created\"
        attribute is not only truthy, but also specifically an instance of datetime.datetime, 
        ensuring the correct data type is returned.
        """
        obj = NonIntegerPKReturningModel.objects.create()
        self.assertTrue(obj.created)
        self.assertIsInstance(obj.created, datetime.datetime)

    def test_insert_returning_multiple(self):
        with CaptureQueriesContext(connection) as captured_queries:
            obj = ReturningModel.objects.create()
        table_name = connection.ops.quote_name(ReturningModel._meta.db_table)
        self.assertIn(
            "RETURNING %s.%s, %s.%s"
            % (
                table_name,
                connection.ops.quote_name(ReturningModel._meta.get_field("id").column),
                table_name,
                connection.ops.quote_name(
                    ReturningModel._meta.get_field("created").column
                ),
            ),
            captured_queries[-1]["sql"],
        )
        self.assertTrue(obj.pk)
        self.assertIsInstance(obj.created, datetime.datetime)

    @skipUnlessDBFeature("can_return_rows_from_bulk_insert")
    def test_bulk_insert(self):
        """

        Tests the bulk insert functionality of the ORM.

        This test case creates a list of model objects, performs a bulk insert operation, 
        and then verifies that each object has been assigned a primary key and has a 
        valid creation date.

        The test requires a database feature that supports returning rows from bulk 
        insert operations. It uses a sub-test for each object to ensure that all objects 
        are properly created and have the expected attributes.

        """
        objs = [ReturningModel(), ReturningModel(pk=2**11), ReturningModel()]
        ReturningModel.objects.bulk_create(objs)
        for obj in objs:
            with self.subTest(obj=obj):
                self.assertTrue(obj.pk)
                self.assertIsInstance(obj.created, datetime.datetime)
