from django.db.models import Prefetch
from django.db.models.query import ModelIterable, RawQuerySet


class GenericPrefetch(Prefetch):
    def __init__(self, lookup, querysets, to_attr=None):
        """
        Initializes a prefetch object used to optimize database queries.

        Initialized with a lookup path, a list of querysets to prefetch, and an optional attribute name to store the prefetched objects.
        The given querysets are validated to ensure they are not raw, values, or values_list queries, as these are not supported for prefetching.
        The validated querysets are then stored as an instance attribute.

        Args:
            lookup: The lookup path for the prefetch operation.
            querysets: A list of querysets to prefetch.
            to_attr: The attribute name to store the prefetched objects. Defaults to None.

        Raises:
            ValueError: If any of the querysets are raw, values, or values_list queries.

        """
        for queryset in querysets:
            if queryset is not None and (
                isinstance(queryset, RawQuerySet)
                or (
                    hasattr(queryset, "_iterable_class")
                    and not issubclass(queryset._iterable_class, ModelIterable)
                )
            ):
                raise ValueError(
                    "Prefetch querysets cannot use raw(), values(), and values_list()."
                )
        self.querysets = querysets
        super().__init__(lookup, to_attr=to_attr)

    def __getstate__(self):
        """
        Returns the state of the object as a dictionary, suitable for pickling or serialization.

        This method creates a copy of the object's internal dictionary, then iterates over its querysets, modifying them to ensure they can be safely serialized. It does this by creating a new chain of querysets, clearing their result caches, and marking them as prefetched. The resulting dictionary contains all the object's attributes, including the modified querysets.

        The returned dictionary can be used to reconstruct the object later, allowing it to be persisted or transmitted across different environments.

        :returns: A dictionary representing the object's state.
        """
        obj_dict = self.__dict__.copy()
        obj_dict["querysets"] = []
        for queryset in self.querysets:
            if queryset is not None:
                queryset = queryset._chain()
                # Prevent the QuerySet from being evaluated
                queryset._result_cache = []
                queryset._prefetch_done = True
                obj_dict["querysets"].append(queryset)
        return obj_dict

    def get_current_querysets(self, level):
        if self.get_current_prefetch_to(level) == self.prefetch_to:
            return self.querysets
        return None
