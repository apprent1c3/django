from types import NoneType

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS
from django.db.backends.ddl_references import Expressions, Statement, Table
from django.db.models import BaseConstraint, Deferrable, F, Q
from django.db.models.expressions import Exists, ExpressionList
from django.db.models.indexes import IndexExpression
from django.db.models.lookups import PostgresOperatorLookup
from django.db.models.sql import Query

__all__ = ["ExclusionConstraint"]


class ExclusionConstraintExpression(IndexExpression):
    template = "%(expressions)s WITH %(operator)s"


class ExclusionConstraint(BaseConstraint):
    template = (
        "CONSTRAINT %(name)s EXCLUDE USING %(index_type)s "
        "(%(expressions)s)%(include)s%(where)s%(deferrable)s"
    )

    def __init__(
        self,
        *,
        name,
        expressions,
        index_type=None,
        condition=None,
        deferrable=None,
        include=None,
        violation_error_code=None,
        violation_error_message=None,
    ):
        """

        Initialize an ExclusionConstraint object.

        The ExclusionConstraint object is used to define an exclusion constraint in a database table.
        It ensures that for any two rows in the table, if the values of certain columns or expressions
        are not distinct according to the operator class of the index, at least one row must not satisfy
        the condition specified by the WHERE clause.

        Parameters
        ----------
        name : str
            The name of the exclusion constraint.
        expressions : list of 2-tuples
            A list of 2-tuples where each tuple contains the column name or expression and the operator
            to use for the exclusion constraint.
        index_type : str, optional
            The type of index to use for the exclusion constraint. It can be either 'GiST' or 'SP-GiST'.
            If not specified, 'GIST' is used by default.
        condition : Q instance, optional
            A condition to be applied to the exclusion constraint.
        deferrable : Deferrable instance, optional
            An object specifying whether the constraint should be checked immediately or deferred.
        include : list or tuple, optional
            A list of columns to include in the index.
        violation_error_code : str, optional
            A custom error code to be used when the exclusion constraint is violated.
        violation_error_message : str, optional
            A custom error message to be used when the exclusion constraint is violated.

        Note
        ----
        At least one expression is required to define an exclusion constraint.
        Each expression must be a 2-tuple containing the column name or expression and the operator.

        """
        if index_type and index_type.lower() not in {"gist", "spgist"}:
            raise ValueError(
                "Exclusion constraints only support GiST or SP-GiST indexes."
            )
        if not expressions:
            raise ValueError(
                "At least one expression is required to define an exclusion "
                "constraint."
            )
        if not all(
            isinstance(expr, (list, tuple)) and len(expr) == 2 for expr in expressions
        ):
            raise ValueError("The expressions must be a list of 2-tuples.")
        if not isinstance(condition, (NoneType, Q)):
            raise ValueError("ExclusionConstraint.condition must be a Q instance.")
        if not isinstance(deferrable, (NoneType, Deferrable)):
            raise ValueError(
                "ExclusionConstraint.deferrable must be a Deferrable instance."
            )
        if not isinstance(include, (NoneType, list, tuple)):
            raise ValueError("ExclusionConstraint.include must be a list or tuple.")
        self.expressions = expressions
        self.index_type = index_type or "GIST"
        self.condition = condition
        self.deferrable = deferrable
        self.include = tuple(include) if include else ()
        super().__init__(
            name=name,
            violation_error_code=violation_error_code,
            violation_error_message=violation_error_message,
        )

    def _get_expressions(self, schema_editor, query):
        """

        Produce a list of exclusion constraint expressions.

        This function processes a series of expressions and operators, converting them
        into ExclusionConstraintExpression objects. It then combines these objects into
        an ExpressionList, which is resolved against a given query.

        The function takes into account the schema editor's connection to determine the
        wrapper classes for each expression.

        The result is an ExpressionList that can be used to enforce exclusion constraints
        in a database schema.

        :param schema_editor: The schema editor used to determine the connection.
        :param query: The query against which the expression list is resolved.
        :return: The resolved ExpressionList of exclusion constraint expressions.

        """
        expressions = []
        for idx, (expression, operator) in enumerate(self.expressions):
            if isinstance(expression, str):
                expression = F(expression)
            expression = ExclusionConstraintExpression(expression, operator=operator)
            expression.set_wrapper_classes(schema_editor.connection)
            expressions.append(expression)
        return ExpressionList(*expressions).resolve_expression(query)

    def _check(self, model, connection):
        """
        Check if the expressions in this object reference valid fields in the given model.

        The function iterates over each expression, converts string expressions to Field objects,
        and retrieves the set of referenced fields. It then invokes a secondary check to verify
        the validity of these references.

        :param model: The model to check the references against
        :param connection: The connection to use for checking the references
        :return: The result of the secondary reference check
        """
        references = set()
        for expr, _ in self.expressions:
            if isinstance(expr, str):
                expr = F(expr)
            references.update(model._get_expr_references(expr))
        return self._check_references(model, references)

    def _get_condition_sql(self, compiler, schema_editor, query):
        if self.condition is None:
            return None
        where = query.build_where(self.condition)
        sql, params = where.as_sql(compiler, schema_editor.connection)
        return sql % tuple(schema_editor.quote_value(p) for p in params)

    def constraint_sql(self, model, schema_editor):
        query = Query(model, alias_cols=False)
        compiler = query.get_compiler(connection=schema_editor.connection)
        expressions = self._get_expressions(schema_editor, query)
        table = model._meta.db_table
        condition = self._get_condition_sql(compiler, schema_editor, query)
        include = [
            model._meta.get_field(field_name).column for field_name in self.include
        ]
        return Statement(
            self.template,
            table=Table(table, schema_editor.quote_name),
            name=schema_editor.quote_name(self.name),
            index_type=self.index_type,
            expressions=Expressions(
                table, expressions, compiler, schema_editor.quote_value
            ),
            where=" WHERE (%s)" % condition if condition else "",
            include=schema_editor._index_include_sql(model, include),
            deferrable=schema_editor._deferrable_constraint_sql(self.deferrable),
        )

    def create_sql(self, model, schema_editor):
        return Statement(
            "ALTER TABLE %(table)s ADD %(constraint)s",
            table=Table(model._meta.db_table, schema_editor.quote_name),
            constraint=self.constraint_sql(model, schema_editor),
        )

    def remove_sql(self, model, schema_editor):
        return schema_editor._delete_constraint_sql(
            schema_editor.sql_delete_check,
            model,
            schema_editor.quote_name(self.name),
        )

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        kwargs["expressions"] = self.expressions
        if self.condition is not None:
            kwargs["condition"] = self.condition
        if self.index_type.lower() != "gist":
            kwargs["index_type"] = self.index_type
        if self.deferrable:
            kwargs["deferrable"] = self.deferrable
        if self.include:
            kwargs["include"] = self.include
        return path, args, kwargs

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.name == other.name
                and self.index_type == other.index_type
                and self.expressions == other.expressions
                and self.condition == other.condition
                and self.deferrable == other.deferrable
                and self.include == other.include
                and self.violation_error_code == other.violation_error_code
                and self.violation_error_message == other.violation_error_message
            )
        return super().__eq__(other)

    def __repr__(self):
        return "<%s: index_type=%s expressions=%s name=%s%s%s%s%s%s>" % (
            self.__class__.__qualname__,
            repr(self.index_type),
            repr(self.expressions),
            repr(self.name),
            "" if self.condition is None else " condition=%s" % self.condition,
            "" if self.deferrable is None else " deferrable=%r" % self.deferrable,
            "" if not self.include else " include=%s" % repr(self.include),
            (
                ""
                if self.violation_error_code is None
                else " violation_error_code=%r" % self.violation_error_code
            ),
            (
                ""
                if self.violation_error_message is None
                or self.violation_error_message == self.default_violation_error_message
                else " violation_error_message=%r" % self.violation_error_message
            ),
        )

    def validate(self, model, instance, exclude=None, using=DEFAULT_DB_ALIAS):
        queryset = model._default_manager.using(using)
        replacement_map = instance._get_field_value_map(
            meta=model._meta, exclude=exclude
        )
        replacements = {F(field): value for field, value in replacement_map.items()}
        lookups = []
        for idx, (expression, operator) in enumerate(self.expressions):
            if isinstance(expression, str):
                expression = F(expression)
            if exclude:
                if isinstance(expression, F):
                    if expression.name in exclude:
                        return
                else:
                    for expr in expression.flatten():
                        if isinstance(expr, F) and expr.name in exclude:
                            return
            rhs_expression = expression.replace_expressions(replacements)
            if hasattr(expression, "get_expression_for_validation"):
                expression = expression.get_expression_for_validation()
            if hasattr(rhs_expression, "get_expression_for_validation"):
                rhs_expression = rhs_expression.get_expression_for_validation()
            lookup = PostgresOperatorLookup(lhs=expression, rhs=rhs_expression)
            lookup.postgres_operator = operator
            lookups.append(lookup)
        queryset = queryset.filter(*lookups)
        model_class_pk = instance._get_pk_val(model._meta)
        if not instance._state.adding and model_class_pk is not None:
            queryset = queryset.exclude(pk=model_class_pk)
        if not self.condition:
            if queryset.exists():
                raise ValidationError(
                    self.get_violation_error_message(), code=self.violation_error_code
                )
        else:
            if (self.condition & Exists(queryset.filter(self.condition))).check(
                replacement_map, using=using
            ):
                raise ValidationError(
                    self.get_violation_error_message(), code=self.violation_error_code
                )
