from django.db.models.functions import Lag, Lead, NthValue, Ntile
from django.test import SimpleTestCase


class ValidationTests(SimpleTestCase):
    def test_nth_negative_nth_value(self):
        """
        Tests that initializing an NthValue object with a negative value for 'nth' raises a ValueError.

        The function verifies that the NthValue class correctly enforces the requirement that 'nth' must be a positive integer.
        It checks if an attempt to create an NthValue object with 'nth' set to -1 results in a ValueError with the expected error message.
        This test ensures that the class behaves as expected and provides informative error messages for invalid input.
        """
        msg = "NthValue requires a positive integer as for nth"
        with self.assertRaisesMessage(ValueError, msg):
            NthValue(expression="salary", nth=-1)

    def test_nth_null_expression(self):
        msg = "NthValue requires a non-null source expression"
        with self.assertRaisesMessage(ValueError, msg):
            NthValue(expression=None)

    def test_lag_negative_offset(self):
        msg = "Lag requires a positive integer for the offset"
        with self.assertRaisesMessage(ValueError, msg):
            Lag(expression="salary", offset=-1)

    def test_lead_negative_offset(self):
        msg = "Lead requires a positive integer for the offset"
        with self.assertRaisesMessage(ValueError, msg):
            Lead(expression="salary", offset=-1)

    def test_null_source_lead(self):
        """

        Test that creating a Lead object with a null source expression raises a ValueError.

        The Lead object requires a valid source expression to function correctly.
        This test ensures that attempting to create a Lead object without a source expression
        results in an exception with a meaningful error message, indicating that a non-null source expression is required.

        """
        msg = "Lead requires a non-null source expression"
        with self.assertRaisesMessage(ValueError, msg):
            Lead(expression=None)

    def test_null_source_lag(self):
        """

        Checks that a ValueError is raised when attempting to create a Lag object with a null source expression.

        The test verifies that a meaningful error message is provided, indicating that the Lag requires a valid, non-null source expression to function correctly.

        """
        msg = "Lag requires a non-null source expression"
        with self.assertRaisesMessage(ValueError, msg):
            Lag(expression=None)

    def test_negative_num_buckets_ntile(self):
        msg = "num_buckets must be greater than 0"
        with self.assertRaisesMessage(ValueError, msg):
            Ntile(num_buckets=-1)
