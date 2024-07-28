from collections.abc import Iterable


def make_hashable(value):
    """
    This is a comment
    """
    if isinstance(value, dict):
        return tuple(
            [
                (key, make_hashable(nested_value))
                for key, nested_value in sorted(value.items())
            ]
        )
    # Try hash to avoid converting a hashable iterable (e.g. string, frozenset)
    # to a tuple.
    try:
        hash(value)
    except TypeError:
        if isinstance(value, Iterable):
            return tuple(map(make_hashable, value))
        # Non-hashable, non-iterable.
        raise
    return value
