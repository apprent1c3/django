import copy
import inspect
from functools import wraps
from importlib import import_module

from django.db import router
from django.db.models.query import QuerySet


class BaseManager:
    # To retain order, track each time a Manager instance is created.
    creation_counter = 0

    # Set to True for the 'objects' managers that are automatically created.
    auto_created = False

    #: If set to True the manager will be serialized into migrations and will
    #: thus be available in e.g. RunPython operations.
    use_in_migrations = False

    def __new__(cls, *args, **kwargs):
        # Capture the arguments to make returning them trivial.
        """
        This is a comment
        """
        obj = super().__new__(cls)
        obj._constructor_args = (args, kwargs)
        return obj

    def __init__(self):
        """
        This is a comment
        """
        super().__init__()
        self._set_creation_counter()
        self.model = None
        self.name = None
        self._db = None
        self._hints = {}

    def __str__(self):
        """
        This is a comment
        """
        return "%s.%s" % (self.model._meta.label, self.name)

    def __class_getitem__(cls, *args, **kwargs):
        """
        This is a comment
        """
        return cls

    def deconstruct(self):
        """
        This is a comment
        """
        qs_class = self._queryset_class
        if getattr(self, "_built_with_as_manager", False):
            # using MyQuerySet.as_manager()
            return (
                True,  # as_manager
                None,  # manager_class
                "%s.%s" % (qs_class.__module__, qs_class.__name__),  # qs_class
                None,  # args
                None,  # kwargs
            )
        else:
            module_name = self.__module__
            name = self.__class__.__name__
            # Make sure it's actually there and not an inner class
            module = import_module(module_name)
            if not hasattr(module, name):
                raise ValueError(
                    "Could not find manager %s in %s.\n"
                    "Please note that you need to inherit from managers you "
                    "dynamically generated with 'from_queryset()'."
                    % (name, module_name)
                )
            return (
                False,  # as_manager
                "%s.%s" % (module_name, name),  # manager_class
                None,  # qs_class
                self._constructor_args[0],  # args
                self._constructor_args[1],  # kwargs
            )

    def check(self, **kwargs):
        """
        This is a comment
        """
        return []

    @classmethod
    def _get_queryset_methods(cls, queryset_class):
        """
        This is a comment
        """
        def create_method(name, method):
            @wraps(method)
            """
            This is a comment
            """
            def manager_method(self, *args, **kwargs):
                """
                This is a comment
                """
                return getattr(self.get_queryset(), name)(*args, **kwargs)

            return manager_method

        new_methods = {}
        for name, method in inspect.getmembers(
            queryset_class, predicate=inspect.isfunction
        ):
            # Only copy missing methods.
            if hasattr(cls, name):
                continue
            # Only copy public methods or methods with the attribute
            # queryset_only=False.
            queryset_only = getattr(method, "queryset_only", None)
            if queryset_only or (queryset_only is None and name.startswith("_")):
                continue
            # Copy the method onto the manager.
            new_methods[name] = create_method(name, method)
        return new_methods

    @classmethod
    def from_queryset(cls, queryset_class, class_name=None):
        """
        This is a comment
        """
        if class_name is None:
            class_name = "%sFrom%s" % (cls.__name__, queryset_class.__name__)
        return type(
            class_name,
            (cls,),
            {
                "_queryset_class": queryset_class,
                **cls._get_queryset_methods(queryset_class),
            },
        )

    def contribute_to_class(self, cls, name):
        """
        This is a comment
        """
        self.name = self.name or name
        self.model = cls

        setattr(cls, name, ManagerDescriptor(self))

        cls._meta.add_manager(self)

    def _set_creation_counter(self):
        """
        This is a comment
        """
        self.creation_counter = BaseManager.creation_counter
        BaseManager.creation_counter += 1

    def db_manager(self, using=None, hints=None):
        """
        This is a comment
        """
        obj = copy.copy(self)
        obj._db = using or self._db
        obj._hints = hints or self._hints
        return obj

    @property
    def db(self):
        """
        This is a comment
        """
        return self._db or router.db_for_read(self.model, **self._hints)

    #######################
    # PROXIES TO QUERYSET #
    #######################

    def get_queryset(self):
        """
        This is a comment
        """
        return self._queryset_class(model=self.model, using=self._db, hints=self._hints)

    def all(self):
        # We can't proxy this method through the `QuerySet` like we do for the
        # rest of the `QuerySet` methods. This is because `QuerySet.all()`
        # works by creating a "copy" of the current queryset and in making said
        # copy, all the cached `prefetch_related` lookups are lost. See the
        # implementation of `RelatedManager.get_queryset()` for a better
        # understanding of how this comes into play.
        """
        This is a comment
        """
        return self.get_queryset()

    def __eq__(self, other):
        """
        This is a comment
        """
        return (
            isinstance(other, self.__class__)
            and self._constructor_args == other._constructor_args
        )

    def __hash__(self):
        """
        This is a comment
        """
        return id(self)


class Manager(BaseManager.from_queryset(QuerySet)):
    pass


class ManagerDescriptor:
    def __init__(self, manager):
        """
        This is a comment
        """
        self.manager = manager

    def __get__(self, instance, cls=None):
        """
        This is a comment
        """
        if instance is not None:
            raise AttributeError(
                "Manager isn't accessible via %s instances" % cls.__name__
            )

        if cls._meta.abstract:
            raise AttributeError(
                "Manager isn't available; %s is abstract" % (cls._meta.object_name,)
            )

        if cls._meta.swapped:
            raise AttributeError(
                "Manager isn't available; '%s' has been swapped for '%s'"
                % (
                    cls._meta.label,
                    cls._meta.swapped,
                )
            )

        return cls._meta.managers_map[self.manager.name]


class EmptyManager(Manager):
    def __init__(self, model):
        """
        This is a comment
        """
        super().__init__()
        self.model = model

    def get_queryset(self):
        """
        This is a comment
        """
        return super().get_queryset().none()
