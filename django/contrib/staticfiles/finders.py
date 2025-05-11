import functools
import os
import warnings

from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles import utils
from django.core.checks import Error, Warning
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage, Storage, default_storage
from django.utils._os import safe_join
from django.utils.deprecation import RemovedInDjango61Warning
from django.utils.functional import LazyObject, empty
from django.utils.module_loading import import_string

# To keep track on which directories the finder has searched the static files.
searched_locations = []


# RemovedInDjango61Warning: When the deprecation ends, remove completely.
def _check_deprecated_find_param(class_name="", find_all=False, **kwargs):
    """
    Checks for deprecated usage of the 'all' argument in find() methods.

    Warns when 'all' is used, suggesting 'find_all' instead, and returns the effective find_all value.
    Raises an error if 'find_all' is already specified or if any other unexpected keyword arguments are provided.
    """
    method_name = "find" if not class_name else f"{class_name}.find"
    if "all" in kwargs:
        legacy_all = kwargs.pop("all")
        msg = (
            "Passing the `all` argument to find() is deprecated. Use `find_all` "
            "instead."
        )
        warnings.warn(msg, RemovedInDjango61Warning, stacklevel=2)

        # If both `find_all` and `all` were given, raise TypeError.
        if find_all is not False:
            raise TypeError(
                f"{method_name}() got multiple values for argument 'find_all'"
            )

        find_all = legacy_all

    if kwargs:  # any remaining kwargs must be a TypeError
        first = list(kwargs.keys()).pop()
        raise TypeError(f"{method_name}() got an unexpected keyword argument '{first}'")

    return find_all


class BaseFinder:
    """
    A base file finder to be used for custom staticfiles finder classes.
    """

    def check(self, **kwargs):
        raise NotImplementedError(
            "subclasses may provide a check() method to verify the finder is "
            "configured correctly."
        )

    # RemovedInDjango61Warning: When the deprecation ends, remove completely.
    def _check_deprecated_find_param(self, **kwargs):
        return _check_deprecated_find_param(
            class_name=self.__class__.__qualname__, **kwargs
        )

    # RemovedInDjango61Warning: When the deprecation ends, replace with:
    # def find(self, path, find_all=False):
    def find(self, path, find_all=False, **kwargs):
        """
        Given a relative file path, find an absolute file path.

        If the ``find_all`` parameter is False (default) return only the first
        found file path; if True, return a list of all found files paths.
        """
        raise NotImplementedError(
            "subclasses of BaseFinder must provide a find() method"
        )

    def list(self, ignore_patterns):
        """
        Given an optional list of paths to ignore, return a two item iterable
        consisting of the relative path and storage instance.
        """
        raise NotImplementedError(
            "subclasses of BaseFinder must provide a list() method"
        )


