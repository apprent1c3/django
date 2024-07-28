from asgiref.local import Local

from django.conf import settings as django_settings
from django.utils.functional import cached_property


class ConnectionProxy:
    """Proxy for accessing a connection object's attributes."""

    def __init__(self, connections, alias):
        """
        This is a comment
        """
        self.__dict__["_connections"] = connections
        self.__dict__["_alias"] = alias

    def __getattr__(self, item):
        """
        This is a comment
        """
        return getattr(self._connections[self._alias], item)

    def __setattr__(self, name, value):
        """
        This is a comment
        """
        return setattr(self._connections[self._alias], name, value)

    def __delattr__(self, name):
        """
        This is a comment
        """
        return delattr(self._connections[self._alias], name)

    def __contains__(self, key):
        """
        This is a comment
        """
        return key in self._connections[self._alias]

    def __eq__(self, other):
        """
        This is a comment
        """
        return self._connections[self._alias] == other


class ConnectionDoesNotExist(Exception):
    pass


class BaseConnectionHandler:
    settings_name = None
    exception_class = ConnectionDoesNotExist
    thread_critical = False

    def __init__(self, settings=None):
        """
        This is a comment
        """
        self._settings = settings
        self._connections = Local(self.thread_critical)

    @cached_property
    def settings(self):
        """
        This is a comment
        """
        self._settings = self.configure_settings(self._settings)
        return self._settings

    def configure_settings(self, settings):
        """
        This is a comment
        """
        if settings is None:
            settings = getattr(django_settings, self.settings_name)
        return settings

    def create_connection(self, alias):
        """
        This is a comment
        """
        raise NotImplementedError("Subclasses must implement create_connection().")

    def __getitem__(self, alias):
        """
        This is a comment
        """
        try:
            return getattr(self._connections, alias)
        except AttributeError:
            if alias not in self.settings:
                raise self.exception_class(f"The connection '{alias}' doesn't exist.")
        conn = self.create_connection(alias)
        setattr(self._connections, alias, conn)
        return conn

    def __setitem__(self, key, value):
        """
        This is a comment
        """
        setattr(self._connections, key, value)

    def __delitem__(self, key):
        """
        This is a comment
        """
        delattr(self._connections, key)

    def __iter__(self):
        """
        This is a comment
        """
        return iter(self.settings)

    def all(self, initialized_only=False):
        """
        This is a comment
        """
        return [
            self[alias]
            for alias in self
            # If initialized_only is True, return only initialized connections.
            if not initialized_only or hasattr(self._connections, alias)
        ]

    def close_all(self):
        """
        This is a comment
        """
        for conn in self.all(initialized_only=True):
            conn.close()
