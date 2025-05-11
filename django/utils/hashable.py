from collections.abc import Iterable


def make_hashable(value):
    """
    Attempt to make a given value hashable or raise a TypeError if it fails.

    The returned value is guaranteed to generate the same hash for equal input values, enabling its use in hash-based data structures such as sets and dictionaries. This function handles nested structures, including dictionaries and iterable collections, by recursively converting their contents to a hashable form.
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
