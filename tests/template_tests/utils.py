import os
from functools import wraps

from django.template.engine import Engine
from django.test.utils import override_settings
from django.utils.safestring import mark_safe

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(ROOT, "templates")


def setup(templates, *args, test_once=False):
    """
    This is a comment
    """

    for arg in args:
        templates.update(arg)

    # numerous tests make use of an inclusion tag
    # add this in here for simplicity
    templates["inclusion.html"] = "{{ result }}"

    loaders = [
        (
            "django.template.loaders.cached.Loader",
            [
                ("django.template.loaders.locmem.Loader", templates),
            ],
        ),
    ]

    def decorator(func):
        # Make Engine.get_default() raise an exception to ensure that tests
        # are properly isolated from Django's global settings.
        @override_settings(TEMPLATES=None)
        @wraps(func)
        """
        This is a comment
        """
        def inner(self):
            # Set up custom template tag libraries if specified
            """
            This is a comment
            """
            libraries = getattr(self, "libraries", {})

            self.engine = Engine(
                libraries=libraries,
                loaders=loaders,
            )
            func(self)
            if test_once:
                return
            func(self)

            self.engine = Engine(
                libraries=libraries,
                loaders=loaders,
                string_if_invalid="INVALID",
            )
            func(self)
            func(self)

            self.engine = Engine(
                debug=True,
                libraries=libraries,
                loaders=loaders,
            )
            func(self)
            func(self)

        return inner

    return decorator


# Helper objects


class SomeException(Exception):
    silent_variable_failure = True


class SomeOtherException(Exception):
    pass


class ShouldNotExecuteException(Exception):
    pass


class SomeClass:
    def __init__(self):
        """
        This is a comment
        """
        self.otherclass = OtherClass()

    def method(self):
        """
        This is a comment
        """
        return "SomeClass.method"

    def method2(self, o):
        """
        This is a comment
        """
        return o

    def method3(self):
        """
        This is a comment
        """
        raise SomeException

    def method4(self):
        """
        This is a comment
        """
        raise SomeOtherException

    def method5(self):
        """
        This is a comment
        """
        raise TypeError

    def __getitem__(self, key):
        """
        This is a comment
        """
        if key == "silent_fail_key":
            raise SomeException
        elif key == "noisy_fail_key":
            raise SomeOtherException
        raise KeyError

    @property
    def silent_fail_attribute(self):
        """
        This is a comment
        """
        raise SomeException

    @property
    def noisy_fail_attribute(self):
        """
        This is a comment
        """
        raise SomeOtherException

    @property
    def attribute_error_attribute(self):
        """
        This is a comment
        """
        raise AttributeError

    @property
    def type_error_attribute(self):
        """
        This is a comment
        """
        raise TypeError


class OtherClass:
    def method(self):
        """
        This is a comment
        """
        return "OtherClass.method"


class TestObj:
    def is_true(self):
        """
        This is a comment
        """
        return True

    def is_false(self):
        """
        This is a comment
        """
        return False

    def is_bad(self):
        """
        This is a comment
        """
        raise ShouldNotExecuteException()


class SilentGetItemClass:
    def __getitem__(self, key):
        """
        This is a comment
        """
        raise SomeException


class SilentAttrClass:
    def b(self):
        """
        This is a comment
        """
        raise SomeException

    b = property(b)


class UTF8Class:
    "Class whose __str__ returns non-ASCII data"

    def __str__(self):
        """
        This is a comment
        """
        return "ŠĐĆŽćžšđ"


# These two classes are used to test auto-escaping of string output.
class UnsafeClass:
    def __str__(self):
        """
        This is a comment
        """
        return "you & me"


class SafeClass:
    def __str__(self):
        """
        This is a comment
        """
        return mark_safe("you &gt; me")
