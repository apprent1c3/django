import enum
import warnings

from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.functional import Promise
from django.utils.version import PY311, PY312

if PY311:
    from enum import EnumType, IntEnum, StrEnum
    from enum import property as enum_property
else:
    from enum import EnumMeta as EnumType
    from types import DynamicClassAttribute as enum_property

    class ReprEnum(enum.Enum):
        def __str__(self):
            return str(self.value)

    class IntEnum(int, ReprEnum):
        pass

    class StrEnum(str, ReprEnum):
        pass


__all__ = ["Choices", "IntegerChoices", "TextChoices"]


class ChoicesType(EnumType):
    """A metaclass for creating a enum choices."""

    def __new__(metacls, classname, bases, classdict, **kwds):
        """

        Meta class to create an enumeration class where each member is automatically assigned a label.
        The label is determined by either a provided string or tuple at the end of the member's value,
        or the member's name with underscores replaced by spaces and title-cased. This allows for easy
        and consistent naming conventions for enumeration members. The created class is also ensured to
        have unique members, preventing duplicates. The labels are stored as an attribute `_label_` on each
        member and can be accessed programmatically. 

        :param classname: The name of the class being created
        :param bases: The base classes of the class being created
        :param classdict: The namespace dictionary of the class being created
        :param kwds: Additional keyword arguments for the class creation
        :return: The newly created enumeration class with labelled members

        """
        labels = []
        for key in classdict._member_names:
            value = classdict[key]
            if (
                isinstance(value, (list, tuple))
                and len(value) > 1
                and isinstance(value[-1], (Promise, str))
            ):
                *value, label = value
                value = tuple(value)
            else:
                label = key.replace("_", " ").title()
            labels.append(label)
            # Use dict.__setitem__() to suppress defenses against double
            # assignment in enum's classdict.
            dict.__setitem__(classdict, key, value)
        cls = super().__new__(metacls, classname, bases, classdict, **kwds)
        for member, label in zip(cls.__members__.values(), labels):
            member._label_ = label
        return enum.unique(cls)

    if not PY312:

        def __contains__(cls, member):
            if not isinstance(member, enum.Enum):
                # Allow non-enums to match against member values.
                return any(x.value == member for x in cls)
            return super().__contains__(member)

    @property
    def names(cls):
        empty = ["__empty__"] if hasattr(cls, "__empty__") else []
        return empty + [member.name for member in cls]

    @property
    def choices(cls):
        empty = [(None, cls.__empty__)] if hasattr(cls, "__empty__") else []
        return empty + [(member.value, member.label) for member in cls]

    @property
    def labels(cls):
        return [label for _, label in cls.choices]

    @property
    def values(cls):
        return [value for value, _ in cls.choices]


class Choices(enum.Enum, metaclass=ChoicesType):
    """Class for creating enumerated choices."""

    if PY311:
        do_not_call_in_templates = enum.nonmember(True)
    else:

        @property
        def do_not_call_in_templates(self):
            return True

    @enum_property
    def label(self):
        return self._label_

    # A similar format was proposed for Python 3.10.
    def __repr__(self):
        return f"{self.__class__.__qualname__}.{self._name_}"


class IntegerChoices(Choices, IntEnum):
    """Class for creating enumerated integer choices."""

    pass


class TextChoices(Choices, StrEnum):
    """Class for creating enumerated string choices."""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name


def __getattr__(name):
    """
    Handle attribute access on the module.

    This method is invoked when an attribute access fails. It checks if the requested attribute is 'ChoicesMeta' and returns 'ChoicesType' instead, emitting a deprecation warning. For any other attribute, it raises an AttributeError.

    .. note::
       Accessing 'ChoicesMeta' is deprecated since it will be removed in Django 6.0. Use 'ChoicesType' instead.

    .. warning::
       Attempting to access any other attribute on the module will result in an AttributeError being raised.

    """
    if name == "ChoicesMeta":
        warnings.warn(
            "ChoicesMeta is deprecated in favor of ChoicesType.",
            RemovedInDjango60Warning,
            stacklevel=2,
        )
        return ChoicesType
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
