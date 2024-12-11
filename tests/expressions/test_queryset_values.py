from django.db.models import F, Sum
from django.test import TestCase

from .models import Company, Employee


class ValuesExpressionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the application.

        This method creates a set of predefined companies with their respective CEOs, 
        including attributes such as company name, number of employees, number of chairs, 
        and CEO details like first name, last name, and salary.

        The test data is used to populate the database, allowing for testing of 
        application functionality without requiring manual data entry.

        The created companies include:
        - Example Inc.
        - Foobar Ltd.
        - Test GmbH

        Each company is assigned a CEO with unique attributes.

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
        """
        Tests that using a crafted alias with an SQL injection payload in a values expression raises a ValueError.

        The function verifies that the ORM correctly sanitizes column aliases to prevent potential SQL injection attacks.
        It checks that a ValueError is raised when an alias containing whitespace characters, quotation marks, semicolons, or SQL comments is used in a values expression.
        The error message returned by the ValueError indicates the restrictions on valid column alias names
        """
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

        Tests the usage of values and expression grouping in database queries.

        This test verifies the expected behavior when using the `values` method
        to retrieve specific fields from the database, and the `annotate` method
        to apply aggregation functions, such as sum, to groups of data.
        It checks that the results are correctly ordered and aggregated when
        using the `order_by` and `annotate` methods, respectively.

        The test focuses on the `Employee` model, specifically the `firstname` and
        `salary` fields, to demonstrate the grouping and aggregation functionality.

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

        Tests chained values with an aggregation expression.

        This test case verifies that chaining multiple values calls with an aggregation
        expression works as expected. It creates an Employee object, filters by name,
        and then applies a values call with and without an additional aggregation
        expression. The results are then compared to the expected output to ensure the
        correct data is being returned.

        The aggregation expression used is a sum of salaries, which is checked to
        be correctly applied when chained with other values calls. The test case checks
        two scenarios: chaining values calls with and without an additional aggregation
        expression, to cover different use cases.

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
        companies = Company.objects.values_list("name", F("ceo__salary"))
        self.assertCountEqual(
            companies, [("Example Inc.", 10), ("Foobar Ltd.", 20), ("Test GmbH", 30)]
        )

    def test_values_list_expression_flat(self):
        companies = Company.objects.values_list(F("ceo__salary"), flat=True)
        self.assertCountEqual(companies, (10, 20, 30))
