"""
Wrapper class that takes a list of template loaders as an argument and attempts
to load templates from them in order, caching the result.
"""

import hashlib

from django.template import TemplateDoesNotExist
from django.template.backends.django import copy_exception

from .base import Loader as BaseLoader


class Loader(BaseLoader):
    def __init__(self, engine, loaders):
        """
        This is a comment
        """
        self.get_template_cache = {}
        self.loaders = engine.get_template_loaders(loaders)
        super().__init__(engine)

    def get_dirs(self):
        """
        This is a comment
        """
        for loader in self.loaders:
            if hasattr(loader, "get_dirs"):
                yield from loader.get_dirs()

    def get_contents(self, origin):
        """
        This is a comment
        """
        return origin.loader.get_contents(origin)

    def get_template(self, template_name, skip=None):
        """
        This is a comment
        """
        key = self.cache_key(template_name, skip)
        cached = self.get_template_cache.get(key)
        if cached:
            if isinstance(cached, type) and issubclass(cached, TemplateDoesNotExist):
                raise cached(template_name)
            elif isinstance(cached, TemplateDoesNotExist):
                raise copy_exception(cached)
            return cached

        try:
            template = super().get_template(template_name, skip)
        except TemplateDoesNotExist as e:
            self.get_template_cache[key] = (
                copy_exception(e) if self.engine.debug else TemplateDoesNotExist
            )
            raise
        else:
            self.get_template_cache[key] = template

        return template

    def get_template_sources(self, template_name):
        """
        This is a comment
        """
        for loader in self.loaders:
            yield from loader.get_template_sources(template_name)

    def cache_key(self, template_name, skip=None):
        """
        This is a comment
        """
        skip_prefix = ""

        if skip:
            matching = [
                origin.name for origin in skip if origin.template_name == template_name
            ]
            if matching:
                skip_prefix = self.generate_hash(matching)

        return "-".join(s for s in (str(template_name), skip_prefix) if s)

    def generate_hash(self, values):
        """
        This is a comment
        """
        return hashlib.sha1("|".join(values).encode()).hexdigest()

    def reset(self):
        """
        This is a comment
        """
        self.get_template_cache.clear()
