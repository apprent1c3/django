from unittest import SkipTest

from django.core import validators
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models
from django.test import SimpleTestCase, TestCase

from .models import (
    BigIntegerModel,
    IntegerModel,
    PositiveBigIntegerModel,
    PositiveIntegerModel,
    PositiveSmallIntegerModel,
    SmallIntegerModel,
)


class IntegerFieldTests(TestCase):
    model = IntegerModel
    documented_range = (-2147483648, 2147483647)
    rel_db_type_class = models.IntegerField

    @property
    def backend_range(self):
        """
        Returns the range of values that can be stored in the 'value' field of the model.

        This property provides information about the valid range of integers that can be used
        in the 'value' field, based on the internal type of the field and the database connection.
        It is useful for validating or filtering input data to ensure it falls within the
        allowed range.

        The returned range is determined by the database backend and the type of the 'value'
        field, and may vary depending on the specific database configuration.

        :rtype: tuple
        :returns: A tuple containing the minimum and maximum values that can be stored in the 'value' field.
        """
        field = self.model._meta.get_field("value")
        internal_type = field.get_internal_type()
        return connection.ops.integer_field_range(internal_type)

    def test_documented_range(self):
        """
        Values within the documented safe range pass validation, and can be
        saved and retrieved without corruption.
        """
        min_value, max_value = self.documented_range

        instance = self.model(value=min_value)
        instance.full_clean()
        instance.save()
        qs = self.model.objects.filter(value__lte=min_value)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs[0].value, min_value)

        instance = self.model(value=max_value)
        instance.full_clean()
        instance.save()
        qs = self.model.objects.filter(value__gte=max_value)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs[0].value, max_value)

    def test_backend_range_save(self):
        """
        Backend specific ranges can be saved without corruption.
        """
        min_value, max_value = self.backend_range

        if min_value is not None:
            instance = self.model(value=min_value)
            instance.full_clean()
            instance.save()
            qs = self.model.objects.filter(value__lte=min_value)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs[0].value, min_value)

        if max_value is not None:
            instance = self.model(value=max_value)
            instance.full_clean()
            instance.save()
            qs = self.model.objects.filter(value__gte=max_value)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs[0].value, max_value)

    def test_backend_range_validation(self):
        """
        Backend specific ranges are enforced at the model validation level
        (#12030).
        """
        min_value, max_value = self.backend_range

        if min_value is not None:
            instance = self.model(value=min_value - 1)
            expected_message = validators.MinValueValidator.message % {
                "limit_value": min_value,
            }
            with self.assertRaisesMessage(ValidationError, expected_message):
                instance.full_clean()
            instance.value = min_value
            instance.full_clean()

        if max_value is not None:
            instance = self.model(value=max_value + 1)
            expected_message = validators.MaxValueValidator.message % {
                "limit_value": max_value,
            }
            with self.assertRaisesMessage(ValidationError, expected_message):
                instance.full_clean()
            instance.value = max_value
            instance.full_clean()

    def test_backend_range_min_value_lookups(self):
        min_value = self.backend_range[0]
        if min_value is None:
            raise SkipTest("Backend doesn't define an integer min value.")
        underflow_value = min_value - 1
        self.model.objects.create(value=min_value)
        # A refresh of obj is necessary because last_insert_id() is bugged
        # on MySQL and returns invalid values.
        obj = self.model.objects.get(value=min_value)
        with self.assertNumQueries(0), self.assertRaises(self.model.DoesNotExist):
            self.model.objects.get(value=underflow_value)
        with self.assertNumQueries(1):
            self.assertEqual(self.model.objects.get(value__gt=underflow_value), obj)
        with self.assertNumQueries(1):
            self.assertEqual(self.model.objects.get(value__gte=underflow_value), obj)
        with self.assertNumQueries(0), self.assertRaises(self.model.DoesNotExist):
            self.model.objects.get(value__lt=underflow_value)
        with self.assertNumQueries(0), self.assertRaises(self.model.DoesNotExist):
            self.model.objects.get(value__lte=underflow_value)

    def test_backend_range_max_value_lookups(self):
        max_value = self.backend_range[-1]
        if max_value is None:
            raise SkipTest("Backend doesn't define an integer max value.")
        overflow_value = max_value + 1
        obj = self.model.objects.create(value=max_value)
        with self.assertNumQueries(0), self.assertRaises(self.model.DoesNotExist):
            self.model.objects.get(value=overflow_value)
        with self.assertNumQueries(0), self.assertRaises(self.model.DoesNotExist):
            self.model.objects.get(value__gt=overflow_value)
        with self.assertNumQueries(0), self.assertRaises(self.model.DoesNotExist):
            self.model.objects.get(value__gte=overflow_value)
        with self.assertNumQueries(1):
            self.assertEqual(self.model.objects.get(value__lt=overflow_value), obj)
        with self.assertNumQueries(1):
            self.assertEqual(self.model.objects.get(value__lte=overflow_value), obj)

    def test_redundant_backend_range_validators(self):
        """
        If there are stricter validators than the ones from the database
        backend then the backend validators aren't added.
        """
        min_backend_value, max_backend_value = self.backend_range

        for callable_limit in (True, False):
            with self.subTest(callable_limit=callable_limit):
                if min_backend_value is not None:
                    min_custom_value = min_backend_value + 1
                    limit_value = (
                        (lambda: min_custom_value)
                        if callable_limit
                        else min_custom_value
                    )
                    ranged_value_field = self.model._meta.get_field("value").__class__(
                        validators=[validators.MinValueValidator(limit_value)]
                    )
                    field_range_message = validators.MinValueValidator.message % {
                        "limit_value": min_custom_value,
                    }
                    with self.assertRaisesMessage(
                        ValidationError, "[%r]" % field_range_message
                    ):
                        ranged_value_field.run_validators(min_backend_value - 1)

                if max_backend_value is not None:
                    max_custom_value = max_backend_value - 1
                    limit_value = (
                        (lambda: max_custom_value)
                        if callable_limit
                        else max_custom_value
                    )
                    ranged_value_field = self.model._meta.get_field("value").__class__(
                        validators=[validators.MaxValueValidator(limit_value)]
                    )
                    field_range_message = validators.MaxValueValidator.message % {
                        "limit_value": max_custom_value,
                    }
                    with self.assertRaisesMessage(
                        ValidationError, "[%r]" % field_range_message
                    ):
                        ranged_value_field.run_validators(max_backend_value + 1)

    def test_types(self):
        """
        teste_types 
             Validates that the 'value' attribute of a model instance remains an integer 
             throughout its lifecycle, including after being saved to the database and 
             subsequently retrieved.
        """
        instance = self.model(value=1)
        self.assertIsInstance(instance.value, int)
        instance.save()
        self.assertIsInstance(instance.value, int)
        instance = self.model.objects.get()
        self.assertIsInstance(instance.value, int)

    def test_coercing(self):
        self.model.objects.create(value="10")
        instance = self.model.objects.get(value="10")
        self.assertEqual(instance.value, 10)

    def test_invalid_value(self):
        """
        Tests the behavior of the model when attempting to create an instance with an invalid value.

        This test checks that the model correctly raises exceptions when passed non-numeric values, including various types such as tuples, lists, dictionaries, sets, objects, complex numbers, and non-numeric strings and byte-strings.

        The expected exceptions and their corresponding error messages are verified, ensuring that the model provides informative feedback when encountering invalid input.

        Validates that the model adheres to the expected data type constraints and provides consistent error handling for different types of invalid input.
        """
        tests = [
            (TypeError, ()),
            (TypeError, []),
            (TypeError, {}),
            (TypeError, set()),
            (TypeError, object()),
            (TypeError, complex()),
            (ValueError, "non-numeric string"),
            (ValueError, b"non-numeric byte-string"),
        ]
        for exception, value in tests:
            with self.subTest(value):
                msg = "Field 'value' expected a number but got %r." % (value,)
                with self.assertRaisesMessage(exception, msg):
                    self.model.objects.create(value=value)

    def test_rel_db_type(self):
        field = self.model._meta.get_field("value")
        rel_db_type = field.rel_db_type(connection)
        self.assertEqual(rel_db_type, self.rel_db_type_class().db_type(connection))


