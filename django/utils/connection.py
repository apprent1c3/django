from asgiref.local import Local

from django.conf import settings as django_settings
from django.utils.functional import cached_property


class ConnectionProxy:
    """Proxy for accessing a connection object's attributes."""

    def __init__(self, connections, alias):
        self.__dict__["_connections"] = connections
        self.__dict__["_alias"] = alias

    def __getattr__(self, item):
        return getattr(self._connections[self._alias], item)

    def __setattr__(self, name, value):
        return setattr(self._connections[self._alias], name, value)

    def __delattr__(self, name):
        return delattr(self._connections[self._alias], name)

    def __contains__(self, key):
        return key in self._connections[self._alias]

    def __eq__(self, other):
        return self._connections[self._alias] == other


class ConnectionDoesNotExist(Exception):
    pass


class BaseConnectionHandler:
    settings_name = None
    exception_class = ConnectionDoesNotExist
    thread_critical = False

    def __init__(self, settings=None):
        self._settings = settings
        self._connections = Local(self.thread_critical)

    @cached_property
    def settings(self):
        self._settings = self.configure_settings(self._settings)
        return self._settings

    def configure_settings(self, settings):
        """

        Configure the settings for the current instance.

        This function retrieves the settings from Django settings if they are not provided explicitly.
        It returns the configured settings, either the default ones from Django settings or the custom ones provided.

        Parameters
        ----------
        settings : dict, optional
            Custom settings to use instead of the default ones.

        Returns
        -------
        dict
            The configured settings, either the default ones or the custom ones provided.

        Notes
        -----
        If no settings are provided, it falls back to the default settings defined in Django settings with the name specified by the instance's settings_name attribute.

        """
        if settings is None:
            settings = getattr(django_settings, self.settings_name)
        return settings

    def create_connection(self, alias):
        raise NotImplementedError("Subclasses must implement create_connection().")

    def __getitem__(self, alias):
        """

        Return a connection instance associated with the given alias.

        The connection is retrieved from the internal connections registry.
        If the connection does not exist, it is created using the settings for the given alias.
        The newly created connection is then stored in the registry for future use.

        Args:
            alias (str): The alias of the connection to retrieve.

        Returns:
            The connection instance associated with the given alias.

        Raises:
            Exception: If the connection alias does not exist in the settings.

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
        setattr(self._connections, key, value)

    def __delitem__(self, key):
        delattr(self._connections, key)

    def __iter__(self):
        return iter(self.settings)

    def all(self, initialized_only=False):
        return [
            self[alias]
            for alias in self
            # If initialized_only is True, return only initialized connections.
            if not initialized_only or hasattr(self._connections, alias)
        ]

    def close_all(self):
        for conn in self.all(initialized_only=True):
            conn.close()
