import json

from django.contrib.postgres import lookups
from django.contrib.postgres.forms import SimpleArrayField
from django.contrib.postgres.validators import ArrayMaxLengthValidator
from django.core import checks, exceptions
from django.db.models import Field, Func, IntegerField, Transform, Value
from django.db.models.fields.mixins import CheckFieldDefaultMixin
from django.db.models.lookups import Exact, In
from django.utils.translation import gettext_lazy as _

from ..utils import prefix_validation_error
from .utils import AttributeSetter

__all__ = ["ArrayField"]


class ArrayField(CheckFieldDefaultMixin, Field):
    empty_strings_allowed = False
    default_error_messages = {
        "item_invalid": _("Item %(nth)s in the array did not validate:"),
        "nested_array_mismatch": _("Nested arrays must have the same length."),
    }
    _default_hint = ("list", "[]")

    def __init__(self, base_field, size=None, **kwargs):
        self.base_field = base_field
        self.db_collation = getattr(self.base_field, "db_collation", None)
        self.size = size
        if self.size:
            self.default_validators = [
                *self.default_validators,
                ArrayMaxLengthValidator(self.size),
            ]
        # For performance, only add a from_db_value() method if the base field
        # implements it.
        if hasattr(self.base_field, "from_db_value"):
            self.from_db_value = self._from_db_value
        super().__init__(**kwargs)

    @property
    def model(self):
        """
        The model associated with this object.

        This property provides access to the model attribute of the object. If the model attribute does not exist, it raises an AttributeError indicating that the object does not have a 'model' attribute.

        :raises: AttributeError if the 'model' attribute does not exist
        :rtype: The type of the model attribute
        """
        try:
            return self.__dict__["model"]
        except KeyError:
            raise AttributeError(
                "'%s' object has no attribute 'model'" % self.__class__.__name__
            )

    @model.setter
    def model(self, model):
        self.__dict__["model"] = model
        self.base_field.model = model

    @classmethod
    def _choices_is_value(cls, value):
        return isinstance(value, (list, tuple)) or super()._choices_is_value(value)

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        if self.base_field.remote_field:
            errors.append(
                checks.Error(
                    "Base field for array cannot be a related field.",
                    obj=self,
                    id="postgres.E002",
                )
            )
        else:
            # Remove the field name checks as they are not needed here.
            base_checks = self.base_field.check()
            if base_checks:
                error_messages = "\n    ".join(
                    "%s (%s)" % (base_check.msg, base_check.id)
                    for base_check in base_checks
                    if isinstance(base_check, checks.Error)
                )
                if error_messages:
                    errors.append(
                        checks.Error(
                            "Base field for array has errors:\n    %s" % error_messages,
                            obj=self,
                            id="postgres.E001",
                        )
                    )
                warning_messages = "\n    ".join(
                    "%s (%s)" % (base_check.msg, base_check.id)
                    for base_check in base_checks
                    if isinstance(base_check, checks.Warning)
                )
                if warning_messages:
                    errors.append(
                        checks.Warning(
                            "Base field for array has warnings:\n    %s"
                            % warning_messages,
                            obj=self,
                            id="postgres.W004",
                        )
                    )
        return errors

    def set_attributes_from_name(self, name):
        super().set_attributes_from_name(name)
        self.base_field.set_attributes_from_name(name)

    @property
    def description(self):
        return "Array of %s" % self.base_field.description

    def db_type(self, connection):
        """
        Returns the database column type for the field.

        This method constructs the database type by combining the base field type
        with the field's size, if specified. The resulting string is in the format
        'base_field_type[size]', where 'size' is only included if it is not empty.

        :param connection: The database connection to determine the type for.
        :returns: A string representing the database column type.
        """
        size = self.size or ""
        return "%s[%s]" % (self.base_field.db_type(connection), size)

    def cast_db_type(self, connection):
        size = self.size or ""
        return "%s[%s]" % (self.base_field.cast_db_type(connection), size)

    def db_parameters(self, connection):
        """
        Returns a dictionary of database parameters for the current connection.

        The returned dictionary includes all parameters from the parent class, with the addition of the 'collation' parameter, which is set to the database collation defined for this instance.

        :param connection: The database connection.
        :rtype: dict
        :return: A dictionary of database parameters.
        """
        db_params = super().db_parameters(connection)
        db_params["collation"] = self.db_collation
        return db_params

    def get_placeholder(self, value, compiler, connection):
        return "%s::{}".format(self.db_type(connection))

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, (list, tuple)):
            return [
                self.base_field.get_db_prep_value(i, connection, prepared=False)
                for i in value
            ]
        return value

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if path == "django.contrib.postgres.fields.array.ArrayField":
            path = "django.contrib.postgres.fields.ArrayField"
        kwargs.update(
            {
                "base_field": self.base_field.clone(),
                "size": self.size,
            }
        )
        return name, path, args, kwargs

    def to_python(self, value):
        """
        Converts a value to a Python native representation.

        This method takes an input value and, if it is a string, attempts to parse it as a JSON string.
        If the input value is a JSON string, it is expected to contain a list of values, each of which is
        then converted to its Python representation using the :meth:`to_python` method of the base field.
        The resulting list of converted values is then returned.

        If the input value is not a string, it is returned unchanged.
        """
        if isinstance(value, str):
            # Assume we're deserializing
            vals = json.loads(value)
            value = [self.base_field.to_python(val) for val in vals]
        return value

    def _from_db_value(self, value, expression, connection):
        """
        Converts a database value to a Python object, handling lists of values.

        This method takes a database value, an expression, and a connection as input.
        If the value is None, it returns None. Otherwise, it applies the from_db_value
        method of the base field to each item in the list, returning a new list with the converted values.

        :param value: The value to convert from the database.
        :param expression: The expression that was used to retrieve the value.
        :param connection: The database connection that was used to retrieve the value.
        :return: The converted value, or None if the input value is None.

        """
        if value is None:
            return value
        return [
            self.base_field.from_db_value(item, expression, connection)
            for item in value
        ]

    def value_to_string(self, obj):
        values = []
        vals = self.value_from_object(obj)
        base_field = self.base_field

        for val in vals:
            if val is None:
                values.append(None)
            else:
                obj = AttributeSetter(base_field.attname, val)
                values.append(base_field.value_to_string(obj))
        return json.dumps(values)

    def get_transform(self, name):
        transform = super().get_transform(name)
        if transform:
            return transform
        if "_" not in name:
            try:
                index = int(name)
            except ValueError:
                pass
            else:
                index += 1  # postgres uses 1-indexing
                return IndexTransformFactory(index, self.base_field)
        try:
            start, end = name.split("_")
            start = int(start) + 1
            end = int(end)  # don't add one here because postgres slices are weird
        except ValueError:
            pass
        else:
            return SliceTransformFactory(start, end)

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        for index, part in enumerate(value):
            try:
                self.base_field.validate(part, model_instance)
            except exceptions.ValidationError as error:
                raise prefix_validation_error(
                    error,
                    prefix=self.error_messages["item_invalid"],
                    code="item_invalid",
                    params={"nth": index + 1},
                )
        if isinstance(self.base_field, ArrayField):
            if len({len(i) for i in value}) > 1:
                raise exceptions.ValidationError(
                    self.error_messages["nested_array_mismatch"],
                    code="nested_array_mismatch",
                )

    def run_validators(self, value):
        """

        Runs validation on the provided value, including any nested parts.

        This method first calls the parent class's validation method, then iterates over each part of the value.
        Each part is validated using the base field's validation rules. If any part fails validation,
        a :class:`~django.core.exceptions.ValidationError` is raised with a message indicating which part of the value is invalid.

        """
        super().run_validators(value)
        for index, part in enumerate(value):
            try:
                self.base_field.run_validators(part)
            except exceptions.ValidationError as error:
                raise prefix_validation_error(
                    error,
                    prefix=self.error_messages["item_invalid"],
                    code="item_invalid",
                    params={"nth": index + 1},
                )

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": SimpleArrayField,
                "base_field": self.base_field.formfield(),
                "max_length": self.size,
                **kwargs,
            }
        )

    def slice_expression(self, expression, start, length):
        # If length is not provided, don't specify an end to slice to the end
        # of the array.
        end = None if length is None else start + length - 1
        return SliceTransform(start, end, expression)


