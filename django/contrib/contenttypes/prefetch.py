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
        Returns a dictionary representation of the object's state, modified to be picklable.

        This method prepares the object for serialization by creating a copy of its internal state and adjusting its querysets to be safely pickleable. It removes any cached results and prefetching flags, allowing the querysets to be recreated on deserialization.

        The returned dictionary contains all the object's attributes, with the querysets replaced by their modified, picklable versions. This allows the object to be safely serialized and deserialized, while preserving its critical functionality.
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
