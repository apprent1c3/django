from unittest import mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models
from django.db.models import F
from django.db.models.constraints import BaseConstraint, UniqueConstraint
from django.db.models.functions import Abs, Lower
from django.db.transaction import atomic
from django.test import SimpleTestCase, TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.test.utils import ignore_warnings
from django.utils.deprecation import RemovedInDjango60Warning

from .models import (
    ChildModel,
    ChildUniqueConstraintProduct,
    JSONFieldModel,
    Product,
    UniqueConstraintConditionProduct,
    UniqueConstraintDeferrable,
    UniqueConstraintInclude,
    UniqueConstraintProduct,
)


def get_constraints(table):
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table)


class BaseConstraintTests(SimpleTestCase):
    def test_constraint_sql(self):
        c = BaseConstraint(name="name")
        msg = "This method must be implemented by a subclass."
        with self.assertRaisesMessage(NotImplementedError, msg):
            c.constraint_sql(None, None)

    def test_contains_expressions(self):
        c = BaseConstraint(name="name")
        self.assertIs(c.contains_expressions, False)

    def test_create_sql(self):
        c = BaseConstraint(name="name")
        msg = "This method must be implemented by a subclass."
        with self.assertRaisesMessage(NotImplementedError, msg):
            c.create_sql(None, None)

    def test_remove_sql(self):
        c = BaseConstraint(name="name")
        msg = "This method must be implemented by a subclass."
        with self.assertRaisesMessage(NotImplementedError, msg):
            c.remove_sql(None, None)

    def test_validate(self):
        c = BaseConstraint(name="name")
        msg = "This method must be implemented by a subclass."
        with self.assertRaisesMessage(NotImplementedError, msg):
            c.validate(None, None)

    def test_default_violation_error_message(self):
        c = BaseConstraint(name="name")
        self.assertEqual(
            c.get_violation_error_message(), "Constraint “name” is violated."
        )

    def test_custom_violation_error_message(self):
        c = BaseConstraint(
            name="base_name", violation_error_message="custom %(name)s message"
        )
        self.assertEqual(c.get_violation_error_message(), "custom base_name message")

    def test_custom_violation_error_message_clone(self):
        constraint = BaseConstraint(
            name="base_name",
            violation_error_message="custom %(name)s message",
        ).clone()
        self.assertEqual(
            constraint.get_violation_error_message(),
            "custom base_name message",
        )

    def test_custom_violation_code_message(self):
        c = BaseConstraint(name="base_name", violation_error_code="custom_code")
        self.assertEqual(c.violation_error_code, "custom_code")

    def test_deconstruction(self):
        """
        Tests the deconstruction of a BaseConstraint instance, verifying that the path, arguments, and keyword arguments are correctly decomposed.
        """
        constraint = BaseConstraint(
            name="base_name",
            violation_error_message="custom %(name)s message",
            violation_error_code="custom_code",
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.BaseConstraint")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "name": "base_name",
                "violation_error_message": "custom %(name)s message",
                "violation_error_code": "custom_code",
            },
        )

    def test_deprecation(self):
        msg = "Passing positional arguments to BaseConstraint is deprecated."
        with self.assertRaisesMessage(RemovedInDjango60Warning, msg):
            BaseConstraint("name", "violation error message")

    def test_name_required(self):
        msg = (
            "BaseConstraint.__init__() missing 1 required keyword-only argument: 'name'"
        )
        with self.assertRaisesMessage(TypeError, msg):
            BaseConstraint()

    @ignore_warnings(category=RemovedInDjango60Warning)
    def test_positional_arguments(self):
        c = BaseConstraint("name", "custom %(name)s message")
        self.assertEqual(c.get_violation_error_message(), "custom name message")