class SmallIntegerFieldTests(IntegerFieldTests):
    model = SmallIntegerModel
    documented_range = (-32768, 32767)
    rel_db_type_class = models.SmallIntegerField


class BigIntegerFieldTests(IntegerFieldTests):
    model = BigIntegerModel
    documented_range = (-9223372036854775808, 9223372036854775807)
    rel_db_type_class = models.BigIntegerField


class PositiveSmallIntegerFieldTests(IntegerFieldTests):
    model = PositiveSmallIntegerModel
    documented_range = (0, 32767)
    rel_db_type_class = (
        models.PositiveSmallIntegerField
        if connection.features.related_fields_match_type
        else models.SmallIntegerField
    )


class PositiveIntegerFieldTests(IntegerFieldTests):
    model = PositiveIntegerModel
    documented_range = (0, 2147483647)
    rel_db_type_class = (
        models.PositiveIntegerField
        if connection.features.related_fields_match_type
        else models.IntegerField
    )

    def test_negative_values(self):
        """
        Tests that attempting to save a :class:`PositiveIntegerModel` instance with a negative value raises an :class:`IntegrityError`.

        This test case verifies the model's validation logic by trying to save an instance with a value less than 0, ensuring that the database constraints are enforced correctly.

        :raises: :class:`IntegrityError` when trying to save the model instance with a negative value
        """
        p = PositiveIntegerModel.objects.create(value=0)
        p.value = models.F("value") - 1
        with self.assertRaises(IntegrityError):
            p.save()


class PositiveBigIntegerFieldTests(IntegerFieldTests):
    model = PositiveBigIntegerModel
    documented_range = (0, 9223372036854775807)
    rel_db_type_class = (
        models.PositiveBigIntegerField
        if connection.features.related_fields_match_type
        else models.BigIntegerField
    )


