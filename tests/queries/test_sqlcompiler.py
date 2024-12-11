from django.db import DEFAULT_DB_ALIAS, connection
from django.db.models.sql import Query
from django.test import SimpleTestCase

from .models import Item


class SQLCompilerTest(SimpleTestCase):
    def test_repr(self):
        """

        Tests the string representation of a SQLCompiler object.

        This test case verifies that the repr function of the compiler returns the expected string,
        containing information about the model, connection, and database alias being used.

        The test checks that the string representation includes the model name, vendor, and alias
        in the expected format, ensuring that the compiler can be properly identified and debugged.

        """
        query = Query(Item)
        compiler = query.get_compiler(DEFAULT_DB_ALIAS, connection)
        self.assertEqual(
            repr(compiler),
            f"<SQLCompiler model=Item connection="
            f"<DatabaseWrapper vendor={connection.vendor!r} alias='default'> "
            f"using='default'>",
        )