class CheckConstraintTests(TestCase):
    def test_eq(self):
        """
        Tests the equality of :class:`~django.db.models.CheckConstraint` instances based on their condition, name, and optional error message and code.
        """
        check1 = models.Q(price__gt=models.F("discounted_price"))
        check2 = models.Q(price__lt=models.F("discounted_price"))
        self.assertEqual(
            models.CheckConstraint(condition=check1, name="price"),
            models.CheckConstraint(condition=check1, name="price"),
        )
        self.assertEqual(
            models.CheckConstraint(condition=check1, name="price"), mock.ANY
        )
        self.assertNotEqual(
            models.CheckConstraint(condition=check1, name="price"),
            models.CheckConstraint(condition=check1, name="price2"),
        )
        self.assertNotEqual(
            models.CheckConstraint(condition=check1, name="price"),
            models.CheckConstraint(condition=check2, name="price"),
        )
        self.assertNotEqual(models.CheckConstraint(condition=check1, name="price"), 1)
        self.assertNotEqual(
            models.CheckConstraint(condition=check1, name="price"),
            models.CheckConstraint(
                condition=check1, name="price", violation_error_message="custom error"
            ),
        )
        self.assertNotEqual(
            models.CheckConstraint(
                condition=check1, name="price", violation_error_message="custom error"
            ),
            models.CheckConstraint(
                condition=check1,
                name="price",
                violation_error_message="other custom error",
            ),
        )
        self.assertEqual(
            models.CheckConstraint(
                condition=check1, name="price", violation_error_message="custom error"
            ),
            models.CheckConstraint(
                condition=check1, name="price", violation_error_message="custom error"
            ),
        )
        self.assertNotEqual(
            models.CheckConstraint(condition=check1, name="price"),
            models.CheckConstraint(
                condition=check1, name="price", violation_error_code="custom_code"
            ),
        )
        self.assertEqual(
            models.CheckConstraint(
                condition=check1, name="price", violation_error_code="custom_code"
            ),
            models.CheckConstraint(
                condition=check1, name="price", violation_error_code="custom_code"
            ),
        )

    def test_repr(self):
        constraint = models.CheckConstraint(
            condition=models.Q(price__gt=models.F("discounted_price")),
            name="price_gt_discounted_price",
        )
        self.assertEqual(
            repr(constraint),
            "<CheckConstraint: condition=(AND: ('price__gt', F(discounted_price))) "
            "name='price_gt_discounted_price'>",
        )

    def test_repr_with_violation_error_message(self):
        constraint = models.CheckConstraint(
            condition=models.Q(price__lt=1),
            name="price_lt_one",
            violation_error_message="More than 1",
        )
        self.assertEqual(
            repr(constraint),
            "<CheckConstraint: condition=(AND: ('price__lt', 1)) name='price_lt_one' "
            "violation_error_message='More than 1'>",
        )

    def test_repr_with_violation_error_code(self):
        constraint = models.CheckConstraint(
            condition=models.Q(price__lt=1),
            name="price_lt_one",
            violation_error_code="more_than_one",
        )
        self.assertEqual(
            repr(constraint),
            "<CheckConstraint: condition=(AND: ('price__lt', 1)) name='price_lt_one' "
            "violation_error_code='more_than_one'>",
        )

    def test_invalid_check_types(self):
        msg = "CheckConstraint.condition must be a Q instance or boolean expression."
        with self.assertRaisesMessage(TypeError, msg):
            models.CheckConstraint(condition=models.F("discounted_price"), name="check")

    def test_deconstruction(self):
        """
        Tests the deconstruction of a CheckConstraint instance, verifying that it correctly returns its path, arguments, and keyword arguments.
        """
        check = models.Q(price__gt=models.F("discounted_price"))
        name = "price_gt_discounted_price"
        constraint = models.CheckConstraint(condition=check, name=name)
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.CheckConstraint")
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {"condition": check, "name": name})

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_database_constraint(self):
        Product.objects.create(price=10, discounted_price=5)
        with self.assertRaises(IntegrityError):
            Product.objects.create(price=10, discounted_price=20)

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_database_constraint_unicode(self):
        Product.objects.create(price=10, discounted_price=5, unit="μg/mL")
        with self.assertRaises(IntegrityError):
            Product.objects.create(price=10, discounted_price=7, unit="l")

    @skipUnlessDBFeature(
        "supports_table_check_constraints", "can_introspect_check_constraints"
    )
    def test_name(self):
        constraints = get_constraints(Product._meta.db_table)
        for expected_name in (
            "price_gt_discounted_price",
            "constraints_product_price_gt_0",
        ):
            with self.subTest(expected_name):
                self.assertIn(expected_name, constraints)

    @skipUnlessDBFeature(
        "supports_table_check_constraints", "can_introspect_check_constraints"
    )
    def test_abstract_name(self):
        constraints = get_constraints(ChildModel._meta.db_table)
        self.assertIn("constraints_childmodel_adult", constraints)

    def test_validate(self):
        """

        Tests the validation of the price constraint, ensuring that the price is greater than the discounted price.

        """
        check = models.Q(price__gt=models.F("discounted_price"))
        constraint = models.CheckConstraint(condition=check, name="price")
        # Invalid product.
        invalid_product = Product(price=10, discounted_price=42)
        with self.assertRaises(ValidationError):
            constraint.validate(Product, invalid_product)
        with self.assertRaises(ValidationError):
            constraint.validate(Product, invalid_product, exclude={"unit"})
        # Fields used by the check constraint are excluded.
        constraint.validate(Product, invalid_product, exclude={"price"})
        constraint.validate(Product, invalid_product, exclude={"discounted_price"})
        constraint.validate(
            Product,
            invalid_product,
            exclude={"discounted_price", "price"},
        )
        # Valid product.
        constraint.validate(Product, Product(price=10, discounted_price=5))

    def test_validate_custom_error(self):
        """
        Tests the validation of a custom error for a check constraint, specifically when a product's price is less than its discounted price, ensuring the correct error message and code are raised.
        """
        check = models.Q(price__gt=models.F("discounted_price"))
        constraint = models.CheckConstraint(
            condition=check,
            name="price",
            violation_error_message="discount is fake",
            violation_error_code="fake_discount",
        )
        # Invalid product.
        invalid_product = Product(price=10, discounted_price=42)
        msg = "discount is fake"
        with self.assertRaisesMessage(ValidationError, msg) as cm:
            constraint.validate(Product, invalid_product)
        self.assertEqual(cm.exception.code, "fake_discount")

    def test_validate_boolean_expressions(self):
        """
        Tests the validation of a boolean expression constraint on the 'price' field of a Product model instance.

         The constraint checks if the price is not equal to 500. The test ensures that validation fails when the price is 500
         and succeeds when the price is greater or less than 500, as expected.
        """
        constraint = models.CheckConstraint(
            condition=models.expressions.ExpressionWrapper(
                models.Q(price__gt=500) | models.Q(price__lt=500),
                output_field=models.BooleanField(),
            ),
            name="price_neq_500_wrap",
        )
        msg = f"Constraint “{constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(Product, Product(price=500, discounted_price=5))
        constraint.validate(Product, Product(price=501, discounted_price=5))
        constraint.validate(Product, Product(price=499, discounted_price=5))

    def test_validate_rawsql_expressions_noop(self):
        constraint = models.CheckConstraint(
            condition=models.expressions.RawSQL(
                "price < %s OR price > %s",
                (500, 500),
                output_field=models.BooleanField(),
            ),
            name="price_neq_500_raw",
        )
        # RawSQL can not be checked and is always considered valid.
        constraint.validate(Product, Product(price=500, discounted_price=5))
        constraint.validate(Product, Product(price=501, discounted_price=5))
        constraint.validate(Product, Product(price=499, discounted_price=5))

    @skipUnlessDBFeature("supports_comparing_boolean_expr")
    def test_validate_nullable_field_with_none(self):
        # Nullable fields should be considered valid on None values.
        constraint = models.CheckConstraint(
            condition=models.Q(price__gte=0),
            name="positive_price",
        )
        constraint.validate(Product, Product())

    @skipIfDBFeature("supports_comparing_boolean_expr")
    def test_validate_nullable_field_with_isnull(self):
        constraint = models.CheckConstraint(
            condition=models.Q(price__gte=0) | models.Q(price__isnull=True),
            name="positive_price",
        )
        constraint.validate(Product, Product())

    @skipUnlessDBFeature("supports_json_field")
    def test_validate_nullable_jsonfield(self):
        """
        Tests validation of nullable JSONField using check constraints.

        Verifies that check constraints correctly validate null and non-null JSONField
        values, raising a ValidationError when the constraint is violated.
        """
        is_null_constraint = models.CheckConstraint(
            condition=models.Q(data__isnull=True),
            name="nullable_data",
        )
        is_not_null_constraint = models.CheckConstraint(
            condition=models.Q(data__isnull=False),
            name="nullable_data",
        )
        is_null_constraint.validate(JSONFieldModel, JSONFieldModel(data=None))
        msg = f"Constraint “{is_null_constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            is_null_constraint.validate(JSONFieldModel, JSONFieldModel(data={}))
        msg = f"Constraint “{is_not_null_constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            is_not_null_constraint.validate(JSONFieldModel, JSONFieldModel(data=None))
        is_not_null_constraint.validate(JSONFieldModel, JSONFieldModel(data={}))

    def test_validate_pk_field(self):
        """
        Tests validation of a model's primary key field against a CheckConstraint.

         Verifies that the constraint correctly raises a ValidationError when the primary key field's value matches a forbidden value, 
         and that it can be bypassed by excluding the primary key field from validation.
        """
        constraint_with_pk = models.CheckConstraint(
            condition=~models.Q(pk=models.F("age")),
            name="pk_not_age_check",
        )
        constraint_with_pk.validate(ChildModel, ChildModel(pk=1, age=2))
        msg = f"Constraint “{constraint_with_pk.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint_with_pk.validate(ChildModel, ChildModel(pk=1, age=1))
        with self.assertRaisesMessage(ValidationError, msg):
            constraint_with_pk.validate(ChildModel, ChildModel(id=1, age=1))
        constraint_with_pk.validate(ChildModel, ChildModel(pk=1, age=1), exclude={"pk"})

    @skipUnlessDBFeature("supports_json_field")
    def test_validate_jsonfield_exact(self):
        """
        Tests the validation of a JSONField with an exact constraint.

        Validates that the JSONField value matches the specified condition and raises a ValidationError if it does not.

        The test checks that a JSONField with a version 'stable' passes validation and a JSONField with a version other than 'stable' raises a ValidationError with the expected error message.
        """
        data = {"release": "5.0.2", "version": "stable"}
        json_exact_constraint = models.CheckConstraint(
            condition=models.Q(data__version="stable"),
            name="only_stable_version",
        )
        json_exact_constraint.validate(JSONFieldModel, JSONFieldModel(data=data))

        data = {"release": "5.0.2", "version": "not stable"}
        msg = f"Constraint “{json_exact_constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            json_exact_constraint.validate(JSONFieldModel, JSONFieldModel(data=data))

    def test_check_deprecation(self):
        """
        Tests that a deprecation warning is raised when using the 'check' attribute in CheckConstraint, instead of the 'condition' attribute.
        """
        msg = "CheckConstraint.check is deprecated in favor of `.condition`."
        condition = models.Q(foo="bar")
        with self.assertWarnsRegex(RemovedInDjango60Warning, msg):
            constraint = models.CheckConstraint(name="constraint", check=condition)
        with self.assertWarnsRegex(RemovedInDjango60Warning, msg):
            self.assertIs(constraint.check, condition)
        other_condition = models.Q(something="else")
        with self.assertWarnsRegex(RemovedInDjango60Warning, msg):
            constraint.check = other_condition
        with self.assertWarnsRegex(RemovedInDjango60Warning, msg):
            self.assertIs(constraint.check, other_condition)


class UniqueConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.p1 = UniqueConstraintProduct.objects.create(name="p1", color="red")
        cls.p2 = UniqueConstraintProduct.objects.create(name="p2")

    def test_eq(self):
        """
        Tests the equality of UniqueConstraint instances based on their fields, name, and error messages or codes.
        """
        self.assertEqual(
            models.UniqueConstraint(fields=["foo", "bar"], name="unique"),
            models.UniqueConstraint(fields=["foo", "bar"], name="unique"),
        )
        self.assertEqual(
            models.UniqueConstraint(fields=["foo", "bar"], name="unique"),
            mock.ANY,
        )
        self.assertNotEqual(
            models.UniqueConstraint(fields=["foo", "bar"], name="unique"),
            models.UniqueConstraint(fields=["foo", "bar"], name="unique2"),
        )
        self.assertNotEqual(
            models.UniqueConstraint(fields=["foo", "bar"], name="unique"),
            models.UniqueConstraint(fields=["foo", "baz"], name="unique"),
        )
        self.assertNotEqual(
            models.UniqueConstraint(fields=["foo", "bar"], name="unique"), 1
        )
        self.assertNotEqual(
            models.UniqueConstraint(fields=["foo", "bar"], name="unique"),
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_message="custom error",
            ),
        )
        self.assertNotEqual(
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_message="custom error",
            ),
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_message="other custom error",
            ),
        )
        self.assertEqual(
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_message="custom error",
            ),
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_message="custom error",
            ),
        )
        self.assertNotEqual(
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_code="custom_error",
            ),
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_code="other_custom_error",
            ),
        )
        self.assertEqual(
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_code="custom_error",
            ),
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                violation_error_code="custom_error",
            ),
        )

    def test_eq_with_condition(self):
        self.assertEqual(
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                condition=models.Q(foo=models.F("bar")),
            ),
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                condition=models.Q(foo=models.F("bar")),
            ),
        )
        self.assertNotEqual(
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                condition=models.Q(foo=models.F("bar")),
            ),
            models.UniqueConstraint(
                fields=["foo", "bar"],
                name="unique",
                condition=models.Q(foo=models.F("baz")),
            ),
        )

    def test_eq_with_deferrable(self):
        constraint_1 = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="unique",
            deferrable=models.Deferrable.DEFERRED,
        )
        constraint_2 = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="unique",
            deferrable=models.Deferrable.IMMEDIATE,
        )
        self.assertEqual(constraint_1, constraint_1)
        self.assertNotEqual(constraint_1, constraint_2)

    def test_eq_with_include(self):
        constraint_1 = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="include",
            include=["baz_1"],
        )
        constraint_2 = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="include",
            include=["baz_2"],
        )
        self.assertEqual(constraint_1, constraint_1)
        self.assertNotEqual(constraint_1, constraint_2)

    def test_eq_with_opclasses(self):
        constraint_1 = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="opclasses",
            opclasses=["text_pattern_ops", "varchar_pattern_ops"],
        )
        constraint_2 = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="opclasses",
            opclasses=["varchar_pattern_ops", "text_pattern_ops"],
        )
        self.assertEqual(constraint_1, constraint_1)
        self.assertNotEqual(constraint_1, constraint_2)

    def test_eq_with_expressions(self):
        """
        Tests equality of UniqueConstraint instances with expressions.

        Verifies that equality is determined by the constraint's name and column definitions,
        regardless of whether the columns are specified as model fields or functional expressions.
        """
        constraint = models.UniqueConstraint(
            Lower("title"),
            F("author"),
            name="book_func_uq",
        )
        same_constraint = models.UniqueConstraint(
            Lower("title"),
            "author",
            name="book_func_uq",
        )
        another_constraint = models.UniqueConstraint(
            Lower("title"),
            name="book_func_uq",
        )
        self.assertEqual(constraint, same_constraint)
        self.assertEqual(constraint, mock.ANY)
        self.assertNotEqual(constraint, another_constraint)

    def test_eq_with_nulls_distinct(self):
        """
        Tests the equality of UniqueConstraint objects with nulls_distinct parameter
        """
        constraint_1 = models.UniqueConstraint(
            Lower("title"),
            nulls_distinct=False,
            name="book_func_nulls_distinct_uq",
        )
        constraint_2 = models.UniqueConstraint(
            Lower("title"),
            nulls_distinct=True,
            name="book_func_nulls_distinct_uq",
        )
        constraint_3 = models.UniqueConstraint(
            Lower("title"),
            name="book_func_nulls_distinct_uq",
        )
        self.assertEqual(constraint_1, constraint_1)
        self.assertEqual(constraint_1, mock.ANY)
        self.assertNotEqual(constraint_1, constraint_2)
        self.assertNotEqual(constraint_1, constraint_3)
        self.assertNotEqual(constraint_2, constraint_3)

    def test_repr(self):
        fields = ["foo", "bar"]
        name = "unique_fields"
        constraint = models.UniqueConstraint(fields=fields, name=name)
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: fields=('foo', 'bar') name='unique_fields'>",
        )

    def test_repr_with_condition(self):
        constraint = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="unique_fields",
            condition=models.Q(foo=models.F("bar")),
        )
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: fields=('foo', 'bar') name='unique_fields' "
            "condition=(AND: ('foo', F(bar)))>",
        )

    def test_repr_with_deferrable(self):
        constraint = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="unique_fields",
            deferrable=models.Deferrable.IMMEDIATE,
        )
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: fields=('foo', 'bar') name='unique_fields' "
            "deferrable=Deferrable.IMMEDIATE>",
        )

    def test_repr_with_include(self):
        constraint = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="include_fields",
            include=["baz_1", "baz_2"],
        )
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: fields=('foo', 'bar') name='include_fields' "
            "include=('baz_1', 'baz_2')>",
        )

    def test_repr_with_opclasses(self):
        constraint = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="opclasses_fields",
            opclasses=["text_pattern_ops", "varchar_pattern_ops"],
        )
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: fields=('foo', 'bar') name='opclasses_fields' "
            "opclasses=['text_pattern_ops', 'varchar_pattern_ops']>",
        )

    def test_repr_with_nulls_distinct(self):
        constraint = models.UniqueConstraint(
            fields=["foo", "bar"],
            name="nulls_distinct_fields",
            nulls_distinct=False,
        )
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: fields=('foo', 'bar') name='nulls_distinct_fields' "
            "nulls_distinct=False>",
        )

    def test_repr_with_expressions(self):
        constraint = models.UniqueConstraint(
            Lower("title"),
            F("author"),
            name="book_func_uq",
        )
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: expressions=(Lower(F(title)), F(author)) "
            "name='book_func_uq'>",
        )

    def test_repr_with_violation_error_message(self):
        constraint = models.UniqueConstraint(
            models.F("baz__lower"),
            name="unique_lower_baz",
            violation_error_message="BAZ",
        )
        self.assertEqual(
            repr(constraint),
            (
                "<UniqueConstraint: expressions=(F(baz__lower),) "
                "name='unique_lower_baz' violation_error_message='BAZ'>"
            ),
        )

    def test_repr_with_violation_error_code(self):
        constraint = models.UniqueConstraint(
            models.F("baz__lower"),
            name="unique_lower_baz",
            violation_error_code="baz",
        )
        self.assertEqual(
            repr(constraint),
            (
                "<UniqueConstraint: expressions=(F(baz__lower),) "
                "name='unique_lower_baz' violation_error_code='baz'>"
            ),
        )

    def test_deconstruction(self):
        """
        Tests the deconstruction of a UniqueConstraint instance to ensure it produces the correct path, arguments, and keyword arguments.
        """
        fields = ["foo", "bar"]
        name = "unique_fields"
        constraint = models.UniqueConstraint(fields=fields, name=name)
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {"fields": tuple(fields), "name": name})

    def test_deconstruction_with_condition(self):
        """
        Tests the deconstruction of a UniqueConstraint with a condition.

        Verifies that a UniqueConstraint instance can be successfully deconstructed into its constituent parts, including
        fields, name, and condition, for storage or re-creation purposes.
        """
        fields = ["foo", "bar"]
        name = "unique_fields"
        condition = models.Q(foo=models.F("bar"))
        constraint = models.UniqueConstraint(
            fields=fields, name=name, condition=condition
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs, {"fields": tuple(fields), "name": name, "condition": condition}
        )

    def test_deconstruction_with_deferrable(self):
        """
        Tests the deconstruction of a UniqueConstraint with deferrable attribute, 
        ensuring that the constraint can be serialized correctly into its constituent parts.
        """
        fields = ["foo"]
        name = "unique_fields"
        constraint = models.UniqueConstraint(
            fields=fields,
            name=name,
            deferrable=models.Deferrable.DEFERRED,
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": tuple(fields),
                "name": name,
                "deferrable": models.Deferrable.DEFERRED,
            },
        )

    def test_deconstruction_with_include(self):
        """
        Checks the correct deconstruction of a UniqueConstraint into its constituent parts.
        """
        fields = ["foo", "bar"]
        name = "unique_fields"
        include = ["baz_1", "baz_2"]
        constraint = models.UniqueConstraint(fields=fields, name=name, include=include)
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": tuple(fields),
                "name": name,
                "include": tuple(include),
            },
        )

    def test_deconstruction_with_opclasses(self):
        """
        Tests deconstruction of a UniqueConstraint instance with operation classes.

        Verifies that the deconstruct method correctly returns the path, arguments, and keyword arguments to reconstruct the UniqueConstraint instance.
        """
        fields = ["foo", "bar"]
        name = "unique_fields"
        opclasses = ["varchar_pattern_ops", "text_pattern_ops"]
        constraint = models.UniqueConstraint(
            fields=fields, name=name, opclasses=opclasses
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": tuple(fields),
                "name": name,
                "opclasses": opclasses,
            },
        )

    def test_deconstruction_with_nulls_distinct(self):
        """
        Tests that UniqueConstraint deconstruction works correctly when nulls_distinct is True.
        """
        fields = ["foo", "bar"]
        name = "unique_fields"
        constraint = models.UniqueConstraint(
            fields=fields, name=name, nulls_distinct=True
        )
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": tuple(fields),
                "name": name,
                "nulls_distinct": True,
            },
        )

    def test_deconstruction_with_expressions(self):
        """
        Tests the deconstruction of a UniqueConstraint instance with an expression.\"\"\"

        \"\"\"Verifies that the path, args, and kwargs of the deconstructed constraint 
        are correctly identified as 'django.db.models.UniqueConstraint', 
        the expression 'Lower(title)', and the name 'unique_fields' respectively.
        """
        name = "unique_fields"
        constraint = models.UniqueConstraint(Lower("title"), name=name)
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, (Lower("title"),))
        self.assertEqual(kwargs, {"name": name})

    def test_database_constraint(self):
        with self.assertRaises(IntegrityError):
            UniqueConstraintProduct.objects.create(
                name=self.p1.name, color=self.p1.color
            )

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_database_constraint_with_condition(self):
        UniqueConstraintConditionProduct.objects.create(name="p1")
        UniqueConstraintConditionProduct.objects.create(name="p2")
        with self.assertRaises(IntegrityError):
            UniqueConstraintConditionProduct.objects.create(name="p1")

    def test_model_validation(self):
        msg = "Unique constraint product with this Name and Color already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            UniqueConstraintProduct(
                name=self.p1.name, color=self.p1.color
            ).validate_constraints()

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_model_validation_with_condition(self):
        """
        Tests that Model.validate_constraints() correctly enforces partial unique constraints, specifically when a unique condition is defined.
        """
        obj1 = UniqueConstraintConditionProduct.objects.create(name="p1", color="red")
        obj2 = UniqueConstraintConditionProduct.objects.create(name="p2")
        UniqueConstraintConditionProduct(
            name=obj1.name, color="blue"
        ).validate_constraints()
        msg = "Constraint “name_without_color_uniq” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            UniqueConstraintConditionProduct(name=obj2.name).validate_constraints()

    def test_model_validation_constraint_no_code_error(self):
        """
        Tests the validation of a model with a custom constraint that always raises a ValidationError.

        Ensures that the validation error is correctly raised and contains the expected error message when the model's constraints are validated.
        """
        class ValidateNoCodeErrorConstraint(UniqueConstraint):
            def validate(self, model, instance, **kwargs):
                raise ValidationError({"name": ValidationError("Already exists.")})

        class NoCodeErrorConstraintModel(models.Model):
            name = models.CharField(max_length=255)

            class Meta:
                constraints = [
                    ValidateNoCodeErrorConstraint(
                        Lower("name"),
                        name="custom_validate_no_code_error",
                    )
                ]

        msg = "{'name': ['Already exists.']}"
        with self.assertRaisesMessage(ValidationError, msg):
            NoCodeErrorConstraintModel(name="test").validate_constraints()

    def test_validate(self):
        """
        Tests the validation of unique constraints on the UniqueConstraintProduct model, ensuring that a product with the same name and color cannot be created and that the validation behaves correctly under various conditions and inheritance scenarios.
        """
        constraint = UniqueConstraintProduct._meta.constraints[0]
        msg = "Unique constraint product with this Name and Color already exists."
        non_unique_product = UniqueConstraintProduct(
            name=self.p1.name, color=self.p1.color
        )
        with self.assertRaisesMessage(ValidationError, msg) as cm:
            constraint.validate(UniqueConstraintProduct, non_unique_product)
        self.assertEqual(cm.exception.code, "unique_together")
        # Null values are ignored.
        constraint.validate(
            UniqueConstraintProduct,
            UniqueConstraintProduct(name=self.p2.name, color=None),
        )
        # Existing instances have their existing row excluded.
        constraint.validate(UniqueConstraintProduct, self.p1)
        # Unique fields are excluded.
        constraint.validate(
            UniqueConstraintProduct,
            non_unique_product,
            exclude={"name"},
        )
        constraint.validate(
            UniqueConstraintProduct,
            non_unique_product,
            exclude={"color"},
        )
        constraint.validate(
            UniqueConstraintProduct,
            non_unique_product,
            exclude={"name", "color"},
        )
        # Validation on a child instance.
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(
                UniqueConstraintProduct,
                ChildUniqueConstraintProduct(name=self.p1.name, color=self.p1.color),
            )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_validate_fields_unattached(self):
        """
        Tests that UniqueConstraint validation prevents duplicate field values.

        This test ensures that when an unattached UniqueConstraint is applied to a model,
        it correctly raises a ValidationError if a duplicate value is attempted to be saved.

        """
        Product.objects.create(price=42)
        constraint = models.UniqueConstraint(fields=["price"], name="uniq_prices")
        msg = "Product with this Price already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(Product, Product(price=42))

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_validate_condition(self):
        """
        Tests the validation of a unique constraint with a conditional clause, ensuring it correctly enforces uniqueness based on specific field conditions.
        """
        p1 = UniqueConstraintConditionProduct.objects.create(name="p1")
        constraint = UniqueConstraintConditionProduct._meta.constraints[0]
        msg = "Constraint “name_without_color_uniq” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(
                UniqueConstraintConditionProduct,
                UniqueConstraintConditionProduct(name=p1.name, color=None),
            )
        # Values not matching condition are ignored.
        constraint.validate(
            UniqueConstraintConditionProduct,
            UniqueConstraintConditionProduct(name=p1.name, color="anything-but-none"),
        )
        # Existing instances have their existing row excluded.
        constraint.validate(UniqueConstraintConditionProduct, p1)
        # Unique field is excluded.
        constraint.validate(
            UniqueConstraintConditionProduct,
            UniqueConstraintConditionProduct(name=p1.name, color=None),
            exclude={"name"},
        )

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_validate_condition_custom_error(self):
        """
        Tests validation of unique constraints with custom error messages when a condition is met.

                Verifies that a :class:`~django.core.exceptions.ValidationError` is raised with a user-defined error code and message when a duplicate entry is attempted under a specific condition.
        """
        p1 = UniqueConstraintConditionProduct.objects.create(name="p1")
        constraint = models.UniqueConstraint(
            fields=["name"],
            name="name_without_color_uniq",
            condition=models.Q(color__isnull=True),
            violation_error_code="custom_code",
            violation_error_message="Custom message",
        )
        msg = "Custom message"
        with self.assertRaisesMessage(ValidationError, msg) as cm:
            constraint.validate(
                UniqueConstraintConditionProduct,
                UniqueConstraintConditionProduct(name=p1.name, color=None),
            )
        self.assertEqual(cm.exception.code, "custom_code")

    def test_validate_expression(self):
        """

        Tests the validation of a unique constraint on the 'name' field.
        Verifies that the constraint is enforced in a case-insensitive manner and ignores excluded fields.

        """
        constraint = models.UniqueConstraint(Lower("name"), name="name_lower_uniq")
        msg = "Constraint “name_lower_uniq” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(
                UniqueConstraintProduct,
                UniqueConstraintProduct(name=self.p1.name.upper()),
            )
        constraint.validate(
            UniqueConstraintProduct,
            UniqueConstraintProduct(name="another-name"),
        )
        # Existing instances have their existing row excluded.
        constraint.validate(UniqueConstraintProduct, self.p1)
        # Unique field is excluded.
        constraint.validate(
            UniqueConstraintProduct,
            UniqueConstraintProduct(name=self.p1.name.upper()),
            exclude={"name"},
        )

    def test_validate_ordered_expression(self):
        """
        Tests the validation of an ordered expression in a unique constraint.

        Verifies that the constraint raises an error when the expression is violated and
        succeeds when it is not, with and without excluded fields.
        """
        constraint = models.UniqueConstraint(
            Lower("name").desc(), name="name_lower_uniq_desc"
        )
        msg = "Constraint “name_lower_uniq_desc” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(
                UniqueConstraintProduct,
                UniqueConstraintProduct(name=self.p1.name.upper()),
            )
        constraint.validate(
            UniqueConstraintProduct,
            UniqueConstraintProduct(name="another-name"),
        )
        # Existing instances have their existing row excluded.
        constraint.validate(UniqueConstraintProduct, self.p1)
        # Unique field is excluded.
        constraint.validate(
            UniqueConstraintProduct,
            UniqueConstraintProduct(name=self.p1.name.upper()),
            exclude={"name"},
        )

    def test_validate_expression_condition(self):
        """
        Tests the validation of a unique constraint with a conditional expression.

        This test case ensures that the constraint is applied correctly when the condition
        is met, and that it allows for exclusions of specific fields.

        """
        constraint = models.UniqueConstraint(
            Lower("name"),
            name="name_lower_without_color_uniq",
            condition=models.Q(color__isnull=True),
        )
        non_unique_product = UniqueConstraintProduct(name=self.p2.name.upper())
        msg = "Constraint “name_lower_without_color_uniq” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(UniqueConstraintProduct, non_unique_product)
        # Values not matching condition are ignored.
        constraint.validate(
            UniqueConstraintProduct,
            UniqueConstraintProduct(name=self.p1.name, color=self.p1.color),
        )
        # Existing instances have their existing row excluded.
        constraint.validate(UniqueConstraintProduct, self.p2)
        # Unique field is excluded.
        constraint.validate(
            UniqueConstraintProduct,
            non_unique_product,
            exclude={"name"},
        )
        # Field from a condition is excluded.
        constraint.validate(
            UniqueConstraintProduct,
            non_unique_product,
            exclude={"color"},
        )

    def test_validate_expression_str(self):
        """

        Tests the validation of a unique constraint on a model instance.

        Checks that a ValidationError is raised when the constraint is violated and that
        validation succeeds when the violating field is excluded.

        """
        constraint = models.UniqueConstraint("name", name="name_uniq")
        msg = "Constraint “name_uniq” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(
                UniqueConstraintProduct,
                UniqueConstraintProduct(name=self.p1.name),
            )
        constraint.validate(
            UniqueConstraintProduct,
            UniqueConstraintProduct(name=self.p1.name),
            exclude={"name"},
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_validate_nullable_textfield_with_isnull_true(self):
        """

        Tests the validation of a nullable text field with a unique constraint containing an 'isnull' condition.

        Verifies that the validation correctly handles both null and non-null conditions,
        and raises a ValidationError when the constraint is violated.

        """
        is_null_constraint = models.UniqueConstraint(
            "price",
            "discounted_price",
            condition=models.Q(unit__isnull=True),
            name="uniq_prices_no_unit",
        )
        is_not_null_constraint = models.UniqueConstraint(
            "price",
            "discounted_price",
            condition=models.Q(unit__isnull=False),
            name="uniq_prices_unit",
        )

        Product.objects.create(price=2, discounted_price=1)
        Product.objects.create(price=4, discounted_price=3, unit="ng/mL")

        msg = "Constraint “uniq_prices_no_unit” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            is_null_constraint.validate(
                Product, Product(price=2, discounted_price=1, unit=None)
            )
        is_null_constraint.validate(
            Product, Product(price=2, discounted_price=1, unit="ng/mL")
        )
        is_null_constraint.validate(Product, Product(price=4, discounted_price=3))

        msg = "Constraint “uniq_prices_unit” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            is_not_null_constraint.validate(
                Product,
                Product(price=4, discounted_price=3, unit="μg/mL"),
            )
        is_not_null_constraint.validate(Product, Product(price=4, discounted_price=3))
        is_not_null_constraint.validate(Product, Product(price=2, discounted_price=1))

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_validate_nulls_distinct_fields(self):
        """
        Tests the validation of UniqueConstraint with nulls_distinct=False.

        Verifies that a UniqueConstraint on a field with nulls_distinct=False correctly
        prevents the creation of multiple rows with the same value (including None) in
        the constrained field, raising a ValidationError on a duplicate insertion attempt.
        """
        Product.objects.create(price=42)
        constraint = models.UniqueConstraint(
            fields=["price"],
            nulls_distinct=False,
            name="uniq_prices_nulls_distinct",
        )
        constraint.validate(Product, Product(price=None))
        Product.objects.create(price=None)
        msg = "Product with this Price already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(Product, Product(price=None))

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_validate_nulls_distinct_expressions(self):
        """
        Checks the behavior of a unique constraint with nulls_distinct=False when validating model instances with null values, ensuring that Django correctly enforces the constraint and raises an error when it's violated.
        """
        Product.objects.create(price=42)
        constraint = models.UniqueConstraint(
            Abs("price"),
            nulls_distinct=False,
            name="uniq_prices_nulls_distinct",
        )
        constraint.validate(Product, Product(price=None))
        Product.objects.create(price=None)
        msg = f"Constraint “{constraint.name}” is violated."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(Product, Product(price=None))

    def test_name(self):
        constraints = get_constraints(UniqueConstraintProduct._meta.db_table)
        expected_name = "name_color_uniq"
        self.assertIn(expected_name, constraints)

    def test_condition_must_be_q(self):
        with self.assertRaisesMessage(
            ValueError, "UniqueConstraint.condition must be a Q instance."
        ):
            models.UniqueConstraint(name="uniq", fields=["name"], condition="invalid")

    @skipUnlessDBFeature("supports_deferrable_unique_constraints")
    def test_initially_deferred_database_constraint(self):
        """

        Tests that initially deferred unique database constraints are enforced correctly.

        This test case verifies that attempting to commit a transaction with pending constraint
        violations raises an IntegrityError.

        Requires a database that supports deferrable unique constraints.

        """
        obj_1 = UniqueConstraintDeferrable.objects.create(name="p1", shelf="front")
        obj_2 = UniqueConstraintDeferrable.objects.create(name="p2", shelf="back")

        def swap():
            obj_1.name, obj_2.name = obj_2.name, obj_1.name
            obj_1.save()
            obj_2.save()

        swap()
        # Behavior can be changed with SET CONSTRAINTS.
        with self.assertRaises(IntegrityError):
            with atomic(), connection.cursor() as cursor:
                constraint_name = connection.ops.quote_name("name_init_deferred_uniq")
                cursor.execute("SET CONSTRAINTS %s IMMEDIATE" % constraint_name)
                swap()

    @skipUnlessDBFeature("supports_deferrable_unique_constraints")
    def test_initially_immediate_database_constraint(self):
        """
        Tests the behavior of a unique database constraint that is initially immediate.

         Verifies that attempting to save an object that violates the constraint raises an IntegrityError,
         and that deferring the constraint allows the objects to be saved successfully.
        """
        obj_1 = UniqueConstraintDeferrable.objects.create(name="p1", shelf="front")
        obj_2 = UniqueConstraintDeferrable.objects.create(name="p2", shelf="back")
        obj_1.shelf, obj_2.shelf = obj_2.shelf, obj_1.shelf
        with self.assertRaises(IntegrityError), atomic():
            obj_1.save()
        # Behavior can be changed with SET CONSTRAINTS.
        with connection.cursor() as cursor:
            constraint_name = connection.ops.quote_name("sheld_init_immediate_uniq")
            cursor.execute("SET CONSTRAINTS %s DEFERRED" % constraint_name)
            obj_1.save()
            obj_2.save()

    def test_deferrable_with_condition(self):
        message = "UniqueConstraint with conditions cannot be deferred."
        with self.assertRaisesMessage(ValueError, message):
            models.UniqueConstraint(
                fields=["name"],
                name="name_without_color_unique",
                condition=models.Q(color__isnull=True),
                deferrable=models.Deferrable.DEFERRED,
            )

    def test_deferrable_with_include(self):
        message = "UniqueConstraint with include fields cannot be deferred."
        with self.assertRaisesMessage(ValueError, message):
            models.UniqueConstraint(
                fields=["name"],
                name="name_inc_color_color_unique",
                include=["color"],
                deferrable=models.Deferrable.DEFERRED,
            )

    def test_deferrable_with_opclasses(self):
        message = "UniqueConstraint with opclasses cannot be deferred."
        with self.assertRaisesMessage(ValueError, message):
            models.UniqueConstraint(
                fields=["name"],
                name="name_text_pattern_ops_unique",
                opclasses=["text_pattern_ops"],
                deferrable=models.Deferrable.DEFERRED,
            )

    def test_deferrable_with_expressions(self):
        message = "UniqueConstraint with expressions cannot be deferred."
        with self.assertRaisesMessage(ValueError, message):
            models.UniqueConstraint(
                Lower("name"),
                name="deferred_expression_unique",
                deferrable=models.Deferrable.DEFERRED,
            )

    def test_invalid_defer_argument(self):
        message = "UniqueConstraint.deferrable must be a Deferrable instance."
        with self.assertRaisesMessage(TypeError, message):
            models.UniqueConstraint(
                fields=["name"],
                name="name_invalid",
                deferrable="invalid",
            )

    @skipUnlessDBFeature(
        "supports_table_check_constraints",
        "supports_covering_indexes",
    )
    def test_include_database_constraint(self):
        UniqueConstraintInclude.objects.create(name="p1", color="red")
        with self.assertRaises(IntegrityError):
            UniqueConstraintInclude.objects.create(name="p1", color="blue")

    def test_invalid_include_argument(self):
        msg = "UniqueConstraint.include must be a list or tuple."
        with self.assertRaisesMessage(TypeError, msg):
            models.UniqueConstraint(
                name="uniq_include",
                fields=["field"],
                include="other",
            )

    def test_invalid_opclasses_argument(self):
        msg = "UniqueConstraint.opclasses must be a list or tuple."
        with self.assertRaisesMessage(TypeError, msg):
            models.UniqueConstraint(
                name="uniq_opclasses",
                fields=["field"],
                opclasses="jsonb_path_ops",
            )

    def test_invalid_nulls_distinct_argument(self):
        msg = "UniqueConstraint.nulls_distinct must be a bool."
        with self.assertRaisesMessage(TypeError, msg):
            models.UniqueConstraint(
                name="uniq_opclasses", fields=["field"], nulls_distinct="NULLS DISTINCT"
            )

    def test_opclasses_and_fields_same_length(self):
        msg = (
            "UniqueConstraint.fields and UniqueConstraint.opclasses must have "
            "the same number of elements."
        )
        with self.assertRaisesMessage(ValueError, msg):
            models.UniqueConstraint(
                name="uniq_opclasses",
                fields=["field"],
                opclasses=["foo", "bar"],
            )

    def test_requires_field_or_expression(self):
        msg = (
            "At least one field or expression is required to define a unique "
            "constraint."
        )
        with self.assertRaisesMessage(ValueError, msg):
            models.UniqueConstraint(name="name")

    def test_expressions_and_fields_mutually_exclusive(self):
        msg = "UniqueConstraint.fields and expressions are mutually exclusive."
        with self.assertRaisesMessage(ValueError, msg):
            models.UniqueConstraint(Lower("field_1"), fields=["field_2"], name="name")

    def test_expressions_with_opclasses(self):
        msg = (
            "UniqueConstraint.opclasses cannot be used with expressions. Use "
            "django.contrib.postgres.indexes.OpClass() instead."
        )
        with self.assertRaisesMessage(ValueError, msg):
            models.UniqueConstraint(
                Lower("field"),
                name="test_func_opclass",
                opclasses=["jsonb_path_ops"],
            )

    def test_requires_name(self):
        msg = "A unique constraint must be named."
        with self.assertRaisesMessage(ValueError, msg):
            models.UniqueConstraint(fields=["field"])
