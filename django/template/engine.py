import functools

from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

from .base import Template
from .context import Context, _builtin_context_processors
from .exceptions import TemplateDoesNotExist
from .library import import_library


class Engine:
    default_builtins = [
        "django.template.defaulttags",
        "django.template.defaultfilters",
        "django.template.loader_tags",
    ]

    def __init__(
        self,
        dirs=None,
        app_dirs=False,
        context_processors=None,
        debug=False,
        loaders=None,
        string_if_invalid="",
        file_charset="utf-8",
        libraries=None,
        builtins=None,
        autoescape=True,
    ):
        """
        Initializes and configures a template engine with various settings, such as template directories, loaders, context processors, and libraries, to control the rendering of templates.
        """
        if dirs is None:
            dirs = []
        if context_processors is None:
            context_processors = []
        if loaders is None:
            loaders = ["django.template.loaders.filesystem.Loader"]
            if app_dirs:
                loaders += ["django.template.loaders.app_directories.Loader"]
            loaders = [("django.template.loaders.cached.Loader", loaders)]
        else:
            if app_dirs:
                raise ImproperlyConfigured(
                    "app_dirs must not be set when loaders is defined."
                )
        if libraries is None:
            libraries = {}
        if builtins is None:
            builtins = []

        self.dirs = dirs
        self.app_dirs = app_dirs
        self.autoescape = autoescape
        self.context_processors = context_processors
        self.debug = debug
        self.loaders = loaders
        self.string_if_invalid = string_if_invalid
        self.file_charset = file_charset
        self.libraries = libraries
        self.template_libraries = self.get_template_libraries(libraries)
        self.builtins = self.default_builtins + builtins
        self.template_builtins = self.get_template_builtins(self.builtins)

    def __repr__(self):
        return (
            "<%s:%s app_dirs=%s%s debug=%s loaders=%s string_if_invalid=%s "
            "file_charset=%s%s%s autoescape=%s>"
        ) % (
            self.__class__.__qualname__,
            "" if not self.dirs else " dirs=%s" % repr(self.dirs),
            self.app_dirs,
            (
                ""
                if not self.context_processors
                else " context_processors=%s" % repr(self.context_processors)
            ),
            self.debug,
            repr(self.loaders),
            repr(self.string_if_invalid),
            repr(self.file_charset),
            "" if not self.libraries else " libraries=%s" % repr(self.libraries),
            "" if not self.builtins else " builtins=%s" % repr(self.builtins),
            repr(self.autoescape),
        )

    @staticmethod
    @functools.lru_cache
    def get_default():
        """
        Retrieves the first configured DjangoTemplates backend or raises an exception if none are found, ensuring compatibility with legacy APIs that rely on a globally available template engine.
        """
        # Since Engine is imported in django.template and since
        # DjangoTemplates is a wrapper around this Engine class,
        # local imports are required to avoid import loops.
        from django.template import engines
        from django.template.backends.django import DjangoTemplates

        for engine in engines.all():
            if isinstance(engine, DjangoTemplates):
                return engine.engine
        raise ImproperlyConfigured("No DjangoTemplates backend is configured.")

    @cached_property
    def template_context_processors(self):
        context_processors = _builtin_context_processors
        context_processors += tuple(self.context_processors)
        return tuple(import_string(path) for path in context_processors)

    def get_template_builtins(self, builtins):
        return [import_library(x) for x in builtins]

    def get_template_libraries(self, libraries):
        loaded = {}
        for name, path in libraries.items():
            loaded[name] = import_library(path)
        return loaded

    @cached_property
    def template_loaders(self):
        return self.get_template_loaders(self.loaders)

    def get_template_loaders(self, template_loaders):
        """
        Filters a list of template loaders and returns a list of valid loaders found by the instance.

        :param template_loaders: List of template loaders to filter
        :returns: List of valid template loaders
        """
        loaders = []
        for template_loader in template_loaders:
            loader = self.find_template_loader(template_loader)
            if loader is not None:
                loaders.append(loader)
        return loaders

    def find_template_loader(self, loader):
        """
        Initializes a template loader instance based on the provided loader configuration.

         The loader can be a string representing the loader class to import, or a tuple/list 
         where the first element is the loader class and the remaining elements are 
         initialization arguments. If the loader configuration is invalid, an error is raised.
        """
        if isinstance(loader, (tuple, list)):
            loader, *args = loader
        else:
            args = []

        if isinstance(loader, str):
            loader_class = import_string(loader)
            return loader_class(self, *args)
        else:
            raise ImproperlyConfigured(
                "Invalid value in template loaders configuration: %r" % loader
            )

    def find_template(self, name, dirs=None, skip=None):
        """

        Finds a template by name, searching through a list of template loaders.

        :param name: The name of the template to find
        :param dirs: Optional list of directories to search for the template
        :param skip: Optional parameter to pass to template loaders

        :returns: A tuple containing the found template and its origin
        :raises TemplateDoesNotExist: If the template is not found in any of the template loaders

        """
        tried = []
        for loader in self.template_loaders:
            try:
                template = loader.get_template(name, skip=skip)
                return template, template.origin
            except TemplateDoesNotExist as e:
                tried.extend(e.tried)
        raise TemplateDoesNotExist(name, tried=tried)

    def from_string(self, template_code):
        """
        Return a compiled Template object for the given template code,
        handling template inheritance recursively.
        """
        return Template(template_code, engine=self)

    def get_template(self, template_name):
        """
        Retrieves a compiled template object for the specified template name, handling inheritance and rendering preparation.
        """
        template, origin = self.find_template(template_name)
        if not hasattr(template, "render"):
            # template needs to be compiled
            template = Template(template, origin, template_name, engine=self)
        return template

    def render_to_string(self, template_name, context=None):
        """
        Render a template as a string based on the provided template name and context, typically used for testing purposes in a Django environment.
        """
        if isinstance(template_name, (list, tuple)):
            t = self.select_template(template_name)
        else:
            t = self.get_template(template_name)
        # Django < 1.8 accepted a Context in `context` even though that's
        # unintended. Preserve this ability but don't rewrap `context`.
        if isinstance(context, Context):
            return t.render(context)
        else:
            return t.render(Context(context, autoescape=self.autoescape))

    def select_template(self, template_name_list):
        """
        Select the first loadable template from a list of template names.

        This function iterates over a list of template names and returns the first template that can be loaded. If none of the templates can be loaded, it raises an exception listing all the templates that were not found.
        """
        if not template_name_list:
            raise TemplateDoesNotExist("No template names provided")
        not_found = []
        for template_name in template_name_list:
            try:
                return self.get_template(template_name)
            except TemplateDoesNotExist as exc:
                if exc.args[0] not in not_found:
                    not_found.append(exc.args[0])
                continue
        # If we get here, none of the templates could be loaded
        raise TemplateDoesNotExist(", ".join(not_found))
