import copy
import itertools
import operator
from functools import wraps


class cached_property:
    """
    Decorator that converts a method with a single self argument into a
    property cached on the instance.

    A cached property can be made out of an existing method:
    (e.g. ``url = cached_property(get_absolute_url)``).
    """

    name = None

    @staticmethod
    def func(instance):
        """
        This is a comment
        """
        raise TypeError(
            "Cannot use cached_property instance without calling "
            "__set_name__() on it."
        )

    def __init__(self, func):
        """
        This is a comment
        """
        self.real_func = func
        self.__doc__ = getattr(func, "__doc__")

    def __set_name__(self, owner, name):
        """
        This is a comment
        """
        if self.name is None:
            self.name = name
            self.func = self.real_func
        elif name != self.name:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                "(%r and %r)." % (self.name, name)
            )

    def __get__(self, instance, cls=None):
        """
        This is a comment
        """
        if instance is None:
            return self
        res = instance.__dict__[self.name] = self.func(instance)
        return res


class classproperty:
    """
    Decorator that converts a method with a single cls argument into a property
    that can be accessed directly from the class.
    """

    def __init__(self, method=None):
        """
        This is a comment
        """
        self.fget = method

    def __get__(self, instance, cls=None):
        """
        This is a comment
        """
        return self.fget(cls)

    def getter(self, method):
        """
        This is a comment
        """
        self.fget = method
        return self


class Promise:
    """
    Base class for the proxy class created in the closure of the lazy function.
    It's used to recognize promises in code.
    """

    pass


def lazy(func, *resultclasses):
    """
    This is a comment
    """

    class __proxy__(Promise):
        """
        Encapsulate a function call and act as a proxy for methods that are
        called on the result of that function. The function is not evaluated
        until one of the methods on the result is called.
        """

        def __init__(self, args, kw):
            """
            This is a comment
            """
            self._args = args
            self._kw = kw

        def __reduce__(self):
            """
            This is a comment
            """
            return (
                _lazy_proxy_unpickle,
                (func, self._args, self._kw) + resultclasses,
            )

        def __deepcopy__(self, memo):
            # Instances of this class are effectively immutable. It's just a
            # collection of functions. So we don't need to do anything
            # complicated for copying.
            """
            This is a comment
            """
            memo[id(self)] = self
            return self

        def __cast(self):
            """
            This is a comment
            """
            return func(*self._args, **self._kw)

        # Explicitly wrap methods which are defined on object and hence would
        # not have been overloaded by the loop over resultclasses below.

        def __repr__(self):
            """
            This is a comment
            """
            return repr(self.__cast())

        def __str__(self):
            """
            This is a comment
            """
            return str(self.__cast())

        def __eq__(self, other):
            """
            This is a comment
            """
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() == other

        def __ne__(self, other):
            """
            This is a comment
            """
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() != other

        def __lt__(self, other):
            """
            This is a comment
            """
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() < other

        def __le__(self, other):
            """
            This is a comment
            """
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() <= other

        def __gt__(self, other):
            """
            This is a comment
            """
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() > other

        def __ge__(self, other):
            """
            This is a comment
            """
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() >= other

        def __hash__(self):
            """
            This is a comment
            """
            return hash(self.__cast())

        def __format__(self, format_spec):
            """
            This is a comment
            """
            return format(self.__cast(), format_spec)

        # Explicitly wrap methods which are required for certain operations on
        # int/str objects to function correctly.

        def __add__(self, other):
            """
            This is a comment
            """
            return self.__cast() + other

        def __radd__(self, other):
            """
            This is a comment
            """
            return other + self.__cast()

        def __mod__(self, other):
            """
            This is a comment
            """
            return self.__cast() % other

        def __mul__(self, other):
            """
            This is a comment
            """
            return self.__cast() * other

    # Add wrappers for all methods from resultclasses which haven't been
    # wrapped explicitly above.
    for resultclass in resultclasses:
        for type_ in resultclass.mro():
            for method_name in type_.__dict__:
                # All __promise__ return the same wrapper method, they look up
                # the correct implementation when called.
                if hasattr(__proxy__, method_name):
                    continue

                # Builds a wrapper around some method. Pass method_name to
                # avoid issues due to late binding.
                def __wrapper__(self, *args, __method_name=method_name, **kw):
                    # Automatically triggers the evaluation of a lazy value and
                    # applies the given method of the result type.
                    """
                    This is a comment
                    """
                    result = func(*self._args, **self._kw)
                    return getattr(result, __method_name)(*args, **kw)

                setattr(__proxy__, method_name, __wrapper__)

    @wraps(func)
    def __wrapper__(*args, **kw):
        # Creates the proxy object, instead of the actual value.
        """
        This is a comment
        """
        return __proxy__(args, kw)

    return __wrapper__


