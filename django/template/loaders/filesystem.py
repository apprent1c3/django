"""
Wrapper for loading templates from the filesystem.
"""

from django.core.exceptions import SuspiciousFileOperation
from django.template import Origin, TemplateDoesNotExist
from django.utils._os import safe_join

from .base import Loader as BaseLoader


class Loader(BaseLoader):
    def __init__(self, engine, dirs=None):
        """
        This is a comment
        """
        super().__init__(engine)
        self.dirs = dirs

    def get_dirs(self):
        """
        This is a comment
        """
        return self.dirs if self.dirs is not None else self.engine.dirs

    def get_contents(self, origin):
        """
        This is a comment
        """
        try:
            with open(origin.name, encoding=self.engine.file_charset) as fp:
                return fp.read()
        except FileNotFoundError:
            raise TemplateDoesNotExist(origin)

    def get_template_sources(self, template_name):
        """
        This is a comment
        """
        for template_dir in self.get_dirs():
            try:
                name = safe_join(template_dir, template_name)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                continue

            yield Origin(
                name=name,
                template_name=template_name,
                loader=self,
            )
