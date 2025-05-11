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
        Initializes an exclusion constraint.

        :param name: The name of the exclusion constraint.
        :param expressions: A list of 2-tuples defining the expressions to which the constraint applies.
        :param index_type: The type of index to use (either 'GIST' or 'SP-GiST'), defaults to 'GIST' if not specified.
        :param condition: A condition under which the constraint applies.
        :param deferrable: Defines when the constraint is checked.
        :param include: A list of columns to include in the index.
        :param violation_error_code: The error code to return when the constraint is violated.
        :param violation_error_message: The error message to return when the constraint is violated.

        This method validates the input parameters and raises a ValueError if any of them are invalid. It then initializes the exclusion constraint with the provided parameters.
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
        Constructs a list of exclusion constraint expressions from the given expressions and resolves them for the specified query.
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
        Checks if the expressions in this object reference valid fields in the given model through a connection.
        """
        references = set()
        for expr, _ in self.expressions:
            if isinstance(expr, str):
                expr = F(expr)
            references.update(model._get_expr_references(expr))
        return self._check_references(model, references)

    def _get_condition_sql(self, compiler, schema_editor, query):
        """
        Generates SQL for a condition based on the provided query, returning the formatted SQL string or None if no condition exists.
        """
        if self.condition is None:
            return None
        where = query.build_where(self.condition)
        sql, params = where.as_sql(compiler, schema_editor.connection)
        return sql % tuple(schema_editor.quote_value(p) for p in params)

    def constraint_sql(self, model, schema_editor):
        """
        Generates a SQL string for creating a database constraint.

        This function takes a model and a schema editor as input, and returns a SQL statement 
        that can be used to create the constraint in the database. The constraint is defined 
        by the expressions and conditions specified in this object, and can include or exclude 
        specific fields as needed. The resulting SQL statement is formatted according to the 
        database connection being used. 
        """
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
        """
        Deconstructs the object into its constituent parts for serialization or replication.

        Returns a tuple containing the path, positional arguments, and keyword arguments
        necessary to reconstruct the object. Specific attributes such as expressions, 
        condition, index type, deferrability, and inclusion are preserved in the 
        deconstructed representation.
        """
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
        """
        Validate a model instance against a set of expressions, raising a ValidationError if any of the conditions are not met.

        The validation is performed by constructing a queryset that filters instances of the given model based on the expressions, 
        and then checking if any instances match the filter. If the condition is not met, a ValidationError is raised.

        The validation can be customized by specifying a set of fields to exclude from the validation, and by using a specific database 
        connection. The validation also takes into account whether the instance is being added or updated, and excludes the current 
        instance from the validation if it is being updated.

        Args:
            model (Model): The model to validate against.
            instance (Model instance): The instance to validate.
            exclude (list of str, optional): A list of fields to exclude from the validation.
            using (str, optional): The database connection to use for the validation.

        Raises:
            ValidationError: If the validation fails.

        """
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
