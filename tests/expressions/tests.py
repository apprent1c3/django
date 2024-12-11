import datetime
import pickle
import unittest
import uuid
from collections import namedtuple
from copy import deepcopy
from decimal import Decimal
from unittest import mock

from django.core.exceptions import FieldError
from django.db import DatabaseError, NotSupportedError, connection
from django.db.models import (
    AutoField,
    Avg,
    BinaryField,
    BooleanField,
    Case,
    CharField,
    Count,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    Exists,
    Expression,
    ExpressionList,
    ExpressionWrapper,
    F,
    FloatField,
    Func,
    IntegerField,
    Max,
    Min,
    Model,
    OrderBy,
    OuterRef,
    PositiveIntegerField,
    Q,
    StdDev,
    Subquery,
    Sum,
    TimeField,
    UUIDField,
    Value,
    Variance,
    When,
)
from django.db.models.expressions import (
    Col,
    Combinable,
    CombinedExpression,
    NegatedExpression,
    RawSQL,
    Ref,
)
from django.db.models.functions import (
    Coalesce,
    Concat,
    Left,
    Length,
    Lower,
    Substr,
    Upper,
)
from django.db.models.sql import constants
from django.db.models.sql.datastructures import Join
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import (
    Approximate,
    CaptureQueriesContext,
    isolate_apps,
    register_lookup,
)
from django.utils.functional import SimpleLazyObject

from .models import (
    UUID,
    UUIDPK,
    Company,
    Employee,
    Experiment,
    Manager,
    Number,
    RemoteEmployee,
    Result,
    SimulationRun,
    Text,
    Time,
)


class BasicExpressionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class.

        This class method creates and stores example company and employee objects to be used
        in tests. The created objects include two companies with varying attributes and a
        separate employee. The objects are stored as class attributes for easy access
        throughout the test suite.

        The example companies include 'Example Inc.', 'Foobar Ltd.', and 'Test GmbH', each
        with different properties such as number of employees, number of chairs, and CEO.
        The 'Foobar Ltd.' company is specifically marked as being based in the EU.

        The created employee, 'Max Mustermann', is assigned as the CEO of 'Test GmbH'.

        """
        cls.example_inc = Company.objects.create(
            name="Example Inc.",
            num_employees=2300,
            num_chairs=5,
            ceo=Employee.objects.create(firstname="Joe", lastname="Smith", salary=10),
        )
        cls.foobar_ltd = Company.objects.create(
            name="Foobar Ltd.",
            num_employees=3,
            num_chairs=4,
            based_in_eu=True,
            ceo=Employee.objects.create(firstname="Frank", lastname="Meyer", salary=20),
        )
        cls.max = Employee.objects.create(
            firstname="Max", lastname="Mustermann", salary=30
        )
        cls.gmbh = Company.objects.create(
            name="Test GmbH", num_employees=32, num_chairs=1, ceo=cls.max
        )

    def setUp(self):
        self.company_query = Company.objects.values(
            "name", "num_employees", "num_chairs"
        ).order_by("name", "num_employees", "num_chairs")

    def test_annotate_values_aggregate(self):
        companies = (
            Company.objects.annotate(
                salaries=F("ceo__salary"),
            )
            .values("num_employees", "salaries")
            .aggregate(
                result=Sum(
                    F("salaries") + F("num_employees"), output_field=IntegerField()
                ),
            )
        )
        self.assertEqual(companies["result"], 2395)

    def test_annotate_values_filter(self):
        """

        Tests the annotation of values using RawSQL and filtering of companies.

        This test case verifies that companies can be annotated with a custom value and 
        then filtered based on that annotation. The test ensures that the filtered 
        companies are returned in the correct order, as specified by their names.

        Checks that the companies 'example Inc', 'foobar Ltd', and 'GmbH' are correctly 
        filtered and ordered when annotated with the 'value' and filtered on the same 
        value.

        """
        companies = (
            Company.objects.annotate(
                foo=RawSQL("%s", ["value"]),
            )
            .filter(foo="value")
            .order_by("name")
        )
        self.assertSequenceEqual(
            companies,
            [self.example_inc, self.foobar_ltd, self.gmbh],
        )

    def test_annotate_values_count(self):
        companies = Company.objects.annotate(foo=RawSQL("%s", ["value"]))
        self.assertEqual(companies.count(), 3)

    @skipUnlessDBFeature("supports_boolean_expr_in_select_clause")
    def test_filtering_on_annotate_that_uses_q(self):
        self.assertEqual(
            Company.objects.annotate(
                num_employees_check=ExpressionWrapper(
                    Q(num_employees__gt=3), output_field=BooleanField()
                )
            )
            .filter(num_employees_check=True)
            .count(),
            2,
        )

    def test_filtering_on_q_that_is_boolean(self):
        self.assertEqual(
            Company.objects.filter(
                ExpressionWrapper(Q(num_employees__gt=3), output_field=BooleanField())
            ).count(),
            2,
        )

    def test_filtering_on_rawsql_that_is_boolean(self):
        self.assertEqual(
            Company.objects.filter(
                RawSQL("num_employees > %s", (3,), output_field=BooleanField()),
            ).count(),
            2,
        )

    def test_filter_inter_attribute(self):
        # We can filter on attribute relationships on same model obj, e.g.
        # find companies where the number of employees is greater
        # than the number of chairs.
        self.assertSequenceEqual(
            self.company_query.filter(num_employees__gt=F("num_chairs")),
            [
                {
                    "num_chairs": 5,
                    "name": "Example Inc.",
                    "num_employees": 2300,
                },
                {"num_chairs": 1, "name": "Test GmbH", "num_employees": 32},
            ],
        )

    def test_update(self):
        # We can set one field to have the value of another field
        # Make sure we have enough chairs
        """
        Tests the update functionality by setting the number of chairs to be equal to the number of employees for each company.

        The test case checks if the update operation successfully modifies the 'num_chairs' attribute of each company in the query result.
        It verifies the correctness of the update by comparing the resulting company data with the expected output.

        The expected outcome is a list of companies with 'num_chairs' matching their respective 'num_employees' counts, ensuring data consistency and accurate updating of company records.
        """
        self.company_query.update(num_chairs=F("num_employees"))
        self.assertSequenceEqual(
            self.company_query,
            [
                {"num_chairs": 2300, "name": "Example Inc.", "num_employees": 2300},
                {"num_chairs": 3, "name": "Foobar Ltd.", "num_employees": 3},
                {"num_chairs": 32, "name": "Test GmbH", "num_employees": 32},
            ],
        )

    def _test_slicing_of_f_expressions(self, model):
        tests = [
            (F("name")[:], "Example Inc."),
            (F("name")[:7], "Example"),
            (F("name")[:6][:5], "Examp"),  # Nested slicing.
            (F("name")[0], "E"),
            (F("name")[13], ""),
            (F("name")[8:], "Inc."),
            (F("name")[0:15], "Example Inc."),
            (F("name")[2:7], "ample"),
            (F("name")[1:][:3], "xam"),
            (F("name")[2:2], ""),
        ]
        for expression, expected in tests:
            with self.subTest(expression=expression, expected=expected):
                obj = model.objects.get(name="Example Inc.")
                try:
                    obj.name = expression
                    obj.save(update_fields=["name"])
                    obj.refresh_from_db()
                    self.assertEqual(obj.name, expected)
                finally:
                    obj.name = "Example Inc."
                    obj.save(update_fields=["name"])

    def test_slicing_of_f_expressions_charfield(self):
        self._test_slicing_of_f_expressions(Company)

    def test_slicing_of_f_expressions_textfield(self):
        Text.objects.bulk_create(
            [Text(name=company.name) for company in Company.objects.all()]
        )
        self._test_slicing_of_f_expressions(Text)

    def test_slicing_of_f_expressions_with_annotate(self):
        qs = Company.objects.annotate(
            first_three=F("name")[:3],
            after_three=F("name")[3:],
            random_four=F("name")[2:5],
            first_letter_slice=F("name")[:1],
            first_letter_index=F("name")[0],
        )
        tests = [
            ("first_three", ["Exa", "Foo", "Tes"]),
            ("after_three", ["mple Inc.", "bar Ltd.", "t GmbH"]),
            ("random_four", ["amp", "oba", "st "]),
            ("first_letter_slice", ["E", "F", "T"]),
            ("first_letter_index", ["E", "F", "T"]),
        ]
        for annotation, expected in tests:
            with self.subTest(annotation):
                self.assertCountEqual(qs.values_list(annotation, flat=True), expected)

    def test_slicing_of_f_expression_with_annotated_expression(self):
        qs = Company.objects.annotate(
            new_name=Case(
                When(based_in_eu=True, then=Concat(Value("EU:"), F("name"))),
                default=F("name"),
            ),
            first_two=F("new_name")[:3],
        )
        self.assertCountEqual(
            qs.values_list("first_two", flat=True),
            ["Exa", "EU:", "Tes"],
        )

    def test_slicing_of_f_expressions_with_negative_index(self):
        """
        Tests the handling of slicing F expressions with negative indices.

        This function verifies that F expressions raise a ValueError when attempting to slice using a negative index.
        It checks various combinations of slicing, including slice objects with negative start and stop values, 
        as well as negative integer indices. The expected error message for all cases is 'Negative indexing is not supported.'
        """
        msg = "Negative indexing is not supported."
        indexes = [slice(0, -4), slice(-4, 0), slice(-4), -5]
        for i in indexes:
            with self.subTest(i=i), self.assertRaisesMessage(ValueError, msg):
                F("name")[i]

    def test_slicing_of_f_expressions_with_slice_stop_less_than_slice_start(self):
        """
        Tests that attempting to slice an F expression with a slice stop less than the slice start raises a ValueError.

        This test ensures that invalid slice indices are properly handled, and an informative error message is provided when the slice stop is less than the slice start, indicating that the slice is not valid.

        :raises ValueError: If the slice stop is less than the slice start.

        """
        msg = "Slice stop must be greater than slice start."
        with self.assertRaisesMessage(ValueError, msg):
            F("name")[4:2]

    def test_slicing_of_f_expressions_with_invalid_type(self):
        """
        Test that slicing of F-expressions with an invalid type raises a TypeError.

        This test case verifies that attempting to slice an F-expression with a non-integer
        or non-slice value results in a TypeError being raised with a descriptive error message.

        The test is designed to ensure that the F-expression slicing logic correctly enforces
        type constraints, preventing potential errors or unexpected behavior when working with
        F-expressions in different contexts.

        :raises TypeError: If the slice argument is not an integer or a slice instance
        """
        msg = "Argument to slice must be either int or slice instance."
        with self.assertRaisesMessage(TypeError, msg):
            F("name")["error"]

    def test_slicing_of_f_expressions_with_step(self):
        msg = "Step argument is not supported."
        with self.assertRaisesMessage(ValueError, msg):
            F("name")[::4]

    def test_slicing_of_f_unsupported_field(self):
        """
        Tests that updating a model field using slicing on an unsupported field raises a NotSupportedError.

        This test case verifies that attempting to slice a field in an update operation, 
        where the field does not support slicing, results in a NotSupportedError with a 
        specific error message indicating that the field does not support slicing. The 
        test ensures that the error message is correctly propagated to the user, 
        providing clear information about the cause of the error.
        """
        msg = "This field does not support slicing."
        with self.assertRaisesMessage(NotSupportedError, msg):
            Company.objects.update(num_chairs=F("num_chairs")[:4])

    def test_slicing_of_outerref(self):
        inner = Company.objects.filter(name__startswith=OuterRef("ceo__firstname")[0])
        outer = Company.objects.filter(Exists(inner)).values_list("name", flat=True)
        self.assertSequenceEqual(outer, ["Foobar Ltd."])

    def test_arithmetic(self):
        # We can perform arithmetic operations in expressions
        # Make sure we have 2 spare chairs
        self.company_query.update(num_chairs=F("num_employees") + 2)
        self.assertSequenceEqual(
            self.company_query,
            [
                {"num_chairs": 2302, "name": "Example Inc.", "num_employees": 2300},
                {"num_chairs": 5, "name": "Foobar Ltd.", "num_employees": 3},
                {"num_chairs": 34, "name": "Test GmbH", "num_employees": 32},
            ],
        )

    def test_order_of_operations(self):
        # Law of order of operations is followed
        self.company_query.update(
            num_chairs=F("num_employees") + 2 * F("num_employees")
        )
        self.assertSequenceEqual(
            self.company_query,
            [
                {"num_chairs": 6900, "name": "Example Inc.", "num_employees": 2300},
                {"num_chairs": 9, "name": "Foobar Ltd.", "num_employees": 3},
                {"num_chairs": 96, "name": "Test GmbH", "num_employees": 32},
            ],
        )

    def test_parenthesis_priority(self):
        # Law of order of operations can be overridden by parentheses
        """

        Tests the correct application of operator precedence in the company query update operation.

        Verifies that the mathematical expression is evaluated as expected, following the standard order of operations (parentheses, exponentiation, multiplication and division, and addition and subtraction).

        The function checks if the updated company query returns the correct results after applying the formula to calculate the number of chairs, ensuring the correct application of the mathematical operations and the F() function. 

        This test case ensures data consistency by validating the output against the expected sequence of dictionaries, each containing the company name, number of employees, and the calculated number of chairs.

        """
        self.company_query.update(
            num_chairs=(F("num_employees") + 2) * F("num_employees")
        )
        self.assertSequenceEqual(
            self.company_query,
            [
                {"num_chairs": 5294600, "name": "Example Inc.", "num_employees": 2300},
                {"num_chairs": 15, "name": "Foobar Ltd.", "num_employees": 3},
                {"num_chairs": 1088, "name": "Test GmbH", "num_employees": 32},
            ],
        )

    def test_update_with_fk(self):
        # ForeignKey can become updated with the value of another ForeignKey.
        self.assertEqual(Company.objects.update(point_of_contact=F("ceo")), 3)
        self.assertQuerySetEqual(
            Company.objects.all(),
            ["Joe Smith", "Frank Meyer", "Max Mustermann"],
            lambda c: str(c.point_of_contact),
            ordered=False,
        )

    def test_update_with_none(self):
        Number.objects.create(integer=1, float=1.0)
        Number.objects.create(integer=2)
        Number.objects.filter(float__isnull=False).update(float=Value(None))
        self.assertQuerySetEqual(
            Number.objects.all(), [None, None], lambda n: n.float, ordered=False
        )

    def test_filter_with_join(self):
        # F Expressions can also span joins
        Company.objects.update(point_of_contact=F("ceo"))
        c = Company.objects.first()
        c.point_of_contact = Employee.objects.create(
            firstname="Guido", lastname="van Rossum"
        )
        c.save()

        self.assertQuerySetEqual(
            Company.objects.filter(ceo__firstname=F("point_of_contact__firstname")),
            ["Foobar Ltd.", "Test GmbH"],
            lambda c: c.name,
            ordered=False,
        )

        Company.objects.exclude(ceo__firstname=F("point_of_contact__firstname")).update(
            name="foo"
        )
        self.assertEqual(
            Company.objects.exclude(ceo__firstname=F("point_of_contact__firstname"))
            .get()
            .name,
            "foo",
        )

        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            Company.objects.exclude(
                ceo__firstname=F("point_of_contact__firstname")
            ).update(name=F("point_of_contact__lastname"))

    def test_object_update(self):
        # F expressions can be used to update attributes on single objects
        self.gmbh.num_employees = F("num_employees") + 4
        self.gmbh.save()
        self.gmbh.refresh_from_db()
        self.assertEqual(self.gmbh.num_employees, 36)

    def test_new_object_save(self):
        # We should be able to use Funcs when inserting new data
        """

        Tests the saving and retrieval of a new object instance.

        Verifies that the instance is correctly persisted to the database and
        that its attributes are saved and loaded as expected. Specifically,
        this test checks that the `name` attribute is correctly converted to
        lowercase despite being initialized with an uppercase value.

        """
        test_co = Company(
            name=Lower(Value("UPPER")), num_employees=32, num_chairs=1, ceo=self.max
        )
        test_co.save()
        test_co.refresh_from_db()
        self.assertEqual(test_co.name, "upper")

    def test_new_object_create(self):
        """
        Tests the creation of a new Company object.

        Verifies that a Company instance can be successfully created with the provided
        attributes, and that the data is correctly persisted in the database. Specifically,
        it checks that the 'name' attribute is properly transformed to lowercase during
        creation, and that the object's attributes match the expected values after
        retrieval from the database.
        """
        test_co = Company.objects.create(
            name=Lower(Value("UPPER")), num_employees=32, num_chairs=1, ceo=self.max
        )
        test_co.refresh_from_db()
        self.assertEqual(test_co.name, "upper")

    def test_object_create_with_aggregate(self):
        # Aggregates are not allowed when inserting new data
        """
        Test that creating an object with an aggregate function raises a FieldError.

        Checks that attempting to create a Company instance with a value for 'num_employees' that is an aggregate function (Max) results in the expected error message. The test ensures that the correct exception is raised with the specified message when trying to create an object with an aggregate value in a field that does not support it.
        """
        msg = (
            "Aggregate functions are not allowed in this query "
            "(num_employees=Max(Value(1)))."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Company.objects.create(
                name="Company",
                num_employees=Max(Value(1)),
                num_chairs=1,
                ceo=Employee.objects.create(
                    firstname="Just", lastname="Doit", salary=30
                ),
            )

    def test_object_update_fk(self):
        # F expressions cannot be used to update attributes which are foreign
        # keys, or attributes which involve joins.
        test_gmbh = Company.objects.get(pk=self.gmbh.pk)
        msg = 'F(ceo)": "Company.point_of_contact" must be a "Employee" instance.'
        with self.assertRaisesMessage(ValueError, msg):
            test_gmbh.point_of_contact = F("ceo")

        test_gmbh.point_of_contact = self.gmbh.ceo
        test_gmbh.save()
        test_gmbh.name = F("ceo__lastname")
        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            test_gmbh.save()

    def test_update_inherited_field_value(self):
        """
        Tests that updating an inherited field value raises a FieldError.

        This test case verifies that attempting to update a field that references a joined field in a query results in an error. It checks that the correct exception (FieldError) is raised with the expected error message when trying to update a field using a joined field reference.

        The test covers a scenario where a query tries to update the 'adjusted_salary' field of RemoteEmployee objects by referencing the 'salary' field and multiplying it by a factor. The test ensures that this operation raises an error as joined field references are not allowed in this type of query.

        Args:
            None

        Returns:
            None

        Raises:
            FieldError: With the message \"Joined field references are not permitted in this query\" when trying to update a field using a joined field reference.

        """
        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            RemoteEmployee.objects.update(adjusted_salary=F("salary") * 5)

    def test_object_update_unsaved_objects(self):
        # F expressions cannot be used to update attributes on objects which do
        # not yet exist in the database
        acme = Company(
            name="The Acme Widget Co.", num_employees=12, num_chairs=5, ceo=self.max
        )
        acme.num_employees = F("num_employees") + 16
        msg = (
            'Failed to insert expression "Col(expressions_company, '
            'expressions.Company.num_employees) + Value(16)" on '
            "expressions.Company.num_employees. F() expressions can only be "
            "used to update, not to insert."
        )
        with self.assertRaisesMessage(ValueError, msg):
            acme.save()

        acme.num_employees = 12
        acme.name = Lower(F("name"))
        msg = (
            'Failed to insert expression "Lower(Col(expressions_company, '
            'expressions.Company.name))" on expressions.Company.name. F() '
            "expressions can only be used to update, not to insert."
        )
        with self.assertRaisesMessage(ValueError, msg):
            acme.save()

    def test_ticket_11722_iexact_lookup(self):
        """
        Tests the iexact lookup type in the Django ORM.

        Verifies that the iexact lookup correctly matches fields in a case-insensitive manner.
         Specifically, it checks that a filter on the 'firstname' field that is iexact to the 'lastname' field
         returns the expected results.

        The test case creates two Employee instances with different first and last names, and then queries
        for Employees where the firstname is iexact to the lastname, expecting only one result to be returned.
        """
        Employee.objects.create(firstname="John", lastname="Doe")
        test = Employee.objects.create(firstname="Test", lastname="test")

        queryset = Employee.objects.filter(firstname__iexact=F("lastname"))
        self.assertSequenceEqual(queryset, [test])

    def test_ticket_16731_startswith_lookup(self):
        Employee.objects.create(firstname="John", lastname="Doe")
        e2 = Employee.objects.create(firstname="Jack", lastname="Jackson")
        e3 = Employee.objects.create(firstname="Jack", lastname="jackson")
        self.assertSequenceEqual(
            Employee.objects.filter(lastname__startswith=F("firstname")),
            [e2, e3] if connection.features.has_case_insensitive_like else [e2],
        )
        qs = Employee.objects.filter(lastname__istartswith=F("firstname")).order_by(
            "pk"
        )
        self.assertSequenceEqual(qs, [e2, e3])

    def test_ticket_18375_join_reuse(self):
        # Reverse multijoin F() references and the lookup target the same join.
        # Pre #18375 the F() join was generated first and the lookup couldn't
        # reuse that join.
        """
        Tests that the ORM correctly reuses existing joins when filtering on related objects.

        This test case ensures that Django's query optimization mechanisms are functioning as expected,
        specifically with regards to avoiding unnecessary join operations when filtering on related models.
        It verifies that the generated SQL query contains only one join operation, demonstrating that the ORM
        is able to reuse existing joins instead of creating redundant ones.
        """
        qs = Employee.objects.filter(
            company_ceo_set__num_chairs=F("company_ceo_set__num_employees")
        )
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_ticket_18375_kwarg_ordering(self):
        # The next query was dict-randomization dependent - if the "gte=1"
        # was seen first, then the F() will reuse the join generated by the
        # gte lookup, if F() was seen first, then it generated a join the
        # other lookups could not reuse.
        """
        Tests that the queryset for Employee objects with filtered company CEO sets is generated with the correct JOIN ordering.

        The test verifies that the resulting SQL query contains only one JOIN operation, ensuring efficient database performance.
        It checks for the condition where the number of chairs in the company CEO set is equal to the number of employees and greater than or equal to 1.
        The test case is referenced by ticket number 18375, which tracks the issue related to keyword argument ordering in queryset generation.
        """
        qs = Employee.objects.filter(
            company_ceo_set__num_chairs=F("company_ceo_set__num_employees"),
            company_ceo_set__num_chairs__gte=1,
        )
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_ticket_18375_kwarg_ordering_2(self):
        # Another similar case for F() than above. Now we have the same join
        # in two filter kwargs, one in the lhs lookup, one in F. Here pre
        # #18375 the amount of joins generated was random if dict
        # randomization was enabled, that is the generated query dependent
        # on which clause was seen first.
        qs = Employee.objects.filter(
            company_ceo_set__num_employees=F("pk"),
            pk=F("company_ceo_set__num_employees"),
        )
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_ticket_18375_chained_filters(self):
        # F() expressions do not reuse joins from previous filter.
        """
        Tests the chaining of filters on related models with F expressions.

        Specifically, this test checks that the ORM correctly generates a query with the expected number of joins when applying two filters on a related model's field and its own field.

        The test verifies that the resulting query string contains two JOIN operations, ensuring that the filters are applied correctly without causing unnecessary database queries or joins.

        This test case is related to ticket #18375, which addresses issues with chained filters on related models with F expressions.
        """
        qs = Employee.objects.filter(company_ceo_set__num_employees=F("pk")).filter(
            company_ceo_set__num_employees=F("company_ceo_set__num_employees")
        )
        self.assertEqual(str(qs.query).count("JOIN"), 2)

    def test_order_by_exists(self):
        mary = Employee.objects.create(
            firstname="Mary", lastname="Mustermann", salary=20
        )
        mustermanns_by_seniority = Employee.objects.filter(
            lastname="Mustermann"
        ).order_by(
            # Order by whether the employee is the CEO of a company
            Exists(Company.objects.filter(ceo=OuterRef("pk"))).desc()
        )
        self.assertSequenceEqual(mustermanns_by_seniority, [self.max, mary])

    def test_order_by_multiline_sql(self):
        raw_order_by = (
            RawSQL(
                """
                CASE WHEN num_employees > 1000
                     THEN num_chairs
                     ELSE 0 END
                """,
                [],
            ).desc(),
            RawSQL(
                """
                CASE WHEN num_chairs > 1
                     THEN 1
                     ELSE 0 END
                """,
                [],
            ).asc(),
        )
        for qs in (
            Company.objects.all(),
            Company.objects.distinct(),
        ):
            with self.subTest(qs=qs):
                self.assertSequenceEqual(
                    qs.order_by(*raw_order_by),
                    [self.example_inc, self.gmbh, self.foobar_ltd],
                )

    def test_outerref(self):
        """
        Tests the usage of OuterRef in a subquery to reference an outer query.

        Verifies that attempting to use a queryset with an OuterRef outside of a subquery raises a ValueError.
        Additionally, checks that annotating a queryset with an Exists condition using the OuterRef works as expected.

        This test case ensures that the OuterRef is correctly used to reference the outer query and that it is only used within a subquery context.
        It also validates the usage of Exists to check for the existence of related objects in the database.
        """
        inner = Company.objects.filter(point_of_contact=OuterRef("pk"))
        msg = (
            "This queryset contains a reference to an outer query and may only "
            "be used in a subquery."
        )
        with self.assertRaisesMessage(ValueError, msg):
            inner.exists()

        outer = Employee.objects.annotate(is_point_of_contact=Exists(inner))
        self.assertIs(outer.exists(), True)

    def test_exist_single_field_output_field(self):
        queryset = Company.objects.values("pk")
        self.assertIsInstance(Exists(queryset).output_field, BooleanField)

    def test_subquery(self):
        Company.objects.filter(name="Example Inc.").update(
            point_of_contact=Employee.objects.get(firstname="Joe", lastname="Smith"),
            ceo=self.max,
        )
        Employee.objects.create(firstname="Bob", lastname="Brown", salary=40)
        qs = (
            Employee.objects.annotate(
                is_point_of_contact=Exists(
                    Company.objects.filter(point_of_contact=OuterRef("pk"))
                ),
                is_not_point_of_contact=~Exists(
                    Company.objects.filter(point_of_contact=OuterRef("pk"))
                ),
                is_ceo_of_small_company=Exists(
                    Company.objects.filter(num_employees__lt=200, ceo=OuterRef("pk"))
                ),
                is_ceo_small_2=~~Exists(
                    Company.objects.filter(num_employees__lt=200, ceo=OuterRef("pk"))
                ),
                largest_company=Subquery(
                    Company.objects.order_by("-num_employees")
                    .filter(Q(ceo=OuterRef("pk")) | Q(point_of_contact=OuterRef("pk")))
                    .values("name")[:1],
                    output_field=CharField(),
                ),
            )
            .values(
                "firstname",
                "is_point_of_contact",
                "is_not_point_of_contact",
                "is_ceo_of_small_company",
                "is_ceo_small_2",
                "largest_company",
            )
            .order_by("firstname")
        )

        results = list(qs)
        # Could use Coalesce(subq, Value('')) instead except for the bug in
        # oracledb mentioned in #23843.
        bob = results[0]
        if (
            bob["largest_company"] == ""
            and connection.features.interprets_empty_strings_as_nulls
        ):
            bob["largest_company"] = None

        self.assertEqual(
            results,
            [
                {
                    "firstname": "Bob",
                    "is_point_of_contact": False,
                    "is_not_point_of_contact": True,
                    "is_ceo_of_small_company": False,
                    "is_ceo_small_2": False,
                    "largest_company": None,
                },
                {
                    "firstname": "Frank",
                    "is_point_of_contact": False,
                    "is_not_point_of_contact": True,
                    "is_ceo_of_small_company": True,
                    "is_ceo_small_2": True,
                    "largest_company": "Foobar Ltd.",
                },
                {
                    "firstname": "Joe",
                    "is_point_of_contact": True,
                    "is_not_point_of_contact": False,
                    "is_ceo_of_small_company": False,
                    "is_ceo_small_2": False,
                    "largest_company": "Example Inc.",
                },
                {
                    "firstname": "Max",
                    "is_point_of_contact": False,
                    "is_not_point_of_contact": True,
                    "is_ceo_of_small_company": True,
                    "is_ceo_small_2": True,
                    "largest_company": "Example Inc.",
                },
            ],
        )
        # A less elegant way to write the same query: this uses a LEFT OUTER
        # JOIN and an IS NULL, inside a WHERE NOT IN which is probably less
        # efficient than EXISTS.
        self.assertCountEqual(
            qs.filter(is_point_of_contact=True).values("pk"),
            Employee.objects.exclude(company_point_of_contact_set=None).values("pk"),
        )

    def test_subquery_eq(self):
        """

        Tests the usage of subqueries in Django ORM queries.

        Verifies that the Exists subquery annotations can be used to filter Employee objects based on their relationships with Company objects.
        Checks that an Employee is a CEO but not a point of contact and is associated with a small company.
        Asserts that the annotations for 'is_ceo', 'is_point_of_contact', and 'small_company' are distinct and correctly applied to the query set.

        This test case ensures the correctness of using subqueries with Exists and OuterRef in Django ORM, allowing for complex filtering operations based on related objects' properties.

        """
        qs = Employee.objects.annotate(
            is_ceo=Exists(Company.objects.filter(ceo=OuterRef("pk"))),
            is_point_of_contact=Exists(
                Company.objects.filter(point_of_contact=OuterRef("pk")),
            ),
            small_company=Exists(
                queryset=Company.objects.filter(num_employees__lt=200),
            ),
        ).filter(is_ceo=True, is_point_of_contact=False, small_company=True)
        self.assertNotEqual(
            qs.query.annotations["is_ceo"],
            qs.query.annotations["is_point_of_contact"],
        )
        self.assertNotEqual(
            qs.query.annotations["is_ceo"],
            qs.query.annotations["small_company"],
        )

    def test_subquery_sql(self):
        employees = Employee.objects.all()
        employees_subquery = Subquery(employees)
        self.assertIs(employees_subquery.query.subquery, True)
        self.assertIs(employees.query.subquery, False)
        compiler = employees_subquery.query.get_compiler(connection=connection)
        sql, _ = employees_subquery.as_sql(compiler, connection)
        self.assertIn("(SELECT ", sql)

    def test_in_subquery(self):
        # This is a contrived test (and you really wouldn't write this query),
        # but it is a succinct way to test the __in=Subquery() construct.
        small_companies = Company.objects.filter(num_employees__lt=200).values("pk")
        subquery_test = Company.objects.filter(pk__in=Subquery(small_companies))
        self.assertCountEqual(subquery_test, [self.foobar_ltd, self.gmbh])
        subquery_test2 = Company.objects.filter(
            pk=Subquery(small_companies.filter(num_employees=3))
        )
        self.assertCountEqual(subquery_test2, [self.foobar_ltd])

    def test_uuid_pk_subquery(self):
        u = UUIDPK.objects.create()
        UUID.objects.create(uuid_fk=u)
        qs = UUIDPK.objects.filter(id__in=Subquery(UUID.objects.values("uuid_fk__id")))
        self.assertCountEqual(qs, [u])

    def test_nested_subquery(self):
        inner = Company.objects.filter(point_of_contact=OuterRef("pk"))
        outer = Employee.objects.annotate(is_point_of_contact=Exists(inner))
        contrived = Employee.objects.annotate(
            is_point_of_contact=Subquery(
                outer.filter(pk=OuterRef("pk")).values("is_point_of_contact"),
                output_field=BooleanField(),
            ),
        )
        self.assertCountEqual(contrived.values_list(), outer.values_list())

    def test_nested_subquery_join_outer_ref(self):
        inner = Employee.objects.filter(pk=OuterRef("ceo__pk")).values("pk")
        qs = Employee.objects.annotate(
            ceo_company=Subquery(
                Company.objects.filter(
                    ceo__in=inner,
                    ceo__pk=OuterRef("pk"),
                ).values("pk"),
            ),
        )
        self.assertSequenceEqual(
            qs.values_list("ceo_company", flat=True),
            [self.example_inc.pk, self.foobar_ltd.pk, self.gmbh.pk],
        )

    def test_nested_subquery_outer_ref_2(self):
        first = Time.objects.create(time="09:00")
        second = Time.objects.create(time="17:00")
        third = Time.objects.create(time="21:00")
        SimulationRun.objects.bulk_create(
            [
                SimulationRun(start=first, end=second, midpoint="12:00"),
                SimulationRun(start=first, end=third, midpoint="15:00"),
                SimulationRun(start=second, end=first, midpoint="00:00"),
            ]
        )
        inner = Time.objects.filter(
            time=OuterRef(OuterRef("time")), pk=OuterRef("start")
        ).values("time")
        middle = SimulationRun.objects.annotate(other=Subquery(inner)).values("other")[
            :1
        ]
        outer = Time.objects.annotate(other=Subquery(middle, output_field=TimeField()))
        # This is a contrived example. It exercises the double OuterRef form.
        self.assertCountEqual(outer, [first, second, third])

    def test_nested_subquery_outer_ref_with_autofield(self):
        """

        Tests the usage of nested subqueries with outer references, specifically when an auto field is involved.

        This function verifies that a subquery referencing an outer query's auto field can correctly retrieve related objects.
        It creates a set of objects representing times and simulation runs, then uses nested subqueries to fetch times related to
        these simulation runs. The result is compared to the expected set of times to ensure the correctness of the subquery.

        The test covers the following key aspects:
        - Creating objects with auto fields
        - Using OuterRef to reference outer query fields
        - Employing Subquery to nest queries
        - Annotating query results with subquery values
        - Validating query results against expected outcomes

        """
        first = Time.objects.create(time="09:00")
        second = Time.objects.create(time="17:00")
        SimulationRun.objects.create(start=first, end=second, midpoint="12:00")
        inner = SimulationRun.objects.filter(start=OuterRef(OuterRef("pk"))).values(
            "start"
        )
        middle = Time.objects.annotate(other=Subquery(inner)).values("other")[:1]
        outer = Time.objects.annotate(
            other=Subquery(middle, output_field=IntegerField())
        )
        # This exercises the double OuterRef form with AutoField as pk.
        self.assertCountEqual(outer, [first, second])

    def test_annotations_within_subquery(self):
        Company.objects.filter(num_employees__lt=50).update(
            ceo=Employee.objects.get(firstname="Frank")
        )
        inner = (
            Company.objects.filter(ceo=OuterRef("pk"))
            .values("ceo")
            .annotate(total_employees=Sum("num_employees"))
            .values("total_employees")
        )
        outer = Employee.objects.annotate(total_employees=Subquery(inner)).filter(
            salary__lte=Subquery(inner)
        )
        self.assertSequenceEqual(
            outer.order_by("-total_employees").values("salary", "total_employees"),
            [
                {"salary": 10, "total_employees": 2300},
                {"salary": 20, "total_employees": 35},
            ],
        )

    def test_subquery_references_joined_table_twice(self):
        """
        ..:func:: test_subquery_references_joined_table_twice

            Tests if a subquery referencing a joined table twice returns the expected results.

            This test case involves creating a subquery that filters companies based on the number of chairs and employees in relation to the salary of the CEO and point of contact. 
            The outer query then checks for the existence of companies that match the subquery conditions.

            The expected outcome is that no companies should match these conditions, resulting in an empty query set.
        """
        inner = Company.objects.filter(
            num_chairs__gte=OuterRef("ceo__salary"),
            num_employees__gte=OuterRef("point_of_contact__salary"),
        )
        # Another contrived example (there is no need to have a subquery here)
        outer = Company.objects.filter(pk__in=Subquery(inner.values("pk")))
        self.assertFalse(outer.exists())

    def test_subquery_filter_by_aggregate(self):
        """

        Tests filtering of Number objects using a subquery on Employee objects.
        The subquery filters employees by salary matching the integer value of a Number object,
        and then annotates the Number object with a count of valuable employees.
        The test asserts that the Number object with a float value is correctly filtered.

        """
        Number.objects.create(integer=1000, float=1.2)
        Employee.objects.create(salary=1000)
        qs = Number.objects.annotate(
            min_valuable_count=Subquery(
                Employee.objects.filter(
                    salary=OuterRef("integer"),
                )
                .annotate(cnt=Count("salary"))
                .filter(cnt__gt=0)
                .values("cnt")[:1]
            ),
        )
        self.assertEqual(qs.get().float, 1.2)

    def test_subquery_filter_by_lazy(self):
        """
        Tests filtering a query set using a subquery with a lazy-loaded object.

        This test case verifies that a Django QuerySet can be filtered by a subquery
        that references an annotated field, using a lazy-loaded object as the filter value.

        The test creates a manager instance, assigns it to an existing object, and then
        uses a subquery to annotate a Company QuerySet with the CEO's manager. It then
        filters the QuerySet using a lazy-loaded version of the manager object, and
        asserts that the resulting QuerySet contains the expected Company instance.
        """
        self.max.manager = Manager.objects.create(name="Manager")
        self.max.save()
        max_manager = SimpleLazyObject(
            lambda: Manager.objects.get(pk=self.max.manager.pk)
        )
        qs = Company.objects.annotate(
            ceo_manager=Subquery(
                Employee.objects.filter(
                    lastname=OuterRef("ceo__lastname"),
                ).values("manager"),
            ),
        ).filter(ceo_manager=max_manager)
        self.assertEqual(qs.get(), self.gmbh)

    def test_aggregate_subquery_annotation(self):
        with self.assertNumQueries(1) as ctx:
            aggregate = Company.objects.annotate(
                ceo_salary=Subquery(
                    Employee.objects.filter(
                        id=OuterRef("ceo_id"),
                    ).values("salary")
                ),
            ).aggregate(
                ceo_salary_gt_20=Count("pk", filter=Q(ceo_salary__gt=20)),
            )
        self.assertEqual(aggregate, {"ceo_salary_gt_20": 1})
        # Aggregation over a subquery annotation doesn't annotate the subquery
        # twice in the inner query.
        sql = ctx.captured_queries[0]["sql"]
        self.assertLessEqual(sql.count("SELECT"), 3)
        # GROUP BY isn't required to aggregate over a query that doesn't
        # contain nested aggregates.
        self.assertNotIn("GROUP BY", sql)

    def test_object_create_with_f_expression_in_subquery(self):
        """

        Tests the creation of an object with a subquery that uses an F expression.

        Verifies that a Company object can be created with a num_employees value that is 
        derived from a subquery. The subquery calculates the maximum number of employees 
        from existing Company objects and then increments this value by 1, demonstrating 
        the use of F expressions within subqueries to perform dynamic calculations.

        The test case validates that the created object has the expected number of employees, 
        ensuring that the subquery and F expression are evaluated correctly.

        """
        Company.objects.create(
            name="Big company", num_employees=100000, num_chairs=1, ceo=self.max
        )
        biggest_company = Company.objects.create(
            name="Biggest company",
            num_chairs=1,
            ceo=self.max,
            num_employees=Subquery(
                Company.objects.order_by("-num_employees")
                .annotate(max_num_employees=Max("num_employees"))
                .annotate(new_num_employees=F("max_num_employees") + 1)
                .values("new_num_employees")[:1]
            ),
        )
        biggest_company.refresh_from_db()
        self.assertEqual(biggest_company.num_employees, 100001)

    @skipUnlessDBFeature("supports_over_clause")
    def test_aggregate_rawsql_annotation(self):
        """

        Tests the annotation of a model's queryset with a RawSQL expression containing an OVER clause,
        specifically for aggregate functions, and verifies that the resulting SQL query does not include
        a GROUP BY statement.

        The test case ensures that the database query is executed efficiently, with only a single query
        being performed, and validates the expected count of results from the aggregated queryset.

        """
        with self.assertNumQueries(1) as ctx:
            aggregate = Company.objects.annotate(
                salary=RawSQL("SUM(num_chairs) OVER (ORDER BY num_employees)", []),
            ).aggregate(
                count=Count("pk"),
            )
            self.assertEqual(aggregate, {"count": 3})
        sql = ctx.captured_queries[0]["sql"]
        self.assertNotIn("GROUP BY", sql)

    def test_explicit_output_field(self):
        """

        Tests that an explicit output field defined in a subclass of Func
        is inherited by an instance of another subclass of Func when used
        as an argument, even if the outer subclass does not define an output field.

        Verifies that the output field of a nested function expression
        is determined by the innermost function that defines an output field.

        """
        class FuncA(Func):
            output_field = CharField()

        class FuncB(Func):
            pass

        expr = FuncB(FuncA())
        self.assertEqual(expr.output_field, FuncA.output_field)

    def test_outerref_mixed_case_table_name(self):
        inner = Result.objects.filter(result_time__gte=OuterRef("experiment__assigned"))
        outer = Result.objects.filter(pk__in=Subquery(inner.values("pk")))
        self.assertFalse(outer.exists())

    def test_outerref_with_operator(self):
        """
        Tests the usage of outer references with operators in database queries.

        This test case verifies that companies can be filtered based on a condition that 
        relates the company's number of employees to the salary of its CEO, demonstrating 
        the correct application of outer references with arithmetic operations in a subquery.

        It ensures that the resulting company matches the expected name, confirming the 
        validity of the query logic.
        """
        inner = Company.objects.filter(num_employees=OuterRef("ceo__salary") + 2)
        outer = Company.objects.filter(pk__in=Subquery(inner.values("pk")))
        self.assertEqual(outer.get().name, "Test GmbH")

    def test_nested_outerref_with_function(self):
        """
        Tests the usage of nested OuterRef in a Django ORM query with a function.

        This test case verifies that a complex query can correctly resolve the CEO of a 
        company by using nested OuterRef to link the point of contact and CEO. Specifically, 
        it checks that an Employee is correctly matched with the company (Test GmbH) for 
        which they are the CEO, when that company's point of contact shares a similar 
        lastname with the Employee being queried.

        The test ensures that the annotation and filtering process correctly yields the 
        expected company name, confirming that the nested OuterRef is functioning 
        correctly in the context of the Subquery and OuterRef operations.
        """
        self.gmbh.point_of_contact = Employee.objects.get(lastname="Meyer")
        self.gmbh.save()
        inner = Employee.objects.filter(
            lastname__startswith=Left(OuterRef(OuterRef("lastname")), 1),
        )
        qs = Employee.objects.annotate(
            ceo_company=Subquery(
                Company.objects.filter(
                    point_of_contact__in=inner,
                    ceo__pk=OuterRef("pk"),
                ).values("name"),
            ),
        ).filter(ceo_company__isnull=False)
        self.assertEqual(qs.get().ceo_company, "Test GmbH")

    def test_annotation_with_outerref(self):
        gmbh_salary = Company.objects.annotate(
            max_ceo_salary_raise=Subquery(
                Company.objects.annotate(
                    salary_raise=OuterRef("num_employees") + F("num_employees"),
                )
                .order_by("-salary_raise")
                .values("salary_raise")[:1],
                output_field=IntegerField(),
            ),
        ).get(pk=self.gmbh.pk)
        self.assertEqual(gmbh_salary.max_ceo_salary_raise, 2332)

    def test_annotation_with_nested_outerref(self):
        """

        Tests the annotation of employees with a subquery referencing a nested outer reference.

        This test case covers a complex query scenario where employees are annotated with 
        the name of the company for which they are the CEO, but only if another employee 
        with a similar last name is the point of contact for that company. The test verifies 
        that the correct company name is returned for an employee that matches this condition.

        The test scenario involves creating a company with a point of contact, then using 
        Django's ORM to construct a query that annotates employees with the name of their 
        company, if they are the CEO and another employee with a similar last name is the 
        point of contact for that company.

        """
        self.gmbh.point_of_contact = Employee.objects.get(lastname="Meyer")
        self.gmbh.save()
        inner = Employee.objects.annotate(
            outer_lastname=OuterRef(OuterRef("lastname")),
        ).filter(lastname__startswith=Left("outer_lastname", 1))
        qs = Employee.objects.annotate(
            ceo_company=Subquery(
                Company.objects.filter(
                    point_of_contact__in=inner,
                    ceo__pk=OuterRef("pk"),
                ).values("name"),
            ),
        ).filter(ceo_company__isnull=False)
        self.assertEqual(qs.get().ceo_company, "Test GmbH")

    def test_annotation_with_deeply_nested_outerref(self):
        """
        Tests the use of nested OuterRef annotations in database queries to filter employees based on the location of their company and secretary. 

        Specifically, verifies that an employee can be retrieved if their company and secretary are both based in the EU, using a deeply nested exists clause to check the secretary's details. 

        The test creates sample data including an employee, a manager, and their relationships, then uses a complex query to filter employees and assert that the correct employee is returned.
        """
        bob = Employee.objects.create(firstname="Bob", based_in_eu=True)
        self.max.manager = Manager.objects.create(name="Rock", secretary=bob)
        self.max.save()
        qs = Employee.objects.filter(
            Exists(
                Manager.objects.filter(
                    Exists(
                        Employee.objects.filter(
                            pk=OuterRef("secretary__pk"),
                        )
                        .annotate(
                            secretary_based_in_eu=OuterRef(OuterRef("based_in_eu"))
                        )
                        .filter(
                            Exists(
                                Company.objects.filter(
                                    # Inner OuterRef refers to an outer
                                    # OuterRef (not ResolvedOuterRef).
                                    based_in_eu=OuterRef("secretary_based_in_eu")
                                )
                            )
                        )
                    ),
                    secretary__pk=OuterRef("pk"),
                )
            )
        )
        self.assertEqual(qs.get(), bob)

    def test_pickle_expression(self):
        """
        Tests that a Value expression can be successfully pickled and unpickled, 
        resulting in an equivalent object. 

        This test ensures that the expression can be serialized and deserialized 
        without losing its value or functionality, which is a crucial aspect of 
        expression persistence and reuse.
        """
        expr = Value(1)
        expr.convert_value  # populate cached property
        self.assertEqual(pickle.loads(pickle.dumps(expr)), expr)

    def test_incorrect_field_in_F_expression(self):
        """

        Tests that using an incorrect field name in an F expression raises a FieldError.
        The function verifies that attempting to filter objects based on a non-existent field
        results in a FieldError with a descriptive error message, ensuring data integrity
        and preventing incorrect field references in database queries.

        :raises FieldError: When an invalid field name is used in the F expression.

        """
        with self.assertRaisesMessage(
            FieldError, "Cannot resolve keyword 'nope' into field."
        ):
            list(Employee.objects.filter(firstname=F("nope")))

    def test_incorrect_joined_field_in_F_expression(self):
        with self.assertRaisesMessage(
            FieldError, "Cannot resolve keyword 'nope' into field."
        ):
            list(Company.objects.filter(ceo__pk=F("point_of_contact__nope")))

    def test_exists_in_filter(self):
        """
        Tests the Exists filter functionality by verifying that two different querysets,
        QS1 and QS2, which use Exists and annotate with Exists respectively, return the same results.
        Also checks that excluding the Exists condition returns an empty queryset and that
        excluding the negation of Exists returns the same results as QS2.
        """
        inner = Company.objects.filter(ceo=OuterRef("pk")).values("pk")
        qs1 = Employee.objects.filter(Exists(inner))
        qs2 = Employee.objects.annotate(found=Exists(inner)).filter(found=True)
        self.assertCountEqual(qs1, qs2)
        self.assertFalse(Employee.objects.exclude(Exists(inner)).exists())
        self.assertCountEqual(qs2, Employee.objects.exclude(~Exists(inner)))

    def test_subquery_in_filter(self):
        inner = Company.objects.filter(ceo=OuterRef("pk")).values("based_in_eu")
        self.assertSequenceEqual(
            Employee.objects.filter(Subquery(inner)),
            [self.foobar_ltd.ceo],
        )

    def test_subquery_group_by_outerref_in_filter(self):
        inner = (
            Company.objects.annotate(
                employee=OuterRef("pk"),
            )
            .values("employee")
            .annotate(
                min_num_chairs=Min("num_chairs"),
            )
            .values("ceo")
        )
        self.assertIs(Employee.objects.filter(pk__in=Subquery(inner)).exists(), True)

    def test_case_in_filter_if_boolean_output_field(self):
        is_ceo = Company.objects.filter(ceo=OuterRef("pk"))
        is_poc = Company.objects.filter(point_of_contact=OuterRef("pk"))
        qs = Employee.objects.filter(
            Case(
                When(Exists(is_ceo), then=True),
                When(Exists(is_poc), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        )
        self.assertCountEqual(qs, [self.example_inc.ceo, self.foobar_ltd.ceo, self.max])

    def test_boolean_expression_combined(self):
        is_ceo = Company.objects.filter(ceo=OuterRef("pk"))
        is_poc = Company.objects.filter(point_of_contact=OuterRef("pk"))
        self.gmbh.point_of_contact = self.max
        self.gmbh.save()
        self.assertCountEqual(
            Employee.objects.filter(Exists(is_ceo) | Exists(is_poc)),
            [self.example_inc.ceo, self.foobar_ltd.ceo, self.max],
        )
        self.assertCountEqual(
            Employee.objects.filter(Exists(is_ceo) & Exists(is_poc)),
            [self.max],
        )
        self.assertCountEqual(
            Employee.objects.filter(Exists(is_ceo) & Q(salary__gte=30)),
            [self.max],
        )
        self.assertCountEqual(
            Employee.objects.filter(Exists(is_poc) | Q(salary__lt=15)),
            [self.example_inc.ceo, self.max],
        )
        self.assertCountEqual(
            Employee.objects.filter(Q(salary__gte=30) & Exists(is_ceo)),
            [self.max],
        )
        self.assertCountEqual(
            Employee.objects.filter(Q(salary__lt=15) | Exists(is_poc)),
            [self.example_inc.ceo, self.max],
        )

    def test_boolean_expression_combined_with_empty_Q(self):
        """
        Tests the combination of boolean expressions with an empty Q object in Django ORM queries.

        This test case verifies that when an Exists condition, which checks for the existence of a related object, is combined with an empty Q object using logical operators (&, |), the resulting query produces the expected results.

        The test covers various combinations of logical operators and nesting of Q objects, ensuring that the query correctly filters objects based on the specified conditions.

        The test case specifically checks that an Employee object is correctly filtered when its related Company object has a point of contact that exists in the database, and that the filter condition is correctly combined with an empty Q object.

        The test uses a set of predefined test cases to verify the correctness of the query results, ensuring that the expected Employee object is returned in all cases.
        """
        is_poc = Company.objects.filter(point_of_contact=OuterRef("pk"))
        self.gmbh.point_of_contact = self.max
        self.gmbh.save()
        tests = [
            Exists(is_poc) & Q(),
            Q() & Exists(is_poc),
            Exists(is_poc) | Q(),
            Q() | Exists(is_poc),
            Q(Exists(is_poc)) & Q(),
            Q() & Q(Exists(is_poc)),
            Q(Exists(is_poc)) | Q(),
            Q() | Q(Exists(is_poc)),
        ]
        for conditions in tests:
            with self.subTest(conditions):
                self.assertCountEqual(Employee.objects.filter(conditions), [self.max])

    def test_boolean_expression_in_Q(self):
        """

        Tests that a boolean expression using a subquery can correctly identify 
        an employee that serves as the point of contact for a company.

        Checks that when an employee is assigned as the point of contact for a company,
        the Exists subquery in the Q expression correctly evaluates to True for that employee.

        """
        is_poc = Company.objects.filter(point_of_contact=OuterRef("pk"))
        self.gmbh.point_of_contact = self.max
        self.gmbh.save()
        self.assertCountEqual(Employee.objects.filter(Q(Exists(is_poc))), [self.max])


class IterableLookupInnerExpressionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the Company and Employee models.

        This method creates a set of companies with varying numbers of employees and chairs,
        each with a single CEO. The created companies are stored as class attributes,
        allowing them to be used in tests.

        Attributes:
            c5020: Company with 50 employees and 20 chairs
            c5040: Company with 50 employees and 40 chairs
            c5050: Company with 50 employees and 50 chairs
            c5060: Company with 50 employees and 60 chairs
            c99300: Company with 99 employees and 300 chairs

        Note:
            The test data includes a range of companies to cover different scenarios,
            ensuring that tests can adequately cover the functionality of the Company model.
        """
        ceo = Employee.objects.create(firstname="Just", lastname="Doit", salary=30)
        # MySQL requires that the values calculated for expressions don't pass
        # outside of the field's range, so it's inconvenient to use the values
        # in the more general tests.
        cls.c5020 = Company.objects.create(
            name="5020 Ltd", num_employees=50, num_chairs=20, ceo=ceo
        )
        cls.c5040 = Company.objects.create(
            name="5040 Ltd", num_employees=50, num_chairs=40, ceo=ceo
        )
        cls.c5050 = Company.objects.create(
            name="5050 Ltd", num_employees=50, num_chairs=50, ceo=ceo
        )
        cls.c5060 = Company.objects.create(
            name="5060 Ltd", num_employees=50, num_chairs=60, ceo=ceo
        )
        cls.c99300 = Company.objects.create(
            name="99300 Ltd", num_employees=99, num_chairs=300, ceo=ceo
        )

    def test_in_lookup_allows_F_expressions_and_expressions_for_integers(self):
        # __in lookups can use F() expressions for integers.
        queryset = Company.objects.filter(num_employees__in=([F("num_chairs") - 10]))
        self.assertSequenceEqual(queryset, [self.c5060])
        self.assertCountEqual(
            Company.objects.filter(
                num_employees__in=([F("num_chairs") - 10, F("num_chairs") + 10])
            ),
            [self.c5040, self.c5060],
        )
        self.assertCountEqual(
            Company.objects.filter(
                num_employees__in=(
                    [F("num_chairs") - 10, F("num_chairs"), F("num_chairs") + 10]
                )
            ),
            [self.c5040, self.c5050, self.c5060],
        )

    def test_expressions_range_lookups_join_choice(self):
        """

        Tests the functionality of range lookups in expressions with joins.

        This function verifies that the range lookup with the midpoint field correctly
        filters SimulationRun instances where the midpoint falls within the range of 
        start and end times. It also checks the join type used in the query. The 
        function tests both the filtering and exclusion of instances based on the 
        range condition.

        The test covers various scenarios, including instances with both start and end 
        times, and instances with either or both of these times as None.

        """
        midpoint = datetime.time(13, 0)
        t1 = Time.objects.create(time=datetime.time(12, 0))
        t2 = Time.objects.create(time=datetime.time(14, 0))
        s1 = SimulationRun.objects.create(start=t1, end=t2, midpoint=midpoint)
        SimulationRun.objects.create(start=t1, end=None, midpoint=midpoint)
        SimulationRun.objects.create(start=None, end=t2, midpoint=midpoint)
        SimulationRun.objects.create(start=None, end=None, midpoint=midpoint)

        queryset = SimulationRun.objects.filter(
            midpoint__range=[F("start__time"), F("end__time")]
        )
        self.assertSequenceEqual(queryset, [s1])
        for alias in queryset.query.alias_map.values():
            if isinstance(alias, Join):
                self.assertEqual(alias.join_type, constants.INNER)

        queryset = SimulationRun.objects.exclude(
            midpoint__range=[F("start__time"), F("end__time")]
        )
        self.assertQuerySetEqual(queryset, [], ordered=False)
        for alias in queryset.query.alias_map.values():
            if isinstance(alias, Join):
                self.assertEqual(alias.join_type, constants.LOUTER)

    def test_range_lookup_allows_F_expressions_and_expressions_for_integers(self):
        # Range lookups can use F() expressions for integers.
        """

        Tests Django's range lookup functionality with F-expressions and integer values.

        This test case verifies that the range lookup can successfully filter objects
        based on a range defined by F-expressions, which represent database columns,
        and integer values. The test covers various scenarios, including filtering
        with a fixed upper bound, using arithmetic operations on F-expressions to
        define the range, and mixing F-expressions with integer values.

        The test checks that the lookup correctly returns the expected set of objects
        for each scenario, ensuring that the range lookup behaves as expected and
        returns the correct results.

        """
        Company.objects.filter(num_employees__exact=F("num_chairs"))
        self.assertCountEqual(
            Company.objects.filter(num_employees__range=(F("num_chairs"), 100)),
            [self.c5020, self.c5040, self.c5050],
        )
        self.assertCountEqual(
            Company.objects.filter(
                num_employees__range=(F("num_chairs") - 10, F("num_chairs") + 10)
            ),
            [self.c5040, self.c5050, self.c5060],
        )
        self.assertCountEqual(
            Company.objects.filter(num_employees__range=(F("num_chairs") - 10, 100)),
            [self.c5020, self.c5040, self.c5050, self.c5060],
        )
        self.assertCountEqual(
            Company.objects.filter(num_employees__range=(1, 100)),
            [self.c5020, self.c5040, self.c5050, self.c5060, self.c99300],
        )

    def test_range_lookup_namedtuple(self):
        """

        Tests the lookup of a range using a namedtuple for Company objects based on the number of employees.

        This test case verifies that the range lookup correctly filters Companies with the specified number of employees.
        The range is defined using a namedtuple with minimum and maximum values, and the test asserts that the result
        matches the expected Company instance.

        Args:
            None

        Returns:
            None

        """
        EmployeeRange = namedtuple("EmployeeRange", ["minimum", "maximum"])
        qs = Company.objects.filter(
            num_employees__range=EmployeeRange(minimum=51, maximum=100),
        )
        self.assertSequenceEqual(qs, [self.c99300])

    @unittest.skipUnless(
        connection.vendor == "sqlite",
        "This defensive test only works on databases that don't validate parameter "
        "types",
    )
    def test_expressions_not_introduce_sql_injection_via_untrusted_string_inclusion(
        self,
    ):
        """
        This tests that SQL injection isn't possible using compilation of
        expressions in iterable filters, as their compilation happens before
        the main query compilation. It's limited to SQLite, as PostgreSQL,
        Oracle and other vendors have defense in depth against this by type
        checking. Testing against SQLite (the most permissive of the built-in
        databases) demonstrates that the problem doesn't exist while keeping
        the test simple.
        """
        queryset = Company.objects.filter(name__in=[F("num_chairs") + "1)) OR ((1==1"])
        self.assertQuerySetEqual(queryset, [], ordered=False)

    def test_range_lookup_allows_F_expressions_and_expressions_for_dates(self):
        start = datetime.datetime(2016, 2, 3, 15, 0, 0)
        end = datetime.datetime(2016, 2, 5, 15, 0, 0)
        experiment_1 = Experiment.objects.create(
            name="Integrity testing",
            assigned=start.date(),
            start=start,
            end=end,
            completed=end.date(),
            estimated_time=end - start,
        )
        experiment_2 = Experiment.objects.create(
            name="Taste testing",
            assigned=start.date(),
            start=start,
            end=end,
            completed=end.date(),
            estimated_time=end - start,
        )
        r1 = Result.objects.create(
            experiment=experiment_1,
            result_time=datetime.datetime(2016, 2, 4, 15, 0, 0),
        )
        Result.objects.create(
            experiment=experiment_1,
            result_time=datetime.datetime(2016, 3, 10, 2, 0, 0),
        )
        Result.objects.create(
            experiment=experiment_2,
            result_time=datetime.datetime(2016, 1, 8, 5, 0, 0),
        )
        tests = [
            # Datetimes.
            ([F("experiment__start"), F("experiment__end")], "result_time__range"),
            # Dates.
            (
                [F("experiment__start__date"), F("experiment__end__date")],
                "result_time__date__range",
            ),
        ]
        for within_experiment_time, lookup in tests:
            with self.subTest(lookup=lookup):
                queryset = Result.objects.filter(**{lookup: within_experiment_time})
                self.assertSequenceEqual(queryset, [r1])


