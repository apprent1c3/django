from django.core.exceptions import FullResultSet
from django.db.models.expressions import OrderByList


class OrderableAggMixin:
    def __init__(self, *expressions, ordering=(), **extra):
        """
        Initializes a database query object.

        This constructor takes in a variable number of expressions and optional keyword arguments.
        The ordering parameter determines how the query results are ordered. If ordering is not provided,
        the results will not be ordered. If ordering is provided as a list or tuple, it will be used to create
        an OrderByList object. Otherwise, the provided ordering will be wrapped in an OrderByList object.

        The extra keyword arguments are passed to the parent class's constructor.

        :param ordering: The ordering of the query results, or None for no ordering.
        :param expressions: Variable number of expressions to be used in the query.
        :param extra: Additional keyword arguments.

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
