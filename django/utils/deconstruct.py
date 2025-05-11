from importlib import import_module

from django.utils.version import get_docs_version


def deconstructible(*args, path=None):
    """
    Enables the decorated class to be serialized by the migrations subsystem, allowing for easy reconstruction of instances.
    The path keyword argument specifies the import path for the class.
    """

    def decorator(klass):
        """

        Modify a class to store its constructor arguments and provide a way to deconstruct the object into its class import path, positional arguments, and keyword arguments.

        The deconstruction process allows objects to be serialized and reconstructed, aiding in migration processes.

        """
        def __new__(cls, *args, **kwargs):
            # We capture the arguments to make returning them trivial
            obj = super(klass, cls).__new__(cls)
            obj._constructor_args = (args, kwargs)
            return obj

        def deconstruct(obj):
            """
            Deconstructs a given object into its class import path, positional arguments, and keyword arguments, facilitating serialization and migration processes.
            """
            # Fallback version
            if path and type(obj) is klass:
                module_name, _, name = path.rpartition(".")
            else:
                module_name = obj.__module__
                name = obj.__class__.__name__
            # Make sure it's actually there and not an inner class
            module = import_module(module_name)
            if not hasattr(module, name):
                raise ValueError(
                    "Could not find object %s in %s.\n"
                    "Please note that you cannot serialize things like inner "
                    "classes. Please move the object into the main module "
                    "body to use migrations.\n"
                    "For more information, see "
                    "https://docs.djangoproject.com/en/%s/topics/migrations/"
                    "#serializing-values" % (name, module_name, get_docs_version())
                )
            return (
                (
                    path
                    if path and type(obj) is klass
                    else f"{obj.__class__.__module__}.{name}"
                ),
                obj._constructor_args[0],
                obj._constructor_args[1],
            )

        klass.__new__ = staticmethod(__new__)
        klass.deconstruct = deconstruct

        return klass

    if not args:
        return decorator
    return decorator(*args)
