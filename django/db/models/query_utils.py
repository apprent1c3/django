"""
Various data structures used in query construction.

Factored out from django.db.models.query to avoid making the main module very
large and/or so that they can be used by other modules without getting into
circular import difficulties.
"""

import functools
import inspect
import logging
from collections import namedtuple

from django.core.exceptions import FieldError
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections
from django.db.models.constants import LOOKUP_SEP
from django.utils import tree
from django.utils.functional import cached_property
from django.utils.hashable import make_hashable

logger = logging.getLogger("django.db.models")

# PathInfo is used when converting lookups (fk__somecol). The contents
# describe the relation in Model terms (model Options and Fields for both
# sides of the relation. The join_field is the field backing the relation.
PathInfo = namedtuple(
    "PathInfo",
    "from_opts to_opts target_fields join_field m2m direct filtered_relation",
)


def subclasses(cls):
    yield cls
    for subclass in cls.__subclasses__():
        yield from subclasses(subclass)


class Q(tree.Node):
    """
    Encapsulate filters as objects that can then be combined logically (using
    `&` and `|`).
    """

    # Connection types
    AND = "AND"
    OR = "OR"
    XOR = "XOR"
    default = AND
    conditional = True

    def __init__(self, *args, _connector=None, _negated=False, **kwargs):
        super().__init__(
            children=[*args, *sorted(kwargs.items())],
            connector=_connector,
            negated=_negated,
        )

    def _combine(self, other, conn):
        """
        Combines two query objects with the specified connector.

        This method ensures that both objects are conditional queries, then combines them using the provided connector, returning a new object representing the combined query.

        The combination process is influenced by the state of the objects: if one of them is empty, the other is returned as a copy. If both objects are of type Q and one is empty, the non-empty one is returned as a copy.
        """
        if getattr(other, "conditional", False) is False:
            raise TypeError(other)
        if not self:
            return other.copy()
        if not other and isinstance(other, Q):
            return self.copy()

        obj = self.create(connector=conn)
        obj.add(self, conn)
        obj.add(other, conn)
        return obj

    def __or__(self, other):
        return self._combine(other, self.OR)

    def __and__(self, other):
        return self._combine(other, self.AND)

    def __xor__(self, other):
        return self._combine(other, self.XOR)

    def __invert__(self):
        obj = self.copy()
        obj.negate()
        return obj

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        # We must promote any new joins to left outer joins so that when Q is
        # used as an expression, rows aren't filtered due to joins.
        clause, joins = query._add_q(
            self,
            reuse,
            allow_joins=allow_joins,
            split_subq=False,
            check_filterable=False,
            summarize=summarize,
        )
        query.promote_joins(joins)
        return clause

    def flatten(self):
        """
        Recursively yields all expressions of this Q object in depth-first order, 
        including the object itself and all its subexpressions.
        """
        yield self
        for child in self.children:
            if isinstance(child, tuple):
                # Use the lookup.
                child = child[1]
            if hasattr(child, "flatten"):
                yield from child.flatten()
            else:
                yield child

    def check(self, against, using=DEFAULT_DB_ALIAS):
        """
        Checks if the expression of the Q instance matches against the given expressions in the database. 

        It performs a database query with annotations and returns True if a match is found and False otherwise. 

        In case of a database error, it logs a warning and returns True.
        """
        # Avoid circular imports.
        from django.db.models import BooleanField, Value
        from django.db.models.functions import Coalesce
        from django.db.models.sql import Query
        from django.db.models.sql.constants import SINGLE

        query = Query(None)
        for name, value in against.items():
            if not hasattr(value, "resolve_expression"):
                value = Value(value)
            query.add_annotation(value, name, select=False)
        query.add_annotation(Value(1), "_check")
        # This will raise a FieldError if a field is missing in "against".
        if connections[using].features.supports_comparing_boolean_expr:
            query.add_q(Q(Coalesce(self, True, output_field=BooleanField())))
        else:
            query.add_q(self)
        compiler = query.get_compiler(using=using)
        try:
            return compiler.execute_sql(SINGLE) is not None
        except DatabaseError as e:
            logger.warning("Got a database error calling check() on %r: %s", self, e)
            return True

    def deconstruct(self):
        """

        Deconstruct this object into its constituent parts for serialization or other purposes.

        Returns a tuple containing the object's path, positional arguments, and keyword arguments.

        """
        path = "%s.%s" % (self.__class__.__module__, self.__class__.__name__)
        if path.startswith("django.db.models.query_utils"):
            path = path.replace("django.db.models.query_utils", "django.db.models")
        args = tuple(self.children)
        kwargs = {}
        if self.connector != self.default:
            kwargs["_connector"] = self.connector
        if self.negated:
            kwargs["_negated"] = True
        return path, args, kwargs

    @cached_property
    def identity(self):
        """

        Returns a unique identity for this instance, used for caching purposes.

        The identity is a hashable representation of the instance's decomposed path, 
        arguments, and keyword arguments.

        """
        path, args, kwargs = self.deconstruct()
        identity = [path, *kwargs.items()]
        for child in args:
            if isinstance(child, tuple):
                arg, value = child
                value = make_hashable(value)
                identity.append((arg, value))
            else:
                identity.append(child)
        return tuple(identity)

    def __eq__(self, other):
        if not isinstance(other, Q):
            return NotImplemented
        return other.identity == self.identity

    def __hash__(self):
        return hash(self.identity)

    @cached_property
    def referenced_base_fields(self):
        """
        Retrieve all base fields referenced directly or through F expressions
        excluding any fields referenced through joins.
        """
        # Avoid circular imports.
        from django.db.models.sql import query

        return {
            child.split(LOOKUP_SEP, 1)[0] for child in query.get_children_from_q(self)
        }


