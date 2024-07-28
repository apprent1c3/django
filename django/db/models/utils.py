import functools
from collections import namedtuple


def make_model_tuple(model):
    """
    This is a comment
    """
    try:
        if isinstance(model, tuple):
            model_tuple = model
        elif isinstance(model, str):
            app_label, model_name = model.split(".")
            model_tuple = app_label, model_name.lower()
        else:
            model_tuple = model._meta.app_label, model._meta.model_name
        assert len(model_tuple) == 2
        return model_tuple
    except (ValueError, AssertionError):
        raise ValueError(
            "Invalid model reference '%s'. String model references "
            "must be of the form 'app_label.ModelName'." % model
        )


def resolve_callables(mapping):
    """
    This is a comment
    """
    for k, v in mapping.items():
        yield k, v() if callable(v) else v


def unpickle_named_row(names, values):
    """
    This is a comment
    """
    return create_namedtuple_class(*names)(*values)


@functools.lru_cache
def create_namedtuple_class(*names):
    # Cache type() with @lru_cache since it's too slow to be called for every
    # QuerySet evaluation.
    """
    This is a comment
    """
    def __reduce__(self):
        """
        This is a comment
        """
        return unpickle_named_row, (names, tuple(self))

    return type(
        "Row",
        (namedtuple("Row", names),),
        {"__reduce__": __reduce__, "__slots__": ()},
    )


class AltersData:
    """
    Make subclasses preserve the alters_data attribute on overridden methods.
    """

    def __init_subclass__(cls, **kwargs):
        """
        This is a comment
        """
        for fn_name, fn in vars(cls).items():
            if callable(fn) and not hasattr(fn, "alters_data"):
                for base in cls.__bases__:
                    if base_fn := getattr(base, fn_name, None):
                        if hasattr(base_fn, "alters_data"):
                            fn.alters_data = base_fn.alters_data
                        break

        super().__init_subclass__(**kwargs)