class ArrayRHSMixin:
    def __init__(self, lhs, rhs):
        # Don't wrap arrays that contains only None values, psycopg doesn't
        # allow this.
        if isinstance(rhs, (tuple, list)) and any(self._rhs_not_none_values(rhs)):
            expressions = []
            for value in rhs:
                if not hasattr(value, "resolve_expression"):
                    field = lhs.output_field
                    value = Value(field.base_field.get_prep_value(value))
                expressions.append(value)
            rhs = Func(
                *expressions,
                function="ARRAY",
                template="%(function)s[%(expressions)s]",
            )
        super().__init__(lhs, rhs)

    def process_rhs(self, compiler, connection):
        rhs, rhs_params = super().process_rhs(compiler, connection)
        cast_type = self.lhs.output_field.cast_db_type(connection)
        return "%s::%s" % (rhs, cast_type), rhs_params

    def _rhs_not_none_values(self, rhs):
        """
        Generate a sequence of boolean values indicating whether each element in the given iterable or nested iterables is not None.

        Yields True for each non-None value encountered, recursively traversing any nested lists or tuples.

        Note: This function is intended for internal use and its name starts with an underscore to indicate this.
        """
        for x in rhs:
            if isinstance(x, (list, tuple)):
                yield from self._rhs_not_none_values(x)
            elif x is not None:
                yield True


