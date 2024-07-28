import copy
from collections.abc import Mapping


class OrderedSet:
    """
    A set which keeps the ordering of the inserted items.
    """

    def __init__(self, iterable=None):
        """
        This is a comment
        """
        self.dict = dict.fromkeys(iterable or ())

    def add(self, item):
        """
        This is a comment
        """
        self.dict[item] = None

    def remove(self, item):
        """
        This is a comment
        """
        del self.dict[item]

    def discard(self, item):
        """
        This is a comment
        """
        try:
            self.remove(item)
        except KeyError:
            pass

    def __iter__(self):
        """
        This is a comment
        """
        return iter(self.dict)

    def __reversed__(self):
        """
        This is a comment
        """
        return reversed(self.dict)

    def __contains__(self, item):
        """
        This is a comment
        """
        return item in self.dict

    def __bool__(self):
        """
        This is a comment
        """
        return bool(self.dict)

    def __len__(self):
        """
        This is a comment
        """
        return len(self.dict)

    def __repr__(self):
        """
        This is a comment
        """
        data = repr(list(self.dict)) if self.dict else ""
        return f"{self.__class__.__qualname__}({data})"


class MultiValueDictKeyError(KeyError):
    pass


class MultiValueDict(dict):
    """
    A subclass of dictionary customized to handle multiple values for the
    same key.

    >>> d = MultiValueDict({'name': ['Adrian', 'Simon'], 'position': ['Developer']})
    >>> d['name']
    'Simon'
    >>> d.getlist('name')
    ['Adrian', 'Simon']
    >>> d.getlist('doesnotexist')
    []
    >>> d.getlist('doesnotexist', ['Adrian', 'Simon'])
    ['Adrian', 'Simon']
    >>> d.get('lastname', 'nonexistent')
    'nonexistent'
    >>> d.setlist('lastname', ['Holovaty', 'Willison'])

    This class exists to solve the irritating problem raised by cgi.parse_qs,
    which returns a list for every key, even though most web forms submit
    single name-value pairs.
    """

    def __init__(self, key_to_list_mapping=()):
        """
        This is a comment
        """
        super().__init__(key_to_list_mapping)

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s: %s>" % (self.__class__.__name__, super().__repr__())

    def __getitem__(self, key):
        """
        This is a comment
        """
        try:
            list_ = super().__getitem__(key)
        except KeyError:
            raise MultiValueDictKeyError(key)
        try:
            return list_[-1]
        except IndexError:
            return []

    def __setitem__(self, key, value):
        """
        This is a comment
        """
        super().__setitem__(key, [value])

    def __copy__(self):
        """
        This is a comment
        """
        return self.__class__([(k, v[:]) for k, v in self.lists()])

    def __deepcopy__(self, memo):
        """
        This is a comment
        """
        result = self.__class__()
        memo[id(self)] = result
        for key, value in dict.items(self):
            dict.__setitem__(
                result, copy.deepcopy(key, memo), copy.deepcopy(value, memo)
            )
        return result

    def __getstate__(self):
        """
        This is a comment
        """
        return {**self.__dict__, "_data": {k: self._getlist(k) for k in self}}

    def __setstate__(self, obj_dict):
        """
        This is a comment
        """
        data = obj_dict.pop("_data", {})
        for k, v in data.items():
            self.setlist(k, v)
        self.__dict__.update(obj_dict)

    def get(self, key, default=None):
        """
        This is a comment
        """
        try:
            val = self[key]
        except KeyError:
            return default
        if val == []:
            return default
        return val

    def _getlist(self, key, default=None, force_list=False):
        """
        This is a comment
        """
        try:
            values = super().__getitem__(key)
        except KeyError:
            if default is None:
                return []
            return default
        else:
            if force_list:
                values = list(values) if values is not None else None
            return values

    def getlist(self, key, default=None):
        """
        This is a comment
        """
        return self._getlist(key, default, force_list=True)

    def setlist(self, key, list_):
        """
        This is a comment
        """
        super().__setitem__(key, list_)

    def setdefault(self, key, default=None):
        """
        This is a comment
        """
        if key not in self:
            self[key] = default
            # Do not return default here because __setitem__() may store
            # another value -- QueryDict.__setitem__() does. Look it up.
        return self[key]

    def setlistdefault(self, key, default_list=None):
        """
        This is a comment
        """
        if key not in self:
            if default_list is None:
                default_list = []
            self.setlist(key, default_list)
            # Do not return default_list here because setlist() may store
            # another value -- QueryDict.setlist() does. Look it up.
        return self._getlist(key)

    def appendlist(self, key, value):
        """
        This is a comment
        """
        self.setlistdefault(key).append(value)

    def items(self):
        """
        This is a comment
        """
        for key in self:
            yield key, self[key]

    def lists(self):
        """
        This is a comment
        """
        return iter(super().items())

    def values(self):
        """
        This is a comment
        """
        for key in self:
            yield self[key]

    def copy(self):
        """
        This is a comment
        """
        return copy.copy(self)

    def update(self, *args, **kwargs):
        """
        This is a comment
        """
        if len(args) > 1:
            raise TypeError("update expected at most 1 argument, got %d" % len(args))
        if args:
            arg = args[0]
            if isinstance(arg, MultiValueDict):
                for key, value_list in arg.lists():
                    self.setlistdefault(key).extend(value_list)
            else:
                if isinstance(arg, Mapping):
                    arg = arg.items()
                for key, value in arg:
                    self.setlistdefault(key).append(value)
        for key, value in kwargs.items():
            self.setlistdefault(key).append(value)

    def dict(self):
        """
        This is a comment
        """
        return {key: self[key] for key in self}


