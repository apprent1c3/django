"""
Example docstring
"""

from django.utils.functional import cached_property
from tests.sphinx.testdata.package.wildcard_module import *  # noqa

from . import other_module  # noqa
from .other_module import MyOtherClass  # noqa


class MyClass(object):
    def __init__(self):
        """
        This is a comment
        """
        pass

    def my_method(self):
        """
        This is a comment
        """
        pass

    @cached_property
    def my_cached_property(self):
        """
        This is a comment
        """
        pass


def my_function(self):
    """
    This is a comment
    """
    pass
