from django.db.models import F, Sum
from django.test import TestCase

from .models import Company, Employee


class ValuesExpressionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the application.

        This class method creates a set of companies with their respective CEOs and other attributes, 
        providing a foundation for testing the application's functionality. 
        The test data includes multiple companies with varying numbers of employees, chairs, and CEO information.

        """
        Company.objects.create(
            name="Example Inc.",
            num_employees=2300,
            num_chairs=5,
            ceo=Employee.objects.create(firstname="Joe", lastname="Smith", salary=10),
        )
        Company.objects.create(
            name="Foobar Ltd.",
            num_employees=3,
            num_chairs=4,
            ceo=Employee.objects.create(firstname="Frank", lastname="Meyer", salary=20),
        )
        Company.objects.create(
            name="Test GmbH",
            num_employees=32,
            num_chairs=1,
            ceo=Employee.objects.create(
                firstname="Max", lastname="Mustermann", salary=30
            ),
        )

    def test_values_expression(self):
        self.assertSequenceEqual(
            Company.objects.values(salary=F("ceo__salary")),
            [{"salary": 10}, {"salary": 20}, {"salary": 30}],
        )

    def test_values_expression_alias_sql_injection(self):
        crafted_alias = """injected_name" from "expressions_company"; --"""
        msg = (
            "Column aliases cannot contain whitespace characters, quotation marks, "
            "semicolons, or SQL comments."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Company.objects.values(**{crafted_alias: F("ceo__salary")})

    def test_values_expression_group_by(self):
        # values() applies annotate() first, so values selected are grouped by
        # id, not firstname.
        """
        .\"\"\"
        Tests the functionality of using values and annotate with group by operations in a Django ORM query.

        This test case covers two main scenarios:
            - The first scenario checks the combination of the `values` method with an aggregated expression (in this case, `Sum`) followed by ordering.
            - The second scenario verifies the usage of the `annotate` method alongside the `values` method to apply an aggregated function and ensure correct grouping.

        The test uses a model representing an Employee, filtering by 'Joe', and performs operations to aggregate salaries, demonstrating the difference between specifying fields in `values` and using `annotate` for aggregation, with the expected outcomes provided for comparison.

        """
        Employee.objects.create(firstname="Joe", lastname="Jones", salary=2)
        joes = Employee.objects.filter(firstname="Joe")
        self.assertSequenceEqual(
            joes.values("firstname", sum_salary=Sum("salary")).order_by("sum_salary"),
            [
                {"firstname": "Joe", "sum_salary": 2},
                {"firstname": "Joe", "sum_salary": 10},
            ],
        )
        self.assertSequenceEqual(
            joes.values("firstname").annotate(sum_salary=Sum("salary")),
            [{"firstname": "Joe", "sum_salary": 12}],
        )

    def test_chained_values_with_expression(self):
        """
        Tests the chaining of values with expressions on a queryset.

        Verifies that using the values() method with an expression, such as a Sum aggregation,
        returns the expected results when applied to a filtered queryset.

        Specifically, this test checks that the values() method can be chained to include
        additional expressions, and that the output matches the expected sequence of dictionaries.

        The test scenario involves creating an employee record, filtering the queryset to
        retrieve the employee's record, and then applying the values() method with an expression
        to calculate the sum of salaries.
        """
        Employee.objects.create(firstname="Joe", lastname="Jones", salary=2)
        joes = Employee.objects.filter(firstname="Joe").values("firstname")
        self.assertSequenceEqual(
            joes.values("firstname", sum_salary=Sum("salary")),
            [{"firstname": "Joe", "sum_salary": 12}],
        )
        self.assertSequenceEqual(
            joes.values(sum_salary=Sum("salary")), [{"sum_salary": 12}]
        )

    def test_values_list_expression(self):
        """

        Tests the values_list expression on Company objects, verifying that it correctly retrieves 
        a list of tuples containing company names and the salaries of their CEOs.

        The test checks that the resulting list contains the expected company names and CEO salaries, 
        regardless of their original order in the database.

        The expected output is a list of tuples, where each tuple contains the name of a company and 
        the salary of its CEO, in any order.

        """
        companies = Company.objects.values_list("name", F("ceo__salary"))
        self.assertCountEqual(
            companies, [("Example Inc.", 10), ("Foobar Ltd.", 20), ("Test GmbH", 30)]
        )

    def test_values_list_expression_flat(self):
        """

        Tests that values_list with flat=True returns a flat list of values.

        This function queries the database for CEO salaries from the Company model and 
        asserts that the result is a flat list containing the expected values, 
        in any order, without duplicates.

        """
        companies = Company.objects.values_list(F("ceo__salary"), flat=True)
        self.assertCountEqual(companies, (10, 20, 30))
