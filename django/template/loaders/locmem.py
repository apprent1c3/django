"""
Wrapper for loading templates from a plain Python dict.
"""

from django.template import Origin, TemplateDoesNotExist

from .base import Loader as BaseLoader


class Loader(BaseLoader):
    def __init__(self, engine, templates_dict):
        self.templates_dict = templates_dict
        super().__init__(engine)

    def get_contents(self, origin):
        """
        Retrieve the contents of a template based on its origin.

        :param origin: The origin of the template to retrieve
        :raises TemplateDoesNotExist: If the template does not exist
        :return: The contents of the requested template
        :rtype: object
        """
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
