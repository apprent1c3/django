from django.core.exceptions import FullResultSet
from django.db.models.expressions import OrderByList


class OrderableAggMixin:
    def __init__(self, *expressions, ordering=(), **extra):
        """
        Initializes a query object with optional sorting parameters.

        The ordering of results can be specified using the `ordering` parameter.
        If no ordering is provided, results will not be sorted.
        Otherwise, ordering is defined using `OrderByList` expressions.

        :param ordering: A list, tuple, or single expression to sort results by.

        """
        if not ordering:
            self.order_by = None
        elif isinstance(ordering, (list, tuple)):
            self.order_by = OrderByList(*ordering)
        else:
            self.order_by = OrderByList(ordering)
        super().__init__(*expressions, **extra)

    def resolve_expression(self, *args, **kwargs):
        if self.order_by is not None:
            self.order_by = self.order_by.resolve_expression(*args, **kwargs)
        return super().resolve_expression(*args, **kwargs)

    def get_source_expressions(self):
        return super().get_source_expressions() + [self.order_by]

    def set_source_expressions(self, exprs):
        *exprs, self.order_by = exprs
        return super().set_source_expressions(exprs)

    def as_sql(self, compiler, connection):
        """

        Generates SQL for the given query, incorporating source expressions, filtering, and ordering.

        Returns a tuple containing the compiled SQL string and a list of parameters to be used with the query.

        """
        *source_exprs, filtering_expr, ordering_expr = self.get_source_expressions()

        order_by_sql = ""
        order_by_params = []
        if ordering_expr is not None:
            order_by_sql, order_by_params = compiler.compile(ordering_expr)

        filter_params = []
        if filtering_expr is not None:
            try:
                _, filter_params = compiler.compile(filtering_expr)
            except FullResultSet:
                pass

        source_params = []
        for source_expr in source_exprs:
            source_params += compiler.compile(source_expr)[1]

        sql, _ = super().as_sql(compiler, connection, ordering=order_by_sql)
        return sql, (*source_params, *order_by_params, *filter_params)
