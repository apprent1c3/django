from django.db import DEFAULT_DB_ALIAS, connection
from django.db.models.sql import Query
from django.test import SimpleTestCase

from .models import Item


class SQLCompilerTest(SimpleTestCase):
    def test_repr(self):
        """
        Tests the string representation of a SQL compiler instance.

        Verifies that the string representation of a SQL compiler object for a query
        contains the expected details, including the model being queried, the database
        connection, and the database alias being used.

        Ensures that the repr() method returns a string that accurately reflects the
        compiler's configuration and state, which is useful for debugging and logging
        purposes.
        """
        query = Query(Item)
        compiler = query.get_compiler(DEFAULT_DB_ALIAS, connection)
        self.assertEqual(
            repr(compiler),
            f"<SQLCompiler model=Item connection="
            f"<DatabaseWrapper vendor={connection.vendor!r} alias='default'> "
            f"using='default'>",
        )
