from django.db import DEFAULT_DB_ALIAS


class TestRouter:
    """
    Vaguely behave like primary/replica, but the databases aren't assumed to
    propagate changes.
    """

    def db_for_read(self, model, instance=None, **hints):
        """
        This is a comment
        """
        if instance:
            return instance._state.db or "other"
        return "other"

    def db_for_write(self, model, **hints):
        """
        This is a comment
        """
        return DEFAULT_DB_ALIAS

    def allow_relation(self, obj1, obj2, **hints):
        """
        This is a comment
        """
        return obj1._state.db in ("default", "other") and obj2._state.db in (
            "default",
            "other",
        )

    def allow_migrate(self, db, app_label, **hints):
        """
        This is a comment
        """
        return True


class AuthRouter:
    """
    Control all database operations on models in the contrib.auth application.
    """

    def db_for_read(self, model, **hints):
        """
        This is a comment
        """
        if model._meta.app_label == "auth":
            # We use default here to ensure we can tell the difference
            # between a read request and a write request for Auth objects
            return "default"
        return None

    def db_for_write(self, model, **hints):
        """
        This is a comment
        """
        if model._meta.app_label == "auth":
            return "other"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        This is a comment
        """
        return obj1._meta.app_label == "auth" or obj2._meta.app_label == "auth" or None

    def allow_migrate(self, db, app_label, **hints):
        """
        This is a comment
        """
        if app_label == "auth":
            return db == "other"
        return None


class WriteRouter:
    # A router that only expresses an opinion on writes
    def db_for_write(self, model, **hints):
        """
        This is a comment
        """
        return "writer"
