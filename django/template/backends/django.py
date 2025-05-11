from collections import defaultdict
from importlib import import_module
from pkgutil import walk_packages

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Warning
from django.template import TemplateDoesNotExist
from django.template.context import make_context
from django.template.engine import Engine
from django.template.library import InvalidTemplateLibrary

from .base import BaseEngine


class DjangoTemplates(BaseEngine):
    app_dirname = "templates"

    def __init__(self, params):
        """
        Initializes the template engine, setting default options and parsing libraries for templating functionality.
        """
        params = params.copy()
        options = params.pop("OPTIONS").copy()
        options.setdefault("autoescape", True)
        options.setdefault("debug", settings.DEBUG)
        options.setdefault("file_charset", "utf-8")
        libraries = options.get("libraries", {})
        options["libraries"] = self.get_templatetag_libraries(libraries)
        super().__init__(params)
        self.engine = Engine(self.dirs, self.app_dirs, **options)

    def check(self, **kwargs):
        return [
            *self._check_string_if_invalid_is_string(),
            *self._check_for_template_tags_with_the_same_name(),
        ]

    def _check_string_if_invalid_is_string(self):
        value = self.engine.string_if_invalid
        if not isinstance(value, str):
            return [
                Error(
                    "'string_if_invalid' in TEMPLATES OPTIONS must be a string but "
                    "got: %r (%s)." % (value, type(value)),
                    obj=self,
                    id="templates.E002",
                )
            ]
        return []

    def _check_for_template_tags_with_the_same_name(self):
        """
        Checks for template tag libraries with duplicate names and returns a list of warnings for such conflicts.
        """
        libraries = defaultdict(set)

        for module_name, module_path in get_template_tag_modules():
            libraries[module_name].add(module_path)

        for module_name, module_path in self.engine.libraries.items():
            libraries[module_name].add(module_path)

        errors = []

        for library_name, items in libraries.items():
            if len(items) > 1:
                items = ", ".join(repr(item) for item in sorted(items))
                errors.append(
                    Warning(
                        f"{library_name!r} is used for multiple template tag modules: "
                        f"{items}",
                        obj=self,
                        id="templates.W003",
                    )
                )

        return errors

    def from_string(self, template_code):
        return Template(self.engine.from_string(template_code), self)

    def get_template(self, template_name):
        try:
            return Template(self.engine.get_template(template_name), self)
        except TemplateDoesNotExist as exc:
            reraise(exc, self)

    def get_templatetag_libraries(self, custom_libraries):
        """
        Return a collation of template tag libraries from installed
        applications and the supplied custom_libraries argument.
        """
        libraries = get_installed_libraries()
        libraries.update(custom_libraries)
        return libraries


class Template:
    def __init__(self, template, backend):
        self.template = template
        self.backend = backend

    @property
    def origin(self):
        return self.template.origin

    def render(self, context=None, request=None):
        """

        Render the template using the provided context and request.

        The context and request are used to create a rendered version of the template.
        If the template does not exist, a TemplateDoesNotExist exception is raised.

        :param context: The context used for rendering the template.
        :param request: The request used for rendering the template.
        :raises TemplateDoesNotExist: If the template does not exist.
        :return: The rendered template.

        """
        context = make_context(
            context, request, autoescape=self.backend.engine.autoescape
        )
        try:
            return self.template.render(context)
        except TemplateDoesNotExist as exc:
            reraise(exc, self.backend)


def copy_exception(exc, backend=None):
    """
    Create a copy of a given exception, preserving its relevant attributes and template debug data while discarding internal Python exception tracking details, making it suitable for caching or storage.
    """
    backend = backend or exc.backend
    new = exc.__class__(*exc.args, tried=exc.tried, backend=backend, chain=exc.chain)
    if hasattr(exc, "template_debug"):
        new.template_debug = exc.template_debug
    return new


def reraise(exc, backend):
    """
    Reraise TemplateDoesNotExist while maintaining template debug information.
    """
    new = copy_exception(exc, backend)
    raise new from exc


def get_template_tag_modules():
    """
    Yield (module_name, module_path) pairs for all installed template tag libraries, 
    allowing access to available template tag modules and their locations.
    """
    candidates = ["django.templatetags"]
    candidates.extend(
        f"{app_config.name}.templatetags" for app_config in apps.get_app_configs()
    )

    for candidate in candidates:
        try:
            pkg = import_module(candidate)
        except ImportError:
            # No templatetags package defined. This is safe to ignore.
            continue

        if hasattr(pkg, "__path__"):
            for name in get_package_libraries(pkg):
                yield name.removeprefix(candidate).lstrip("."), name


def get_installed_libraries():
    """
    Return the built-in template tag libraries and those from installed
    applications. Libraries are stored in a dictionary where keys are the
    individual module names, not the full module paths. Example:
    django.templatetags.i18n is stored as i18n.
    """
    return {
        module_name: full_name for module_name, full_name in get_template_tag_modules()
    }


def get_package_libraries(pkg):
    """
    _searches a package for template tag libraries and returns them. 
    The function recursively traverses the package's submodules to find libraries 
    that can be used for template tagging._
    """
    for entry in walk_packages(pkg.__path__, pkg.__name__ + "."):
        try:
            module = import_module(entry[1])
        except ImportError as e:
            raise InvalidTemplateLibrary(
                "Invalid template library specified. ImportError raised when "
                "trying to load '%s': %s" % (entry[1], e)
            ) from e

        if hasattr(module, "register"):
            yield entry[1]
