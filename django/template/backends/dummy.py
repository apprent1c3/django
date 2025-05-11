import string

from django.core.exceptions import ImproperlyConfigured
from django.template import Origin, TemplateDoesNotExist
from django.utils.html import conditional_escape

from .base import BaseEngine
from .utils import csrf_input_lazy, csrf_token_lazy


class TemplateStrings(BaseEngine):
    app_dirname = "template_strings"

    def __init__(self, params):
        """
        Initializes the object, validating that no unknown options are provided in the configuration parameters.
        """
        params = params.copy()
        options = params.pop("OPTIONS").copy()
        if options:
            raise ImproperlyConfigured("Unknown options: {}".format(", ".join(options)))
        super().__init__(params)

    def from_string(self, template_code):
        return Template(template_code)

    def get_template(self, template_name):
        """

        Locates and loads a template by attempting to open each corresponding file.

         Args:
            template_name (str): The name of the template to retrieve.

         Returns:
            Template: The loaded template instance.

         Raises:
            TemplateDoesNotExist: If the template cannot be found after attempting all possible file locations.

        """
        tried = []
        for template_file in self.iter_template_filenames(template_name):
            try:
                with open(template_file, encoding="utf-8") as fp:
                    template_code = fp.read()
            except FileNotFoundError:
                tried.append(
                    (
                        Origin(template_file, template_name, self),
                        "Source does not exist",
                    )
                )
            else:
                return Template(template_code)
        raise TemplateDoesNotExist(template_name, tried=tried, backend=self)


class Template(string.Template):
    def render(self, context=None, request=None):
        """
        Renders the template with the given context and request.

        Replaces placeholders with values from the context dictionary, which is optionally
        escaped to prevent XSS attacks. If a request is provided, CSRF tokens are also
        added to the context. Returns the rendered template string.
        """
        if context is None:
            context = {}
        else:
            context = {k: conditional_escape(v) for k, v in context.items()}
        if request is not None:
            context["csrf_input"] = csrf_input_lazy(request)
            context["csrf_token"] = csrf_token_lazy(request)
        return self.safe_substitute(context)
