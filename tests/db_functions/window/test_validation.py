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
        """
        Tests that creating a Lead object with a negative offset raises a ValueError.

        The Lead object is expected to require a positive integer for its offset. This test
        ensures that passing a negative value for the offset results in a ValueError with
        a specific error message indicating that the offset must be a positive integer.

        :raises: ValueError when a negative offset is used to create a Lead object
        """
        msg = "Lead requires a positive integer for the offset"
        with self.assertRaisesMessage(ValueError, msg):
            Lead(expression="salary", offset=-1)

    def test_null_source_lead(self):
        msg = "Lead requires a non-null source expression"
        with self.assertRaisesMessage(ValueError, msg):
            Lead(expression=None)

    def test_null_source_lag(self):
        """
        Tests that a ValueError is raised when attempting to create a Lag object with a null source expression.

        The Lag object requires a valid source expression to function correctly. This test verifies that an exception is thrown when this requirement is not met, ensuring the integrity of the Lag object and preventing potential errors. 
        """
        msg = "Lag requires a non-null source expression"
        with self.assertRaisesMessage(ValueError, msg):
            Lag(expression=None)

    def test_negative_num_buckets_ntile(self):
        msg = "num_buckets must be greater than 0"
        with self.assertRaisesMessage(ValueError, msg):
            Ntile(num_buckets=-1)