class FTests(SimpleTestCase):
    def test_deepcopy(self):
        f = F("foo")
        g = deepcopy(f)
        self.assertEqual(f.name, g.name)

    def test_deconstruct(self):
        """
        Tests the deconstruction of an F expression object.

        Deconstruction involves breaking down the object into its constituent parts,
        including the path, positional arguments, and keyword arguments, which can be
        used to reconstruct the object.

        Verifies that the deconstructed path corresponds to the correct F expression
        class, and that the positional arguments contain the expected field name, with
        no keyword arguments present.
        """
        f = F("name")
        path, args, kwargs = f.deconstruct()
        self.assertEqual(path, "django.db.models.F")
        self.assertEqual(args, (f.name,))
        self.assertEqual(kwargs, {})

    def test_equal(self):
        f = F("name")
        same_f = F("name")
        other_f = F("username")
        self.assertEqual(f, same_f)
        self.assertNotEqual(f, other_f)

    def test_hash(self):
        d = {F("name"): "Bob"}
        self.assertIn(F("name"), d)
        self.assertEqual(d[F("name")], "Bob")

    def test_not_equal_Value(self):
        """

        Verifies that a Field object and a Value object are not considered equal when compared.

        This test checks for non-equality in both directions, i.e., when a Field object is compared to a Value object and vice versa.

        It ensures that these two distinct objects, although potentially sharing similar attributes or properties, are treated as separate entities and do not inadvertently return a false positive for equality.

        """
        f = F("name")
        value = Value("name")
        self.assertNotEqual(f, value)
        self.assertNotEqual(value, f)

    def test_contains(self):
        """

        Tests if attempting to check for containment in an instance of F raises a TypeError.

        The test asserts that a TypeError is raised when trying to use the 'in' operator on an instance of F, 
        with a message indicating that the argument of type 'F' is not iterable.

        """
        msg = "argument of type 'F' is not iterable"
        with self.assertRaisesMessage(TypeError, msg):
            "" in F("name")


