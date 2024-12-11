"""
Wrapper for loading templates from a plain Python dict.
"""

from django.template import Origin, TemplateDoesNotExist

from .base import Loader as BaseLoader


class Loader(BaseLoader):
    def __init__(self, engine, templates_dict):
        """
        Initializes the object with a template engine and a dictionary of templates.

        :param engine: The template engine to be used.
        :param templates_dict: A dictionary containing the available templates.

        The templates dictionary is stored as an instance variable, allowing for easy access to the templates.
        The initialization also incorporates the parent class's initialization through the engine parameter.
        """
        self.templates_dict = templates_dict
        super().__init__(engine)

    def get_contents(self, origin):
        try:
            return self.templates_dict[origin.name]
        except KeyError:
            raise TemplateDoesNotExist(origin)

    def get_template_sources(self, template_name):
        yield Origin(
            name=template_name,
            template_name=template_name,
            loader=self,
        )
