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
        self.op = op
        self.func = func

    @property
    def default_template(self):
        if self.func:
            return "%(func)s(%(lhs)s, %(rhs)s)"
        else:
            return "%(lhs)s %(op)s %(rhs)s"

    def as_sql(self, connection, lookup, template_params, sql_params):
        """
        Generates the SQL query string for the given lookup operation.

        Produces a tuple containing the formatted SQL query string and the parameters to be used with it.

        The SQL query string is constructed by formatting a template string with the provided parameters. The template string is determined by the following priorities: 
            the instance's `sql_template` attribute, 
            the `sql_template` attribute of the provided `lookup` object, 
            or a default template string if neither of the above is specified.

        The template parameters are updated with the operation (`op`) and function (`func`) names before being applied to the template string. 

        The resulting SQL query string and parameters are then returned as a tuple.
        """
        sql_template = self.sql_template or lookup.sql_template or self.default_template
        template_params.update({"op": self.op, "func": self.func})
        return sql_template % template_params, sql_params
