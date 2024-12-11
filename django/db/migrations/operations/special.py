from django.db import router

from .base import Operation, OperationCategory


class SeparateDatabaseAndState(Operation):
    """
    Take two lists of operations - ones that will be used for the database,
    and ones that will be used for the state change. This allows operations
    that don't support state change to have it applied, or have operations
    that affect the state or not the database, or so on.
    """

    category = OperationCategory.MIXED
    serialization_expand_args = ["database_operations", "state_operations"]

    def __init__(self, database_operations=None, state_operations=None):
        self.database_operations = database_operations or []
        self.state_operations = state_operations or []

    def deconstruct(self):
        kwargs = {}
        if self.database_operations:
            kwargs["database_operations"] = self.database_operations
        if self.state_operations:
            kwargs["state_operations"] = self.state_operations
        return (self.__class__.__qualname__, [], kwargs)

    def state_forwards(self, app_label, state):
        for state_operation in self.state_operations:
            state_operation.state_forwards(app_label, state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # We calculate state separately in here since our state functions aren't useful
        for database_operation in self.database_operations:
            to_state = from_state.clone()
            database_operation.state_forwards(app_label, to_state)
            database_operation.database_forwards(
                app_label, schema_editor, from_state, to_state
            )
            from_state = to_state

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # We calculate state separately in here since our state functions aren't useful
        to_states = {}
        for dbop in self.database_operations:
            to_states[dbop] = to_state
            to_state = to_state.clone()
            dbop.state_forwards(app_label, to_state)
        # to_state now has the states of all the database_operations applied
        # which is the from_state for the backwards migration of the last
        # operation.
        for database_operation in reversed(self.database_operations):
            from_state = to_state
            to_state = to_states[database_operation]
            database_operation.database_backwards(
                app_label, schema_editor, from_state, to_state
            )

    def describe(self):
        return "Custom state/database change combination"


class RunSQL(Operation):
    """
    Run some raw SQL. A reverse SQL statement may be provided.

    Also accept a list of operations that represent the state change effected
    by this SQL change, in case it's custom column/table creation/deletion.
    """

    category = OperationCategory.SQL
    noop = ""

    def __init__(
        self, sql, reverse_sql=None, state_operations=None, hints=None, elidable=False
    ):
        """
        Initializes a database migration operation.

        :param sql: The SQL query to execute for this migration operation.
        :param reverse_sql: The SQL query to execute to reverse this migration operation, defaults to None.
        :param state_operations: A list of state operations to perform after executing the SQL query, defaults to an empty list.
        :param hints: A dictionary of hints to use when executing the SQL query, defaults to an empty dictionary.
        :param elidable: A boolean indicating whether this migration operation can be elided, defaults to False.

        This initializer sets up the necessary parameters for a database migration operation, allowing for flexible and reversible migrations with optional state operations and hints.
        """
        self.sql = sql
        self.reverse_sql = reverse_sql
        self.state_operations = state_operations or []
        self.hints = hints or {}
        self.elidable = elidable

    def deconstruct(self):
        kwargs = {
            "sql": self.sql,
        }
        if self.reverse_sql is not None:
            kwargs["reverse_sql"] = self.reverse_sql
        if self.state_operations:
            kwargs["state_operations"] = self.state_operations
        if self.hints:
            kwargs["hints"] = self.hints
        return (self.__class__.__qualname__, [], kwargs)

    @property
    def reversible(self):
        return self.reverse_sql is not None

    def state_forwards(self, app_label, state):
        for state_operation in self.state_operations:
            state_operation.state_forwards(app_label, state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if router.allow_migrate(
            schema_editor.connection.alias, app_label, **self.hints
        ):
            self._run_sql(schema_editor, self.sql)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        """

        Reverses a database migration operation.

        This method is used to revert changes made by a forward migration operation. It checks if the migration is reversible and if the database connection is allowed to migrate. If the conditions are met, it executes the reverse SQL statement.

        :param app_label: The label of the application being migrated.
        :param schema_editor: The schema editor used to execute the reverse operation.
        :param from_state: The current state of the database.
        :param to_state: The target state of the database after the reverse operation.

        :raises NotImplementedError: If the migration operation is not reversible.

        """
        if self.reverse_sql is None:
            raise NotImplementedError("You cannot reverse this operation")
        if router.allow_migrate(
            schema_editor.connection.alias, app_label, **self.hints
        ):
            self._run_sql(schema_editor, self.reverse_sql)

    def describe(self):
        return "Raw SQL operation"

    def _run_sql(self, schema_editor, sqls):
        if isinstance(sqls, (list, tuple)):
            for sql in sqls:
                params = None
                if isinstance(sql, (list, tuple)):
                    elements = len(sql)
                    if elements == 2:
                        sql, params = sql
                    else:
                        raise ValueError("Expected a 2-tuple but got %d" % elements)
                schema_editor.execute(sql, params=params)
        elif sqls != RunSQL.noop:
            statements = schema_editor.connection.ops.prepare_sql_script(sqls)
            for statement in statements:
                schema_editor.execute(statement, params=None)


class RunPython(Operation):
    """
    Run Python code in a context suitable for doing versioned ORM operations.
    """

    category = OperationCategory.PYTHON
    reduces_to_sql = False

    def __init__(
        self, code, reverse_code=None, atomic=None, hints=None, elidable=False
    ):
        self.atomic = atomic
        # Forwards code
        if not callable(code):
            raise ValueError("RunPython must be supplied with a callable")
        self.code = code
        # Reverse code
        if reverse_code is None:
            self.reverse_code = None
        else:
            if not callable(reverse_code):
                raise ValueError("RunPython must be supplied with callable arguments")
            self.reverse_code = reverse_code
        self.hints = hints or {}
        self.elidable = elidable

    def deconstruct(self):
        kwargs = {
            "code": self.code,
        }
        if self.reverse_code is not None:
            kwargs["reverse_code"] = self.reverse_code
        if self.atomic is not None:
            kwargs["atomic"] = self.atomic
        if self.hints:
            kwargs["hints"] = self.hints
        return (self.__class__.__qualname__, [], kwargs)

    @property
    def reversible(self):
        return self.reverse_code is not None

    def state_forwards(self, app_label, state):
        # RunPython objects have no state effect. To add some, combine this
        # with SeparateDatabaseAndState.
        pass

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # RunPython has access to all models. Ensure that all models are
        # reloaded in case any are delayed.
        """

        Apply database migration forwards for the specified application label.

        This method is responsible for applying the necessary database migration operations 
        to move the database from the current state (`from_state`) to the desired state (`to_state`).
        It first clears the cache of delayed applications for the current state, 
        then checks if migration is allowed for the given application label and database connection.
        If migration is permitted, it executes the migration code using the provided schema editor.

        :param app_label: The label of the application for which the migration is being applied.
        :param schema_editor: The schema editor instance used to execute the migration operations.
        :param from_state: The current state of the database before applying the migration.
        :param to_state: The desired state of the database after applying the migration.

        """
        from_state.clear_delayed_apps_cache()
        if router.allow_migrate(
            schema_editor.connection.alias, app_label, **self.hints
        ):
            # We now execute the Python code in a context that contains a 'models'
            # object, representing the versioned models as an app registry.
            # We could try to override the global cache, but then people will still
            # use direct imports, so we go with a documentation approach instead.
            self.code(from_state.apps, schema_editor)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if self.reverse_code is None:
            raise NotImplementedError("You cannot reverse this operation")
        if router.allow_migrate(
            schema_editor.connection.alias, app_label, **self.hints
        ):
            self.reverse_code(from_state.apps, schema_editor)

    def describe(self):
        return "Raw Python operation"

    @staticmethod
    def noop(apps, schema_editor):
        return None