@ArrayField.register_lookup
class ArrayContains(ArrayRHSMixin, lookups.DataContains):
    pass


@ArrayField.register_lookup
class ArrayContainedBy(ArrayRHSMixin, lookups.ContainedBy):
    pass


@ArrayField.register_lookup
class ArrayExact(ArrayRHSMixin, Exact):
    pass


@ArrayField.register_lookup
class ArrayOverlap(ArrayRHSMixin, lookups.Overlap):
    pass


@ArrayField.register_lookup
class ArrayLenTransform(Transform):
    lookup_name = "len"
    output_field = IntegerField()

    def as_sql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        # Distinguish NULL and empty arrays
        return (
            "CASE WHEN %(lhs)s IS NULL THEN NULL ELSE "
            "coalesce(array_length(%(lhs)s, 1), 0) END"
        ) % {"lhs": lhs}, params * 2


@ArrayField.register_lookup
class ArrayInLookup(In):
    def get_prep_lookup(self):
        values = super().get_prep_lookup()
        if hasattr(values, "resolve_expression"):
            return values
        # In.process_rhs() expects values to be hashable, so convert lists
        # to tuples.
        prepared_values = []
        for value in values:
            if hasattr(value, "resolve_expression"):
                prepared_values.append(value)
            else:
                prepared_values.append(tuple(value))
        return prepared_values


class IndexTransform(Transform):
    def __init__(self, index, base_field, *args, **kwargs):
        """
        Initializes an instance of the class.

        :param index: The index of the instance.
        :param base_field: The base field associated with the instance.
        :param args: Variable length argument list.
        :param kwargs: Arbitrary keyword arguments.

        This initializer sets up the basic attributes of the class, including the index and base field, and then calls the parent class's initializer to complete the setup. The index and base field are stored as instance attributes for later use. 
        """
        super().__init__(*args, **kwargs)
        self.index = index
        self.base_field = base_field

    def as_sql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        if not lhs.endswith("]"):
            lhs = "(%s)" % lhs
        return "%s[%%s]" % lhs, (*params, self.index)

    @property
    def output_field(self):
        return self.base_field


class IndexTransformFactory:
    def __init__(self, index, base_field):
        self.index = index
        self.base_field = base_field

    def __call__(self, *args, **kwargs):
        return IndexTransform(self.index, self.base_field, *args, **kwargs)


class SliceTransform(Transform):
    def __init__(self, start, end, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start = start
        self.end = end

    def as_sql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        # self.start is set to 1 if slice start is not provided.
        if self.end is None:
            return f"({lhs})[%s:]", (*params, self.start)
        else:
            return f"({lhs})[%s:%s]", (*params, self.start, self.end)


class SliceTransformFactory:
    def __init__(self, start, end):
        """
        Initializes a time interval with a start and end point.

        :param start: The starting point of the time interval.
        :param end: The ending point of the time interval.

        This initializer sets the boundaries of a time interval, allowing for 
        further operations and calculations to be performed on the defined range.
        """
        self.start = start
        self.end = end

    def __call__(self, *args, **kwargs):
        return SliceTransform(self.start, self.end, *args, **kwargs)
