from operator import attrgetter

from django.test.testcases import TestCase

from .models import Address, Contact, Customer


class TestLookupQuery(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class.

        This class method creates and stores fixed test data for use in subsequent tests.
        The test data includes an address, a customer, and a contact, all associated with 
        a specific company and customer ID.

        The created test data is stored as class attributes for easy access in other test methods.

        This method is typically called before running a series of tests to ensure a consistent 
        dataset for testing purposes.
        """
        cls.address = Address.objects.create(company=1, customer_id=20)
        cls.customer1 = Customer.objects.create(company=1, customer_id=20)
        cls.contact1 = Contact.objects.create(company_code=1, customer_code=20)

    def test_deep_mixed_forward(self):
        self.assertQuerySetEqual(
            Address.objects.filter(customer__contacts=self.contact1),
            [self.address.id],
            attrgetter("id"),
        )

    def test_deep_mixed_backward(self):
        self.assertQuerySetEqual(
            Contact.objects.filter(customer__address=self.address),
            [self.contact1.id],
            attrgetter("id"),
        )
