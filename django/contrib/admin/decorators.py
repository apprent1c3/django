def action(function=None, *, permissions=None, description=None):
    """
    Conveniently adds attributes to an action function, such as permissions and description, through a decorator. This simplifies the process of defining actions with custom permissions and descriptions, making the code more readable and maintainable.
    """

    def decorator(func):
        """

        Decorates a function with permission and description metadata.

        Assigns allowed permissions and a short description to the decorated function,
        providing additional context for its usage and access control.

        :param func: The function to be decorated
        :return: The decorated function with updated metadata

        """
        if permissions is not None:
            func.allowed_permissions = permissions
        if description is not None:
            func.short_description = description
        return func

    if function is None:
        return decorator
    else:
        return decorator(function)


def display(
    function=None, *, boolean=None, ordering=None, description=None, empty_value=None
):
    """
    A decorator that conveniently adds display attributes to a function, 
    such as rendering the output as a boolean, specifying a field for ordering,
    providing a short description, or displaying a custom value for empty results.
    """

    def decorator(func):
        """

        A decorator to modify function behavior for display purposes.

        Sets various display-related attributes on the decorated function, such as
        boolean representation, admin ordering field, short description, and
        empty value display. Raises an error if both boolean and empty_value
        are provided, as they are mutually exclusive.

        """
        if boolean is not None and empty_value is not None:
            raise ValueError(
                "The boolean and empty_value arguments to the @display "
                "decorator are mutually exclusive."
            )
        if boolean is not None:
            func.boolean = boolean
        if ordering is not None:
            func.admin_order_field = ordering
        if description is not None:
            func.short_description = description
        if empty_value is not None:
            func.empty_value_display = empty_value
        return func

    if function is None:
        return decorator
    else:
        return decorator(function)


def register(*models, site=None):
    """
    Register one or more model classes with an admin site, optionally specifying a custom admin site. This allows for customization of the admin interface for the registered models.
    """
    from django.contrib.admin import ModelAdmin
    from django.contrib.admin.sites import AdminSite
    from django.contrib.admin.sites import site as default_site

    def _model_admin_wrapper(admin_class):
        """

        Registers a model admin class with the admin site, performing necessary checks and validation.

        :raises ValueError: If no models are provided, the site is not an instance of AdminSite, or the wrapped class does not subclass ModelAdmin.
        :returns: The registered model admin class

        """
        if not models:
            raise ValueError("At least one model must be passed to register.")

        admin_site = site or default_site

        if not isinstance(admin_site, AdminSite):
            raise ValueError("site must subclass AdminSite")

        if not issubclass(admin_class, ModelAdmin):
            raise ValueError("Wrapped class must subclass ModelAdmin.")

        admin_site.register(models, admin_class=admin_class)

        return admin_class

    return _model_admin_wrapper
