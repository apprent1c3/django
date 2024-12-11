from django.db.models import Prefetch
from django.db.models.query import ModelIterable, RawQuerySet


class GenericPrefetch(Prefetch):
    def __init__(self, lookup, querysets, to_attr=None):
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
        Returns a dictionary representing the state of the object, suitable for pickling.

        This method creates a copy of the object's internal dictionary and modifies the 'querysets' key to contain a list of memoized querysets.
        Each queryset is prepared for serialization by clearing its result cache and marking it as prefetched.
        The resulting dictionary can be used to reconstruct the object at a later time, preserving its internal state.
        Note that any querysets originally stored in the object are replaced with memoized versions to prevent the loss of query state during serialization.
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
