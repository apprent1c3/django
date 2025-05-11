import pkgutil
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# For backwards compatibility with Django < 3.2
from django.utils.connection import ConnectionDoesNotExist  # NOQA: F401
from django.utils.connection import BaseConnectionHandler
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

DEFAULT_DB_ALIAS = "default"
DJANGO_VERSION_PICKLE_KEY = "_django_version"


class Error(Exception):
    pass


class InterfaceError(Error):
    pass


class DatabaseError(Error):
    pass


class DataError(DatabaseError):
    pass


class OperationalError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class InternalError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class NotSupportedError(DatabaseError):
    pass


class DatabaseErrorWrapper:
    """
    Context manager and decorator that reraises backend-specific database
    exceptions using Django's common wrappers.
    """

    def __init__(self, wrapper):
        """
        wrapper is a database wrapper.

        It must have a Database attribute defining PEP-249 exceptions.
        """
        self.wrapper = wrapper

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        """

        Handle exceptions that occur within a runtime context, converting low-level database errors into Django's exception hierarchy.

        If an exception occurs, this method checks if it is a subclass of a Django database exception type and raises a corresponding Django exception if so, preserving the original traceback.

        """
        if exc_type is None:
            return
        for dj_exc_type in (
            DataError,
            OperationalError,
            IntegrityError,
            InternalError,
            ProgrammingError,
            NotSupportedError,
            DatabaseError,
            InterfaceError,
            Error,
        ):
            db_exc_type = getattr(self.wrapper.Database, dj_exc_type.__name__)
            if issubclass(exc_type, db_exc_type):
                dj_exc_value = dj_exc_type(*exc_value.args)
                # Only set the 'errors_occurred' flag for errors that may make
                # the connection unusable.
                if dj_exc_type not in (DataError, IntegrityError):
                    self.wrapper.errors_occurred = True
                raise dj_exc_value.with_traceback(traceback) from exc_value

    def __call__(self, func):
        # Note that we are intentionally not using @wraps here for performance
        # reasons. Refs #21109.
        def inner(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return inner


def load_backend(backend_name):
    """
    Return a database backend's "base" module given a fully qualified database
    backend name, or raise an error if it doesn't exist.
    """
    # This backend was renamed in Django 1.9.
    if backend_name == "django.db.backends.postgresql_psycopg2":
        backend_name = "django.db.backends.postgresql"

    try:
        return import_module("%s.base" % backend_name)
    except ImportError as e_user:
        # The database backend wasn't found. Display a helpful error message
        # listing all built-in database backends.
        import django.db.backends

        builtin_backends = [
            name
            for _, name, ispkg in pkgutil.iter_modules(django.db.backends.__path__)
            if ispkg and name not in {"base", "dummy"}
        ]
        if backend_name not in ["django.db.backends.%s" % b for b in builtin_backends]:
            backend_reprs = map(repr, sorted(builtin_backends))
            raise ImproperlyConfigured(
                "%r isn't an available database backend or couldn't be "
                "imported. Check the above exception. To use one of the "
                "built-in backends, use 'django.db.backends.XXX', where XXX "
                "is one of:\n"
                "    %s" % (backend_name, ", ".join(backend_reprs))
            ) from e_user
        else:
            # If there's some other error, this must be an error in Django
            raise


class ConnectionHandler(BaseConnectionHandler):
    settings_name = "DATABASES"
    # Connections needs to still be an actual thread local, as it's truly
    # thread-critical. Database backends should use @async_unsafe to protect
    # their code from async contexts, but this will give those contexts
    # separate connections in case it's needed as well. There's no cleanup
    # after async contexts, though, so we don't allow that if we can help it.
    thread_critical = True

    def configure_settings(self, databases):
        """
        Configures database settings by setting default values and performing validation. 
        Ensures a default database is defined and sets various database connection settings 
        to their default values if not explicitly provided. Raises an exception if the default 
        database alias is not defined in the databases dictionary.
        """
        databases = super().configure_settings(databases)
        if databases == {}:
            databases[DEFAULT_DB_ALIAS] = {"ENGINE": "django.db.backends.dummy"}
        elif DEFAULT_DB_ALIAS not in databases:
            raise ImproperlyConfigured(
                f"You must define a '{DEFAULT_DB_ALIAS}' database."
            )
        elif databases[DEFAULT_DB_ALIAS] == {}:
            databases[DEFAULT_DB_ALIAS]["ENGINE"] = "django.db.backends.dummy"

        # Configure default settings.
        for conn in databases.values():
            conn.setdefault("ATOMIC_REQUESTS", False)
            conn.setdefault("AUTOCOMMIT", True)
            conn.setdefault("ENGINE", "django.db.backends.dummy")
            if conn["ENGINE"] == "django.db.backends." or not conn["ENGINE"]:
                conn["ENGINE"] = "django.db.backends.dummy"
            conn.setdefault("CONN_MAX_AGE", 0)
            conn.setdefault("CONN_HEALTH_CHECKS", False)
            conn.setdefault("OPTIONS", {})
            conn.setdefault("TIME_ZONE", None)
            for setting in ["NAME", "USER", "PASSWORD", "HOST", "PORT"]:
                conn.setdefault(setting, "")

            test_settings = conn.setdefault("TEST", {})
            default_test_settings = [
                ("CHARSET", None),
                ("COLLATION", None),
                ("MIGRATE", True),
                ("MIRROR", None),
                ("NAME", None),
            ]
            for key, value in default_test_settings:
                test_settings.setdefault(key, value)
        return databases

    @property
    def databases(self):
        # Maintained for backward compatibility as some 3rd party packages have
        # made use of this private API in the past. It is no longer used within
        # Django itself.
        return self.settings

    def create_connection(self, alias):
        db = self.settings[alias]
        backend = load_backend(db["ENGINE"])
        return backend.DatabaseWrapper(db, alias)


class ConnectionRouter:
    def __init__(self, routers=None):
        """
        If routers is not specified, default to settings.DATABASE_ROUTERS.
        """
        self._routers = routers

    @cached_property
    def routers(self):
        """
        Returns a list of database routers configured for the instance, 
        instantiating any router specified as a string using import_string.
        """
        if self._routers is None:
            self._routers = settings.DATABASE_ROUTERS
        routers = []
        for r in self._routers:
            if isinstance(r, str):
                router = import_string(r)()
            else:
                router = r
            routers.append(router)
        return routers

    def _router_func(action):
        """

        Determines the database to be used for a given model based on routing rules.

        This function returns a closure that iterates over registered routers to find a suitable database
        for the specified model. If no router decides on a database, it falls back to the default database
        alias or the instance's state database if available.

        :param action: The action to be performed on the router (e.g., 'db_for_read', 'db_for_write')
        :returns: A function that takes a model, hints, and returns the chosen database.

        """
        def _route_db(self, model, **hints):
            """
            Determines the database to use for a given model, following a specific routing order.

            The function iterates through the list of available routers, utilizing the first router that returns a non-empty database choice.
            If no routers return a choice, it falls back to the instance's database if available, and finally defaults to the default database alias.
            """
            chosen_db = None
            for router in self.routers:
                try:
                    method = getattr(router, action)
                except AttributeError:
                    # If the router doesn't have a method, skip to the next one.
                    pass
                else:
                    chosen_db = method(model, **hints)
                    if chosen_db:
                        return chosen_db
            instance = hints.get("instance")
            if instance is not None and instance._state.db:
                return instance._state.db
            return DEFAULT_DB_ALIAS

        return _route_db

    db_for_read = _router_func("db_for_read")
    db_for_write = _router_func("db_for_write")

    def allow_relation(self, obj1, obj2, **hints):
        """

        Determines whether a relation between two objects is allowed.
        Checks all routers for a custom allowance decision, falling back to
        a simple database-level check if no custom decision is made.

        """
        for router in self.routers:
            try:
                method = router.allow_relation
            except AttributeError:
                # If the router doesn't have a method, skip to the next one.
                pass
            else:
                allow = method(obj1, obj2, **hints)
                if allow is not None:
                    return allow
        return obj1._state.db == obj2._state.db

    def allow_migrate(self, db, app_label, **hints):
        """
        Determines whether a migration operation is allowed on a given database and app.

        This method iterates over a list of database routers and checks if they allow migration.
        The first router to provide a explicit decision (True or False) dictates the outcome,
        otherwise it defaults to allowing the migration. The decision is based on the database,
        app label, and any additional hints provided.
        """
        for router in self.routers:
            try:
                method = router.allow_migrate
            except AttributeError:
                # If the router doesn't have a method, skip to the next one.
                continue

            allow = method(db, app_label, **hints)

            if allow is not None:
                return allow
        return True

    def allow_migrate_model(self, db, model):
        return self.allow_migrate(
            db,
            model._meta.app_label,
            model_name=model._meta.model_name,
            model=model,
        )

    def get_migratable_models(self, app_config, db, include_auto_created=False):
        """Return app models allowed to be migrated on provided db."""
        models = app_config.get_models(include_auto_created=include_auto_created)
        return [model for model in models if self.allow_migrate_model(db, model)]