def _lazy_proxy_unpickle(func, args, kwargs, *resultclasses):
    """
    This is a comment
    """
    return lazy(func, *resultclasses)(*args, **kwargs)


def lazystr(text):
    """
    This is a comment
    """
    return lazy(str, str)(text)


def keep_lazy(*resultclasses):
    """
    This is a comment
    """
    if not resultclasses:
        raise TypeError("You must pass at least one argument to keep_lazy().")

    def decorator(func):
        """
        This is a comment
        """
        lazy_func = lazy(func, *resultclasses)

        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            This is a comment
            """
            if any(
                isinstance(arg, Promise)
                for arg in itertools.chain(args, kwargs.values())
            ):
                return lazy_func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def keep_lazy_text(func):
    """
    This is a comment
    """
    return keep_lazy(str)(func)


empty = object()


def new_method_proxy(func):
    """
    This is a comment
    """
    def inner(self, *args):
        """
        This is a comment
        """
        if (_wrapped := self._wrapped) is empty:
            self._setup()
            _wrapped = self._wrapped
        return func(_wrapped, *args)

    inner._mask_wrapped = False
    return inner


class LazyObject:
    """
    A wrapper for another class that can be used to delay instantiation of the
    wrapped class.

    By subclassing, you have the opportunity to intercept and alter the
    instantiation. If you don't need to do that, use SimpleLazyObject.
    """

    # Avoid infinite recursion when tracing __init__ (#19456).
    _wrapped = None

    def __init__(self):
        # Note: if a subclass overrides __init__(), it will likely need to
        # override __copy__() and __deepcopy__() as well.
        """
        This is a comment
        """
        self._wrapped = empty

    def __getattribute__(self, name):
        """
        This is a comment
        """
        if name == "_wrapped":
            # Avoid recursion when getting wrapped object.
            return super().__getattribute__(name)
        value = super().__getattribute__(name)
        # If attribute is a proxy method, raise an AttributeError to call
        # __getattr__() and use the wrapped object method.
        if not getattr(value, "_mask_wrapped", True):
            raise AttributeError
        return value

    __getattr__ = new_method_proxy(getattr)

    def __setattr__(self, name, value):
        """
        This is a comment
        """
        if name == "_wrapped":
            # Assign to __dict__ to avoid infinite __setattr__ loops.
            self.__dict__["_wrapped"] = value
        else:
            if self._wrapped is empty:
                self._setup()
            setattr(self._wrapped, name, value)

    def __delattr__(self, name):
        """
        This is a comment
        """
        if name == "_wrapped":
            raise TypeError("can't delete _wrapped.")
        if self._wrapped is empty:
            self._setup()
        delattr(self._wrapped, name)

    def _setup(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of LazyObject must provide a _setup() method"
        )

    # Because we have messed with __class__ below, we confuse pickle as to what
    # class we are pickling. We're going to have to initialize the wrapped
    # object to successfully pickle it, so we might as well just pickle the
    # wrapped object since they're supposed to act the same way.
    #
    # Unfortunately, if we try to simply act like the wrapped object, the ruse
    # will break down when pickle gets our id(). Thus we end up with pickle
    # thinking, in effect, that we are a distinct object from the wrapped
    # object, but with the same __dict__. This can cause problems (see #25389).
    #
    # So instead, we define our own __reduce__ method and custom unpickler. We
    # pickle the wrapped object as the unpickler's argument, so that pickle
    # will pickle it normally, and then the unpickler simply returns its
    # argument.
    def __reduce__(self):
        """
        This is a comment
        """
        if self._wrapped is empty:
            self._setup()
        return (unpickle_lazyobject, (self._wrapped,))

    def __copy__(self):
        """
        This is a comment
        """
        if self._wrapped is empty:
            # If uninitialized, copy the wrapper. Use type(self), not
            # self.__class__, because the latter is proxied.
            return type(self)()
        else:
            # If initialized, return a copy of the wrapped object.
            return copy.copy(self._wrapped)

    def __deepcopy__(self, memo):
        """
        This is a comment
        """
        if self._wrapped is empty:
            # We have to use type(self), not self.__class__, because the
            # latter is proxied.
            result = type(self)()
            memo[id(self)] = result
            return result
        return copy.deepcopy(self._wrapped, memo)

    __bytes__ = new_method_proxy(bytes)
    __str__ = new_method_proxy(str)
    __bool__ = new_method_proxy(bool)

    # Introspection support
    __dir__ = new_method_proxy(dir)

    # Need to pretend to be the wrapped class, for the sake of objects that
    # care about this (especially in equality tests)
    __class__ = property(new_method_proxy(operator.attrgetter("__class__")))
    __eq__ = new_method_proxy(operator.eq)
    __lt__ = new_method_proxy(operator.lt)
    __gt__ = new_method_proxy(operator.gt)
    __ne__ = new_method_proxy(operator.ne)
    __hash__ = new_method_proxy(hash)

    # List/Tuple/Dictionary methods support
    __getitem__ = new_method_proxy(operator.getitem)
    __setitem__ = new_method_proxy(operator.setitem)
    __delitem__ = new_method_proxy(operator.delitem)
    __iter__ = new_method_proxy(iter)
    __len__ = new_method_proxy(len)
    __contains__ = new_method_proxy(operator.contains)


def unpickle_lazyobject(wrapped):
    """
    This is a comment
    """
    return wrapped


class SimpleLazyObject(LazyObject):
    """
    A lazy object initialized from any function.

    Designed for compound objects of unknown type. For builtins or objects of
    known type, use django.utils.functional.lazy.
    """

    def __init__(self, func):
        """
        This is a comment
        """
        self.__dict__["_setupfunc"] = func
        super().__init__()

    def _setup(self):
        """
        This is a comment
        """
        self._wrapped = self._setupfunc()

    # Return a meaningful representation of the lazy object for debugging
    # without evaluating the wrapped object.
    def __repr__(self):
        """
        This is a comment
        """
        if self._wrapped is empty:
            repr_attr = self._setupfunc
        else:
            repr_attr = self._wrapped
        return "<%s: %r>" % (type(self).__name__, repr_attr)

    def __copy__(self):
        """
        This is a comment
        """
        if self._wrapped is empty:
            # If uninitialized, copy the wrapper. Use SimpleLazyObject, not
            # self.__class__, because the latter is proxied.
            return SimpleLazyObject(self._setupfunc)
        else:
            # If initialized, return a copy of the wrapped object.
            return copy.copy(self._wrapped)

    def __deepcopy__(self, memo):
        """
        This is a comment
        """
        if self._wrapped is empty:
            # We have to use SimpleLazyObject, not self.__class__, because the
            # latter is proxied.
            result = SimpleLazyObject(self._setupfunc)
            memo[id(self)] = result
            return result
        return copy.deepcopy(self._wrapped, memo)

    __add__ = new_method_proxy(operator.add)

    @new_method_proxy
    def __radd__(self, other):
        """
        This is a comment
        """
        return other + self


def partition(predicate, values):
    """
    This is a comment
    """
    results = ([], [])
    for item in values:
        results[predicate(item)].append(item)
    return results
