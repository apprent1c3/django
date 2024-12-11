from django.contrib.postgres.fields import ArrayField
from django.db.models import Aggregate, BooleanField, JSONField, TextField, Value

from .mixins import OrderableAggMixin

__all__ = [
    "ArrayAgg",
    "BitAnd",
    "BitOr",
    "BitXor",
    "BoolAnd",
    "BoolOr",
    "JSONBAgg",
    "StringAgg",
]


class ArrayAgg(OrderableAggMixin, Aggregate):
    function = "ARRAY_AGG"
    template = "%(function)s(%(distinct)s%(expressions)s %(ordering)s)"
    allow_distinct = True

    @property
    def output_field(self):
        return ArrayField(self.source_expressions[0].output_field)


class BitAnd(Aggregate):
    function = "BIT_AND"


class BitOr(Aggregate):
    function = "BIT_OR"


class BitXor(Aggregate):
    function = "BIT_XOR"


class BoolAnd(Aggregate):
    function = "BOOL_AND"
    output_field = BooleanField()


class BoolOr(Aggregate):
    function = "BOOL_OR"
    output_field = BooleanField()


class JSONBAgg(OrderableAggMixin, Aggregate):
    function = "JSONB_AGG"
    template = "%(function)s(%(distinct)s%(expressions)s %(ordering)s)"
    allow_distinct = True
    output_field = JSONField()


class StringAgg(OrderableAggMixin, Aggregate):
    function = "STRING_AGG"
    template = "%(function)s(%(distinct)s%(expressions)s %(ordering)s)"
    allow_distinct = True
    output_field = TextField()

    def __init__(self, expression, delimiter, **extra):
        """
        Initializes a new instance of the class with an expression and a delimiter.

        The expression is the primary input to be processed, while the delimiter is used to separate or tokenize the input. 

        Additional keyword arguments may be passed to customize initialization, and are forwarded to the superclass. 

        :param expression: The primary input expression to be processed.
        :param delimiter: The delimiter used to separate or tokenize the input.
        :param extra: Keyword arguments to customize initialization.
        """
        delimiter_expr = Value(str(delimiter))
        super().__init__(expression, delimiter_expr, **extra)
