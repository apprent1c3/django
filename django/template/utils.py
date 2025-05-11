import functools
from collections import Counter
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from django.utils.module_loading import import_string


class InvalidTemplateEngineError(ImproperlyConfigured):
    pass


class EngineHandler:
    def __init__(self, templates=None):
        """
        templates is an optional list of template engine definitions
        (structured like settings.TEMPLATES).
        """
        self._templates = templates
        self._engines = {}

    @cached_property
    def templates(self):
        """
        Returns a dictionary of template engines configured in the application, ensuring each engine has a unique name and providing a standardized structure for engine settings. Raises an error if a template engine is improperly configured or if duplicate engine names are found.
        """
        if self._templates is None:
            self._templates = settings.TEMPLATES

        templates = {}
        backend_names = []
        for tpl in self._templates:
            try:
                # This will raise an exception if 'BACKEND' doesn't exist or
                # isn't a string containing at least one dot.
                default_name = tpl["BACKEND"].rsplit(".", 2)[-2]
            except Exception:
                invalid_backend = tpl.get("BACKEND", "<not defined>")
                raise ImproperlyConfigured(
                    "Invalid BACKEND for a template engine: {}. Check "
                    "your TEMPLATES setting.".format(invalid_backend)
                )

            tpl = {
                "NAME": default_name,
                "DIRS": [],
                "APP_DIRS": False,
                "OPTIONS": {},
                **tpl,
            }

            templates[tpl["NAME"]] = tpl
            backend_names.append(tpl["NAME"])

        counts = Counter(backend_names)
        duplicates = [alias for alias, count in counts.most_common() if count > 1]
        if duplicates:
            raise ImproperlyConfigured(
                "Template engine aliases aren't unique, duplicates: {}. "
                "Set a unique NAME for each engine in settings.TEMPLATES.".format(
                    ", ".join(duplicates)
                )
            )

        return templates

    def __getitem__(self, alias):
        """
        Return a template engine instance for the given alias.

        Retrieve an existing engine instance or create a new one based on the template configuration settings.
        If the engine is not found, raise an InvalidTemplateEngineError.

        :param alias: The alias of the template engine to retrieve.
        :rtype: Template engine instance
        """
        try:
            return self._engines[alias]
        except KeyError:
            try:
                params = self.templates[alias]
            except KeyError:
                raise InvalidTemplateEngineError(
                    "Could not find config for '{}' "
                    "in settings.TEMPLATES".format(alias)
                )

            # If importing or initializing the backend raises an exception,
            # self._engines[alias] isn't set and this code may get executed
            # again, so we must preserve the original params. See #24265.
            params = params.copy()
            backend = params.pop("BACKEND")
            engine_cls = import_string(backend)
            engine = engine_cls(params)

            self._engines[alias] = engine
            return engine

    def __iter__(self):
        return iter(self.templates)

    def all(self):
        return [self[alias] for alias in self]


@functools.lru_cache
def get_app_template_dirs(dirname):
    """
    Return an iterable of paths of directories to load app templates from.

    dirname is the name of the subdirectory containing templates inside
    installed applications.
    """
    # Immutable return value because it will be cached and shared by callers.
    return tuple(
        path
        for app_config in apps.get_app_configs()
        if app_config.path and (path := Path(app_config.path) / dirname).is_dir()
    )
