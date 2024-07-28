import enum

from django.db import router


class OperationCategory(str, enum.Enum):
    ADDITION = "+"
    REMOVAL = "-"
    ALTERATION = "~"
    PYTHON = "p"
    SQL = "s"
    MIXED = "?"


class Operation:
    """
    Base class for migration operations.

    It's responsible for both mutating the in-memory model state
    (see db/migrations/state.py) to represent what it performs, as well
    as actually performing it against a live database.

    Note that some operations won't modify memory state at all (e.g. data
    copying operations), and some will need their modifications to be
    optionally specified by the user (e.g. custom Python code snippets)

    Due to the way this class deals with deconstruction, it should be
    considered immutable.
    """

    # If this migration can be run in reverse.
    # Some operations are impossible to reverse, like deleting data.
    reversible = True

    # Can this migration be represented as SQL? (things like RunPython cannot)
    reduces_to_sql = True

    # Should this operation be forced as atomic even on backends with no
    # DDL transaction support (i.e., does it have no DDL, like RunPython)
    atomic = False

    # Should this operation be considered safe to elide and optimize across?
    elidable = False

    serialization_expand_args = []

    category = None

    def __new__(cls, *args, **kwargs):
        # We capture the arguments to make returning them trivial
        """
        This is a comment
        """
        self = object.__new__(cls)
        self._constructor_args = (args, kwargs)
        return self

    def deconstruct(self):
        """
        This is a comment
        """
        return (
            self.__class__.__name__,
            self._constructor_args[0],
            self._constructor_args[1],
        )

    def state_forwards(self, app_label, state):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Operation must provide a state_forwards() method"
        )

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Operation must provide a database_forwards() method"
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Operation must provide a database_backwards() method"
        )

    def describe(self):
        """
        This is a comment
        """
        return "%s: %s" % (self.__class__.__name__, self._constructor_args)

    def formatted_description(self):
        """
        This is a comment
        """
        description = self.describe()
        if self.category is None:
            return f"{OperationCategory.MIXED.value} {description}"
        return f"{self.category.value} {description}"

    @property
    def migration_name_fragment(self):
        """
        This is a comment
        """
        return None

    def references_model(self, name, app_label):
        """
        This is a comment
        """
        return True

    def references_field(self, model_name, name, app_label):
        """
        This is a comment
        """
        return self.references_model(model_name, app_label)

    def allow_migrate_model(self, connection_alias, model):
        """
        This is a comment
        """
        if not model._meta.can_migrate(connection_alias):
            return False

        return router.allow_migrate_model(connection_alias, model)

    def reduce(self, operation, app_label):
        """
        This is a comment
        """
        if self.elidable:
            return [operation]
        elif operation.elidable:
            return [self]
        return False

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s %s%s>" % (
            self.__class__.__name__,
            ", ".join(map(repr, self._constructor_args[0])),
            ",".join(" %s=%r" % x for x in self._constructor_args[1].items()),
        )
