from django.db.models.expressions import Func
from django.db.models.fields import FloatField, IntegerField

__all__ = [
    "CumeDist",
    "DenseRank",
    "FirstValue",
    "Lag",
    "LastValue",
    "Lead",
    "NthValue",
    "Ntile",
    "PercentRank",
    "Rank",
    "RowNumber",
]


class CumeDist(Func):
    function = "CUME_DIST"
    output_field = FloatField()
    window_compatible = True


class DenseRank(Func):
    function = "DENSE_RANK"
    output_field = IntegerField()
    window_compatible = True


class FirstValue(Func):
    arity = 1
    function = "FIRST_VALUE"
    window_compatible = True


class LagLeadFunction(Func):
    window_compatible = True

    def __init__(self, expression, offset=1, default=None, **extra):
        """
        Initializes an object representing a source expression with an optional offset and default value.

        :param expression: The source expression, required and must be non-null.
        :param offset: A positive integer that represents the offset of the expression.
        :param default: An optional default value to be used when the expression is absent.
        :param extra: Additional keyword arguments to be passed to the superclass initializer.
        :raises ValueError: If the expression is None or the offset is not a positive integer.
        """
        if expression is None:
            raise ValueError(
                "%s requires a non-null source expression." % self.__class__.__name__
            )
        if offset is None or offset <= 0:
            raise ValueError(
                "%s requires a positive integer for the offset."
                % self.__class__.__name__
            )
        args = (expression, offset)
        if default is not None:
            args += (default,)
        super().__init__(*args, **extra)

    def _resolve_output_field(self):
        sources = self.get_source_expressions()
        return sources[0].output_field


class Lag(LagLeadFunction):
    function = "LAG"


class LastValue(Func):
    arity = 1
    function = "LAST_VALUE"
    window_compatible = True


class Lead(LagLeadFunction):
    function = "LEAD"


class NthValue(Func):
    function = "NTH_VALUE"
    window_compatible = True

    def __init__(self, expression, nth=1, **extra):
        """
        Initializes the object with an expression and optional parameters, ensuring the expression is non-null and nth is a positive integer.
        """
        if expression is None:
            raise ValueError(
                "%s requires a non-null source expression." % self.__class__.__name__
            )
        if nth is None or nth <= 0:
            raise ValueError(
                "%s requires a positive integer as for nth." % self.__class__.__name__
            )
        super().__init__(expression, nth, **extra)

    def _resolve_output_field(self):
        sources = self.get_source_expressions()
        return sources[0].output_field


class Ntile(Func):
    function = "NTILE"
    output_field = IntegerField()
    window_compatible = True

    def __init__(self, num_buckets=1, **extra):
        if num_buckets <= 0:
            raise ValueError("num_buckets must be greater than 0.")
        super().__init__(num_buckets, **extra)


class PercentRank(Func):
    function = "PERCENT_RANK"
    output_field = FloatField()
    window_compatible = True


class Rank(Func):
    function = "RANK"
    output_field = IntegerField()
    window_compatible = True


class RowNumber(Func):
    function = "ROW_NUMBER"
    output_field = IntegerField()
    window_compatible = True