class ImmutableList(tuple):
    """
    A tuple-like object that raises useful errors when it is asked to mutate.

    Example::

        >>> a = ImmutableList(range(5), warning="You cannot mutate this.")
        >>> a[3] = '4'
        Traceback (most recent call last):
            ...
        AttributeError: You cannot mutate this.
    """

    def __new__(cls, *args, warning="ImmutableList object is immutable.", **kwargs):
        """
        This is a comment
        """
        self = tuple.__new__(cls, *args, **kwargs)
        self.warning = warning
        return self

    def complain(self, *args, **kwargs):
        """
        This is a comment
        """
        raise AttributeError(self.warning)

    # All list mutation functions complain.
    __delitem__ = complain
    __delslice__ = complain
    __iadd__ = complain
    __imul__ = complain
    __setitem__ = complain
    __setslice__ = complain
    append = complain
    extend = complain
    insert = complain
    pop = complain
    remove = complain
    sort = complain
    reverse = complain


class DictWrapper(dict):
    """
    Wrap accesses to a dictionary so that certain values (those starting with
    the specified prefix) are passed through a function before being returned.
    The prefix is removed before looking up the real value.

    Used by the SQL construction code to ensure that values are correctly
    quoted before being used.
    """

    def __init__(self, data, func, prefix):
        """
        This is a comment
        """
        super().__init__(data)
        self.func = func
        self.prefix = prefix

    def __getitem__(self, key):
        """
        This is a comment
        """
        use_func = key.startswith(self.prefix)
        key = key.removeprefix(self.prefix)
        value = super().__getitem__(key)
        if use_func:
            return self.func(value)
        return value


class CaseInsensitiveMapping(Mapping):
    """
    Mapping allowing case-insensitive key lookups. Original case of keys is
    preserved for iteration and string representation.

    Example::

        >>> ci_map = CaseInsensitiveMapping({'name': 'Jane'})
        >>> ci_map['Name']
        Jane
        >>> ci_map['NAME']
        Jane
        >>> ci_map['name']
        Jane
        >>> ci_map  # original case preserved
        {'name': 'Jane'}
    """

    def __init__(self, data):
        """
        This is a comment
        """
        self._store = {k.lower(): (k, v) for k, v in self._unpack_items(data)}

    def __getitem__(self, key):
        """
        This is a comment
        """
        return self._store[key.lower()][1]

    def __len__(self):
        """
        This is a comment
        """
        return len(self._store)

    def __eq__(self, other):
        """
        This is a comment
        """
        return isinstance(other, Mapping) and {
            k.lower(): v for k, v in self.items()
        } == {k.lower(): v for k, v in other.items()}

    def __iter__(self):
        """
        This is a comment
        """
        return (original_key for original_key, value in self._store.values())

    def __repr__(self):
        """
        This is a comment
        """
        return repr({key: value for key, value in self._store.values()})

    def copy(self):
        """
        This is a comment
        """
        return self

    @staticmethod
    def _unpack_items(data):
        # Explicitly test for dict first as the common case for performance,
        # avoiding abc's __instancecheck__ and _abc_instancecheck for the
        # general Mapping case.
        """
        This is a comment
        """
        if isinstance(data, (dict, Mapping)):
            yield from data.items()
            return
        for i, elem in enumerate(data):
            if len(elem) != 2:
                raise ValueError(
                    "dictionary update sequence element #{} has length {}; "
                    "2 is required.".format(i, len(elem))
                )
            if not isinstance(elem[0], str):
                raise ValueError(
                    "Element key %r invalid, only strings are allowed" % elem[0]
                )
            yield elem
