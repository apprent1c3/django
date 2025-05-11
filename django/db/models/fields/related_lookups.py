from django.db.models.lookups import (
    Exact,
    GreaterThan,
    GreaterThanOrEqual,
    In,
    IsNull,
    LessThan,
    LessThanOrEqual,
)


class MultiColSource:
    contains_aggregate = False
    contains_over_clause = False

    def __init__(self, alias, targets, sources, field):
        self.targets, self.sources, self.field, self.alias = (
            targets,
            sources,
            field,
            alias,
        )
        self.output_field = self.field

    def __repr__(self):
        return "{}({}, {})".format(self.__class__.__name__, self.alias, self.field)

    def relabeled_clone(self, relabels):
        return self.__class__(
            relabels.get(self.alias, self.alias), self.targets, self.sources, self.field
        )

    def get_lookup(self, lookup):
        return self.output_field.get_lookup(lookup)

    def resolve_expression(self, *args, **kwargs):
        return self


def get_normalized_value(value, lhs):
    """
    ```\"\"\":return: A normalized value that can be used for filtering, based on the provided value and the left-hand side of a filter expression.

    The function takes a value and an lhs (left-hand side) as input, and returns a tuple containing the normalized values.
    If the input value is a Django model instance, the function extracts the relevant field values from the instance.
    If the input value is not a model instance, the function returns a tuple containing the original value.

    :raises ValueError: If the input value is a Django model instance that has not been saved.
    :rtype: tuple\"\"\"```
    """
    from django.db.models import Model

    if isinstance(value, Model):
        if value.pk is None:
            raise ValueError("Model instances passed to related filters must be saved.")
        value_list = []
        sources = lhs.output_field.path_infos[-1].target_fields
        for source in sources:
            while not isinstance(value, source.model) and source.remote_field:
                source = source.remote_field.model._meta.get_field(
                    source.remote_field.field_name
                )
            try:
                value_list.append(getattr(value, source.attname))
            except AttributeError:
                # A case like Restaurant.objects.filter(place=restaurant_instance),
                # where place is a OneToOneField and the primary key of Restaurant.
                return (value.pk,)
        return tuple(value_list)
    if not isinstance(value, tuple):
        return (value,)
    return value


class RelatedIn(In):
    def get_prep_lookup(self):
        """
        Prepare the lookup by converting and preparing the right-hand side values 
        according to the left-hand side field, and then delegate to the superclass method 
        for final preparation.\"\"\"



        \"\"\"Prepares the right-hand side values for a lookup operation, converting them 
        to match the type and requirements of the left-hand side field, and then 
        continues the preparation process through the superclass method.
        """
        if not isinstance(self.lhs, MultiColSource):
            if self.rhs_is_direct_value():
                # If we get here, we are dealing with single-column relations.
                self.rhs = [get_normalized_value(val, self.lhs)[0] for val in self.rhs]
                # We need to run the related field's get_prep_value(). Consider
                # case ForeignKey to IntegerField given value 'abc'. The
                # ForeignKey itself doesn't have validation for non-integers,
                # so we must run validation using the target field.
                if hasattr(self.lhs.output_field, "path_infos"):
                    # Run the target field's get_prep_value. We can safely
                    # assume there is only one as we don't get to the direct
                    # value branch otherwise.
                    target_field = self.lhs.output_field.path_infos[-1].target_fields[
                        -1
                    ]
                    self.rhs = [target_field.get_prep_value(v) for v in self.rhs]
            elif not getattr(self.rhs, "has_select_fields", True) and not getattr(
                self.lhs.field.target_field, "primary_key", False
            ):
                if (
                    getattr(self.lhs.output_field, "primary_key", False)
                    and self.lhs.output_field.model == self.rhs.model
                ):
                    # A case like
                    # Restaurant.objects.filter(place__in=restaurant_qs), where
                    # place is a OneToOneField and the primary key of
                    # Restaurant.
                    target_field = self.lhs.field.name
                else:
                    target_field = self.lhs.field.target_field.name
                self.rhs.set_values([target_field])
        return super().get_prep_lookup()

    def as_sql(self, compiler, connection):
        """
        Translates a complex lookup operation into an SQL query. Supports lookups involving multiple columns and handles cases where the right-hand side of the operation is either a direct value or a subquery. Returns a SQL representation of the lookup operation.
        """
        if isinstance(self.lhs, MultiColSource):
            # For multicolumn lookups we need to build a multicolumn where clause.
            # This clause is either a SubqueryConstraint (for values that need
            # to be compiled to SQL) or an OR-combined list of
            # (col1 = val1 AND col2 = val2 AND ...) clauses.
            from django.db.models.sql.where import (
                AND,
                OR,
                SubqueryConstraint,
                WhereNode,
            )

            root_constraint = WhereNode(connector=OR)
            if self.rhs_is_direct_value():
                values = [get_normalized_value(value, self.lhs) for value in self.rhs]
                for value in values:
                    value_constraint = WhereNode()
                    for source, target, val in zip(
                        self.lhs.sources, self.lhs.targets, value
                    ):
                        lookup_class = target.get_lookup("exact")
                        lookup = lookup_class(
                            target.get_col(self.lhs.alias, source), val
                        )
                        value_constraint.add(lookup, AND)
                    root_constraint.add(value_constraint, OR)
            else:
                root_constraint.add(
                    SubqueryConstraint(
                        self.lhs.alias,
                        [target.column for target in self.lhs.targets],
                        [source.name for source in self.lhs.sources],
                        self.rhs,
                    ),
                    AND,
                )
            return root_constraint.as_sql(compiler, connection)
        return super().as_sql(compiler, connection)


