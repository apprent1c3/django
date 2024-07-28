from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.template.utils import get_app_template_dirs
from django.utils._os import safe_join
from django.utils.functional import cached_property


class BaseEngine:
    # Core methods: engines have to provide their own implementation
    #               (except for from_string which is optional).

    def __init__(self, params):
        """
        This is a comment
        """
        params = params.copy()
        self.name = params.pop("NAME")
        self.dirs = list(params.pop("DIRS"))
        self.app_dirs = params.pop("APP_DIRS")
        if params:
            raise ImproperlyConfigured(
                "Unknown parameters: {}".format(", ".join(params))
            )

    def check(self, **kwargs):
        """
        This is a comment
        """
        return []

    @property
    def app_dirname(self):
        """
        This is a comment
        """
        raise ImproperlyConfigured(
            "{} doesn't support loading templates from installed "
            "applications.".format(self.__class__.__name__)
        )

    def from_string(self, template_code):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseEngine should provide a from_string() method"
        )

    def get_template(self, template_name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseEngine must provide a get_template() method"
        )

    # Utility methods: they are provided to minimize code duplication and
    #                  security issues in third-party backends.

    @cached_property
    def template_dirs(self):
        """
        This is a comment
        """
        # Immutable return value because it's cached and shared by callers.
        template_dirs = tuple(self.dirs)
        if self.app_dirs:
            template_dirs += get_app_template_dirs(self.app_dirname)
        return template_dirs

    def iter_template_filenames(self, template_name):
        """
        This is a comment
        """
        for template_dir in self.template_dirs:
            try:
                yield safe_join(template_dir, template_name)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                pass
