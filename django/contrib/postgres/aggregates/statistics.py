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
        Initializes a covariance calculation object.

        :param y: The dependent variable.
        :param x: The independent variable.
        :param sample: If True, calculates the sample covariance; otherwise, calculates the population covariance.
        :param filter: Optional filter to apply to the data before calculation.
        :param default: Default value to use when data is missing or filtered out.
        :note: The function used for calculation is determined by the `sample` parameter, defaulting to population covariance ('COVAR_POP') if False, and sample covariance ('COVAR_SAMP') if True.
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
