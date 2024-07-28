from django.db import connection
from django.test import TestCase

from .models import A01, A02, B01, B02, C01, C02, Managed1, Unmanaged2


class SimpleTests(TestCase):
    def test_simple(self):
        """
        This is a comment
        """
        # Insert some data into one set of models.
        a = A01.objects.create(f_a="foo", f_b=42)
        B01.objects.create(fk_a=a, f_a="fred", f_b=1729)
        c = C01.objects.create(f_a="barney", f_b=1)
        c.mm_a.set([a])

        # ... and pull it out via the other set.
        a2 = A02.objects.all()[0]
        self.assertIsInstance(a2, A02)
        self.assertEqual(a2.f_a, "foo")

        b2 = B02.objects.all()[0]
        self.assertIsInstance(b2, B02)
        self.assertEqual(b2.f_a, "fred")

        self.assertIsInstance(b2.fk_a, A02)
        self.assertEqual(b2.fk_a.f_a, "foo")

        self.assertEqual(list(C02.objects.filter(f_a=None)), [])

        resp = list(C02.objects.filter(mm_a=a.id))
        self.assertEqual(len(resp), 1)

        self.assertIsInstance(resp[0], C02)
        self.assertEqual(resp[0].f_a, "barney")


class ManyToManyUnmanagedTests(TestCase):
    def test_many_to_many_between_unmanaged(self):
        """
        This is a comment
        """
        table = Unmanaged2._meta.get_field("mm").m2m_db_table()
        tables = connection.introspection.table_names()
        self.assertNotIn(
            table, tables, "Table '%s' should not exist, but it does." % table
        )

    def test_many_to_many_between_unmanaged_and_managed(self):
        """
        This is a comment
        """
        table = Managed1._meta.get_field("mm").m2m_db_table()
        tables = connection.introspection.table_names()
        self.assertIn(table, tables, "Table '%s' does not exist." % table)