class ExpressionsTests(TestCase):
    def test_F_reuse(self):
        """

        Tests the reusability of the F expression in filtering queries across different models.

        This test case verifies that an F expression can be used to filter objects of different models, 
        in this case Company and Number, by their id field. It ensures that the F expression is reusable 
        and returns the correct objects when used in queries for different models.

        The test covers the creation of a Company and a Number instance, and then uses an F expression 
        to filter these objects based on their id. It checks that the filtered query returns the 
        expected objects, demonstrating the reusability of the F expression.

        """
        f = F("id")
        n = Number.objects.create(integer=-1)
        c = Company.objects.create(
            name="Example Inc.",
            num_employees=2300,
            num_chairs=5,
            ceo=Employee.objects.create(firstname="Joe", lastname="Smith"),
        )
        c_qs = Company.objects.filter(id=f)
        self.assertEqual(c_qs.get(), c)
        # Reuse the same F-object for another queryset
        n_qs = Number.objects.filter(id=f)
        self.assertEqual(n_qs.get(), n)
        # The original query still works correctly
        self.assertEqual(c_qs.get(), c)

    def test_patterns_escape(self):
        r"""
        Special characters (e.g. %, _ and \) stored in database are
        properly escaped when using a pattern lookup with an expression
        refs #16731
        """
        Employee.objects.bulk_create(
            [
                Employee(firstname="Johnny", lastname="%John"),
                Employee(firstname="Jean-Claude", lastname="Claud_"),
                Employee(firstname="Jean-Claude", lastname="Claude%"),
                Employee(firstname="Johnny", lastname="Joh\\n"),
                Employee(firstname="Johnny", lastname="_ohn"),
            ]
        )
        claude = Employee.objects.create(firstname="Jean-Claude", lastname="Claude")
        john = Employee.objects.create(firstname="Johnny", lastname="John")
        john_sign = Employee.objects.create(firstname="%Joh\\nny", lastname="%Joh\\n")

        self.assertCountEqual(
            Employee.objects.filter(firstname__contains=F("lastname")),
            [john_sign, john, claude],
        )
        self.assertCountEqual(
            Employee.objects.filter(firstname__startswith=F("lastname")),
            [john_sign, john],
        )
        self.assertSequenceEqual(
            Employee.objects.filter(firstname__endswith=F("lastname")),
            [claude],
        )

    def test_insensitive_patterns_escape(self):
        r"""
        Special characters (e.g. %, _ and \) stored in database are
        properly escaped when using a case insensitive pattern lookup with an
        expression -- refs #16731
        """
        Employee.objects.bulk_create(
            [
                Employee(firstname="Johnny", lastname="%john"),
                Employee(firstname="Jean-Claude", lastname="claud_"),
                Employee(firstname="Jean-Claude", lastname="claude%"),
                Employee(firstname="Johnny", lastname="joh\\n"),
                Employee(firstname="Johnny", lastname="_ohn"),
            ]
        )
        claude = Employee.objects.create(firstname="Jean-Claude", lastname="claude")
        john = Employee.objects.create(firstname="Johnny", lastname="john")
        john_sign = Employee.objects.create(firstname="%Joh\\nny", lastname="%joh\\n")

        self.assertCountEqual(
            Employee.objects.filter(firstname__icontains=F("lastname")),
            [john_sign, john, claude],
        )
        self.assertCountEqual(
            Employee.objects.filter(firstname__istartswith=F("lastname")),
            [john_sign, john],
        )
        self.assertSequenceEqual(
            Employee.objects.filter(firstname__iendswith=F("lastname")),
            [claude],
        )


@isolate_apps("expressions")
class SimpleExpressionTests(SimpleTestCase):
    def test_equal(self):
        """
        Tests the equality of Expression instances.

            This test case checks for equality between different instances of the Expression class.
            The equality is evaluated based on the field type or model field instance associated with each Expression instance.
            Two Expression instances are considered equal if they have the same field type or model field instance.
            The test covers scenarios including equal and unequal Expression instances with different field types, 
            as well as instances referencing different model fields. 

            The test ensures that the equality checks are performed correctly, and it provides a guarantee 
            that Expression instances can be safely compared using equality operators.

        """
        self.assertEqual(Expression(), Expression())
        self.assertEqual(
            Expression(IntegerField()), Expression(output_field=IntegerField())
        )
        self.assertEqual(Expression(IntegerField()), mock.ANY)
        self.assertNotEqual(Expression(IntegerField()), Expression(CharField()))

        class TestModel(Model):
            field = IntegerField()
            other_field = IntegerField()

        self.assertNotEqual(
            Expression(TestModel._meta.get_field("field")),
            Expression(TestModel._meta.get_field("other_field")),
        )

    def test_hash(self):
        """

        Tests the hashing behavior of the Expression class.

        This test suite verifies that the hash of an Expression instance is determined
        by its type and attributes. It checks for the following conditions:

        * Two Expression instances with no fields have the same hash.
        * Two Expression instances with the same field type have the same hash, regardless of whether the field is passed as a positional argument or as a keyword argument to the 'output_field' parameter.
        * Two Expression instances with different field types have different hashes.
        * Two Expression instances referencing different fields of the same model have different hashes.

        """
        self.assertEqual(hash(Expression()), hash(Expression()))
        self.assertEqual(
            hash(Expression(IntegerField())),
            hash(Expression(output_field=IntegerField())),
        )
        self.assertNotEqual(
            hash(Expression(IntegerField())),
            hash(Expression(CharField())),
        )

        class TestModel(Model):
            field = IntegerField()
            other_field = IntegerField()

        self.assertNotEqual(
            hash(Expression(TestModel._meta.get_field("field"))),
            hash(Expression(TestModel._meta.get_field("other_field"))),
        )

    def test_get_expression_for_validation_only_one_source_expression(self):
        expression = Expression()
        expression.constraint_validation_compatible = False
        msg = (
            "Expressions with constraint_validation_compatible set to False must have "
            "only one source expression."
        )
        with self.assertRaisesMessage(ValueError, msg):
            expression.get_expression_for_validation()


class ExpressionsNumericTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Number(integer=-1).save()
        Number(integer=42).save()
        Number(integer=1337).save()
        Number.objects.update(float=F("integer"))

    def test_fill_with_value_from_same_object(self):
        """
        We can fill a value in all objects with an other value of the
        same object.
        """
        self.assertQuerySetEqual(
            Number.objects.all(),
            [(-1, -1), (42, 42), (1337, 1337)],
            lambda n: (n.integer, round(n.float)),
            ordered=False,
        )

    def test_increment_value(self):
        """
        We can increment a value of all objects in a query set.
        """
        self.assertEqual(
            Number.objects.filter(integer__gt=0).update(integer=F("integer") + 1), 2
        )
        self.assertQuerySetEqual(
            Number.objects.all(),
            [(-1, -1), (43, 42), (1338, 1337)],
            lambda n: (n.integer, round(n.float)),
            ordered=False,
        )

    def test_filter_not_equals_other_field(self):
        """
        We can filter for objects, where a value is not equals the value
        of an other field.
        """
        self.assertEqual(
            Number.objects.filter(integer__gt=0).update(integer=F("integer") + 1), 2
        )
        self.assertQuerySetEqual(
            Number.objects.exclude(float=F("integer")),
            [(43, 42), (1338, 1337)],
            lambda n: (n.integer, round(n.float)),
            ordered=False,
        )

    def test_filter_decimal_expression(self):
        """

        Tests the filtering of a decimal expression in a Django ORM query.

        This test case creates a Number object and then uses Django's ORM to filter the 
        objects based on a decimal expression. It checks if the filter correctly matches 
        the object's decimal value and other conditions.

        The test covers the use of the ExpressionWrapper and Q objects to construct the 
        filter condition, and verifies that the resulting queryset contains the expected 
        object.

        It ensures that the filtering logic works as intended and returns the correct 
        results when dealing with decimal values.

        """
        obj = Number.objects.create(integer=0, float=1, decimal_value=Decimal("1"))
        qs = Number.objects.annotate(
            x=ExpressionWrapper(Value(1), output_field=DecimalField()),
        ).filter(Q(x=1, integer=0) & Q(x=Decimal("1")))
        self.assertSequenceEqual(qs, [obj])

    def test_complex_expressions(self):
        """
        Complex expressions of different connection types are possible.
        """
        n = Number.objects.create(integer=10, float=123.45)
        self.assertEqual(
            Number.objects.filter(pk=n.pk).update(float=F("integer") + F("float") * 2),
            1,
        )

        self.assertEqual(Number.objects.get(pk=n.pk).integer, 10)
        self.assertEqual(
            Number.objects.get(pk=n.pk).float, Approximate(256.900, places=3)
        )

    def test_decimal_expression(self):
        """
        Tests the correctness of decimal arithmetic operations when updating a Number object's decimal value. 
        The test case verifies that subtracting a decimal value from the current decimal value of a Number object and saving the changes results in the expected outcome, ensuring the updated value is correctly persisted in the database.
        """
        n = Number.objects.create(integer=1, decimal_value=Decimal("0.5"))
        n.decimal_value = F("decimal_value") - Decimal("0.4")
        n.save()
        n.refresh_from_db()
        self.assertEqual(n.decimal_value, Decimal("0.1"))


class ExpressionOperatorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up the test data for the class.

        This class method creates and stores test data instances of the Number model, 
        including a positive and a negative number with both integer and floating point values.

        The created instances are stored as class attributes, allowing them to be reused 
        across multiple test methods. This improves test efficiency by reducing the need 
        to recreate the same test data for each test case.

        Attributes set by this method:
            n: A Number instance with positive integer and float values.
            n1: A Number instance with negative integer and float values.
        """
        cls.n = Number.objects.create(integer=42, float=15.5)
        cls.n1 = Number.objects.create(integer=-42, float=-15.5)

    def test_lefthand_addition(self):
        # LH Addition of floats and integers
        Number.objects.filter(pk=self.n.pk).update(
            integer=F("integer") + 15, float=F("float") + 42.7
        )

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 57)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(58.200, places=3)
        )

    def test_lefthand_subtraction(self):
        # LH Subtraction of floats and integers
        """

        Tests the subtraction functionality on the lefthand side of an update operation.

        Verifies that subtracting a constant value from both integer and float fields within a Number model instance results in the expected values.
        The test case performs the following operations:
        - Updates the integer field by subtracting 15 and the float field by subtracting 42.7.
        - Asserts that the resulting integer value matches the expected outcome of 27.
        - Asserts that the resulting float value is approximately -27.2, allowing for minor floating point precision discrepancies.

        """
        Number.objects.filter(pk=self.n.pk).update(
            integer=F("integer") - 15, float=F("float") - 42.7
        )

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 27)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(-27.200, places=3)
        )

    def test_lefthand_multiplication(self):
        # Multiplication of floats and integers
        Number.objects.filter(pk=self.n.pk).update(
            integer=F("integer") * 15, float=F("float") * 42.7
        )

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 630)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(661.850, places=3)
        )

    def test_lefthand_division(self):
        # LH Division of floats and integers
        """

        Tests the functionality of left-hand division (/) on integer and float fields in the database.

        This test case updates an existing Number object in the database, performing division operations on its integer and float fields.
        The integer field is divided by 2 and the float field is divided by 42.7.
        The test then verifies that the updated values match the expected results, including an approximation for the float value due to potential rounding differences.

        """
        Number.objects.filter(pk=self.n.pk).update(
            integer=F("integer") / 2, float=F("float") / 42.7
        )

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 21)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(0.363, places=3)
        )

    def test_lefthand_modulo(self):
        # LH Modulo arithmetic on integers
        """
        Tests the lefthand modulo operation by updating a Number object's integer field 
        and verifying the result against an expected value.

        This test case checks that the modulo operation correctly calculates the remainder 
        of the division of the integer field by a given divisor (20 in this case), 
        and that the updated value is correctly stored in the database.
        """
        Number.objects.filter(pk=self.n.pk).update(integer=F("integer") % 20)
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 2)

    def test_lefthand_modulo_null(self):
        # LH Modulo arithmetic on integers.
        Employee.objects.create(firstname="John", lastname="Doe", salary=None)
        qs = Employee.objects.annotate(modsalary=F("salary") % 20)
        self.assertIsNone(qs.get().salary)

    def test_lefthand_bitwise_and(self):
        # LH Bitwise ands on integers
        """
        Tests the left-hand bitwise AND operation on integer fields in the database.

        The function performs two updates: one with a positive value (56) and another with a negative value (-56). 
        It then verifies that the resulting values after applying the bitwise AND operation are as expected, 
        demonstrating the correct implementation of the left-hand bitwise AND operation with both positive and negative numbers.
        """
        Number.objects.filter(pk=self.n.pk).update(integer=F("integer").bitand(56))
        Number.objects.filter(pk=self.n1.pk).update(integer=F("integer").bitand(-56))

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 40)
        self.assertEqual(Number.objects.get(pk=self.n1.pk).integer, -64)

    def test_lefthand_bitwise_left_shift_operator(self):
        Number.objects.update(integer=F("integer").bitleftshift(2))
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 168)
        self.assertEqual(Number.objects.get(pk=self.n1.pk).integer, -168)

    def test_lefthand_bitwise_right_shift_operator(self):
        Number.objects.update(integer=F("integer").bitrightshift(2))
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 10)
        self.assertEqual(Number.objects.get(pk=self.n1.pk).integer, -11)

    def test_lefthand_bitwise_or(self):
        # LH Bitwise or on integers
        """
        Tests the left-hand side bitwise OR operation on integer fields in the database.

        This test updates all Number objects by performing a bitwise OR operation with the value 48, 
        and then verifies that the results are correct for two specific objects.

        The expected outcomes are:
        - For the object with primary key self.n.pk, the integer value should be 58 after the operation.
        - For the object with primary key self.n1.pk, the integer value should be -10 after the operation.

        This test ensures that the bitwise OR operation is applied correctly to the integer field 
        on the database level, using the F expression to avoid loading the objects into memory.
        """
        Number.objects.update(integer=F("integer").bitor(48))

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 58)
        self.assertEqual(Number.objects.get(pk=self.n1.pk).integer, -10)

    def test_lefthand_transformed_field_bitwise_or(self):
        """
        Test that the lefthand transformed field supports the bitwise OR operation.

        This function checks the correct application of the bitwise OR operation on a transformed
        field. It creates a test employee, annotates a queryset with the length of the 
        lastname field and performs a bitwise OR operation with a given value, then verifies 
        that the result matches the expected output.
        """
        Employee.objects.create(firstname="Max", lastname="Mustermann")
        with register_lookup(CharField, Length):
            qs = Employee.objects.annotate(bitor=F("lastname__length").bitor(48))
            self.assertEqual(qs.get().bitor, 58)

    def test_lefthand_power(self):
        # LH Power arithmetic operation on floats and integers
        """
        Tests the left-hand side of the power operator on integer and float fields.

         The function updates an existing number object in the database by squaring its integer value and raising its float value to the power of 1.5.

         It then asserts that the resulting integer value matches the expected result of 1764, and that the resulting float value is approximately 61.02, rounded to two decimal places.
        """
        Number.objects.filter(pk=self.n.pk).update(
            integer=F("integer") ** 2, float=F("float") ** 1.5
        )
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 1764)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(61.02, places=2)
        )

    def test_lefthand_bitwise_xor(self):
        """

        Tests the lefthand bitwise XOR operation on model instances.

        This test case updates the 'integer' field of all Number objects using the bitwise XOR operator with the value 48.
        It then verifies that the resulting values are as expected for two specific instances, checking that the bitwise XOR operation has been applied correctly.

        """
        Number.objects.update(integer=F("integer").bitxor(48))
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 26)
        self.assertEqual(Number.objects.get(pk=self.n1.pk).integer, -26)

    def test_lefthand_bitwise_xor_null(self):
        employee = Employee.objects.create(firstname="John", lastname="Doe")
        Employee.objects.update(salary=F("salary").bitxor(48))
        employee.refresh_from_db()
        self.assertIsNone(employee.salary)

    def test_lefthand_bitwise_xor_right_null(self):
        """
        Tests the behavior of bitwise XOR operation when the right-hand operand is null.

        This test case verifies that when the bitwise XOR operation is applied to a valid
        value with a null value, the result is null. Specifically, it checks that updating
        an employee's salary using a bitwise XOR operation with a null value results in
        the salary being set to null.

        The test creates an employee with an initial salary, applies the bitwise XOR
        operation with a null value, and then checks that the employee's salary has been
        updated to null.

        """
        employee = Employee.objects.create(firstname="John", lastname="Doe", salary=48)
        Employee.objects.update(salary=F("salary").bitxor(None))
        employee.refresh_from_db()
        self.assertIsNone(employee.salary)

    @unittest.skipUnless(
        connection.vendor == "oracle", "Oracle doesn't support bitwise XOR."
    )
    def test_lefthand_bitwise_xor_not_supported(self):
        msg = "Bitwise XOR is not supported in Oracle."
        with self.assertRaisesMessage(NotSupportedError, msg):
            Number.objects.update(integer=F("integer").bitxor(48))

    def test_right_hand_addition(self):
        # Right hand operators
        """

        Tests that values can be added to the right hand side of objects in the database.

        Verifies that F expressions for integer and float fields can be used to update
        existing values in the database. Specifically, checks that addition operations
        are correctly performed and result in the expected values.

        """
        Number.objects.filter(pk=self.n.pk).update(
            integer=15 + F("integer"), float=42.7 + F("float")
        )

        # RH Addition of floats and integers
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 57)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(58.200, places=3)
        )

    def test_right_hand_subtraction(self):
        Number.objects.filter(pk=self.n.pk).update(
            integer=15 - F("integer"), float=42.7 - F("float")
        )

        # RH Subtraction of floats and integers
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, -27)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(27.200, places=3)
        )

    def test_right_hand_multiplication(self):
        # RH Multiplication of floats and integers
        Number.objects.filter(pk=self.n.pk).update(
            integer=15 * F("integer"), float=42.7 * F("float")
        )

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 630)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(661.850, places=3)
        )

    def test_right_hand_division(self):
        # RH Division of floats and integers
        Number.objects.filter(pk=self.n.pk).update(
            integer=640 / F("integer"), float=42.7 / F("float")
        )

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 15)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(2.755, places=3)
        )

    def test_right_hand_modulo(self):
        # RH Modulo arithmetic on integers
        Number.objects.filter(pk=self.n.pk).update(integer=69 % F("integer"))

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 27)

    def test_righthand_power(self):
        # RH Power arithmetic operation on floats and integers
        """
        .. method:: test_righthand_power

           Tests the correct implementation of right-hand power operator on integer and float fields.

           The test updates an existing number object's integer and float values by raising 2 and 1.5 to the power of their current values respectively, and then asserts that the updated values match the expected results. 

           The result of the float power operation is checked with a tolerance of 3 decimal places due to potential floating point precision issues.
        """
        Number.objects.filter(pk=self.n.pk).update(
            integer=2 ** F("integer"), float=1.5 ** F("float")
        )
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 4398046511104)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(536.308, places=3)
        )


class FTimeDeltaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for experiments.

        This method creates a set of experiments with varying start and end times, 
        assigned dates, and estimated durations. It initializes class attributes 
        with these experiments, along with lists of time deltas, delays, and days 
        longer than the experiment duration.

        These test data are used to support unit tests and other functionality 
        that relies on a pre-populated database of experiments. 

        Attributes initialized by this method include:

        - sday and stime: a base date and time used for creating experiments
        - deltas: a list of time deltas associated with each experiment
        - delays: a list of delays between the assigned date and start time of each experiment
        - days_long: a list of time periods between the assigned date and completion date of each experiment
        - expnames: a list of names of all created experiments
        """
        cls.sday = sday = datetime.date(2010, 6, 25)
        cls.stime = stime = datetime.datetime(2010, 6, 25, 12, 15, 30, 747000)
        midnight = datetime.time(0)

        delta0 = datetime.timedelta(0)
        delta1 = datetime.timedelta(microseconds=253000)
        delta2 = datetime.timedelta(seconds=44)
        delta3 = datetime.timedelta(hours=21, minutes=8)
        delta4 = datetime.timedelta(days=10)
        delta5 = datetime.timedelta(days=90)

        # Test data is set so that deltas and delays will be
        # strictly increasing.
        cls.deltas = []
        cls.delays = []
        cls.days_long = []

        # e0: started same day as assigned, zero duration
        end = stime + delta0
        cls.e0 = Experiment.objects.create(
            name="e0",
            assigned=sday,
            start=stime,
            end=end,
            completed=end.date(),
            estimated_time=delta0,
        )
        cls.deltas.append(delta0)
        cls.delays.append(
            cls.e0.start - datetime.datetime.combine(cls.e0.assigned, midnight)
        )
        cls.days_long.append(cls.e0.completed - cls.e0.assigned)

        # e1: started one day after assigned, tiny duration, data
        # set so that end time has no fractional seconds, which
        # tests an edge case on sqlite.
        delay = datetime.timedelta(1)
        end = stime + delay + delta1
        e1 = Experiment.objects.create(
            name="e1",
            assigned=sday,
            start=stime + delay,
            end=end,
            completed=end.date(),
            estimated_time=delta1,
        )
        cls.deltas.append(delta1)
        cls.delays.append(e1.start - datetime.datetime.combine(e1.assigned, midnight))
        cls.days_long.append(e1.completed - e1.assigned)

        # e2: started three days after assigned, small duration
        end = stime + delta2
        e2 = Experiment.objects.create(
            name="e2",
            assigned=sday - datetime.timedelta(3),
            start=stime,
            end=end,
            completed=end.date(),
            estimated_time=datetime.timedelta(hours=1),
        )
        cls.deltas.append(delta2)
        cls.delays.append(e2.start - datetime.datetime.combine(e2.assigned, midnight))
        cls.days_long.append(e2.completed - e2.assigned)

        # e3: started four days after assigned, medium duration
        delay = datetime.timedelta(4)
        end = stime + delay + delta3
        e3 = Experiment.objects.create(
            name="e3",
            assigned=sday,
            start=stime + delay,
            end=end,
            completed=end.date(),
            estimated_time=delta3,
        )
        cls.deltas.append(delta3)
        cls.delays.append(e3.start - datetime.datetime.combine(e3.assigned, midnight))
        cls.days_long.append(e3.completed - e3.assigned)

        # e4: started 10 days after assignment, long duration
        end = stime + delta4
        e4 = Experiment.objects.create(
            name="e4",
            assigned=sday - datetime.timedelta(10),
            start=stime,
            end=end,
            completed=end.date(),
            estimated_time=delta4 - datetime.timedelta(1),
        )
        cls.deltas.append(delta4)
        cls.delays.append(e4.start - datetime.datetime.combine(e4.assigned, midnight))
        cls.days_long.append(e4.completed - e4.assigned)

        # e5: started a month after assignment, very long duration
        delay = datetime.timedelta(30)
        end = stime + delay + delta5
        e5 = Experiment.objects.create(
            name="e5",
            assigned=sday,
            start=stime + delay,
            end=end,
            completed=end.date(),
            estimated_time=delta5,
        )
        cls.deltas.append(delta5)
        cls.delays.append(e5.start - datetime.datetime.combine(e5.assigned, midnight))
        cls.days_long.append(e5.completed - e5.assigned)

        cls.expnames = [e.name for e in Experiment.objects.all()]

    def test_multiple_query_compilation(self):
        # Ticket #21643
        """
        Tests that compiling a query multiple times results in the same SQL query.

        Checks that the Experiment objects filter query is consistent across multiple 
        compilations. This ensures that the same query is executed on the database 
        regardless of how many times it is compiled, which is important for 
        performance and data integrity.

        The test uses a query that filters Experiment objects based on a datetime 
        condition, specifically looking for experiments that end within an hour of 
        starting. It then verifies that the SQL query generated by the queryset is 
        identical when compiled multiple times.
        """
        queryset = Experiment.objects.filter(
            end__lt=F("start") + datetime.timedelta(hours=1)
        )
        q1 = str(queryset.query)
        q2 = str(queryset.query)
        self.assertEqual(q1, q2)

    def test_query_clone(self):
        # Ticket #21643 - Crash when compiling query more than once
        """
        Tests the cloning behavior of a query set.

        This function creates a query set of experiments where the end time is less than one hour after the start time.
        It then creates a clone of this query set and evaluates both query sets to ensure they produce the same results.
        The purpose of this test is to verify that the query set cloning process is working correctly, 
        preserving the original query's conditions in the cloned query set.
        """
        qs = Experiment.objects.filter(end__lt=F("start") + datetime.timedelta(hours=1))
        qs2 = qs.all()
        list(qs)
        list(qs2)
        # Intentionally no assert

    def test_delta_add(self):
        """
        Tests the addition of delta values to experiment end dates.

        This test method iterates over a series of delta values and checks if the 
        experiment names are correctly filtered based on the addition of these deltas 
        to the experiment start dates. The filtering is performed using both less-than 
        and less-than-or-equal-to comparisons. The test ensures that the resulting 
        experiment names match the expected output for each delta value.

        The test covers three scenarios:
        - Experiments ending before the start date plus the delta
        - Experiments ending before the delta added to the start date (equivalent to the first scenario)
        - Experiments ending on or before the start date plus the delta
        """
        for i, delta in enumerate(self.deltas):
            test_set = [
                e.name for e in Experiment.objects.filter(end__lt=F("start") + delta)
            ]
            self.assertEqual(test_set, self.expnames[:i])

            test_set = [
                e.name for e in Experiment.objects.filter(end__lt=delta + F("start"))
            ]
            self.assertEqual(test_set, self.expnames[:i])

            test_set = [
                e.name for e in Experiment.objects.filter(end__lte=F("start") + delta)
            ]
            self.assertEqual(test_set, self.expnames[: i + 1])

    def test_delta_subtract(self):
        """
        Tests the subtraction of time deltas from end dates of experiments, verifying that the resulting sets of experiment names match the expected sets.

         The function iterates over a list of time deltas, applying each delta to filter experiments based on their start and end times. It checks two cases for each delta: 
         1. experiments that start strictly after the end time minus the delta, and 
         2. experiments that start at or after the end time minus the delta.

         For each case, it asserts that the set of experiment names returned by the filter matches the expected set of names, which is a prefix of the list of all experiment names up to the current index.
        """
        for i, delta in enumerate(self.deltas):
            test_set = [
                e.name for e in Experiment.objects.filter(start__gt=F("end") - delta)
            ]
            self.assertEqual(test_set, self.expnames[:i])

            test_set = [
                e.name for e in Experiment.objects.filter(start__gte=F("end") - delta)
            ]
            self.assertEqual(test_set, self.expnames[: i + 1])

    def test_exclude(self):
        """

        Tests the exclude method of the Experiment model's query set.

        This test checks the exclude method's behavior when filtering experiments based on their start and end times.
        It iterates over a list of time deltas and for each delta, it checks that the correct experiments are excluded
        when using both the less than (`__lt`) and less than or equal to (`__lte`) lookup types.
        The test ensures that the resulting experiment names match the expected names for each delta.

        """
        for i, delta in enumerate(self.deltas):
            test_set = [
                e.name for e in Experiment.objects.exclude(end__lt=F("start") + delta)
            ]
            self.assertEqual(test_set, self.expnames[i:])

            test_set = [
                e.name for e in Experiment.objects.exclude(end__lte=F("start") + delta)
            ]
            self.assertEqual(test_set, self.expnames[i + 1 :])

    def test_date_comparison(self):
        for i, days in enumerate(self.days_long):
            test_set = [
                e.name
                for e in Experiment.objects.filter(completed__lt=F("assigned") + days)
            ]
            self.assertEqual(test_set, self.expnames[:i])

            test_set = [
                e.name
                for e in Experiment.objects.filter(completed__lte=F("assigned") + days)
            ]
            self.assertEqual(test_set, self.expnames[: i + 1])

    def test_datetime_and_durationfield_addition_with_filter(self):
        """
        Tests the addition of DateTimeField and DurationField on the Experiment model with a database query filter.

        Verifies that the filter correctly selects experiments where the end date is equal to the start date plus the estimated time.

        Ensures the filtered results match the expected set of experiments based on the same condition applied manually to all experiments.

        This test case checks for both the correctness of the filtering and the equality of the filtered results with the expected output.
        """
        test_set = Experiment.objects.filter(end=F("start") + F("estimated_time"))
        self.assertGreater(test_set.count(), 0)
        self.assertEqual(
            [e.name for e in test_set],
            [
                e.name
                for e in Experiment.objects.all()
                if e.end == e.start + e.estimated_time
            ],
        )

    def test_datetime_and_duration_field_addition_with_annotate_and_no_output_field(
        self,
    ):
        """
        Test that adding datetime and duration fields in an annotation produces the expected results.

        The function verifies that when the start datetime and estimated time duration of experiments are added together using Django's annotation functionality, the resulting estimated end datetime matches the expected result. This ensures that datetime arithmetic operations are correctly performed when using annotations in database queries.
        """
        test_set = Experiment.objects.annotate(
            estimated_end=F("start") + F("estimated_time")
        )
        self.assertEqual(
            [e.estimated_end for e in test_set],
            [e.start + e.estimated_time for e in test_set],
        )

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_datetime_subtraction_with_annotate_and_no_output_field(self):
        """

        Tests the subtraction of datetime fields in a query using Django's ORM.
        Specifically, it verifies that annotating a queryset with the difference 
        between two datetime fields (end and start) yields the same result as 
        performing the subtraction in Python.

        The test checks for temporal subtraction support in the underlying database 
        before running, to ensure compatibility.

        It uses an Experiment queryset and checks the equality of the annotated 
        calculated duration and the duration calculated using raw Python date 
        subtraction, across all experiments in the test set.

        """
        test_set = Experiment.objects.annotate(
            calculated_duration=F("end") - F("start")
        )
        self.assertEqual(
            [e.calculated_duration for e in test_set],
            [e.end - e.start for e in test_set],
        )

    def test_mixed_comparisons1(self):
        """

        Tests mixed comparisons by filtering experiments based on assigned and start time.
        Verifies that experiments are correctly filtered when the assigned time is greater than 
        or greater than or equal to the start time minus a given delay.

        The function iterates through a list of delays and for each delay, it checks two conditions:
        - assigned time is greater than the start time minus the delay
        - assigned time is greater than or equal to the start time minus the delay
        It asserts that the resulting experiment names match the expected experiment names 
        for each condition, up to the current iteration and the current iteration plus one, respectively.

        """
        for i, delay in enumerate(self.delays):
            test_set = [
                e.name
                for e in Experiment.objects.filter(assigned__gt=F("start") - delay)
            ]
            self.assertEqual(test_set, self.expnames[:i])

            test_set = [
                e.name
                for e in Experiment.objects.filter(assigned__gte=F("start") - delay)
            ]
            self.assertEqual(test_set, self.expnames[: i + 1])

    def test_mixed_comparisons2(self):
        for i, delay in enumerate(self.delays):
            delay = datetime.timedelta(delay.days)
            test_set = [
                e.name
                for e in Experiment.objects.filter(start__lt=F("assigned") + delay)
            ]
            self.assertEqual(test_set, self.expnames[:i])

            test_set = [
                e.name
                for e in Experiment.objects.filter(
                    start__lte=F("assigned") + delay + datetime.timedelta(1)
                )
            ]
            self.assertEqual(test_set, self.expnames[: i + 1])

    def test_delta_update(self):
        for delta in self.deltas:
            exps = Experiment.objects.all()
            expected_durations = [e.duration() for e in exps]
            expected_starts = [e.start + delta for e in exps]
            expected_ends = [e.end + delta for e in exps]

            Experiment.objects.update(start=F("start") + delta, end=F("end") + delta)
            exps = Experiment.objects.all()
            new_starts = [e.start for e in exps]
            new_ends = [e.end for e in exps]
            new_durations = [e.duration() for e in exps]
            self.assertEqual(expected_starts, new_starts)
            self.assertEqual(expected_ends, new_ends)
            self.assertEqual(expected_durations, new_durations)

    def test_invalid_operator(self):
        """
        Tests that an invalid operator in a queryset raises a DatabaseError.

        This tests that attempting to use an unsupported operator, such as multiplying a
        datetime field by a timedelta, results in a DatabaseError being raised.

        :raises: DatabaseError
        :raises TypeError: If underlying database operations are incorrect
        """
        with self.assertRaises(DatabaseError):
            list(Experiment.objects.filter(start=F("start") * datetime.timedelta(0)))

    def test_durationfield_add(self):
        """
        Tests the functionality of the DurationField in various scenarios.

        This test case covers the following:

        * Verifies that adding a DurationField to a DateTimeField results in the correct outcome.
        * Checks that experiments are correctly filtered when their end time is less than their start time plus the estimated duration.
        * Validates the calculation of a DateTimeField after adding a DurationField with a timedelta value.
        * Ensures that annotating a queryset with a DurationField and a null value results in a null output, as expected.

        The test serves as a comprehensive check of the DurationField's arithmetic operations and its interaction with querysets and datetime-related calculations.
        """
        zeros = [
            e.name
            for e in Experiment.objects.filter(start=F("start") + F("estimated_time"))
        ]
        self.assertEqual(zeros, ["e0"])

        end_less = [
            e.name
            for e in Experiment.objects.filter(end__lt=F("start") + F("estimated_time"))
        ]
        self.assertEqual(end_less, ["e2"])

        delta_math = [
            e.name
            for e in Experiment.objects.filter(
                end__gte=F("start") + F("estimated_time") + datetime.timedelta(hours=1)
            )
        ]
        self.assertEqual(delta_math, ["e4"])

        queryset = Experiment.objects.annotate(
            shifted=ExpressionWrapper(
                F("start") + Value(None, output_field=DurationField()),
                output_field=DateTimeField(),
            )
        )
        self.assertIsNone(queryset.first().shifted)

    def test_durationfield_multiply_divide(self):
        """
        Tests that DurationField correctly handles multiplication and division.

        This test case verifies the functionality of the DurationField when it is
        subjected to multiplication and division operations. The test updates the scalar
        field of all Experiment objects and then checks the results of annotating these
        objects with multiplied and divided expressions.

        The test covers various cases, including multiplying and dividing by a constant
        value, a model field, and a decimal value. It ensures that the results of these
        operations match the expected outcomes, providing confidence in the correctness
        of DurationField's arithmetic operations.

        The test cases cover the following scenarios:
        - Multiplying and dividing by a constant value
        - Multiplying and dividing by a model field
        - Multiplying and dividing by a decimal value
        """
        Experiment.objects.update(scalar=2)
        tests = [
            (Decimal("2"), 2),
            (F("scalar"), 2),
            (2, 2),
            (3.2, 3.2),
        ]
        for expr, scalar in tests:
            with self.subTest(expr=expr):
                qs = Experiment.objects.annotate(
                    multiplied=ExpressionWrapper(
                        expr * F("estimated_time"),
                        output_field=DurationField(),
                    ),
                    divided=ExpressionWrapper(
                        F("estimated_time") / expr,
                        output_field=DurationField(),
                    ),
                )
                for experiment in qs:
                    self.assertEqual(
                        experiment.multiplied,
                        experiment.estimated_time * scalar,
                    )
                    self.assertEqual(
                        experiment.divided,
                        experiment.estimated_time / scalar,
                    )

    def test_duration_expressions(self):
        """
        Checks the correctness of duration calculations for experiments.

        This test verifies that the duration of experiments, calculated by adding a given time delta to the estimated time, matches the expected result.

        It iterates over a set of predefined time deltas, annotates each experiment with the calculated duration, and asserts that the annotated duration equals the estimated time plus the delta for each experiment.

        This ensures the accuracy of duration expressions and annotations in the Experiment model, providing a foundation for reliable time-based calculations and queries.
        """
        for delta in self.deltas:
            qs = Experiment.objects.annotate(duration=F("estimated_time") + delta)
            for obj in qs:
                self.assertEqual(obj.duration, obj.estimated_time + delta)

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_date_subtraction(self):
        queryset = Experiment.objects.annotate(
            completion_duration=F("completed") - F("assigned"),
        )

        at_least_5_days = {
            e.name
            for e in queryset.filter(
                completion_duration__gte=datetime.timedelta(days=5)
            )
        }
        self.assertEqual(at_least_5_days, {"e3", "e4", "e5"})

        at_least_120_days = {
            e.name
            for e in queryset.filter(
                completion_duration__gte=datetime.timedelta(days=120)
            )
        }
        self.assertEqual(at_least_120_days, {"e5"})

        less_than_5_days = {
            e.name
            for e in queryset.filter(completion_duration__lt=datetime.timedelta(days=5))
        }
        self.assertEqual(less_than_5_days, {"e0", "e1", "e2"})

        queryset = Experiment.objects.annotate(
            difference=F("completed") - Value(None, output_field=DateField()),
        )
        self.assertIsNone(queryset.first().difference)

        queryset = Experiment.objects.annotate(
            shifted=ExpressionWrapper(
                F("completed") - Value(None, output_field=DurationField()),
                output_field=DateField(),
            )
        )
        self.assertIsNone(queryset.first().shifted)

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_date_subquery_subtraction(self):
        subquery = Experiment.objects.filter(pk=OuterRef("pk")).values("completed")
        queryset = Experiment.objects.annotate(
            difference=subquery - F("completed"),
        ).filter(difference=datetime.timedelta())
        self.assertTrue(queryset.exists())

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_date_case_subtraction(self):
        queryset = Experiment.objects.annotate(
            date_case=Case(
                When(Q(name="e0"), then=F("completed")),
                output_field=DateField(),
            ),
            completed_value=Value(
                self.e0.completed,
                output_field=DateField(),
            ),
            difference=F("date_case") - F("completed_value"),
        ).filter(difference=datetime.timedelta())
        self.assertEqual(queryset.get(), self.e0)

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_time_subtraction(self):
        Time.objects.create(time=datetime.time(12, 30, 15, 2345))
        queryset = Time.objects.annotate(
            difference=F("time") - Value(datetime.time(11, 15, 0)),
        )
        self.assertEqual(
            queryset.get().difference,
            datetime.timedelta(hours=1, minutes=15, seconds=15, microseconds=2345),
        )

        queryset = Time.objects.annotate(
            difference=F("time") - Value(None, output_field=TimeField()),
        )
        self.assertIsNone(queryset.first().difference)

        queryset = Time.objects.annotate(
            shifted=ExpressionWrapper(
                F("time") - Value(None, output_field=DurationField()),
                output_field=TimeField(),
            )
        )
        self.assertIsNone(queryset.first().shifted)

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_time_subquery_subtraction(self):
        Time.objects.create(time=datetime.time(12, 30, 15, 2345))
        subquery = Time.objects.filter(pk=OuterRef("pk")).values("time")
        queryset = Time.objects.annotate(
            difference=subquery - F("time"),
        ).filter(difference=datetime.timedelta())
        self.assertTrue(queryset.exists())

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_datetime_subtraction(self):
        """
        Tests the correctness of temporal subtraction operations on datetime fields.

            Checks if the subtraction of datetime fields results in correct temporal
            differences for experiments with under and over estimated times. Additionally,
            verifies that subtracting from a datetime field with a None value results in
            None, and that similar behavior is observed when using an ExpressionWrapper
            with a DurationField output type.

            The test includes the following assertions:
            - Experiments with estimated times less than the actual duration ('e4') are
              correctly identified.
            - Experiments with estimated times greater than the actual duration ('e2') are
              correctly identified.
            - Subtracting a None value from a datetime field results in None.
            - Using an ExpressionWrapper with a DurationField output type and a None value
              results in None.

        """
        under_estimate = [
            e.name
            for e in Experiment.objects.filter(estimated_time__gt=F("end") - F("start"))
        ]
        self.assertEqual(under_estimate, ["e2"])

        over_estimate = [
            e.name
            for e in Experiment.objects.filter(estimated_time__lt=F("end") - F("start"))
        ]
        self.assertEqual(over_estimate, ["e4"])

        queryset = Experiment.objects.annotate(
            difference=F("start") - Value(None, output_field=DateTimeField()),
        )
        self.assertIsNone(queryset.first().difference)

        queryset = Experiment.objects.annotate(
            shifted=ExpressionWrapper(
                F("start") - Value(None, output_field=DurationField()),
                output_field=DateTimeField(),
            )
        )
        self.assertIsNone(queryset.first().shifted)

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_datetime_subquery_subtraction(self):
        """
        Tests if datetime subtraction in a subquery works correctly with a database.

        This test case verifies that the database supports temporal subtraction, which is 
        used to calculate the difference between a datetime value from a subquery and 
        a column value in the main query. It checks if this difference can be used as 
        a filter condition to retrieve specific data.

        The test uses a subquery to retrieve the 'start' datetime value for each 
        Experiment object and then annotates the main queryset with the difference 
        between this value and the 'start' value of the outer query. The test then 
        filters the queryset to include only objects where this difference is zero, 
        meaning the two datetime values are equal. The test finally verifies that at 
        least one object exists in the filtered queryset, confirming that the database 
        supports the required functionality. 

        Requires a database that supports temporal subtraction.
        """
        subquery = Experiment.objects.filter(pk=OuterRef("pk")).values("start")
        queryset = Experiment.objects.annotate(
            difference=subquery - F("start"),
        ).filter(difference=datetime.timedelta())
        self.assertTrue(queryset.exists())

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_datetime_subtraction_microseconds(self):
        delta = datetime.timedelta(microseconds=8999999999999999)
        Experiment.objects.update(end=F("start") + delta)
        qs = Experiment.objects.annotate(delta=F("end") - F("start"))
        for e in qs:
            self.assertEqual(e.delta, delta)

    def test_duration_with_datetime(self):
        # Exclude e1 which has very high precision so we can test this on all
        # backends regardless of whether or not it supports
        # microsecond_precision.
        """

        Tests that the experiment durations are calculated correctly.

        This function verifies that experiments with durations exceeding their estimated times
        are identified correctly. It checks experiments that have completed after their estimated
        end times, excluding a specific experiment ('e1'), and ensures the expected results
        are returned in a sorted order.

        The test asserts that the query returns a set of experiments with names 'e3', 'e4', and 'e5',
        which have completed beyond their estimated durations.

        """
        over_estimate = (
            Experiment.objects.exclude(name="e1")
            .filter(
                completed__gt=self.stime + F("estimated_time"),
            )
            .order_by("name")
        )
        self.assertQuerySetEqual(over_estimate, ["e3", "e4", "e5"], lambda e: e.name)

    def test_duration_with_datetime_microseconds(self):
        """

        Checks the duration of an experiment by adding a large timedelta with microseconds to the start datetime.

        This test verifies the correct calculation of a future datetime by adding a timedelta
        to the start time of an experiment. The test case covers a large timedelta value 
        with microseconds precision, ensuring the result matches the expected sum of 
        the start time and the given timedelta.

        """
        delta = datetime.timedelta(microseconds=8999999999999999)
        qs = Experiment.objects.annotate(
            dt=ExpressionWrapper(
                F("start") + delta,
                output_field=DateTimeField(),
            )
        )
        for e in qs:
            self.assertEqual(e.dt, e.start + delta)

    def test_date_minus_duration(self):
        more_than_4_days = Experiment.objects.filter(
            assigned__lt=F("completed") - Value(datetime.timedelta(days=4))
        )
        self.assertQuerySetEqual(more_than_4_days, ["e3", "e4", "e5"], lambda e: e.name)

    def test_negative_timedelta_update(self):
        # subtract 30 seconds, 30 minutes, 2 hours and 2 days
        experiments = (
            Experiment.objects.filter(name="e0")
            .annotate(
                start_sub_seconds=F("start") + datetime.timedelta(seconds=-30),
            )
            .annotate(
                start_sub_minutes=F("start_sub_seconds")
                + datetime.timedelta(minutes=-30),
            )
            .annotate(
                start_sub_hours=F("start_sub_minutes") + datetime.timedelta(hours=-2),
            )
            .annotate(
                new_start=F("start_sub_hours") + datetime.timedelta(days=-2),
            )
        )
        expected_start = datetime.datetime(2010, 6, 23, 9, 45, 0)
        # subtract 30 microseconds
        experiments = experiments.annotate(
            new_start=F("new_start") + datetime.timedelta(microseconds=-30)
        )
        expected_start += datetime.timedelta(microseconds=+746970)
        experiments.update(start=F("new_start"))
        e0 = Experiment.objects.get(name="e0")
        self.assertEqual(e0.start, expected_start)


