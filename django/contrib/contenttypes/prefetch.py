from django.db.models import Prefetch
from django.db.models.query import ModelIterable, RawQuerySet


class GenericPrefetch(Prefetch):
    def __init__(self, lookup, querysets, to_attr=None):
        """
        Initializes a prefetch object for efficient retrieval of related objects.

        Validates a list of querysets to ensure they are compatible with prefetching, 
        rejecting those that use raw queries, values, or values_list.

        :param lookup: The relationship to prefetch.
        :param querysets: A list of querysets to prefetch.
        :param to_attr: The attribute to store the prefetched objects in (optional).
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
        Returns a dictionary representing the object's state, modified to support serialization by clearing cached results and prefetch data from querysets.
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