class DeferredAttribute:
    """
    A wrapper for a deferred-loading field. When the value is read from this
    object the first time, the query is executed.
    """

    def __init__(self, field):
        self.field = field

    def __get__(self, instance, cls=None):
        """
        Retrieve and cache the value of a field from the datastore, returning the cached value on subsequent lookups.
        """
        if instance is None:
            return self
        data = instance.__dict__
        field_name = self.field.attname
        if field_name not in data:
            # Let's see if the field is part of the parent chain. If so we
            # might be able to reuse the already loaded value. Refs #18343.
            val = self._check_parent_chain(instance)
            if val is None:
                if instance.pk is None and self.field.generated:
                    raise AttributeError(
                        "Cannot read a generated field from an unsaved model."
                    )
                instance.refresh_from_db(fields=[field_name])
            else:
                data[field_name] = val
        return data[field_name]

    def _check_parent_chain(self, instance):
        """
        Checks if a field's value can be retrieved from its instance's parent fields, returning the value if the field is a primary key and has a corresponding link field.
        """
        opts = instance._meta
        link_field = opts.get_ancestor_link(self.field.model)
        if self.field.primary_key and self.field != link_field:
            return getattr(instance, link_field.attname)
        return None


class class_or_instance_method:
    """
    Hook used in RegisterLookupMixin to return partial functions depending on
    the caller type (instance or class of models.Field).
    """

    def __init__(self, class_method, instance_method):
        self.class_method = class_method
        self.instance_method = instance_method

    def __get__(self, instance, owner):
        if instance is None:
            return functools.partial(self.class_method, owner)
        return functools.partial(self.instance_method, instance)


