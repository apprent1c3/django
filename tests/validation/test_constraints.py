from django.core.exceptions import ValidationError
from django.test import TestCase, skipUnlessDBFeature

from .models import (
    ChildProduct,
    ChildUniqueConstraintProduct,
    Product,
    UniqueConstraintConditionProduct,
    UniqueConstraintProduct,
)


class PerformConstraintChecksTest(TestCase):
    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_full_clean_with_check_constraints(self):
        """

        Tests that full_clean on a model instance raises a ValidationError when a check constraint is violated.

        This test case specifically checks for the price_gt_discounted_price_validation constraint,
        ensuring that attempting to create or save a model instance with an invalid price setup raises an error.

        The test verifies that the correct error message is raised, indicating that the constraint has been violated.

        """
        product = Product(price=10, discounted_price=15)
        with self.assertRaises(ValidationError) as cm:
            product.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "__all__": [
                    "Constraint “price_gt_discounted_price_validation” is violated."
                ]
            },
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_full_clean_with_check_constraints_on_child_model(self):
        product = ChildProduct(price=10, discounted_price=15)
        with self.assertRaises(ValidationError) as cm:
            product.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "__all__": [
                    "Constraint “price_gt_discounted_price_validation” is violated."
                ]
            },
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_full_clean_with_check_constraints_disabled(self):
        product = Product(price=10, discounted_price=15)
        product.full_clean(validate_constraints=False)

    def test_full_clean_with_unique_constraints(self):
        """
        Tests that the full_clean method correctly raises a ValidationError when a unique constraint is violated.

        Checks that attempting to create or save a UniqueConstraintProduct or ChildUniqueConstraintProduct instance with a duplicate 
        name and color, or a duplicate rank, results in a ValidationError with the expected error messages.

        Verifies that the error messages include both a generic message indicating that a unique constraint has been violated, 
        and a field-specific message highlighting the specific field that caused the constraint to be violated.
        """
        UniqueConstraintProduct.objects.create(name="product", color="yellow", rank=1)
        tests = [
            UniqueConstraintProduct(name="product", color="yellow", rank=1),
            # Child model.
            ChildUniqueConstraintProduct(name="product", color="yellow", rank=1),
        ]
        for product in tests:
            with self.subTest(model=product.__class__.__name__):
                with self.assertRaises(ValidationError) as cm:
                    product.full_clean()
                self.assertEqual(
                    cm.exception.message_dict,
                    {
                        "__all__": [
                            "Unique constraint product with this Name and Color "
                            "already exists."
                        ],
                        "rank": [
                            "Unique constraint product with this Rank already exists."
                        ],
                    },
                )

    def test_full_clean_with_unique_constraints_disabled(self):
        """
        Tests the full clean method of a model instance when unique constraints are disabled, 
        allowing for the creation of duplicate entries, by creating an existing product 
        and then attempting to add another product with the same attributes without 
        enforcing unique constraints validation.
        """
        UniqueConstraintProduct.objects.create(name="product", color="yellow", rank=1)
        product = UniqueConstraintProduct(name="product", color="yellow", rank=1)
        product.full_clean(validate_constraints=False)

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_full_clean_with_partial_unique_constraints(self):
        UniqueConstraintConditionProduct.objects.create(name="product")
        product = UniqueConstraintConditionProduct(name="product")
        with self.assertRaises(ValidationError) as cm:
            product.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {
                "__all__": [
                    "Constraint “name_without_color_uniq_validation” is violated."
                ]
            },
        )

    @skipUnlessDBFeature("supports_partial_indexes")
    def test_full_clean_with_partial_unique_constraints_disabled(self):
        """
        Tests the full clean functionality with partial unique constraints disabled.

        This test case creates a new product instance and then calls the full clean method
        on it, bypassing constraint validation. It verifies that the full clean process
        completes successfully even when partial unique constraints are not enforced.

        The purpose of this test is to ensure that the model's full clean functionality
        remains operational when constraint checking is disabled, allowing for flexible
        data validation and cleaning in various database scenarios.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        None

        Notes
        -----
        This test is skipped unless the database backend supports partial indexes.
        """
        UniqueConstraintConditionProduct.objects.create(name="product")
        product = UniqueConstraintConditionProduct(name="product")
        product.full_clean(validate_constraints=False)
