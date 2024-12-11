import datetime

from django.db import connection
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from .models import DumbCategory, NonIntegerPKReturningModel, ReturningModel


@skipUnlessDBFeature("can_return_columns_from_insert")
class ReturningValuesTests(TestCase):
    def test_insert_returning(self):
        """
        Tests that the insert query uses the RETURNING clause to retrieve the inserted ID, ensuring that the database correctly handles the insertion and returns the generated ID. This test ensures that the created object is properly saved to the database and its ID is retrieved as expected.
        """
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
        Tests that inserting a NonIntegerPKReturningModel instance returns a valid non-integer primary key.

        Verifies that the object's creation is successful and that its 'created' timestamp is a datetime object, 
        indicating that the model's primary key is properly set and the object is inserted as expected.
        """
        obj = NonIntegerPKReturningModel.objects.create()
        self.assertTrue(obj.created)
        self.assertIsInstance(obj.created, datetime.datetime)

    def test_insert_returning_multiple(self):
        """

        Tests that inserting a new object into the database using the model manager's create method 
        returns the newly created object with its primary key and other fields populated.

        Specifically, it verifies that the SQL query used to create the object includes a RETURNING 
        clause to retrieve the object's id and created fields after insertion. The test also checks 
        that the created object has a valid primary key and a datetime object for the created field.

        """
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
        objs = [ReturningModel(), ReturningModel(pk=2**11), ReturningModel()]
        ReturningModel.objects.bulk_create(objs)
        for obj in objs:
            with self.subTest(obj=obj):
                self.assertTrue(obj.pk)
                self.assertIsInstance(obj.created, datetime.datetime)