class FileSystemFinder(BaseFinder):
    """
    A static files finder that uses the ``STATICFILES_DIRS`` setting
    to locate files.
    """

    def __init__(self, app_names=None, *args, **kwargs):
        # List of locations with static files
        """
        Initializes the static file storage system, populating locations and storages based on settings.

        :param app_names: Optional list of application names to consider for static file storage.

        """
        self.locations = []
        # Maps dir paths to an appropriate storage instance
        self.storages = {}
        for root in settings.STATICFILES_DIRS:
            if isinstance(root, (list, tuple)):
                prefix, root = root
            else:
                prefix = ""
            if (prefix, root) not in self.locations:
                self.locations.append((prefix, root))
        for prefix, root in self.locations:
            filesystem_storage = FileSystemStorage(location=root)
            filesystem_storage.prefix = prefix
            self.storages[root] = filesystem_storage
        super().__init__(*args, **kwargs)

    def check(self, **kwargs):
        """
        Checks the configuration of static file directories for potential errors.

        This function verifies the STATICFILES_DIRS setting to ensure it is properly formatted and does not conflict with the STATIC_ROOT setting. It also checks for the existence of directories specified in STATICFILES_DIRS.

        Returns a list of errors and warnings encountered during the validation process.
        """
        errors = []
        if not isinstance(settings.STATICFILES_DIRS, (list, tuple)):
            errors.append(
                Error(
                    "The STATICFILES_DIRS setting is not a tuple or list.",
                    hint="Perhaps you forgot a trailing comma?",
                    id="staticfiles.E001",
                )
            )
            return errors
        for root in settings.STATICFILES_DIRS:
            if isinstance(root, (list, tuple)):
                prefix, root = root
                if prefix.endswith("/"):
                    errors.append(
                        Error(
                            "The prefix %r in the STATICFILES_DIRS setting must "
                            "not end with a slash." % prefix,
                            id="staticfiles.E003",
                        )
                    )
            if settings.STATIC_ROOT and os.path.abspath(
                settings.STATIC_ROOT
            ) == os.path.abspath(root):
                errors.append(
                    Error(
                        "The STATICFILES_DIRS setting should not contain the "
                        "STATIC_ROOT setting.",
                        id="staticfiles.E002",
                    )
                )
            if not os.path.isdir(root):
                errors.append(
                    Warning(
                        f"The directory '{root}' in the STATICFILES_DIRS setting "
                        f"does not exist.",
                        id="staticfiles.W004",
                    )
                )
        return errors

    # RemovedInDjango61Warning: When the deprecation ends, replace with:
    # def find(self, path, find_all=False):
    def find(self, path, find_all=False, **kwargs):
        """
        Look for files in the extra locations as defined in STATICFILES_DIRS.

        :param path: Path to the file being searched for
        :param find_all: If True, returns all matching files; otherwise, returns the first match
        :param **kwargs: Additional deprecated parameters, still accepted for backwards compatibility
        :return: Path(s) to the matching file(s) if found, or an empty list if not found
        """
        # RemovedInDjango61Warning.
        if kwargs:
            find_all = self._check_deprecated_find_param(find_all=find_all, **kwargs)
        matches = []
        for prefix, root in self.locations:
            if root not in searched_locations:
                searched_locations.append(root)
            matched_path = self.find_location(root, path, prefix)
            if matched_path:
                if not find_all:
                    return matched_path
                matches.append(matched_path)
        return matches

    def find_location(self, root, path, prefix=None):
        """
        Find a requested static file in a location and return its absolute path, or None if not found. The search can be constrained by a prefix, which is removed from the path if a match is found.
        """
        if prefix:
            prefix = "%s%s" % (prefix, os.sep)
            if not path.startswith(prefix):
                return None
            path = path.removeprefix(prefix)
        path = safe_join(root, path)
        if os.path.exists(path):
            return path

    def list(self, ignore_patterns):
        """

        List all files in all locations, filtering out files that match the specified ignore patterns.

        :arg ignore_patterns: A list of patterns to exclude from the results
        :yield: Tuples containing the file path and its corresponding storage object

        """
        for prefix, root in self.locations:
            # Skip nonexistent directories.
            if os.path.isdir(root):
                storage = self.storages[root]
                for path in utils.get_files(storage, ignore_patterns):
                    yield path, storage


class AppDirectoriesFinder(BaseFinder):
    """
    A static files finder that looks in the directory of each app as
    specified in the source_dir attribute.
    """

    storage_class = FileSystemStorage
    source_dir = "static"

    def __init__(self, app_names=None, *args, **kwargs):
        # The list of apps that are handled
        """

        Initialize the object, optionally filtering app configurations by name.

        This constructor sets up the internal state by iterating over available app configurations,
        creating storage instances for each, and storing them in a dictionary for later access.
        The `app_names` parameter allows specifying a subset of apps to consider.

        """
        self.apps = []
        # Mapping of app names to storage instances
        self.storages = {}
        app_configs = apps.get_app_configs()
        if app_names:
            app_names = set(app_names)
            app_configs = [ac for ac in app_configs if ac.name in app_names]
        for app_config in app_configs:
            app_storage = self.storage_class(
                os.path.join(app_config.path, self.source_dir)
            )
            if os.path.isdir(app_storage.location):
                self.storages[app_config.name] = app_storage
                if app_config.name not in self.apps:
                    self.apps.append(app_config.name)
        super().__init__(*args, **kwargs)

    def list(self, ignore_patterns):
        """
        List all files in all app storages, excluding those that match the specified ignore patterns, and yield their paths along with their respective storage locations.
        """
        for storage in self.storages.values():
            if storage.exists(""):  # check if storage location exists
                for path in utils.get_files(storage, ignore_patterns):
                    yield path, storage

    # RemovedInDjango61Warning: When the deprecation ends, replace with:
    # def find(self, path, find_all=False):
    def find(self, path, find_all=False, **kwargs):
        """
        Look for files in application directories based on the provided path.

        :param path: The path to search for.
        :param find_all: If True, returns all matching files; otherwise returns the first match.
        :param **kwargs: Additional keyword arguments (unsupported, for backwards compatibility).
        :return: A list of matching files if find_all is True, otherwise a single match or None if not found.
        """
        # RemovedInDjango61Warning.
        if kwargs:
            find_all = self._check_deprecated_find_param(find_all=find_all, **kwargs)
        matches = []
        for app in self.apps:
            app_location = self.storages[app].location
            if app_location not in searched_locations:
                searched_locations.append(app_location)
            match = self.find_in_app(app, path)
            if match:
                if not find_all:
                    return match
                matches.append(match)
        return matches

    def find_in_app(self, app, path):
        """
        Find a requested static file within an application's static locations.

            :param app: The application to search for the file
            :param path: The path of the static file to find
            :return: The full path to the static file if found, otherwise None
        """
        storage = self.storages.get(app)
        # Only try to find a file if the source dir actually exists.
        if storage and storage.exists(path):
            matched_path = storage.path(path)
            if matched_path:
                return matched_path