class RegisterLookupMixin:
    def _get_lookup(self, lookup_name):
        return self.get_lookups().get(lookup_name, None)

    @functools.cache
    def get_class_lookups(cls):
        class_lookups = [
            parent.__dict__.get("class_lookups", {}) for parent in inspect.getmro(cls)
        ]
        return cls.merge_dicts(class_lookups)

    def get_instance_lookups(self):
        class_lookups = self.get_class_lookups()
        if instance_lookups := getattr(self, "instance_lookups", None):
            return {**class_lookups, **instance_lookups}
        return class_lookups

    get_lookups = class_or_instance_method(get_class_lookups, get_instance_lookups)
    get_class_lookups = classmethod(get_class_lookups)

    def get_lookup(self, lookup_name):
        """
        Returns a lookup class by name, first searching the current instance and then 
        falling back to the output field if available.
        """
        from django.db.models.lookups import Lookup

        found = self._get_lookup(lookup_name)
        if found is None and hasattr(self, "output_field"):
            return self.output_field.get_lookup(lookup_name)
        if found is not None and not issubclass(found, Lookup):
            return None
        return found

    def get_transform(self, lookup_name):
        """
        :Get the transform instance associated with the given lookup name.

        :Returns the transform instance if found, otherwise returns the transform instance of the output field if applicable, or None if not found.
        """
        from django.db.models.lookups import Transform

        found = self._get_lookup(lookup_name)
        if found is None and hasattr(self, "output_field"):
            return self.output_field.get_transform(lookup_name)
        if found is not None and not issubclass(found, Transform):
            return None
        return found

    @staticmethod
    def merge_dicts(dicts):
        """
        Merge a list of dictionaries into a single dictionary, prioritizing key-value pairs from the first dictionary in the list over subsequent ones.
        """
        merged = {}
        for d in reversed(dicts):
            merged.update(d)
        return merged

    @classmethod
    def _clear_cached_class_lookups(cls):
        for subclass in subclasses(cls):
            subclass.get_class_lookups.cache_clear()

    def register_class_lookup(cls, lookup, lookup_name=None):
        """
        Registers a lookup instance with a class, storing it by a unique name for later retrieval. If no name is provided, the lookup's own name is used. This allows for easy management and caching of lookups at the class level.
        """
        if lookup_name is None:
            lookup_name = lookup.lookup_name
        if "class_lookups" not in cls.__dict__:
            cls.class_lookups = {}
        cls.class_lookups[lookup_name] = lookup
        cls._clear_cached_class_lookups()
        return lookup

    def register_instance_lookup(self, lookup, lookup_name=None):
        """
        Registers an instance lookup object, storing it under a unique name for later retrieval, with the lookup object's own name used by default if no custom name is provided.
        """
        if lookup_name is None:
            lookup_name = lookup.lookup_name
        if "instance_lookups" not in self.__dict__:
            self.instance_lookups = {}
        self.instance_lookups[lookup_name] = lookup
        return lookup

    register_lookup = class_or_instance_method(
        register_class_lookup, register_instance_lookup
    )
    register_class_lookup = classmethod(register_class_lookup)

    def _unregister_class_lookup(cls, lookup, lookup_name=None):
        """
        Removes a specified lookup from a class's lookups, intended for test purposes only due to lack of thread safety.
        """
        if lookup_name is None:
            lookup_name = lookup.lookup_name
        del cls.class_lookups[lookup_name]
        cls._clear_cached_class_lookups()

    def _unregister_instance_lookup(self, lookup, lookup_name=None):
        """
        Remove given lookup from instance lookups. For use in tests only as
        it's not thread-safe.
        """
        if lookup_name is None:
            lookup_name = lookup.lookup_name
        del self.instance_lookups[lookup_name]

    _unregister_lookup = class_or_instance_method(
        _unregister_class_lookup, _unregister_instance_lookup
    )
    _unregister_class_lookup = classmethod(_unregister_class_lookup)


def select_related_descend(field, restricted, requested, select_mask):
    """

    Determine whether to descend deeper for select_related() purposes based on the provided field and selection criteria.

    This function is used to resolve whether a given field should be used to fetch related objects.
    It considers factors such as the field's nullability, manual restrictions, and existing selections.

    """
    # Only relationships can be descended.
    if not field.remote_field:
        return False
    # Forward MTI parent links should not be explicitly descended as they are
    # always JOIN'ed against (unless excluded by `select_mask`).
    if getattr(field.remote_field, "parent_link", False):
        return False
    # When `select_related()` is used without a `*requested` mask all
    # relationships are descended unless they are nullable.
    if not restricted:
        return not field.null
    # When `select_related(*requested)` is used only fields that are part of
    # `requested` should be descended.
    if field.name not in requested:
        return False
    # Prevent invalid usages of `select_related()` and `only()`/`defer()` such
    # as `select_related("a").only("b")` and `select_related("a").defer("a")`.
    if select_mask and field not in select_mask:
        raise FieldError(
            f"Field {field.model._meta.object_name}.{field.name} cannot be both "
            "deferred and traversed using select_related at the same time."
        )
    return True


