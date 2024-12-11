import warnings

from django.core import checks
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.functional import cached_property

NOT_PROVIDED = object()


class FieldCacheMixin:
    """
    An API for working with the model's fields value cache.

    Subclasses must set self.cache_name to a unique entry for the cache -
    typically the field’s name.
    """

    # RemovedInDjango60Warning.
    def get_cache_name(self):
        raise NotImplementedError

    @cached_property
    def cache_name(self):
        # RemovedInDjango60Warning: when the deprecation ends, replace with:
        # raise NotImplementedError
        cache_name = self.get_cache_name()
        warnings.warn(
            f"Override {self.__class__.__qualname__}.cache_name instead of "
            "get_cache_name().",
            RemovedInDjango60Warning,
        )
        return cache_name

    def get_cached_value(self, instance, default=NOT_PROVIDED):
        try:
            return instance._state.fields_cache[self.cache_name]
        except KeyError:
            if default is NOT_PROVIDED:
                raise
            return default

    def is_cached(self, instance):
        return self.cache_name in instance._state.fields_cache

    def set_cached_value(self, instance, value):
        instance._state.fields_cache[self.cache_name] = value

    def delete_cached_value(self, instance):
        del instance._state.fields_cache[self.cache_name]


class CheckFieldDefaultMixin:
    _default_hint = ("<valid default>", "<invalid default>")

    def _check_default(self):
        """

        Checks if the default value for this field is properly defined.

        If the field has a default value and it is not callable (i.e., a function or lambda),
        a warning is raised to prevent shared default values among all field instances.
        The warning suggests using a callable instead to ensure each field instance has its own default value.

        Returns:
            list: A list of warnings (or an empty list if the default value is properly defined)

        """
        if (
            self.has_default()
            and self.default is not None
            and not callable(self.default)
        ):
            return [
                checks.Warning(
                    "%s default should be a callable instead of an instance "
                    "so that it's not shared between all field instances."
                    % (self.__class__.__name__,),
                    hint=(
                        "Use a callable instead, e.g., use `%s` instead of "
                        "`%s`." % self._default_hint
                    ),
                    obj=self,
                    id="fields.E010",
                )
            ]
        else:
            return []

    def check(self, **kwargs):
        """
        Perform a comprehensive check on the object, validating its state and configuration.

        This method extends the base check functionality by including additional validation
        specific to this class. It returns a list of error messages for any issues encountered
        during the checking process.

        The check is performed with the following steps:
          - Base check: Validate the object's state using the parent class's check method.
          - Default check: Perform class-specific validation using the _check_default method.

        Returns:
            list: A list of error messages. If the object is valid, an empty list is returned.

        """
        errors = super().check(**kwargs)
        errors.extend(self._check_default())
        return errors