class BaseStorageFinder(BaseFinder):
    """
    A base static files finder to be used to extended
    with an own storage class.
    """

    storage = None

    def __init__(self, storage=None, *args, **kwargs):
        """
        Initializes the static files finder instance with the given storage class, ensuring it is properly configured and set up for use.
        """
        if storage is not None:
            self.storage = storage
        if self.storage is None:
            raise ImproperlyConfigured(
                "The staticfiles storage finder %r "
                "doesn't have a storage class "
                "assigned." % self.__class__
            )
        # Make sure we have a storage instance here.
        if not isinstance(self.storage, (Storage, LazyObject)):
            self.storage = self.storage()
        super().__init__(*args, **kwargs)

    # RemovedInDjango61Warning: When the deprecation ends, replace with:
    # def find(self, path, find_all=False):
    def find(self, path, find_all=False, **kwargs):
        """

        Look for files in the default local file storage.

        SEARCHBehaviour can be controlled by the find_all parameter. If set, 
        returns a list of all matches, otherwise a single match or an empty list.

        Parameters
        ----------
        path : str
            Path to the file to look for
        find_all : bool
            Whether to return all matches (default: False)
        kwargs
            Additional, deprecated, keyword arguments

        Returns
        -------
        str or list
            The matching file path(s) if found, otherwise an empty list

        """
        # RemovedInDjango61Warning.
        if kwargs:
            find_all = self._check_deprecated_find_param(find_all=find_all, **kwargs)
        try:
            self.storage.path("")
        except NotImplementedError:
            pass
        else:
            if self.storage.location not in searched_locations:
                searched_locations.append(self.storage.location)
            if self.storage.exists(path):
                match = self.storage.path(path)
                if find_all:
                    match = [match]
                return match
        return []

    def list(self, ignore_patterns):
        """
        List all files of the storage.
        """
        for path in utils.get_files(self.storage, ignore_patterns):
            yield path, self.storage


class DefaultStorageFinder(BaseStorageFinder):
    """
    A static files finder that uses the default storage backend.
    """

    storage = default_storage

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_location = getattr(self.storage, "base_location", empty)
        if not base_location:
            raise ImproperlyConfigured(
                "The storage backend of the "
                "staticfiles finder %r doesn't have "
                "a valid location." % self.__class__
            )


# RemovedInDjango61Warning: When the deprecation ends, replace with:
# def find(path, find_all=False):
def find(path, find_all=False, **kwargs):
    """
    Locate a static file by its path, utilizing all available finders.

    The search can be configured to return either the first matching file path or all matching paths. If no matches are found, it returns None (or an empty list, depending on the find_all parameter).
    """
    # RemovedInDjango61Warning.
    if kwargs:
        find_all = _check_deprecated_find_param(find_all=find_all, **kwargs)
    searched_locations[:] = []
    matches = []
    for finder in get_finders():
        result = finder.find(path, find_all=find_all)
        if not find_all and result:
            return result
        if not isinstance(result, (list, tuple)):
            result = [result]
        matches.extend(result)
    if matches:
        return matches
    # No match.
    return [] if find_all else None


def get_finders():
    for finder_path in settings.STATICFILES_FINDERS:
        yield get_finder(finder_path)


@functools.cache
def get_finder(import_path):
    """
    Imports and instantiates a static files finder class based on the provided import path, ensuring it is a subclass of BaseFinder.
    """
    Finder = import_string(import_path)
    if not issubclass(Finder, BaseFinder):
        raise ImproperlyConfigured(
            'Finder "%s" is not a subclass of "%s"' % (Finder, BaseFinder)
        )
    return Finder()
