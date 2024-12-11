from django.db.models import Aggregate, FloatField, IntegerField

__all__ = [
    "CovarPop",
    "Corr",
    "RegrAvgX",
    "RegrAvgY",
    "RegrCount",
    "RegrIntercept",
    "RegrR2",
    "RegrSlope",
    "RegrSXX",
    "RegrSXY",
    "RegrSYY",
    "StatAggregate",
]


class StatAggregate(Aggregate):
    output_field = FloatField()

    def __init__(self, y, x, output_field=None, filter=None, default=None):
        if not x or not y:
            raise ValueError("Both y and x must be provided.")
        super().__init__(
            y, x, output_field=output_field, filter=filter, default=default
        )


class Corr(StatAggregate):
    function = "CORR"


class CovarPop(StatAggregate):
    def __init__(self, y, x, sample=False, filter=None, default=None):
        """

        Initializes a covariance calculator.

        The calculator can operate in either sample or population mode, 
        determined by the `sample` parameter. If `sample` is True, the 
        calculator uses the sample covariance formula. Otherwise, it uses 
        the population covariance formula.

        :param y: The dependent variable.
        :param x: The independent variable.
        :param sample: Whether to calculate the sample covariance (default: False).
        :param filter: Optional filter to apply to the data.
        :param default: Default value to use when data is missing or filtered out.

        """
        self.function = "COVAR_SAMP" if sample else "COVAR_POP"
        super().__init__(y, x, filter=filter, default=default)


class RegrAvgX(StatAggregate):
    function = "REGR_AVGX"


class RegrAvgY(StatAggregate):
    function = "REGR_AVGY"


class RegrCount(StatAggregate):
    function = "REGR_COUNT"
    output_field = IntegerField()
    empty_result_set_value = 0


class RegrIntercept(StatAggregate):
    function = "REGR_INTERCEPT"


class RegrR2(StatAggregate):
    function = "REGR_R2"


class RegrSlope(StatAggregate):
    function = "REGR_SLOPE"


class RegrSXX(StatAggregate):
    function = "REGR_SXX"


class RegrSXY(StatAggregate):
    function = "REGR_SXY"


class RegrSYY(StatAggregate):
    function = "REGR_SYY"
