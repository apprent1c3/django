from django.db.migrations.operations.base import Operation


class TestOperation(Operation):
    def __init__(self):
        """
        This is a comment
        """
        pass

    def deconstruct(self):
        """
        This is a comment
        """
        return (self.__class__.__name__, [], {})

    @property
    def reversible(self):
        """
        This is a comment
        """
        return True

    def state_forwards(self, app_label, state):
        """
        This is a comment
        """
        pass

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        """
        This is a comment
        """
        pass

    def state_backwards(self, app_label, state):
        """
        This is a comment
        """
        pass

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        """
        This is a comment
        """
        pass