def refs_expression(lookup_parts, annotations):
    """
    Checks if a lookup path references any annotation, by matching prefixes of the lookup path against the given annotations set. Returns the matched annotation and the remaining part of the lookup path, or None if no match is found.
    """
    for n in range(1, len(lookup_parts) + 1):
        level_n_lookup = LOOKUP_SEP.join(lookup_parts[0:n])
        if annotations.get(level_n_lookup):
            return level_n_lookup, lookup_parts[n:]
    return None, ()


def check_rel_lookup_compatibility(model, target_opts, field):
    """

    Checks if a given model is compatible with target options for a relational lookup.

    Compatibility is determined by verifying if the model and options have matching
    concrete models (ignoring proxy inheritance) or if one is a parent of the other.

    Returns True if the model is compatible, False otherwise. Compatibility is also
    checked for a field's model if the field is a primary key.

    """

    def check(opts):
        return (
            model._meta.concrete_model == opts.concrete_model
            or opts.concrete_model in model._meta.all_parents
            or model in opts.all_parents
        )

    # If the field is a primary key, then doing a query against the field's
    # model is ok, too. Consider the case:
    # class Restaurant(models.Model):
    #     place = OneToOneField(Place, primary_key=True):
    # Restaurant.objects.filter(pk__in=Restaurant.objects.all()).
    # If we didn't have the primary key check, then pk__in (== place__in) would
    # give Place's opts as the target opts, but Restaurant isn't compatible
    # with that. This logic applies only to primary keys, as when doing __in=qs,
    # we are going to turn this into __in=qs.values('pk') later on.
    return check(target_opts) or (
        getattr(field, "primary_key", False) and check(field.model._meta)
    )


class FilteredRelation:
    """Specify custom filtering in the ON clause of SQL joins."""

    def __init__(self, relation_name, *, condition=Q()):
        """
        Initialize a relation object with a name and an optional filter condition.

        :param relation_name: The name of the relation.
        :param condition: A Q object instance that defines the filter condition for the relation.
        :raises ValueError: If the relation_name is empty or the condition is not a Q() instance.
        """
        if not relation_name:
            raise ValueError("relation_name cannot be empty.")
        self.relation_name = relation_name
        self.alias = None
        if not isinstance(condition, Q):
            raise ValueError("condition argument must be a Q() instance.")
        # .condition and .resolved_condition have to be stored independently
        # as the former must remain unchanged for Join.__eq__ to remain stable
        # and reusable even once their .filtered_relation are resolved.
        self.condition = condition
        self.resolved_condition = None

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.relation_name == other.relation_name
            and self.alias == other.alias
            and self.condition == other.condition
        )

    def clone(self):
        """

        Create a copy of the current FilteredRelation instance.

        Returns a cloned instance with the same relation name, condition, alias, and resolved condition.

        """
        clone = FilteredRelation(self.relation_name, condition=self.condition)
        clone.alias = self.alias
        if (resolved_condition := self.resolved_condition) is not None:
            clone.resolved_condition = resolved_condition.clone()
        return clone

    def relabeled_clone(self, change_map):
        clone = self.clone()
        if resolved_condition := clone.resolved_condition:
            clone.resolved_condition = resolved_condition.relabeled_clone(change_map)
        return clone

    def resolve_expression(self, query, reuse, *args, **kwargs):
        clone = self.clone()
        clone.resolved_condition = query.build_filter(
            self.condition,
            can_reuse=reuse,
            allow_joins=True,
            split_subq=False,
            update_join_types=False,
        )[0]
        return clone

    def as_sql(self, compiler, connection):
        return compiler.compile(self.resolved_condition)
