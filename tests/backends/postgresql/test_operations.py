import unittest

from django.core.management.color import no_style
from django.db import connection
from django.db.models.expressions import Col
from django.db.models.functions import Cast
from django.test import SimpleTestCase

from ..models import Author, Book, Person, Tag


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL tests.")
class PostgreSQLOperationsTests(SimpleTestCase):
    def test_sql_flush(self):
        self.assertEqual(
            connection.ops.sql_flush(
                no_style(),
                [Person._meta.db_table, Tag._meta.db_table],
            ),
            ['TRUNCATE "backends_person", "backends_tag";'],
        )

    def test_sql_flush_allow_cascade(self):
        self.assertEqual(
            connection.ops.sql_flush(
                no_style(),
                [Person._meta.db_table, Tag._meta.db_table],
                allow_cascade=True,
            ),
            ['TRUNCATE "backends_person", "backends_tag" CASCADE;'],
        )

    def test_sql_flush_sequences(self):
        self.assertEqual(
            connection.ops.sql_flush(
                no_style(),
                [Person._meta.db_table, Tag._meta.db_table],
                reset_sequences=True,
            ),
            ['TRUNCATE "backends_person", "backends_tag" RESTART IDENTITY;'],
        )

    def test_sql_flush_sequences_allow_cascade(self):
        self.assertEqual(
            connection.ops.sql_flush(
                no_style(),
                [Person._meta.db_table, Tag._meta.db_table],
                reset_sequences=True,
                allow_cascade=True,
            ),
            ['TRUNCATE "backends_person", "backends_tag" RESTART IDENTITY CASCADE;'],
        )

    def test_prepare_join_on_clause_same_type(self):
        author_table = Author._meta.db_table
        author_id_field = Author._meta.get_field("id")
        lhs_expr, rhs_expr = connection.ops.prepare_join_on_clause(
            author_table,
            author_id_field,
            author_table,
            author_id_field,
        )
        self.assertEqual(lhs_expr, Col(author_table, author_id_field))
        self.assertEqual(rhs_expr, Col(author_table, author_id_field))

    def test_prepare_join_on_clause_different_types(self):
        """

        Tests the preparation of a join on clause for tables with different field types.

        This test case verifies that the `prepare_join_on_clause` method correctly handles joins between tables
        where the primary key and foreign key fields have different data types. It checks that the resulting
        left-hand side and right-hand side expressions are correctly constructed to allow for proper joining
        of the tables.

        The test uses the `Author` and `Book` tables as examples, where the `Author` table has a primary key
        `id` field and the `Book` table has a foreign key `author` field referencing the `Author` table.

        """
        author_table = Author._meta.db_table
        author_id_field = Author._meta.get_field("id")
        book_table = Book._meta.db_table
        book_fk_field = Book._meta.get_field("author")
        lhs_expr, rhs_expr = connection.ops.prepare_join_on_clause(
            author_table,
            author_id_field,
            book_table,
            book_fk_field,
        )
        self.assertEqual(lhs_expr, Col(author_table, author_id_field))
        self.assertEqual(
            rhs_expr, Cast(Col(book_table, book_fk_field), author_id_field)
        )
