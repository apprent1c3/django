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
    """

    Retrieve constraints associated with a given database table.

    This function takes the name of a database table as input and returns a dictionary
    containing information about the constraints defined on that table.

    The constraints include primary keys, foreign keys, unique constraints, and check
    constraints. The returned dictionary is keyed by constraint name, with values
    representing the type and details of each constraint.

    The function leverages the underlying database connection to introspect the table
    schema and retrieve the constraint information.

    Parameters
    ----------
    table : str
        The name of the database table for which to retrieve constraints.

    Returns
    -------
    dict
        A dictionary containing information about the constraints defined on the table.

    """
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, table)


class BaseConstraintTests(SimpleTestCase):
    def test_constraint_sql(self):
        """
        Tests that the constraint_sql method raises a NotImplementedError when called on the base class.

        This test ensures that any subclasses of BaseConstraint implement the constraint_sql method, 
        as it is not implemented in the base class itself. The test passes if calling constraint_sql 
        on an instance of BaseConstraint raises a NotImplementedError with the expected message.
        """
        c = BaseConstraint(name="name")
        msg = "This method must be implemented by a subclass."
        with self.assertRaisesMessage(NotImplementedError, msg):
            c.constraint_sql(None, None)

    def test_contains_expressions(self):
        """

        Tests that a newly created BaseConstraint instance does not contain expressions by default.

        Checks the initial state of the :attr:`contains_expressions` attribute, ensuring it is properly initialized to False when a constraint is first created.

        """
        c = BaseConstraint(name="name")
        self.assertIs(c.contains_expressions, False)

    def test_create_sql(self):
        c = BaseConstraint(name="name")
        msg = "This method must be implemented by a subclass."
        with self.assertRaisesMessage(NotImplementedError, msg):
            c.create_sql(None, None)

    def test_remove_sql(self):
        """
        Test that the remove_sql method of a BaseConstraint instance raises a NotImplementedError.

        This test ensures that subclasses of BaseConstraint must provide an implementation for the remove_sql method,
        as it is not implemented in the base class. It verifies that calling remove_sql on a BaseConstraint instance
        raises a NotImplementedError with the expected error message.

        :raises: AssertionError, if the remove_sql method does not raise a NotImplementedError as expected
        """
        c = BaseConstraint(name="name")
        msg = "This method must be implemented by a subclass."
        with self.assertRaisesMessage(NotImplementedError, msg):
            c.remove_sql(None, None)

    def test_validate(self):
        """

        Tests that the validate method in a constraint class raises a NotImplementedError 
        when not implemented by a subclass. This ensures that any concrete constraint 
        subclasses must provide a proper implementation of the validate method. 

        """
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
        """
        Tests the functionality to clone a BaseConstraint instance and verify that the cloned instance 
        preserves the custom violation error message. 

        The test confirms that when the clone method is called on a BaseConstraint object with a 
        custom violation error message, the resulting cloned object retains this custom message, 
        substituting any placeholders with the actual attribute values of the constraint, 
        such as its name, thus ensuring consistent and customized error reporting across cloned instances.
        """
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
        """

        Tests that positional arguments in a constraint's error message are correctly replaced.

        This test case verifies that the BaseConstraint class can properly substitute
        positional arguments in its custom error message. It checks that the error message
        returned by the get_violation_error_message method contains the expected
        replacement of the positional argument.

        The test creates a BaseConstraint instance with a custom error message containing
        a positional argument, and then asserts that the get_violation_error_message method
        returns the expected error message with the positional argument replaced.

        """
        c = BaseConstraint("name", "custom %(name)s message")
        self.assertEqual(c.get_violation_error_message(), "custom name message")