class ValueTests(TestCase):
    def test_update_TimeField_using_Value(self):
        """

        Tests the successful update of a TimeField using a Value object.

        This test case verifies that the TimeField can be updated with a new time value 
        using the Value object from Django's database functions. It checks that the 
        updated value is correctly stored in the database and can be retrieved.

        """
        Time.objects.create()
        Time.objects.update(time=Value(datetime.time(1), output_field=TimeField()))
        self.assertEqual(Time.objects.get().time, datetime.time(1))

    def test_update_UUIDField_using_Value(self):
        """

        Tests the update functionality of a UUIDField using a database Value object.

        This test case checks if a UUIDField can be successfully updated using a Value object, 
        which is a way to pass Python objects to the database without Django's ORM processing them. 
        It verifies that the updated value is correctly stored and retrieved from the database.

        The test creates a new UUID object, updates its uuid field using a Value object, 
        and then asserts that the retrieved uuid field matches the expected value.

        """
        UUID.objects.create()
        UUID.objects.update(
            uuid=Value(
                uuid.UUID("12345678901234567890123456789012"), output_field=UUIDField()
            )
        )
        self.assertEqual(
            UUID.objects.get().uuid, uuid.UUID("12345678901234567890123456789012")
        )

    def test_deconstruct(self):
        """
        Tests the deconstruction of a Value object.

        This test case verifies that the deconstruct method of a Value object returns
        the correct path, arguments, and keyword arguments. The path should match the
        string representation of the Value class, the arguments should contain the
        value of the Value object, and the keyword arguments should be empty.

        The purpose of this test is to ensure that the Value object can be properly
        deconstructed and reconstructed, which is essential for tasks such as Serializing
        and deserializing model instances.

        """
        value = Value("name")
        path, args, kwargs = value.deconstruct()
        self.assertEqual(path, "django.db.models.Value")
        self.assertEqual(args, (value.value,))
        self.assertEqual(kwargs, {})

    def test_deconstruct_output_field(self):
        """
        Tests the deconstruction of a model field's Value object output field.

        This test ensures that the deconstruct method of a Value object, which has an output field,
        returns the expected path, arguments, and keyword arguments.

        The test verifies that the path points to the correct Value class,
        the arguments contain the value of the Value object, and the keyword arguments
        contain the output field, which is correctly deconstructed as a CharField.
        """
        value = Value("name", output_field=CharField())
        path, args, kwargs = value.deconstruct()
        self.assertEqual(path, "django.db.models.Value")
        self.assertEqual(args, (value.value,))
        self.assertEqual(len(kwargs), 1)
        self.assertEqual(
            kwargs["output_field"].deconstruct(), CharField().deconstruct()
        )

    def test_repr(self):
        """

        Tests the repr function of the Value class.

        This test ensures that the repr function correctly returns a string representation of the Value object.
        It checks various types of input values, including None, strings, booleans, integers, datetime objects, and Decimal objects,
        to verify that the repr function handles each type correctly and returns the expected string representation.

        """
        tests = [
            (None, "Value(None)"),
            ("str", "Value('str')"),
            (True, "Value(True)"),
            (42, "Value(42)"),
            (
                datetime.datetime(2019, 5, 15),
                "Value(datetime.datetime(2019, 5, 15, 0, 0))",
            ),
            (Decimal("3.14"), "Value(Decimal('3.14'))"),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(repr(Value(value)), expected)

    def test_equal(self):
        value = Value("name")
        self.assertEqual(value, Value("name"))
        self.assertNotEqual(value, Value("username"))

    def test_hash(self):
        """

        Tests the hashing functionality of the Value class.

        This test case verifies that instances of the Value class can be used as keys in a dictionary,
        and that the hash value of a Value instance is correctly generated.
        It checks that a Value instance can be found in a dictionary and that its corresponding value can be retrieved.

        """
        d = {Value("name"): "Bob"}
        self.assertIn(Value("name"), d)
        self.assertEqual(d[Value("name")], "Bob")

    def test_equal_output_field(self):
        """
        Tests that Value instances are considered equal when their output fields are the same.

        Checks for equality between Value instances with identical output fields, 
        as well as inequality when output fields differ or are not specified.
        Verifies the correctness of the equality comparison logic for Value objects.
        """
        value = Value("name", output_field=CharField())
        same_value = Value("name", output_field=CharField())
        other_value = Value("name", output_field=TimeField())
        no_output_field = Value("name")
        self.assertEqual(value, same_value)
        self.assertNotEqual(value, other_value)
        self.assertNotEqual(value, no_output_field)

    def test_raise_empty_expressionlist(self):
        msg = "ExpressionList requires at least one expression"
        with self.assertRaisesMessage(ValueError, msg):
            ExpressionList()

    def test_compile_unresolved(self):
        # This test might need to be revisited later on if #25425 is enforced.
        compiler = Time.objects.all().query.get_compiler(connection=connection)
        value = Value("foo")
        self.assertEqual(value.as_sql(compiler, connection), ("%s", ["foo"]))
        value = Value("foo", output_field=CharField())
        self.assertEqual(value.as_sql(compiler, connection), ("%s", ["foo"]))

    def test_output_field_decimalfield(self):
        Time.objects.create()
        time = Time.objects.annotate(one=Value(1, output_field=DecimalField())).first()
        self.assertEqual(time.one, 1)

    def test_resolve_output_field(self):
        """
        Tests the resolution of output fields for various data types.

        This function checks that the output field type of a Value expression is correctly resolved
        for different input values, including strings, booleans, integers, floats, dates, times, 
        durations, decimals, binaries, and UUIDs. It verifies that the output field type matches
        the expected field type for each input value type.

        The test covers a range of value types to ensure that the output field resolution works
        as expected across different data types. It uses the subTest context manager to run
        a separate test for each value type, providing more detailed error messages in case
        of failure.
        """
        value_types = [
            ("str", CharField),
            (True, BooleanField),
            (42, IntegerField),
            (3.14, FloatField),
            (datetime.date(2019, 5, 15), DateField),
            (datetime.datetime(2019, 5, 15), DateTimeField),
            (datetime.time(3, 16), TimeField),
            (datetime.timedelta(1), DurationField),
            (Decimal("3.14"), DecimalField),
            (b"", BinaryField),
            (uuid.uuid4(), UUIDField),
        ]
        for value, output_field_type in value_types:
            with self.subTest(type=type(value)):
                expr = Value(value)
                self.assertIsInstance(expr.output_field, output_field_type)

    def test_resolve_output_field_failure(self):
        """
        Tests that a FieldError is raised when attempting to resolve the output field 
        of a Value object with an unknown output field type.

        The test verifies that the error message matches the expected string, 
        indicating that the expression type cannot be resolved and the output field is unknown.

        This test case covers the scenario where the output field of a Value object 
        cannot be determined, resulting in a FieldError being raised.
        """
        msg = "Cannot resolve expression type, unknown output_field"
        with self.assertRaisesMessage(FieldError, msg):
            Value(object()).output_field

    def test_output_field_does_not_create_broken_validators(self):
        """
        The output field for a given Value doesn't get cleaned & validated,
        however validators may still be instantiated for a given field type
        and this demonstrates that they don't throw an exception.
        """
        value_types = [
            "str",
            True,
            42,
            3.14,
            datetime.date(2019, 5, 15),
            datetime.datetime(2019, 5, 15),
            datetime.time(3, 16),
            datetime.timedelta(1),
            Decimal("3.14"),
            b"",
            uuid.uuid4(),
        ]
        for value in value_types:
            with self.subTest(type=type(value)):
                field = Value(value)._resolve_output_field()
                field.clean(value, model_instance=None)


class ExistsTests(TestCase):
    def test_optimizations(self):
        """
        Tests database query optimizations for the Experiment model.

        Verifies that the query generated by the ORM optimizes away unnecessary
        operations, specifically ensuring that only a single query is executed,
        the primary key column is not quoted in the SQL, a limit is applied to
        the query, and no unnecessary ORDER BY clause is included in the query.

        This test case ensures that the database query is optimized to improve
        performance by minimizing the amount of data transferred and the number
        of database operations required to retrieve the data.
        """
        with CaptureQueriesContext(connection) as context:
            list(
                Experiment.objects.values(
                    exists=Exists(
                        Experiment.objects.order_by("pk"),
                    )
                ).order_by()
            )
        captured_queries = context.captured_queries
        self.assertEqual(len(captured_queries), 1)
        captured_sql = captured_queries[0]["sql"]
        self.assertNotIn(
            connection.ops.quote_name(Experiment._meta.pk.column),
            captured_sql,
        )
        self.assertIn(
            connection.ops.limit_offset_sql(None, 1),
            captured_sql,
        )
        self.assertNotIn("ORDER BY", captured_sql)

    def test_negated_empty_exists(self):
        manager = Manager.objects.create()
        qs = Manager.objects.filter(~Exists(Manager.objects.none()) & Q(pk=manager.pk))
        self.assertSequenceEqual(qs, [manager])

    def test_select_negated_empty_exists(self):
        """
        Tests the selection of objects where a negated exists clause is applied, verifying that an empty exists clause correctly negates to True when the object exists. 

        The test creates a Manager object and uses Django's ORM to annotate the object with a 'not_exists' attribute, which is set to True if no matching objects exist in the provided QuerySet. It then filters the QuerySet to retrieve the created Manager object, asserting that the object is retrieved successfully and the 'not_exists' attribute is set to True, as expected.
        """
        manager = Manager.objects.create()
        qs = Manager.objects.annotate(
            not_exists=~Exists(Manager.objects.none())
        ).filter(pk=manager.pk)
        self.assertSequenceEqual(qs, [manager])
        self.assertIs(qs.get().not_exists, True)

    def test_filter_by_empty_exists(self):
        """

        Tests filtering of objects based on the existence of a related query.

        This test case verifies that a Manager object can be retrieved when filtered by 
        the existence of a related query that is known to be empty. It checks that the 
        object is correctly annotated with 'exists' as False and that it can be filtered 
        based on this annotation. The test ensures that the resulting query set contains 
        the expected Manager object and that its 'exists' attribute is accurately set to 
        False.

        """
        manager = Manager.objects.create()
        qs = Manager.objects.annotate(exists=Exists(Manager.objects.none())).filter(
            pk=manager.pk, exists=False
        )
        self.assertSequenceEqual(qs, [manager])
        self.assertIs(qs.get().exists, False)


class FieldTransformTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class.

        This method creates a sample experiment object with predefined attributes, including
        name, assigned date, completed date, estimated time, start time, and end time.
        The sample experiment is used for testing purposes and provides a consistent
        dataset for evaluating the class's functionality. 

        The following attributes are set:
            - start date (25th June 2010)
            - start time (12:15:30.747 on 25th June 2010)
            - assigned and completed dates (25th June 2010 and 27th June 2010 respectively)
            - estimated and actual duration (both 2 days)
        """
        cls.sday = sday = datetime.date(2010, 6, 25)
        cls.stime = stime = datetime.datetime(2010, 6, 25, 12, 15, 30, 747000)
        cls.ex1 = Experiment.objects.create(
            name="Experiment 1",
            assigned=sday,
            completed=sday + datetime.timedelta(2),
            estimated_time=datetime.timedelta(2),
            start=stime,
            end=stime + datetime.timedelta(2),
        )

    def test_month_aggregation(self):
        self.assertEqual(
            Experiment.objects.aggregate(month_count=Count("assigned__month")),
            {"month_count": 1},
        )

    def test_transform_in_values(self):
        self.assertSequenceEqual(
            Experiment.objects.values("assigned__month"),
            [{"assigned__month": 6}],
        )

    def test_multiple_transforms_in_values(self):
        self.assertSequenceEqual(
            Experiment.objects.values("end__date__month"),
            [{"end__date__month": 6}],
        )


class ReprTests(SimpleTestCase):
    def test_expressions(self):
        """
        Tests various expressions in Django's database framework.

        This test suite covers a range of expressions, including:
            - Case and When statements
            - Column references
            - Field references
            - Combined expressions
            - Expression wrappers
            - Function calls
            - Slicing expressions
            - Ordering expressions
            - Raw SQL expressions
            - References to aggregate values
            - Literal values
            - Lists of expressions

        Each test case verifies that the string representation of an expression
        matches the expected output, helping ensure that complex database queries
        are correctly formulated and executed.
        """
        self.assertEqual(
            repr(Case(When(a=1))),
            "<Case: CASE WHEN <Q: (AND: ('a', 1))> THEN Value(None), ELSE Value(None)>",
        )
        self.assertEqual(
            repr(When(Q(age__gte=18), then=Value("legal"))),
            "<When: WHEN <Q: (AND: ('age__gte', 18))> THEN Value('legal')>",
        )
        self.assertEqual(repr(Col("alias", "field")), "Col(alias, field)")
        self.assertEqual(repr(F("published")), "F(published)")
        self.assertEqual(
            repr(F("cost") + F("tax")), "<CombinedExpression: F(cost) + F(tax)>"
        )
        self.assertEqual(
            repr(ExpressionWrapper(F("cost") + F("tax"), IntegerField())),
            "ExpressionWrapper(F(cost) + F(tax))",
        )
        self.assertEqual(
            repr(Func("published", function="TO_CHAR")),
            "Func(F(published), function=TO_CHAR)",
        )
        self.assertEqual(
            repr(F("published")[0:2]), "Sliced(F(published), slice(0, 2, None))"
        )
        self.assertEqual(
            repr(OuterRef("name")[1:5]), "Sliced(OuterRef(name), slice(1, 5, None))"
        )
        self.assertEqual(repr(OrderBy(Value(1))), "OrderBy(Value(1), descending=False)")
        self.assertEqual(repr(RawSQL("table.col", [])), "RawSQL(table.col, [])")
        self.assertEqual(
            repr(Ref("sum_cost", Sum("cost"))), "Ref(sum_cost, Sum(F(cost)))"
        )
        self.assertEqual(repr(Value(1)), "Value(1)")
        self.assertEqual(
            repr(ExpressionList(F("col"), F("anothercol"))),
            "ExpressionList(F(col), F(anothercol))",
        )
        self.assertEqual(
            repr(ExpressionList(OrderBy(F("col"), descending=False))),
            "ExpressionList(OrderBy(F(col), descending=False))",
        )

    def test_functions(self):
        """
        Tests the functionality of various database functions to ensure they produce the correct string representations.
        These functions include Coalesce, Concat, Length, Lower, Substr, and Upper, and are tested for their ability to accurately generate SQL-like function calls.
        Each test case verifies that the function under test returns a string that matches the expected output, confirming that the functions behave as intended.
        """
        self.assertEqual(repr(Coalesce("a", "b")), "Coalesce(F(a), F(b))")
        self.assertEqual(repr(Concat("a", "b")), "Concat(ConcatPair(F(a), F(b)))")
        self.assertEqual(repr(Length("a")), "Length(F(a))")
        self.assertEqual(repr(Lower("a")), "Lower(F(a))")
        self.assertEqual(repr(Substr("a", 1, 3)), "Substr(F(a), Value(1), Value(3))")
        self.assertEqual(repr(Upper("a")), "Upper(F(a))")

    def test_aggregates(self):
        """
        Tests the string representation of various aggregate functions.

        Verifies that the repr() method returns the expected string for each aggregate function,
        including Avg, Count, Max, Min, StdDev, Sum, and Variance, with different arguments and options.

        Ensures that the string representation accurately reflects the aggregate function's name, field, 
        and other parameters, such as sample size for StdDev and Variance calculations.
        """
        self.assertEqual(repr(Avg("a")), "Avg(F(a))")
        self.assertEqual(repr(Count("a")), "Count(F(a))")
        self.assertEqual(repr(Count("*")), "Count('*')")
        self.assertEqual(repr(Max("a")), "Max(F(a))")
        self.assertEqual(repr(Min("a")), "Min(F(a))")
        self.assertEqual(repr(StdDev("a")), "StdDev(F(a), sample=False)")
        self.assertEqual(repr(Sum("a")), "Sum(F(a))")
        self.assertEqual(
            repr(Variance("a", sample=True)), "Variance(F(a), sample=True)"
        )

    def test_distinct_aggregates(self):
        """
        Tests the creation of distinct aggregate functions, specifically the Count function.

        This test case verifies that the Count function is correctly represented when 
        the distinct parameter is set to True. It checks the string representation of 
        the Count function when applied to a field and when applied to all fields (*).
        """
        self.assertEqual(repr(Count("a", distinct=True)), "Count(F(a), distinct=True)")
        self.assertEqual(repr(Count("*", distinct=True)), "Count('*', distinct=True)")

    def test_filtered_aggregates(self):
        filter = Q(a=1)
        self.assertEqual(
            repr(Avg("a", filter=filter)), "Avg(F(a), filter=(AND: ('a', 1)))"
        )
        self.assertEqual(
            repr(Count("a", filter=filter)), "Count(F(a), filter=(AND: ('a', 1)))"
        )
        self.assertEqual(
            repr(Max("a", filter=filter)), "Max(F(a), filter=(AND: ('a', 1)))"
        )
        self.assertEqual(
            repr(Min("a", filter=filter)), "Min(F(a), filter=(AND: ('a', 1)))"
        )
        self.assertEqual(
            repr(StdDev("a", filter=filter)),
            "StdDev(F(a), filter=(AND: ('a', 1)), sample=False)",
        )
        self.assertEqual(
            repr(Sum("a", filter=filter)), "Sum(F(a), filter=(AND: ('a', 1)))"
        )
        self.assertEqual(
            repr(Variance("a", sample=True, filter=filter)),
            "Variance(F(a), filter=(AND: ('a', 1)), sample=True)",
        )
        self.assertEqual(
            repr(Count("a", filter=filter, distinct=True)),
            "Count(F(a), distinct=True, filter=(AND: ('a', 1)))",
        )


class CombinableTests(SimpleTestCase):
    bitwise_msg = (
        "Use .bitand(), .bitor(), and .bitxor() for bitwise logical operations."
    )

    def test_negation(self):
        c = Combinable()
        self.assertEqual(-c, c * -1)

    def test_and(self):
        """
        Tests that the bitwise AND operator (&) is not implemented for the Combinable class, raising a NotImplementedError with a specific error message.
        """
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            Combinable() & Combinable()

    def test_or(self):
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            Combinable() | Combinable()

    def test_xor(self):
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            Combinable() ^ Combinable()

    def test_reversed_and(self):
        """
        Tests that a TypeError is not directly raised but rather a NotImplementedError when attempting 
        to perform a bitwise AND operation with an object that doesn't support this operation and a Combinable instance.
        Verifies that the error message matches the expected bitwise operation message.

        """
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            object() & Combinable()

    def test_reversed_or(self):
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            object() | Combinable()

    def test_reversed_xor(self):
        """
        Tests that attempting to perform a bitwise XOR operation with an object that does not support it raises a NotImplementedError with the expected error message.
        """
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            object() ^ Combinable()


class CombinedExpressionTests(SimpleTestCase):
    def test_resolve_output_field_positive_integer(self):
        connectors = [
            Combinable.ADD,
            Combinable.MUL,
            Combinable.DIV,
            Combinable.MOD,
            Combinable.POW,
        ]
        for connector in connectors:
            with self.subTest(connector=connector):
                expr = CombinedExpression(
                    Expression(PositiveIntegerField()),
                    connector,
                    Expression(PositiveIntegerField()),
                )
                self.assertIsInstance(expr.output_field, PositiveIntegerField)

    def test_resolve_output_field_number(self):
        """

        Tests the ability to resolve the output field number of a CombinedExpression.

        This test ensures that when two expressions with different field types are combined using various arithmetic operations, the resulting output field type is correctly determined.

        The test covers various combinations of field types, including IntegerField, AutoField, DecimalField, and FloatField, and arithmetic operations such as addition, subtraction, multiplication, division, and modulus.

        It verifies that the output field type of the combined expression is an instance of the expected type, based on the types of the input fields and the operation used to combine them.

        """
        tests = [
            (IntegerField, AutoField, IntegerField),
            (AutoField, IntegerField, IntegerField),
            (IntegerField, DecimalField, DecimalField),
            (DecimalField, IntegerField, DecimalField),
            (IntegerField, FloatField, FloatField),
            (FloatField, IntegerField, FloatField),
        ]
        connectors = [
            Combinable.ADD,
            Combinable.SUB,
            Combinable.MUL,
            Combinable.DIV,
            Combinable.MOD,
        ]
        for lhs, rhs, combined in tests:
            for connector in connectors:
                with self.subTest(
                    lhs=lhs, connector=connector, rhs=rhs, combined=combined
                ):
                    expr = CombinedExpression(
                        Expression(lhs()),
                        connector,
                        Expression(rhs()),
                    )
                    self.assertIsInstance(expr.output_field, combined)

    def test_resolve_output_field_with_null(self):
        """

        Tests the resolve output field of a CombinedExpression with null values.

        Verifies that attempting to determine the output field of an expression 
        involving null values and various field types (including numeric and 
        datetime fields) raises a FieldError with a descriptive message. The test 
        covers different combinations of field types and operators (addition and 
        subtraction) to ensure that the resolve output field functionality 
        correctly handles null values and reports errors as expected.

        The test cases cover the following scenarios:
        - Using null with various field types (e.g., AutoField, DecimalField, FloatField, etc.)
        - Using various field types with null as the left- or right-hand side of an expression
        - Attempting to perform addition and subtraction operations with null values

        The expected outcome is that a FieldError is raised with a message indicating 
        that the type of the expression cannot be inferred.

        """
        def null():
            return Value(None)

        tests = [
            # Numbers.
            (AutoField, Combinable.ADD, null),
            (DecimalField, Combinable.ADD, null),
            (FloatField, Combinable.ADD, null),
            (IntegerField, Combinable.ADD, null),
            (IntegerField, Combinable.SUB, null),
            (null, Combinable.ADD, IntegerField),
            # Dates.
            (DateField, Combinable.ADD, null),
            (DateTimeField, Combinable.ADD, null),
            (DurationField, Combinable.ADD, null),
            (TimeField, Combinable.ADD, null),
            (TimeField, Combinable.SUB, null),
            (null, Combinable.ADD, DateTimeField),
            (DateField, Combinable.SUB, null),
        ]
        for lhs, connector, rhs in tests:
            msg = (
                f"Cannot infer type of {connector!r} expression involving these types: "
            )
            with self.subTest(lhs=lhs, connector=connector, rhs=rhs):
                expr = CombinedExpression(
                    Expression(lhs()),
                    connector,
                    Expression(rhs()),
                )
                with self.assertRaisesMessage(FieldError, msg):
                    expr.output_field

    def test_resolve_output_field_numbers_with_null(self):
        """

        Tests whether the output field of a CombinedExpression is resolved correctly 
        when either or both of the input values are None.

        The test covers various combinations of numeric input values (float, integer, decimal) 
        and different operators (addition, subtraction, multiplication, division, modulus, exponentiation).
        It verifies that the output field is of the expected type (FloatField, IntegerField, DecimalField) 
        even when one of the input values is null.

        """
        test_values = [
            (3.14159, None, FloatField),
            (None, 3.14159, FloatField),
            (None, 42, IntegerField),
            (42, None, IntegerField),
            (None, Decimal("3.14"), DecimalField),
            (Decimal("3.14"), None, DecimalField),
        ]
        connectors = [
            Combinable.ADD,
            Combinable.SUB,
            Combinable.MUL,
            Combinable.DIV,
            Combinable.MOD,
            Combinable.POW,
        ]
        for lhs, rhs, expected_output_field in test_values:
            for connector in connectors:
                with self.subTest(lhs=lhs, connector=connector, rhs=rhs):
                    expr = CombinedExpression(Value(lhs), connector, Value(rhs))
                    self.assertIsInstance(expr.output_field, expected_output_field)

    def test_resolve_output_field_dates(self):
        """
        Tests the resolve_output_field_dates method to ensure correct field type resolution when combining date and time fields using ADD and SUB operations.

        The function verifies the expected output field type for various combinations of date and time fields, including DateField, DateTimeField, TimeField, and DurationField, and checks for the correct exception handling when the field type cannot be inferred.

        The test cases cover a wide range of scenarios, including:

        - Adding two date or time fields
        - Adding a date or time field with a duration field
        - Subtracting two date or time fields
        - Subtracting a duration field from a date or time field

        Each test case checks if the resulting field type matches the expected type or if a FieldError is raised when the field type cannot be determined.

        This test ensures that the resolve_output_field_dates method behaves correctly and provides the expected output field type for different date and time field combinations, helping to prevent potential type-related errors in the application.
        """
        tests = [
            # Add - same type.
            (DateField, Combinable.ADD, DateField, FieldError),
            (DateTimeField, Combinable.ADD, DateTimeField, FieldError),
            (TimeField, Combinable.ADD, TimeField, FieldError),
            (DurationField, Combinable.ADD, DurationField, DurationField),
            # Add - different type.
            (DateField, Combinable.ADD, DurationField, DateTimeField),
            (DateTimeField, Combinable.ADD, DurationField, DateTimeField),
            (TimeField, Combinable.ADD, DurationField, TimeField),
            (DurationField, Combinable.ADD, DateField, DateTimeField),
            (DurationField, Combinable.ADD, DateTimeField, DateTimeField),
            (DurationField, Combinable.ADD, TimeField, TimeField),
            # Subtract - same type.
            (DateField, Combinable.SUB, DateField, DurationField),
            (DateTimeField, Combinable.SUB, DateTimeField, DurationField),
            (TimeField, Combinable.SUB, TimeField, DurationField),
            (DurationField, Combinable.SUB, DurationField, DurationField),
            # Subtract - different type.
            (DateField, Combinable.SUB, DurationField, DateTimeField),
            (DateTimeField, Combinable.SUB, DurationField, DateTimeField),
            (TimeField, Combinable.SUB, DurationField, TimeField),
            (DurationField, Combinable.SUB, DateField, FieldError),
            (DurationField, Combinable.SUB, DateTimeField, FieldError),
            (DurationField, Combinable.SUB, DateTimeField, FieldError),
        ]
        for lhs, connector, rhs, combined in tests:
            msg = (
                f"Cannot infer type of {connector!r} expression involving these types: "
            )
            with self.subTest(lhs=lhs, connector=connector, rhs=rhs, combined=combined):
                expr = CombinedExpression(
                    Expression(lhs()),
                    connector,
                    Expression(rhs()),
                )
                if issubclass(combined, Exception):
                    with self.assertRaisesMessage(combined, msg):
                        expr.output_field
                else:
                    self.assertIsInstance(expr.output_field, combined)

    def test_mixed_char_date_with_annotate(self):
        """
        Tests that attempting to annotate a queryset with a mixed operation between a CharField and a DateField raises a FieldError.

        This test case ensures that Django's ORM correctly handles the case where a '+' operator is applied to fields of incompatible types, 
        requiring the user to specify an output_field to resolve the ambiguity.

        The expected error message is checked to verify that the FieldError is raised with the correct message, 
        indicating that the user must set output_field to proceed with the annotation operation.
        """
        queryset = Experiment.objects.annotate(nonsense=F("name") + F("assigned"))
        msg = (
            "Cannot infer type of '+' expression involving these types: CharField, "
            "DateField. You must set output_field."
        )
        with self.assertRaisesMessage(FieldError, msg):
            list(queryset)


class ExpressionWrapperTests(SimpleTestCase):
    def test_empty_group_by(self):
        expr = ExpressionWrapper(Value(3), output_field=IntegerField())
        self.assertEqual(expr.get_group_by_cols(), [])

    def test_non_empty_group_by(self):
        value = Value("f")
        value.output_field = None
        expr = ExpressionWrapper(Lower(value), output_field=IntegerField())
        group_by_cols = expr.get_group_by_cols()
        self.assertEqual(group_by_cols, [expr.expression])
        self.assertEqual(group_by_cols[0].output_field, expr.output_field)


class NegatedExpressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the class.

        This method creates test instances of Employee and Company objects, including a CEO and two companies,
        one based in the EU and the other outside the EU. The created instances are stored as class attributes,
        making them available for use in subsequent tests.

        The test data includes a CEO with basic attributes, and two companies with various characteristics,
        such as name, number of employees, number of chairs, and EU status.

        """
        ceo = Employee.objects.create(firstname="Joe", lastname="Smith", salary=10)
        cls.eu_company = Company.objects.create(
            name="Example Inc.",
            num_employees=2300,
            num_chairs=5,
            ceo=ceo,
            based_in_eu=True,
        )
        cls.non_eu_company = Company.objects.create(
            name="Foobar Ltd.",
            num_employees=3,
            num_chairs=4,
            ceo=ceo,
            based_in_eu=False,
        )

    def test_invert(self):
        f = F("field")
        self.assertEqual(~f, NegatedExpression(f))
        self.assertIsNot(~~f, f)
        self.assertEqual(~~f, f)

    def test_filter(self):
        """
        Tests the filtering of Company objects based on logical conditions.

        This test ensures that the model's filter method correctly applies negation and double negation to field values,
        and that it works with annotated fields and F-expressions. The test cases cover various scenarios,
        including filtering by a negated field, a double negated field, and an annotated field.
        """
        self.assertSequenceEqual(
            Company.objects.filter(~F("based_in_eu")),
            [self.non_eu_company],
        )

        qs = Company.objects.annotate(eu_required=~Value(False))
        self.assertSequenceEqual(
            qs.filter(based_in_eu=F("eu_required")).order_by("eu_required"),
            [self.eu_company],
        )
        self.assertSequenceEqual(
            qs.filter(based_in_eu=~~F("eu_required")),
            [self.eu_company],
        )
        self.assertSequenceEqual(
            qs.filter(based_in_eu=~F("eu_required")),
            [self.non_eu_company],
        )
        self.assertSequenceEqual(qs.filter(based_in_eu=~F("based_in_eu")), [])

    def test_values(self):
        self.assertSequenceEqual(
            Company.objects.annotate(negated=~F("based_in_eu"))
            .values_list("name", "negated")
            .order_by("name"),
            [("Example Inc.", False), ("Foobar Ltd.", True)],
        )


class OrderByTests(SimpleTestCase):
    def test_equal(self):
        """
        Tests the equality of OrderBy instances.

        Ensures that two OrderBy instances are considered equal when they have the same field and nulls order,
        and not equal when the nulls order differs.

        This is crucial for proper comparison and sorting of ordered fields in queries. 

        It verifies that the equality check correctly handles the 'nulls_last' parameter, 
        which determines whether NULL values are placed at the beginning or end of the sorted results.

        """
        self.assertEqual(
            OrderBy(F("field"), nulls_last=True),
            OrderBy(F("field"), nulls_last=True),
        )
        self.assertNotEqual(
            OrderBy(F("field"), nulls_last=True),
            OrderBy(F("field")),
        )

    def test_hash(self):
        self.assertEqual(
            hash(OrderBy(F("field"), nulls_last=True)),
            hash(OrderBy(F("field"), nulls_last=True)),
        )
        self.assertNotEqual(
            hash(OrderBy(F("field"), nulls_last=True)),
            hash(OrderBy(F("field"))),
        )

    def test_nulls_false(self):
        """
        ..: 
            Test that nulls_first and nulls_last parameters are valid.

            This test ensures that the OrderBy function and the asc and desc methods
            of the F function raise a ValueError when the nulls_first or nulls_last
            parameters are set to False. These parameters must be either True or None.
        """
        msg = "nulls_first and nulls_last values must be True or None."
        with self.assertRaisesMessage(ValueError, msg):
            OrderBy(F("field"), nulls_first=False)
        with self.assertRaisesMessage(ValueError, msg):
            OrderBy(F("field"), nulls_last=False)
        with self.assertRaisesMessage(ValueError, msg):
            F("field").asc(nulls_first=False)
        with self.assertRaisesMessage(ValueError, msg):
            F("field").desc(nulls_last=False)
