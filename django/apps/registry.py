import functools
import sys
import threading
import warnings
from collections import Counter, defaultdict
from functools import partial

from django.core.exceptions import AppRegistryNotReady, ImproperlyConfigured

from .config import AppConfig


class Apps:
    """
    A registry that stores the configuration of installed applications.

    It also keeps track of models, e.g. to provide reverse relations.
    """

    def __init__(self, installed_apps=()):
        # installed_apps is set to None when creating the main registry
        # because it cannot be populated at that point. Other registries must
        # provide a list of installed apps and are populated immediately.
        """
        Initializes the application with the given installed apps.

        This initialization method sets up the application's configuration and model storage.
        It processes the installed applications and prepares the application for use.
        If no installed apps are provided and a default is available, it raises an error.
        The initialization occurs in a thread-safe manner to prevent concurrent access issues.
        """
        if installed_apps is None and hasattr(sys.modules[__name__], "apps"):
            raise RuntimeError("You must supply an installed_apps argument.")

        # Mapping of app labels => model names => model classes. Every time a
        # model is imported, ModelBase.__new__ calls apps.register_model which
        # creates an entry in all_models. All imported models are registered,
        # regardless of whether they're defined in an installed application
        # and whether the registry has been populated. Since it isn't possible
        # to reimport a module safely (it could reexecute initialization code)
        # all_models is never overridden or reset.
        self.all_models = defaultdict(dict)

        # Mapping of labels to AppConfig instances for installed apps.
        self.app_configs = {}

        # Stack of app_configs. Used to store the current state in
        # set_available_apps and set_installed_apps.
        self.stored_app_configs = []

        # Whether the registry is populated.
        self.apps_ready = self.models_ready = self.ready = False
        # For the autoreloader.
        self.ready_event = threading.Event()

        # Lock for thread-safe population.
        self._lock = threading.RLock()
        self.loading = False

        # Maps ("app_label", "modelname") tuples to lists of functions to be
        # called when the corresponding model is ready. Used by this class's
        # `lazy_model_operation()` and `do_pending_operations()` methods.
        self._pending_operations = defaultdict(list)

        # Populate apps and models, unless it's the main registry.
        if installed_apps is not None:
            self.populate(installed_apps)

    def populate(self, installed_apps=None):
        """
        Load and initialize application configurations and models.

        This method is responsible for setting up application configurations, importing models, and ensuring that all necessary applications are properly loaded and configured.

        It provides thread safety, but is not reentrant, meaning it should not be called while another call to this method is still in progress. If the initialization process has already completed, this method will do nothing.

        It validates the uniqueness of application labels and names, raising an error if duplicates are found.

        Once all configurations are loaded, it triggers the `ready` method for each application, indicating that the setup is complete.
        """
        if self.ready:
            return

        # populate() might be called by two threads in parallel on servers
        # that create threads before initializing the WSGI callable.
        with self._lock:
            if self.ready:
                return

            # An RLock prevents other threads from entering this section. The
            # compare and set operation below is atomic.
            if self.loading:
                # Prevent reentrant calls to avoid running AppConfig.ready()
                # methods twice.
                raise RuntimeError("populate() isn't reentrant")
            self.loading = True

            # Phase 1: initialize app configs and import app modules.
            for entry in installed_apps:
                if isinstance(entry, AppConfig):
                    app_config = entry
                else:
                    app_config = AppConfig.create(entry)
                if app_config.label in self.app_configs:
                    raise ImproperlyConfigured(
                        "Application labels aren't unique, "
                        "duplicates: %s" % app_config.label
                    )

                self.app_configs[app_config.label] = app_config
                app_config.apps = self

            # Check for duplicate app names.
            counts = Counter(
                app_config.name for app_config in self.app_configs.values()
            )
            duplicates = [name for name, count in counts.most_common() if count > 1]
            if duplicates:
                raise ImproperlyConfigured(
                    "Application names aren't unique, "
                    "duplicates: %s" % ", ".join(duplicates)
                )

            self.apps_ready = True

            # Phase 2: import models modules.
            for app_config in self.app_configs.values():
                app_config.import_models()

            self.clear_cache()

            self.models_ready = True

            # Phase 3: run ready() methods of app configs.
            for app_config in self.get_app_configs():
                app_config.ready()

            self.ready = True
            self.ready_event.set()

    def check_apps_ready(self):
        """
        Checks if all applications are ready and imported, raising an exception if the import process is incomplete.
        """
        if not self.apps_ready:
            from django.conf import settings

            # If "not ready" is due to unconfigured settings, accessing
            # INSTALLED_APPS raises a more helpful ImproperlyConfigured
            # exception.
            settings.INSTALLED_APPS
            raise AppRegistryNotReady("Apps aren't loaded yet.")

    def check_models_ready(self):
        """Raise an exception if all models haven't been imported yet."""
        if not self.models_ready:
            raise AppRegistryNotReady("Models aren't loaded yet.")

    def get_app_configs(self):
        """Import applications and return an iterable of app configs."""
        self.check_apps_ready()
        return self.app_configs.values()

    def get_app_config(self, app_label):
        """
        Retrieves the application configuration for the specified app label, raising a LookupError if no matching application exists.
        """
        self.check_apps_ready()
        try:
            return self.app_configs[app_label]
        except KeyError:
            message = "No installed app with label '%s'." % app_label
            for app_config in self.get_app_configs():
                if app_config.name == app_label:
                    message += " Did you mean '%s'?" % app_config.label
                    break
            raise LookupError(message)

    # This method is performance-critical at least for Django's test suite.
    @functools.cache
    def get_models(self, include_auto_created=False, include_swapped=False):
        """
        Return a list of all installed models.

        The list can be filtered to exclude auto-created models for many-to-many relations 
        and swapped-out models, or include them using the include_auto_created and 
        include_swapped parameters.
        """
        self.check_models_ready()

        result = []
        for app_config in self.app_configs.values():
            result.extend(app_config.get_models(include_auto_created, include_swapped))
        return result

    def get_model(self, app_label, model_name=None, require_ready=True):
        """
        Return the model matching the given app_label and model_name.

        As a shortcut, app_label may be in the form <app_label>.<model_name>.

        model_name is case-insensitive.

        Raise LookupError if no application exists with this label, or no
        model exists with this name in the application. Raise ValueError if
        called with a single argument that doesn't contain exactly one dot.
        """
        if require_ready:
            self.check_models_ready()
        else:
            self.check_apps_ready()

        if model_name is None:
            app_label, model_name = app_label.split(".")

        app_config = self.get_app_config(app_label)

        if not require_ready and app_config.models is None:
            app_config.import_models()

        return app_config.get_model(model_name, require_ready=require_ready)

    def register_model(self, app_label, model):
        # Since this method is called when models are imported, it cannot
        # perform imports because of the risk of import loops. It mustn't
        # call get_app_config().
        """
        Registers a model with the system, storing it by app label and model name, and performs necessary post-registration operations to ensure consistency and update relevant caches. If a model with the same name already exists for the given app label, it raises an exception unless the existing model is identical, in which case it issues a warning.
        """
        model_name = model._meta.model_name
        app_models = self.all_models[app_label]
        if model_name in app_models:
            if (
                model.__name__ == app_models[model_name].__name__
                and model.__module__ == app_models[model_name].__module__
            ):
                warnings.warn(
                    "Model '%s.%s' was already registered. Reloading models is not "
                    "advised as it can lead to inconsistencies, most notably with "
                    "related models." % (app_label, model_name),
                    RuntimeWarning,
                    stacklevel=2,
                )
            else:
                raise RuntimeError(
                    "Conflicting '%s' models in application '%s': %s and %s."
                    % (model_name, app_label, app_models[model_name], model)
                )
        app_models[model_name] = model
        self.do_pending_operations(model)
        self.clear_cache()

    def is_installed(self, app_name):
        """
        Check whether an application with this name exists in the registry.

        app_name is the full name of the app e.g. 'django.contrib.admin'.
        """
        self.check_apps_ready()
        return any(ac.name == app_name for ac in self.app_configs.values())

    def get_containing_app_config(self, object_name):
        """

        Look for an application configuration containing a given object.

        :param object_name: the dotted Python path to the object
        :return: the innermost application configuration containing the object, or None if not found

        """
        self.check_apps_ready()
        candidates = []
        for app_config in self.app_configs.values():
            if object_name.startswith(app_config.name):
                subpath = object_name.removeprefix(app_config.name)
                if subpath == "" or subpath[0] == ".":
                    candidates.append(app_config)
        if candidates:
            return sorted(candidates, key=lambda ac: -len(ac.name))[0]

    def get_registered_model(self, app_label, model_name):
        """
        Retrieves a registered model by its app label and name, handling cases where the app may not be fully initialized.
        """
        model = self.all_models[app_label].get(model_name.lower())
        if model is None:
            raise LookupError("Model '%s.%s' not registered." % (app_label, model_name))
        return model

    @functools.cache
    def get_swappable_settings_name(self, to_string):
        """
        For a given model string, returns the name of the corresponding swappable settings name if the model is swappable, otherwise returns None. This method is optimized for performance in migrations by caching results.
        """
        to_string = to_string.lower()
        for model in self.get_models(include_swapped=True):
            swapped = model._meta.swapped
            # Is this model swapped out for the model given by to_string?
            if swapped and swapped.lower() == to_string:
                return model._meta.swappable
            # Is this model swappable and the one given by to_string?
            if model._meta.swappable and model._meta.label_lower == to_string:
                return model._meta.swappable
        return None

    def set_available_apps(self, available):
        """
        Restrict the set of installed apps used by get_app_config[s] to improve performance, 
        particularly in TransactionTestCase. The provided iterable of application names 
        determines which apps are accessible. Use unset_available_apps() to restore the 
        original set of apps. This method does not trigger any imports, ensuring safe 
        operation, and validates that the specified available apps are a subset of 
        installed apps.
        """
        available = set(available)
        installed = {app_config.name for app_config in self.get_app_configs()}
        if not available.issubset(installed):
            raise ValueError(
                "Available apps isn't a subset of installed apps, extra apps: %s"
                % ", ".join(available - installed)
            )

        self.stored_app_configs.append(self.app_configs)
        self.app_configs = {
            label: app_config
            for label, app_config in self.app_configs.items()
            if app_config.name in available
        }
        self.clear_cache()

    def unset_available_apps(self):
        """Cancel a previous call to set_available_apps()."""
        self.app_configs = self.stored_app_configs.pop()
        self.clear_cache()

    def set_installed_apps(self, installed):
        """
        Enable a different set of installed apps for Django's application configuration. 
        This method must be balanced with unset_installed_apps() to properly manage the application registry, even in the event of an exception.
        Primarily used in testing scenarios to dynamically change the installed apps configuration.
        """
        if not self.ready:
            raise AppRegistryNotReady("App registry isn't ready yet.")
        self.stored_app_configs.append(self.app_configs)
        self.app_configs = {}
        self.apps_ready = self.models_ready = self.loading = self.ready = False
        self.clear_cache()
        self.populate(installed)

    def unset_installed_apps(self):
        """Cancel a previous call to set_installed_apps()."""
        self.app_configs = self.stored_app_configs.pop()
        self.apps_ready = self.models_ready = self.ready = True
        self.clear_cache()

    def clear_cache(self):
        """

            Clear all internal caches.

            Typically used in testing scenarios to reset the application registry.

        """
        self.get_swappable_settings_name.cache_clear()
        # Call expire cache on each model. This will purge
        # the relation tree and the fields cache.
        self.get_models.cache_clear()
        if self.ready:
            # Circumvent self.get_models() to prevent that the cache is refilled.
            # This particularly prevents that an empty value is cached while cloning.
            for app_config in self.app_configs.values():
                for model in app_config.get_models(include_auto_created=True):
                    model._meta._expire_cache()

    def lazy_model_operation(self, function, *model_keys):
        """
        Execute a function with model classes as arguments once all required models are imported and registered.

         The function is called with the model classes corresponding to the provided model keys, 
         in the order they were specified.

         :param function: The function to be executed with the model classes.
         :param model_keys: Variable number of (\"app_label\", \"modelname\") tuples identifying the required models.

        """
        # Base case: no arguments, just execute the function.
        if not model_keys:
            function()
        # Recursive case: take the head of model_keys, wait for the
        # corresponding model class to be imported and registered, then apply
        # that argument to the supplied function. Pass the resulting partial
        # to lazy_model_operation() along with the remaining model args and
        # repeat until all models are loaded and all arguments are applied.
        else:
            next_model, *more_models = model_keys

            # This will be executed after the class corresponding to next_model
            # has been imported and registered. The `func` attribute provides
            # duck-type compatibility with partials.
            def apply_next_model(model):
                next_function = partial(apply_next_model.func, model)
                self.lazy_model_operation(next_function, *more_models)

            apply_next_model.func = function

            # If the model has already been imported and registered, partially
            # apply it to the function now. If not, add it to the list of
            # pending operations for the model, where it will be executed with
            # the model class as its sole argument once the model is ready.
            try:
                model_class = self.get_registered_model(*next_model)
            except LookupError:
                self._pending_operations[next_model].append(apply_next_model)
            else:
                apply_next_model(model_class)

    def do_pending_operations(self, model):
        """
        Take a newly-prepared model and pass it to each function waiting for
        it. This is called at the very end of Apps.register_model().
        """
        key = model._meta.app_label, model._meta.model_name
        for function in self._pending_operations.pop(key, []):
            function(model)


apps = Apps(installed_apps=None)
