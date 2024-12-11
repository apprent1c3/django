from django.db.models.functions import Lag, Lead, NthValue, Ntile
from django.test import SimpleTestCase


class ValidationTests(SimpleTestCase):
    def test_nth_negative_nth_value(self):
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

        Tests that creating a Lead object with a null source expression raises a ValueError.
        The Lead object requires a valid source expression to operate correctly.

        """
        msg = "Lead requires a non-null source expression"
        with self.assertRaisesMessage(ValueError, msg):
            Lead(expression=None)

    def test_null_source_lag(self):
        """
        Tests that a ValueError is raised when attempting to create a Lag object with a null source expression.

        Verifies that the Lag class correctly handles invalid input by checking for a specific error message when the source expression is None. This test ensures that the Lag class is robust and provides informative error messages in case of incorrect usage.

        :raises ValueError: if the source expression is null
        """
        msg = "Lag requires a non-null source expression"
        with self.assertRaisesMessage(ValueError, msg):
            Lag(expression=None)

    def test_negative_num_buckets_ntile(self):
        """
        -tests whether the Ntile class correctly raises a ValueError when attempting to create an instance with a negative number of buckets.
        """
        msg = "num_buckets must be greater than 0"
        with self.assertRaisesMessage(ValueError, msg):
            Ntile(num_buckets=-1)