class RelatedLookupMixin:
    def get_prep_lookup(self):
        """
        Prepares the lookup by normalizing and preparing the right-hand side value.

         Returns the prepared lookup, handling cases where the left-hand side is not a MultiColSource and the right-hand side needs resolution or preparation.

         The preparation involves converting the right-hand side to a normalized value and potentially applying the output field's specific preparation logic if required. 
        """
        if not isinstance(self.lhs, MultiColSource) and not hasattr(
            self.rhs, "resolve_expression"
        ):
            # If we get here, we are dealing with single-column relations.
            self.rhs = get_normalized_value(self.rhs, self.lhs)[0]
            # We need to run the related field's get_prep_value(). Consider case
            # ForeignKey to IntegerField given value 'abc'. The ForeignKey itself
            # doesn't have validation for non-integers, so we must run validation
            # using the target field.
            if self.prepare_rhs and hasattr(self.lhs.output_field, "path_infos"):
                # Get the target field. We can safely assume there is only one
                # as we don't get to the direct value branch otherwise.
                target_field = self.lhs.output_field.path_infos[-1].target_fields[-1]
                self.rhs = target_field.get_prep_value(self.rhs)

        return super().get_prep_lookup()

    def as_sql(self, compiler, connection):
        """
        Generates SQL for a conditional statement, handling the case where a multi-column source is compared to a value, by breaking down the operation into simpler constraints and combining them with AND logic.
        """
        if isinstance(self.lhs, MultiColSource):
            assert self.rhs_is_direct_value()
            self.rhs = get_normalized_value(self.rhs, self.lhs)
            from django.db.models.sql.where import AND, WhereNode

            root_constraint = WhereNode()
            for target, source, val in zip(
                self.lhs.targets, self.lhs.sources, self.rhs
            ):
                lookup_class = target.get_lookup(self.lookup_name)
                root_constraint.add(
                    lookup_class(target.get_col(self.lhs.alias, source), val), AND
                )
            return root_constraint.as_sql(compiler, connection)
        return super().as_sql(compiler, connection)


class RelatedExact(RelatedLookupMixin, Exact):
    pass


class RelatedLessThan(RelatedLookupMixin, LessThan):
    pass


class RelatedGreaterThan(RelatedLookupMixin, GreaterThan):
    pass


class RelatedGreaterThanOrEqual(RelatedLookupMixin, GreaterThanOrEqual):
    pass


class RelatedLessThanOrEqual(RelatedLookupMixin, LessThanOrEqual):
    pass


class RelatedIsNull(RelatedLookupMixin, IsNull):
    pass