class ValidationTests(SimpleTestCase):
    class Choices(models.IntegerChoices):
        A = 1

    def test_integerfield_cleans_valid_string(self):
        f = models.IntegerField()
        self.assertEqual(f.clean("2", None), 2)

    def test_integerfield_raises_error_on_invalid_intput(self):
        """
        ..: 
            Tests that the IntegerField raises a ValidationError when given an invalid input.

            This test case ensures that attempting to clean a non-integer value using the IntegerField
            results in the expected error being raised, thus maintaining data integrity and preventing 
            potential issues that may arise from incorrect data types.
        """
        f = models.IntegerField()
        with self.assertRaises(ValidationError):
            f.clean("a", None)

    def test_choices_validation_supports_named_groups(self):
        f = models.IntegerField(choices=(("group", ((10, "A"), (20, "B"))), (30, "C")))
        self.assertEqual(10, f.clean(10, None))

    def test_choices_validation_supports_named_groups_dicts(self):
        f = models.IntegerField(choices={"group": ((10, "A"), (20, "B")), 30: "C"})
        self.assertEqual(10, f.clean(10, None))

    def test_choices_validation_supports_named_groups_nested_dicts(self):
        """

        Tests that validation of choices for a model field supports named groups of choices 
        defined as nested dictionaries.

        Verifies that the clean method correctly handles and validates choices when 
        they are organized into a nested structure, ensuring that the field can properly 
        accept and process values from the named groups.

        """
        f = models.IntegerField(choices={"group": {10: "A", 20: "B"}, 30: "C"})
        self.assertEqual(10, f.clean(10, None))

    def test_nullable_integerfield_raises_error_with_blank_false(self):
        """

        Tests that an IntegerField with null=True and blank=False raises a ValidationError when a blank value is passed.

        The purpose of this test is to ensure that the field's validation behaves correctly when 
        the field is allowed to be null (i.e., have no value in the database), but not blank 
        (i.e., have an empty value in a form).

        The test verifies that a ValidationError is raised when the clean method is called with 
        a value of None, even though null is True, because blank is False.

        """
        f = models.IntegerField(null=True, blank=False)
        with self.assertRaises(ValidationError):
            f.clean(None, None)

    def test_nullable_integerfield_cleans_none_on_null_and_blank_true(self):
        """
        Tests that an IntegerField with null and blank set to True correctly cleans None values.

        The test verifies that when the IntegerField is given a value of None, the clean method returns None, 
        confirming that the field can accept null values and will not raise any errors when doing so. 

        This ensures the field behaves as expected when null and blank are True, allowing for optional integer values. 
        """
        f = models.IntegerField(null=True, blank=True)
        self.assertIsNone(f.clean(None, None))

    def test_integerfield_raises_error_on_empty_input(self):
        """
        Tests that the IntegerField raises a ValidationError when given empty input.

        This test checks two scenarios: when the input is None and when the input is an empty string.
        It ensures that the IntegerField enforces its null=False constraint and rejects empty values.

        Args:
            None

        Returns:
            None

        Raises:
            ValidationError: When the input is empty (None or empty string).
        """
        f = models.IntegerField(null=False)
        with self.assertRaises(ValidationError):
            f.clean(None, None)
        with self.assertRaises(ValidationError):
            f.clean("", None)

    def test_integerfield_validates_zero_against_choices(self):
        """
        Tests that IntegerField validation correctly raises a ValidationError when the input value is zero and not among the provided choices. This ensures that the field properly enforces its constraints and prevents invalid data from being accepted.
        """
        f = models.IntegerField(choices=((1, 1),))
        with self.assertRaises(ValidationError):
            f.clean("0", None)

    def test_enum_choices_cleans_valid_string(self):
        """
        Tests that an IntegerField with choices correctly cleans a valid string input.

         Verifies that when a valid string representing an integer is passed to the clean method,
         it is successfully converted to an integer and returned, ensuring the model field is populated correctly.
        """
        f = models.IntegerField(choices=self.Choices)
        self.assertEqual(f.clean("1", None), 1)

    def test_enum_choices_invalid_input(self):
        f = models.IntegerField(choices=self.Choices)
        with self.assertRaises(ValidationError):
            f.clean("A", None)
        with self.assertRaises(ValidationError):
            f.clean("3", None)

    def test_callable_choices(self):
        """


        Tests that callable choices in IntegerField are properly validated.

        This test case verifies that the clean method of an IntegerField with callable
        choices correctly returns valid values and raises a ValidationError for invalid
        values. The callable choices function returns a dictionary where keys are integers
        and values are string representations of these integers. The test checks that
        integer values within the range defined by the choices function are accepted
        and that non-integer and out-of-range values are rejected.


        """
        def get_choices():
            return {i: str(i) for i in range(3)}

        f = models.IntegerField(choices=get_choices)

        for i in get_choices():
            with self.subTest(i=i):
                self.assertEqual(i, f.clean(i, None))

        with self.assertRaises(ValidationError):
            f.clean("A", None)
        with self.assertRaises(ValidationError):
            f.clean("3", None)
