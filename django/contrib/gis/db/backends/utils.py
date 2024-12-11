"""
A collection of utility routines and classes used by the spatial
backends.
"""


class SpatialOperator:
    """
    Class encapsulating the behavior specific to a GIS operation (used by lookups).
    """

    sql_template = None

    def __init__(self, op=None, func=None):
        """
        Initializes an instance of the class, setting the basic parameters for its operation.

        :param op: The operation to be performed, defaults to None
        :param func: The function associated with the operation, defaults to None
        :note: Both `op` and `func` are stored as instance attributes for later use.
        """
        self.op = op
        self.func = func

    @property
    def default_template(self):
        if self.func:
            return "%(func)s(%(lhs)s, %(rhs)s)"
        else:
            return "%(lhs)s %(op)s %(rhs)s"

    def as_sql(self, connection, lookup, template_params, sql_params):
        sql_template = self.sql_template or lookup.sql_template or self.default_template
        template_params.update({"op": self.op, "func": self.func})
        return sql_template % template_params, sql_params