class CheckConstraintTests(TestCase):
    def test_eq(self):
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
        """
        Tests the string representation of a CheckConstraint object.

        Verifies that the repr method returns a string that accurately reflects the
        constraint's condition and name. The condition is represented as a logical
        expression, and the name is included as a string literal. This test ensures
        that the repr method provides a useful and readable representation of the
        constraint, which can be helpful for debugging and logging purposes.
        """
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
        """
        Tests the representation of a CheckConstraint with a violation error message.

        Verifies that the repr function correctly formats the constraint's condition, 
        name, and custom violation error message into a string. The condition is expected 
        to be represented as a logical expression, and the name and violation error message 
        are displayed as attributes of the constraint. The test ensures that the repr string 
        accurately reflects the constraint's properties, including the custom error message 
        that is displayed when the constraint is violated.

        Parameters are not applicable in this test case as it is focused on the representation 
        of the constraint object itself rather than its functionality with external inputs.

        Returns: 
            None. The test passes if the representation string matches the expected format, 
            and fails otherwise. 

        See Also: models.CheckConstraint
        """
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
        """

        Tests that a TypeError is raised when creating a CheckConstraint with an invalid condition type.

        The test verifies that the condition must be a Q instance or a boolean expression, 
        ensuring that the CheckConstraint is properly configured to validate data.

        """
        msg = "CheckConstraint.condition must be a Q instance or boolean expression."
        with self.assertRaisesMessage(TypeError, msg):
            models.CheckConstraint(condition=models.F("discounted_price"), name="check")

    def test_deconstruction(self):
        check = models.Q(price__gt=models.F("discounted_price"))
        name = "price_gt_discounted_price"
        constraint = models.CheckConstraint(condition=check, name=name)
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.CheckConstraint")
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {"condition": check, "name": name})

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_database_constraint(self):
        """
        Tests the database constraint that ensures the discounted price of a product is less than or equal to its regular price.

        This test verifies that attempting to create a product with a discounted price higher than its regular price raises an IntegrityError, demonstrating the enforcement of the table check constraint by the database.

        The test case covers the creation of a valid product and then attempts to create an invalid product, allowing the database to enforce its constraints and validate the test outcome.
        """
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
        """

        Tests the naming of check constraints in the database.

        This test verifies that the check constraints defined in the Product model are correctly
        introduced into the database and can be introspected. It checks for the presence of two
        specific constraints, 'price_gt_discounted_price' and 'constraints_product_price_gt_0',
        in the list of constraints retrieved from the database.

        The test relies on the database supporting table check constraints and introspection
        of these constraints. If the database does not support these features, the test is skipped.

        """
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
        """

        Tests that an abstract model's name appears in the name of its table check constraints.

        This test case aims to verify that the name of an abstract model is correctly
        incorporated into the name of the database constraints defined on its tables.
        The test checks for the presence of a specific constraint name in the list of
        constraints retrieved from the database for the table associated with the
        ChildModel.

        The test requires the database backend to support table check constraints and
        the ability to introspect them.

        """
        constraints = get_constraints(ChildModel._meta.db_table)
        self.assertIn("constraints_childmodel_adult", constraints)

    def test_validate(self):
        """
        Tests the validation of a CheckConstraint that ensures the price of a product is greater than its discounted price.

        This function creates a CheckConstraint and tests its validation under various conditions, including when the constraint is violated and when certain fields are excluded from validation.

        The validation test cases cover scenarios where:
        - The price is less than the discounted price, triggering a ValidationError.
        - Specific fields are excluded from validation, and the expected validation result is confirmed.
        - A valid product price and discounted price combination is provided, and no ValidationError is raised.

        The tests verify that the CheckConstraint correctly enforces the business rule that a product's price must be greater than its discounted price, unless specific fields are excluded from the validation check.
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

        Validate the custom error behavior of a CheckConstraint.

        This test ensures that when a Product instance's price is less than its discounted price,
        a ValidationError is raised with a specific error message and code.

        The validation process checks whether a product's price exceeds its discounted price,
        and if not, raises an exception with a custom error message ('discount is fake') and code ('fake_discount').

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

        Test the validation of a boolean expression that checks if the product price is not equal to 500.

        The test case creates a check constraint that validates if the product price is greater than or less than 500.
        It then attempts to validate a product with a price of 500, which should raise a ValidationError, and verifies that
        products with prices of 499 and 501 are successfully validated without raising an error.

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
        """

        Tests the validation of raw SQL expressions without operational impact.

        Checks if the check constraint correctly validates instances of the Product model 
        against a raw SQL condition, ensuring that the price is not equal to 500. 

        The validation is performed on different price scenarios, including prices equal to, 
        less than, and greater than the specified value, to ensure the constraint is working 
        as expected. 

        Validates the condition using a raw SQL expression with parameter substitution, 
        returning a boolean result indicating whether the condition is met.

        """
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
        """
        Tests the validation of a nullable field with a null value.

        This test case checks if a model instance with a null value in a field that has a check constraint
        is validated correctly. The check constraint ensures that the 'price' field is greater than or equal to 0.
        The test uses the Product model and an instance of the Product model to validate the constraint.

        The test is skipped if the database feature 'supports_comparing_boolean_expr' is not supported.
        """
        constraint = models.CheckConstraint(
            condition=models.Q(price__gte=0),
            name="positive_price",
        )
        constraint.validate(Product, Product())

    @skipIfDBFeature("supports_comparing_boolean_expr")
    def test_validate_nullable_field_with_isnull(self):
        """
        Tests validation of a nullable model field with a CheckConstraint that allows null values.

        This test case ensures that a field with a check constraint permitting null values is validated correctly.
        The constraint checks if the 'price' field is either greater than or equal to 0 or null.
        It verifies that the validation passes when the field is null, thus allowing nullable values for the field.

        The test covers the scenario where the 'supports_comparing_boolean_expr' database feature is not supported.

        """
        constraint = models.CheckConstraint(
            condition=models.Q(price__gte=0) | models.Q(price__isnull=True),
            name="positive_price",
        )
        constraint.validate(Product, Product())

    @skipUnlessDBFeature("supports_json_field")
    def test_validate_nullable_jsonfield(self):
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

        Tests the validation of a primary key field against a custom check constraint.

        The function tests a check constraint that ensures the primary key of an instance 
        is not equal to its 'age' field. It creates a check constraint and validates it 
        against several instances of a model, including cases where the constraint is 
        violated and cases where it is not. The test also checks that the validation 
        can be excluded for specific fields, such as the primary key itself.

        The test covers various scenarios, including:

        * Valid instances that satisfy the check constraint
        * Invalid instances where the primary key equals the 'age' field
        * Instances with missing primary key (using 'id' instead of 'pk')
        * Excluding specific fields from the validation process

        The function raises a ValidationError with a descriptive message when the 
        constraint is violated.

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
        """

        Sets up test data for the current test class.

        This method creates two UniqueConstraintProduct instances, p1 and p2, 
        with specific attribute values and stores them as class attributes.
        These instances can be used throughout the test class for testing purposes.

        """
        cls.p1 = UniqueConstraintProduct.objects.create(name="p1", color="red")
        cls.p2 = UniqueConstraintProduct.objects.create(name="p2")

    def test_eq(self):
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
        """

        Tests the equality of UniqueConstraint instances with a condition.

        Checks that UniqueConstraint instances are equal when they have the same fields, name, 
        and condition, and not equal when they differ in their condition. This ensures 
        that the equality check correctly handles UniqueConstraint instances with conditional 
        logic applied.

        The test covers two scenarios: 
        - Equality test: verifies that two UniqueConstraint instances with identical 
          fields, name, and condition are considered equal.
        - Inequality test: verifies that two UniqueConstraint instances with identical 
          fields and name but different conditions are considered not equal.

        """
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
        """

        Tests the equality of UniqueConstraint instances with different deferrable settings.

        This test case verifies that two UniqueConstraint instances are considered equal
        if they have the same fields and name, regardless of their deferrable setting.
        It also checks that two UniqueConstraint instances with different deferrable
        settings (e.g., DEFERRED vs IMMEDIATE) are not considered equal.

        The test covers the following scenarios:
        - Equality of a UniqueConstraint instance with itself.
        - Inequality of UniqueConstraint instances with different deferrable settings.

        """
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
        """

        Tests the equality of UniqueConstraint instances when they include additional fields.

        This method verifies that UniqueConstraint instances are considered equal when they have the same fields, name, and include the same additional fields.
        It also checks that instances with different included fields are not considered equal, even if their fields and name are the same.

        """
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

        Tests the equality of UniqueConstraint instances with different nulls_distinct settings.

        This test case verifies that UniqueConstraint objects are considered equal when 
        they have the same properties, including the nulls_distinct parameter, and unequal 
        when these properties differ. The nulls_distinct parameter determines whether 
        null values are treated as distinct from one another.

        The test checks equality between constraints with the same field, function, and 
        name, but different nulls_distinct settings, as well as between constraints with 
        default nulls_distinct settings.

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
        """

        Tests the representation of a UniqueConstraint instance.

        Verifies that the repr function returns a string that accurately reflects the
        fields and name of the constraint, in the format expected for a UniqueConstraint
        object.

        """
        fields = ["foo", "bar"]
        name = "unique_fields"
        constraint = models.UniqueConstraint(fields=fields, name=name)
        self.assertEqual(
            repr(constraint),
            "<UniqueConstraint: fields=('foo', 'bar') name='unique_fields'>",
        )

    def test_repr_with_condition(self):
        """

        Tests the representation of a UniqueConstraint with a conditional clause.

        Verifies that the repr function correctly formats the constraint's fields, name, and condition.
        The condition used in this test is a simple equality check between two fields, 'foo' and 'bar'.
        The expected representation is a string that clearly displays the constraint's details, including the fields, name, and conditional expression.

        This test ensures that the repr function provides a useful and readable string representation of the UniqueConstraint, which can be helpful for debugging and logging purposes.

        """
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
        """

        Tests that the repr method of a UniqueConstraint returns the expected string representation.

        This test case verifies that the UniqueConstraint object is correctly represented as a string,
        including its fields, name, and opclasses, to ensure accurate and informative output.

        """
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
        """

        Tests that the string representation of a UniqueConstraint with nulls_distinct=False is correctly formatted.

        This test case checks that the repr function generates a string that accurately reflects the fields, name, and nulls_distinct status of the constraint.

        The test is specific to the case where nulls_distinct is set to False, which allows for the possibility of multiple rows with null values in the columns defined by the constraint.

        """
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
        """
        Tests the representation of a UniqueConstraint instance with expressions.

        The function verifies that the repr method of a UniqueConstraint object correctly 
        represents its constituent expressions and name. It checks if the string 
        representation of the constraint matches the expected format when the constraint 
        is defined with function-based expressions, such as Lower and F.
        """
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
        """
        Tests the string representation of a UniqueConstraint with a custom violation error message.

        Verifies that the repr function correctly outputs the constraint's details, including the 
        expressions and name, as well as any custom error messages defined for constraint violations.

        Ensures that the output matches the expected format for a UniqueConstraint instance, 
        providing a human-readable summary of the constraint's properties and behavior.

        Use this test to confirm that UniqueConstraint instances are properly represented as strings,
        which can be useful for debugging and logging purposes in applications that utilize these constraints.
        """
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
        fields = ["foo", "bar"]
        name = "unique_fields"
        constraint = models.UniqueConstraint(fields=fields, name=name)
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {"fields": tuple(fields), "name": name})

    def test_deconstruction_with_condition(self):
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

        Tests the deconstruction of a UniqueConstraint with deferrable attribute.

        The deconstruction process involves breaking down the UniqueConstraint object into its constituent parts, 
        including the path to the constraint class, positional arguments, and keyword arguments. 

        This test checks if the deconstruction correctly returns the expected values for the path, 
        positional arguments, and keyword arguments.

        The keyword arguments include the fields affected by the constraint, the name of the constraint, 
        and the deferrable status of the constraint, which determines when the constraint is enforced.

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
        Tests the deconstruction of a UniqueConstraint with operation classes.

        This test case verifies that a UniqueConstraint object with specified fields, 
        name, and operation classes can be successfully deconstructed into its 
        constituent parts, including the path, arguments, and keyword arguments. The 
        deconstruction process is essential for serializing and deserializing 
        database constraints.

        The test checks the correctness of the deconstructed path, arguments, and 
        keyword arguments, ensuring they match the expected values. This ensures 
        that the UniqueConstraint can be properly reconstructed from its 
        deconstructed parts, maintaining the integrity of the database constraints 
        during serialization and deserialization operations.
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
        Tests the deconstruction of a UniqueConstraint model field with nulls_distinct set to True.

        This function verifies that a UniqueConstraint field with specified fields, name, and nulls_distinct=True can be successfully deconstructed into its constituent parts, including the path, positional arguments, and keyword arguments.

        The deconstruction process is essential for serializing and deserializing model fields, particularly when working with databases that support unique constraints with distinct null values. The test ensures that the deconstruction output matches the expected format, which includes the correct path to the UniqueConstraint class, empty positional arguments, and keyword arguments containing the specified fields, name, and nulls_distinct value.

        By validating the deconstruction process, this test provides assurance that UniqueConstraint fields with nulls_distinct=True can be properly reconstructed and used in various database operations, including migration and schema changes.
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
        name = "unique_fields"
        constraint = models.UniqueConstraint(Lower("title"), name=name)
        path, args, kwargs = constraint.deconstruct()
        self.assertEqual(path, "django.db.models.UniqueConstraint")
        self.assertEqual(args, (Lower("title"),))
        self.assertEqual(kwargs, {"name": name})

    def test_database_constraint(self):
        """
        Tests that a database constraint is enforced, ensuring that duplicate products with the same name and color cannot be created.

        This test case verifies that an IntegrityError is raised when attempting to insert a record that violates the uniqueness constraint.

        """
        with self.assertRaises(IntegrityError):
            UniqueConstraintProduct.objects.create(
                name=self.p1.name, color=self.p1.color
            )

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_database_constraint_with_condition(self):
        """
        Tests the functionality of database constraints with conditional unique constraints.

        Verifies that a unique constraint with a condition is enforced by attempting to create duplicate entries
        and checking for the raising of an IntegrityError.

        Ensures that the database correctly handles conditional uniqueness and prevents duplicate values under
        the specified condition, demonstrating the support for partial indexes in the database system.
        """
        UniqueConstraintConditionProduct.objects.create(name="p1")
        UniqueConstraintConditionProduct.objects.create(name="p2")
        with self.assertRaises(IntegrityError):
            UniqueConstraintConditionProduct.objects.create(name="p1")

    def test_model_validation(self):
        """

        Tests that validation of UniqueConstraintProduct raises a ValidationError
        when attempting to create a product with a name and color that already exists.
        The test ensures that the error message correctly identifies the duplicate
        product constraint.

        """
        msg = "Unique constraint product with this Name and Color already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            UniqueConstraintProduct(
                name=self.p1.name, color=self.p1.color
            ).validate_constraints()

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_model_validation_with_condition(self):
        """
        Partial unique constraints are not ignored by
        Model.validate_constraints().
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
        Tests the validation of a unique constraint on a product model.

        Verifies that the unique constraint on the `Name` and `Color` fields is enforced when creating a new product with an existing combination of these values. The test covers various scenarios, including:

        * Attempting to create a product with an existing name and color, which should raise a `ValidationError` with a specific message.
        * Creating products with missing or excluded fields, which should pass validation.
        * Verifying that the validation error code is 'unique_together'.
        * Testing the validation of a child product model that inherits from the product model.

        Ensures that the unique constraint is properly enforced and that the validation behavior is correct in different situations.
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
        Validate that a database constraint prevents duplicate Product instances with the same price.

        This test case ensures that when a Product instance with an existing price is created, 
        a ValidationError is raised to prevent data duplication. The test specifically checks 
        for the presence of a 'uniq_prices' unique constraint on the Product model's 'price' field, 
        and verifies that a meaningful error message is displayed when attempting to save a duplicate.
        """
        Product.objects.create(price=42)
        constraint = models.UniqueConstraint(fields=["price"], name="uniq_prices")
        msg = "Product with this Price already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            constraint.validate(Product, Product(price=42))

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_validate_condition(self):
        """

        Tests the validation of a unique constraint with a condition on a model.

        This test ensures that the constraint correctly enforces uniqueness based on the
        condition, and raises a validation error when the constraint is violated. It also
        checks that the constraint is satisfied when the condition is met, and that the
        validation can be bypassed by excluding specific fields from the validation.

        The test covers different scenarios, including validating instances with and
        without the condition, and validating an instance while excluding specific
        fields. It verifies that the expected error message is raised when the constraint
        is violated.

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
        Tests the validation of a unique constraint expression.

        This test ensures that a unique constraint applied to a model field is enforced correctly.
        It checks that the validation fails when a duplicate value is provided, and succeeds when the value is unique or the field is excluded from validation.

        The test covers the following scenarios:
            - Validation failure when a duplicate value is provided, regardless of case.
            - Validation success when a unique value is provided.
            - Validation success when the same value is provided but the field is excluded from validation.

        The test verifies that the correct error message is raised when the constraint is violated, and that no error is raised when the constraint is satisfied.

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

        Tests the validation of an ordered expression constraint.

        This test case verifies the functionality of a unique constraint applied to a model field.
        The constraint checks for uniqueness of a field value in descending order, with case insensitivity.
        It ensures that the constraint is correctly enforced when a duplicate value is provided,
        and that it allows for non-duplicate values. Additionally, it tests the exclusion of fields from the constraint.

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

        Tests the validation of a unique constraint condition on a model instance.

        This test ensures that the unique constraint is enforced based on the specified
        condition, and that a ValidationError is raised when the condition is violated.
        The test covers various scenarios, including cases where the constraint is valid
        and invalid, as well as cases where the validation is skipped due to excluded
        fields.

        The test validates the UniqueConstraint object with a condition that checks for
        a unique 'name' field (in lowercase) when the 'color' field is Null. It verifies
        that a ValidationError is raised when a duplicate product with the same name
        (up to case) and no color is encountered, and that the validation succeeds in
        other cases.

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

        Tests the validation of unique constraints with nullable text fields.

        This test case checks the validity of two unique constraints: one that applies when a 
        specific field ('unit') is null, and another that applies when it is not null. The 
        test ensures that these constraints behave correctly in preventing duplicate values 
        for the 'price' and 'discounted_price' fields under the specified conditions.

        The test covers scenarios where the constraints are violated and when they are not, 
        verifying that the correct validation errors are raised in each case.

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
        """

        Tests if the 'name_color_uniq' constraint is present in the UniqueConstraintProduct database table.

        This test case verifies that the database table has the expected unique constraint 
        to prevent duplicate combinations of name and color.

        """
        constraints = get_constraints(UniqueConstraintProduct._meta.db_table)
        expected_name = "name_color_uniq"
        self.assertIn(expected_name, constraints)

    def test_condition_must_be_q(self):
        """

        Tests that a ValueError is raised when the condition argument of UniqueConstraint is not a Q instance.

        This test case verifies that the UniqueConstraint class properly validates its condition parameter, ensuring it is a valid Q instance.
        If an invalid condition is provided, a ValueError is expected to be raised with a descriptive error message.

        """
        with self.assertRaisesMessage(
            ValueError, "UniqueConstraint.condition must be a Q instance."
        ):
            models.UniqueConstraint(name="uniq", fields=["name"], condition="invalid")

    @skipUnlessDBFeature("supports_deferrable_unique_constraints")
    def test_initially_deferred_database_constraint(self):
        """
        Tests the behavior of a unique constraint that is initially deferred.

        This test case verifies that a unique constraint that is defined as deferrable
        can be initially deferred, allowing temporary violations of the constraint
        until it is checked at the end of a transaction. It creates two objects with
        unique constraints, swaps their names, and then checks that an IntegrityError
        is raised when the constraint is set to be checked immediately and the swap is
        attempted again within a transaction.
        """
        obj_1 = UniqueConstraintDeferrable.objects.create(name="p1", shelf="front")
        obj_2 = UniqueConstraintDeferrable.objects.create(name="p2", shelf="back")

        def swap():
            """

            Swap the names of two objects in the database.

            This function exchanges the 'name' attribute of two objects, obj_1 and obj_2, 
            and then saves the updated objects to the database.

            Note:
                The objects being swapped must have a 'name' attribute and support the 'save' method.
                The actual implementation of the swap operation is done in a single, atomic operation.

            """
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
        """
        Tests that attempting to create a UniqueConstraint with a condition and a deferred constraint raises a ValueError, as conditional UniqueConstraints cannot be deferred.
        """
        message = "UniqueConstraint with conditions cannot be deferred."
        with self.assertRaisesMessage(ValueError, message):
            models.UniqueConstraint(
                fields=["name"],
                name="name_without_color_unique",
                condition=models.Q(color__isnull=True),
                deferrable=models.Deferrable.DEFERRED,
            )

    def test_deferrable_with_include(self):
        """
        Tests that creating a UniqueConstraint with include fields and deferrable set to DEFERRED raises a ValueError. 

        The UniqueConstraint is created with a fields list, name, and include list, and it is verified that attempting to defer the constraint results in the expected exception message. 

        .. note:: Unique constraints with include fields cannot be deferred.
        """
        message = "UniqueConstraint with include fields cannot be deferred."
        with self.assertRaisesMessage(ValueError, message):
            models.UniqueConstraint(
                fields=["name"],
                name="name_inc_color_color_unique",
                include=["color"],
                deferrable=models.Deferrable.DEFERRED,
            )

    def test_deferrable_with_opclasses(self):
        """
        Tests that a UniqueConstraint with opclasses cannot be deferred.

        This test validates the behavior when creating a UniqueConstraint with 
        opclasses and attempting to set it as deferrable. It verifies that a 
        ValueError is raised with the expected error message, ensuring that 
        unique constraints with opclasses are always enforced immediately, 
        preventing deferral.

        :raises ValueError: If a UniqueConstraint with opclasses is set as deferrable.
        """
        message = "UniqueConstraint with opclasses cannot be deferred."
        with self.assertRaisesMessage(ValueError, message):
            models.UniqueConstraint(
                fields=["name"],
                name="name_text_pattern_ops_unique",
                opclasses=["text_pattern_ops"],
                deferrable=models.Deferrable.DEFERRED,
            )

    def test_deferrable_with_expressions(self):
        """
        Tests that creating a unique constraint with an expression cannot be deferred.

        The function checks that attempting to create a unique constraint with an expression 
        (i.e., a column wrapped in a database function) and setting it as deferrable raises 
        a ValueError with the expected error message. This ensures that the UniqueConstraint 
        class correctly enforces the database constraint that deferrable constraints cannot 
        be used with expressions.
        """
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
        """

        Tests the inclusion of unique database constraints in the model.

        This test case verifies that the database enforces unique constraints defined in the model.
        It checks that attempting to create a duplicate entry raises an IntegrityError.
        The test covers the scenario where a unique constraint is applied to a specific field,
        ensuring data consistency and preventing duplicate records from being inserted.

        """
        UniqueConstraintInclude.objects.create(name="p1", color="red")
        with self.assertRaises(IntegrityError):
            UniqueConstraintInclude.objects.create(name="p1", color="blue")

    def test_invalid_include_argument(self):
        """
        ..: 
            Validates that the include argument of a UniqueConstraint must be a list or tuple.

            This test case checks that a TypeError is raised when attempting to create a UniqueConstraint with an invalid include argument. The error message indicates that the include parameter must be either a list or a tuple, rather than any other type.
        """
        msg = "UniqueConstraint.include must be a list or tuple."
        with self.assertRaisesMessage(TypeError, msg):
            models.UniqueConstraint(
                name="uniq_include",
                fields=["field"],
                include="other",
            )

    def test_invalid_opclasses_argument(self):
        """
        Tests that providing a non-iterable value for the opclasses argument of UniqueConstraint results in a TypeError. The opclasses argument must be a list or tuple to specify the operator classes to use for the constraint.
        """
        msg = "UniqueConstraint.opclasses must be a list or tuple."
        with self.assertRaisesMessage(TypeError, msg):
            models.UniqueConstraint(
                name="uniq_opclasses",
                fields=["field"],
                opclasses="jsonb_path_ops",
            )

    def test_invalid_nulls_distinct_argument(self):
        """

        Tests that the nulls_distinct argument of UniqueConstraint is validated correctly.

        This test case verifies that passing a non-boolean value to the nulls_distinct argument
        raises a TypeError with a specific error message, ensuring that the UniqueConstraint
        enforces proper type checking for this parameter.

        """
        msg = "UniqueConstraint.nulls_distinct must be a bool."
        with self.assertRaisesMessage(TypeError, msg):
            models.UniqueConstraint(
                name="uniq_opclasses", fields=["field"], nulls_distinct="NULLS DISTINCT"
            )

    def test_opclasses_and_fields_same_length(self):
        """
        Tests if the UniqueConstraint raises a ValueError when the lengths of fields and opclasses lists do not match.

        The function verifies that creating a UniqueConstraint with different numbers of elements in the fields and opclasses lists results in an error.

        It checks for a ValueError with the specific message indicating that the fields and opclasses must have the same number of elements, ensuring the constraint's consistency and preventing incorrect usage.
        """
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
        """
        Tests that creating a UniqueConstraint without a name raises an error.

        Verifies that a ValueError is raised when attempting to create a UniqueConstraint
        without specifying a name, as a unique constraint must have a name for database
        identification purposes.

        :raises ValueError: If a UniqueConstraint is created without a name.

        """
        msg = "A unique constraint must be named."
        with self.assertRaisesMessage(ValueError, msg):
            models.UniqueConstraint(fields=["field"])
