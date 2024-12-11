from django.db import DEFAULT_DB_ALIAS


class TestRouter:
    """
    Vaguely behave like primary/replica, but the databases aren't assumed to
    propagate changes.
    """

    def db_for_read(self, model, instance=None, **hints):
        """
        Specify the database to use for reading operations.

        This method determines the database alias to use when reading data from the database.
        It considers the model being accessed and any available instance data.
        If an instance is provided, the database associated with the instance is used; otherwise, the default database alias 'other' is returned.

        :param model: The model being accessed
        :param instance: An instance of the model, if available
        :param hints: Additional hints to influence the database selection

        :return: The database alias to use for reading operations
        """
        if instance:
            return instance._state.db or "other"
        return "other"

    def db_for_write(self, model, **hints):
        return DEFAULT_DB_ALIAS

    def allow_relation(self, obj1, obj2, **hints):
        return obj1._state.db in ("default", "other") and obj2._state.db in (
            "default",
            "other",
        )

    def allow_migrate(self, db, app_label, **hints):
        return True


class AuthRouter:
    """
    Control all database operations on models in the contrib.auth application.
    """

    def db_for_read(self, model, **hints):
        "Point all read operations on auth models to 'default'"
        if model._meta.app_label == "auth":
            # We use default here to ensure we can tell the difference
            # between a read request and a write request for Auth objects
            return "default"
        return None

    def db_for_write(self, model, **hints):
        "Point all operations on auth models to 'other'"
        if model._meta.app_label == "auth":
            return "other"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        "Allow any relation if a model in Auth is involved"
        return obj1._meta.app_label == "auth" or obj2._meta.app_label == "auth" or None

    def allow_migrate(self, db, app_label, **hints):
        "Make sure the auth app only appears on the 'other' db"
        if app_label == "auth":
            return db == "other"
        return None


class WriteRouter:
    # A router that only expresses an opinion on writes
    def db_for_write(self, model, **hints):
        return "writer"
