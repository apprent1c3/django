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

        Tests that annotating values using a RawSQL expression correctly filters companies.

        The test verifies that companies are annotated with a specific value, 
        then filtered to only include those with a matching annotation, 
        and finally ordered alphabetically by name.
        The expected result is a sequence containing the example company, foobar ltd, and gmbh.

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
        """

        Tests that annotating values using RawSQL correctly counts the number of companies.

        This test case verifies that the annotation is applied correctly and does not 
        affect the overall count of companies in the database. It checks that the count 
        of annotated companies matches the expected total count of 3.

        """
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
        Tests the update functionality by modifying the number of chairs to match the number of employees for each company.

        Verifies that the update operation correctly sets the number of chairs to be equal to the number of employees in the company query, and that the resulting data matches the expected output.

        Returns:
            None

        Note:
            This test method asserts that the updated company query data contains the expected number of chairs and employees for each company.

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
        """

        Tests the slicing of F expressions in Django model fields.

        This test case covers a variety of slicing scenarios, including:
        - Slicing from the start of the string
        - Slicing from the start of the string with a specified end index
        - Slicing from a specified start index to the end of the string
        - Slicing from a specified start index to a specified end index
        - Chaining slice operations

        Each test case sets the value of a model field using an F expression with the specified slice operation,
        saves the model instance, and then asserts that the resulting value is as expected.
        The original value of the field is restored after each test case.

        """
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
        msg = "Negative indexing is not supported."
        indexes = [slice(0, -4), slice(-4, 0), slice(-4), -5]
        for i in indexes:
            with self.subTest(i=i), self.assertRaisesMessage(ValueError, msg):
                F("name")[i]

    def test_slicing_of_f_expressions_with_slice_stop_less_than_slice_start(self):
        msg = "Slice stop must be greater than slice start."
        with self.assertRaisesMessage(ValueError, msg):
            F("name")[4:2]

    def test_slicing_of_f_expressions_with_invalid_type(self):
        msg = "Argument to slice must be either int or slice instance."
        with self.assertRaisesMessage(TypeError, msg):
            F("name")["error"]

    def test_slicing_of_f_expressions_with_step(self):
        msg = "Step argument is not supported."
        with self.assertRaisesMessage(ValueError, msg):
            F("name")[::4]

    def test_slicing_of_f_unsupported_field(self):
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
        """

        Tests the correct application of the order of operations in a database query update.
        The test verifies that the query updates the 'num_chairs' field by applying the correct
        mathematical operations on the 'num_employees' field, specifically multiplication before addition.
        The expected outcome is compared to a predefined sequence of company data, ensuring the update
        operation produces the correct results.

        """
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
        """

        Tests the functionality of filtering a queryset with a join operation.

        This test case checks if a queryset can be successfully filtered based on a join
        operation between two fields. It also verifies that attempting to update a field
        based on a joined field reference raises a FieldError.

        The test covers the following scenarios:
        - Filtering a queryset with a join operation using the `filter` method.
        - Excluding objects from a queryset based on a join operation using the `exclude` method.
        - Updating objects in a queryset with a direct value.
        - Attempting to update objects in a queryset with a joined field reference, which should raise an error.

        """
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
        test_co = Company(
            name=Lower(Value("UPPER")), num_employees=32, num_chairs=1, ceo=self.max
        )
        test_co.save()
        test_co.refresh_from_db()
        self.assertEqual(test_co.name, "upper")

    def test_new_object_create(self):
        """

        Tests the creation of a new object in the database.

        Verifies that a Company object is successfully created with the specified attributes,
        and that the object's name is properly converted to lowercase during the creation process.

        """
        test_co = Company.objects.create(
            name=Lower(Value("UPPER")), num_employees=32, num_chairs=1, ceo=self.max
        )
        test_co.refresh_from_db()
        self.assertEqual(test_co.name, "upper")

    def test_object_create_with_aggregate(self):
        # Aggregates are not allowed when inserting new data
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
        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            RemoteEmployee.objects.update(adjusted_salary=F("salary") * 5)

    def test_object_update_unsaved_objects(self):
        # F expressions cannot be used to update attributes on objects which do
        # not yet exist in the database
        """
        Tests that attempting to save an object with unsaved F() expressions raises a ValueError.

        This test case verifies that when creating a new object and assigning an F() expression 
        to one of its attributes, an error is raised when trying to save the object, as F() 
        expressions are only allowed for updating existing objects, not for inserting new ones.

        The test covers scenarios where F() expressions are used with both numeric and string 
        attributes, ensuring that the expected error message is raised in each case.
        """
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

        Test to ensure correct joining of tables when using keyword arguments in filter operations.

        This test case verifies that the Django ORM correctly orders joins when using keyword arguments to filter querysets.
        It specifically checks that a single join is performed when filtering on related objects with multiple conditions.

        The test confirms that the generated SQL query contains only one 'JOIN' statement, indicating efficient joining of tables.

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
        """
        Test the ordering of keyword arguments in the Django ORM's filter method, 
        specifically ensuring that the number of employees in a company's CEO set 
        matches the primary key of the Employee model, and vice versa, 
        while also verifying that the resulting query only includes a single JOIN statement.
        """
        qs = Employee.objects.filter(
            company_ceo_set__num_employees=F("pk"),
            pk=F("company_ceo_set__num_employees"),
        )
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_ticket_18375_chained_filters(self):
        # F() expressions do not reuse joins from previous filter.
        """

        Tests that chained filters on the same related field do not result in duplicate joins.

        Verifies that when applying multiple filters on the same related field, the resulting query only includes the necessary joins, avoiding redundant joins that could impact performance.

        """
        qs = Employee.objects.filter(company_ceo_set__num_employees=F("pk")).filter(
            company_ceo_set__num_employees=F("company_ceo_set__num_employees")
        )
        self.assertEqual(str(qs.query).count("JOIN"), 2)

    def test_order_by_exists(self):
        """
        Tests the functionality of ordering objects by the existence of related objects.

        This test case verifies that employees with a matching CEO in the Company model are ordered according to their seniority.

        The test creates an employee instance and then queries the database for employees with the same last name, ordering them by the existence of a company where the employee is the CEO, in descending order.

        It asserts that the resulting sequence of employees is as expected, with the most senior employee first.
        """
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
        Test the functionality of OuterRef in a subquery.

        This test case verifies that a queryset containing an OuterRef cannot be evaluated directly.
        It also checks that such a queryset can be successfully used in a subquery, specifically within an Exists annotation.

        The test consists of two main parts: 
        1. Verifying that attempting to directly evaluate the queryset raises a ValueError.
        2. Ensuring that using the queryset in an Exists annotation within another query returns the expected result, indicating the successful use of OuterRef in a subquery context.

        The outcome of this test confirms the correct behavior of OuterRef in both its intended and unintended usage scenarios.
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
        """

        Tests that a single field output from a queryset using the Exists function
        results in a BooleanField being used as the output field.

        This test case ensures that when a queryset is constrained to a single field,
        the Exists function correctly determines the output field type, which is
        expected to be a BooleanField, indicating whether the query set contains any
        results.

        """
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

        Tests the usage of subqueries with the 'Exists' clause in Django ORM queries.

        This test verifies that the 'is_ceo', 'is_point_of_contact', and 'small_company' annotations are correctly applied to the Employee queryset, and that they are distinct from one another.

        The test checks for the following conditions:
        - The 'is_ceo' annotation is True, indicating the employee is a CEO.
        - The 'is_point_of_contact' annotation is False, indicating the employee is not a point of contact.
        - The 'small_company' annotation is True, indicating the company has fewer than 200 employees.

        The test also ensures that the annotations 'is_ceo', 'is_point_of_contact', and 'small_company' are not equal to each other, verifying that they represent distinct conditions.

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
        """

        Tests the generation of SQL for a subquery operation.

        Verifies that a subquery is correctly identified and rendered as a SQL subquery.
        The function checks the existence of a subquery in the query object, 
        and then inspects the generated SQL to ensure it contains the expected subquery syntax.

        """
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
        """

        Tests the usage of a nested subquery to identify employees who are points of contact.

        This test case verifies that the results of using an Exists annotation and a Subquery 
        annotation to filter employees are equivalent. The Exists annotation checks if a 
        related company has the employee as its point of contact, while the Subquery 
        annotation uses the results of this Exists annotation to further filter the 
        employees. The test asserts that both methods produce the same set of results.

        """
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
        """

        Tests the use of nested subqueries with outer references in a django ORM query.
        The test creates simulation runs with start, end, and midpoint times, then uses a subquery
        to filter times based on the start time of a simulation run. It then uses another subquery
        to get the time of a simulation run and checks that all created times are returned.

        """
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
        Tests if subqueries can correctly reference a joined table multiple times.

        This test case evaluates the ability of the ORM to handle subqueries that reference
        a joined table more than once. It constructs an inner query that filters companies
        based on conditions referencing both the CEO's salary and the point of contact's salary,
        then uses this inner query as a subquery in an outer query to filter companies.
        The test asserts that the outer query should return no results, verifying that the
        subquery is correctly processed and that the references to the joined table are handled
        as expected.
        """
        inner = Company.objects.filter(
            num_chairs__gte=OuterRef("ceo__salary"),
            num_employees__gte=OuterRef("point_of_contact__salary"),
        )
        # Another contrived example (there is no need to have a subquery here)
        outer = Company.objects.filter(pk__in=Subquery(inner.values("pk")))
        self.assertFalse(outer.exists())

    def test_subquery_filter_by_aggregate(self):
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
        Tests the creation of an object with an F expression in a subquery.

        This test case verifies that it is possible to create a new object using a subquery
        that utilizes an F expression to dynamically calculate a value. The subquery is
        used to determine the number of employees for the new object, which should be one
        more than the current maximum number of employees.

        The test creates a new company with a certain number of employees, then creates
        another company with a number of employees that is calculated by the subquery.
        The test then checks that the number of employees for the second company is indeed
        one more than the number of employees for the first company.
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
        class FuncA(Func):
            output_field = CharField()

        class FuncB(Func):
            pass

        expr = FuncB(FuncA())
        self.assertEqual(expr.output_field, FuncA.output_field)

    def test_outerref_mixed_case_table_name(self):
        """

        Tests that a subquery with an OuterRef referencing a model relation 
        with a mixed case table name does not produce any results.

        This test verifies the correct behavior of the OuterRef and Subquery 
        mechanisms when dealing with mixed case table names, ensuring that 
        no results are returned when the query is executed.

        """
        inner = Result.objects.filter(result_time__gte=OuterRef("experiment__assigned"))
        outer = Result.objects.filter(pk__in=Subquery(inner.values("pk")))
        self.assertFalse(outer.exists())

    def test_outerref_with_operator(self):
        """

        Tests the use of OuterRef with a database operator in a subquery.

        This test case verifies that a company is correctly retrieved when its number of employees
        is related to the salary of its CEO, using an OuterRef in a subquery. The test checks
        that the retrieved company matches the expected one ('Test GmbH').

        The test covers the scenario where a subquery is used to filter companies based on a
        relationship between two fields, demonstrating the correct application of OuterRef
        and operator usage in a query.

        """
        inner = Company.objects.filter(num_employees=OuterRef("ceo__salary") + 2)
        outer = Company.objects.filter(pk__in=Subquery(inner.values("pk")))
        self.assertEqual(outer.get().name, "Test GmbH")

    def test_nested_outerref_with_function(self):
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
        expr = Value(1)
        expr.convert_value  # populate cached property
        self.assertEqual(pickle.loads(pickle.dumps(expr)), expr)

    def test_incorrect_field_in_F_expression(self):
        with self.assertRaisesMessage(
            FieldError, "Cannot resolve keyword 'nope' into field."
        ):
            list(Employee.objects.filter(firstname=F("nope")))

    def test_incorrect_joined_field_in_F_expression(self):
        """
        Tests that an incorrect joined field in an F-expression raises a FieldError.

        Verifies that Django's ORM correctly handles invalid field names in F-expressions
        used within filter queries, ensuring that a meaningful error message is raised
        when attempting to resolve a non-existent field. The test checks that the error
        message specifically indicates the inability to resolve the provided keyword into
        a field, helping to diagnose and correct issues with joined field references in
        queries.
        """
        with self.assertRaisesMessage(
            FieldError, "Cannot resolve keyword 'nope' into field."
        ):
            list(Company.objects.filter(ceo__pk=F("point_of_contact__nope")))

    def test_exists_in_filter(self):
        inner = Company.objects.filter(ceo=OuterRef("pk")).values("pk")
        qs1 = Employee.objects.filter(Exists(inner))
        qs2 = Employee.objects.annotate(found=Exists(inner)).filter(found=True)
        self.assertCountEqual(qs1, qs2)
        self.assertFalse(Employee.objects.exclude(Exists(inner)).exists())
        self.assertCountEqual(qs2, Employee.objects.exclude(~Exists(inner)))

    def test_subquery_in_filter(self):
        """

        Tests the functionality of using a subquery within a filter to retrieve specific objects.

        This test case verifies that the Employee objects can be filtered based on a subquery 
        that checks for companies whose CEO works for them, and ensures that the result matches 
        the expected Employee object.

        """
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
        """

        Tests the functionality of using a case expression in a filter to identify employees who are either a CEO or a point of contact.

        The test checks if the query correctly identifies employees holding these key positions by comparing the result set with the expected set of employees.

        It verifies that the case expression in the filter correctly handles boolean outputs, ensuring that the resulting query set only includes employees who match the given conditions.

        """
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
        """
        This method tests the filtering of employee records based on boolean expressions combining exists and other conditions.

        It verifies that the correct employees are returned when filtering using the following logic:
        - Employees who are either CEOs or points of contact of a company.
        - Employees who are both CEOs and points of contact.
        - Employees who are CEOs and have a salary greater than or equal to a certain threshold.
        - Employees who are either points of contact or have a salary less than a certain threshold.
        - Employees who meet certain salary conditions and are CEOs or points of contact.

        The method ensures that the queries using `Exists` and `Q` objects return the expected employee records, covering various scenarios of logical operations and filtering conditions.
        """
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

        Tests the usage of a boolean expression in a Django ORM Q object, 
        specifically checking for the existence of a related point of contact.
        Verifies that an Employee instance is correctly filtered when it exists as 
        a point of contact for at least one Company instance.

        """
        is_poc = Company.objects.filter(point_of_contact=OuterRef("pk"))
        self.gmbh.point_of_contact = self.max
        self.gmbh.save()
        self.assertCountEqual(Employee.objects.filter(Q(Exists(is_poc))), [self.max])


class IterableLookupInnerExpressionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for testing purposes.

        This method creates a test employee and five companies with varying numbers of employees and chairs.
        The companies are created with the same CEO and different employee and chair counts to facilitate testing of different scenarios.
        The created companies are stored as class attributes for later use in tests.

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
        Test searching for companies by a range of employee numbers using a named tuple to specify the range boundaries.

        The function verifies that a query correctly filters companies based on the number of employees within a specified range (in this case, between 51 and 100 employees) and asserts that the resulting query set matches the expected company instance.
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
        Checks that Field and Value objects with the same name are not considered equal. This test validates that these two distinct object types maintain their identity and are distinguished by the equality operator, even when they share the same underlying attribute, such as name.
        """
        f = F("name")
        value = Value("name")
        self.assertNotEqual(f, value)
        self.assertNotEqual(value, f)

    def test_contains(self):
        """
        Tests whether an attempt to check for containment of an element in an instance of class F raises a TypeError with a message indicating that the class instance is not iterable. The test ensures that trying to use the 'in' operator on an instance of F, such as checking if a string is contained within it, correctly results in an error due to its non-iterable nature.
        """
        msg = "argument of type 'F' is not iterable"
        with self.assertRaisesMessage(TypeError, msg):
            "" in F("name")


class ExpressionsTests(TestCase):
    def test_F_reuse(self):
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

        Tests the hash functionality of the Expression class.

        This method validates that instances of Expression with the same attributes produce the same hash value, 
        while instances with different attributes produce distinct hash values.

        In particular, it checks for the following conditions:
        - Two empty Expression instances have the same hash value.
        - Expression instances with the same output field have the same hash value, 
          regardless of whether the field is passed as an argument or by keyword argument.
        - Expression instances with different output fields have different hash values.
        - Expression instances referencing different model fields have different hash values.

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
        n = Number.objects.create(integer=1, decimal_value=Decimal("0.5"))
        n.decimal_value = F("decimal_value") - Decimal("0.4")
        n.save()
        n.refresh_from_db()
        self.assertEqual(n.decimal_value, Decimal("0.1"))


class ExpressionOperatorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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

        Tests subtraction of a constant from the left-hand side of an assignment in a database query.

        Verifies that subtracting an integer from an integer field and a float from a float field
        updates the corresponding values correctly in the database.

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

        Tests left-hand division operation in database query operations.

        Verifies that division assignments update the values of integer and float fields
        in the database correctly. This includes testing both integer and floating-point
        divisions with specific expected results.

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
        and verifying the result is as expected.

        The test case updates the integer field of a specific Number object to be the 
        remainder of its current value divided by 20, then asserts that the updated value 
        is correct. This ensures that the modulo operation is applied correctly to the 
        object's field in the database.
        """
        Number.objects.filter(pk=self.n.pk).update(integer=F("integer") % 20)
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 2)

    def test_lefthand_modulo_null(self):
        # LH Modulo arithmetic on integers.
        """

        Tests the behavior of the modulo operator on a left-hand side null value.

        Verifies that when a null value is encountered in a modulo operation, the result does not cause any errors, but instead, the original null value is preserved.
        This ensures that the null value is not altered or replaced with a default value, maintaining data integrity and avoiding potential inconsistencies.

        """
        Employee.objects.create(firstname="John", lastname="Doe", salary=None)
        qs = Employee.objects.annotate(modsalary=F("salary") % 20)
        self.assertIsNone(qs.get().salary)

    def test_lefthand_bitwise_and(self):
        # LH Bitwise ands on integers
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

        Tests the lefthand bitwise OR operation on integer fields in the database.
        Verifies that performing a bitwise OR operation with a given integer updates 
        the values correctly, checking for both positive and negative integer cases.

        """
        Number.objects.update(integer=F("integer").bitor(48))

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 58)
        self.assertEqual(Number.objects.get(pk=self.n1.pk).integer, -10)

    def test_lefthand_transformed_field_bitwise_or(self):
        Employee.objects.create(firstname="Max", lastname="Mustermann")
        with register_lookup(CharField, Length):
            qs = Employee.objects.annotate(bitor=F("lastname__length").bitor(48))
            self.assertEqual(qs.get().bitor, 58)

    def test_lefthand_power(self):
        # LH Power arithmetic operation on floats and integers
        Number.objects.filter(pk=self.n.pk).update(
            integer=F("integer") ** 2, float=F("float") ** 1.5
        )
        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 1764)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(61.02, places=2)
        )

    def test_lefthand_bitwise_xor(self):
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

        Tests the behavior of a left-hand bitwise XOR operation with a right-hand null value.

        This test case creates an Employee instance, updates the salary attribute using a bitwise XOR operation with a null value, 
        and then verifies that the resulting salary is None.

        """
        employee = Employee.objects.create(firstname="John", lastname="Doe", salary=48)
        Employee.objects.update(salary=F("salary").bitxor(None))
        employee.refresh_from_db()
        self.assertIsNone(employee.salary)

    @unittest.skipUnless(
        connection.vendor == "oracle", "Oracle doesn't support bitwise XOR."
    )
    def test_lefthand_bitwise_xor_not_supported(self):
        """

        Tests that an error is raised when attempting to perform a lefthand bitwise XOR operation on an Oracle database.

        The Oracle database does not support bitwise XOR operations, and this test verifies that the
        correct error message is raised when such an operation is attempted through the Django ORM.

        The test checks that a NotSupportedError is raised with a specific message indicating that
        bitwise XOR is not supported in Oracle.

        """
        msg = "Bitwise XOR is not supported in Oracle."
        with self.assertRaisesMessage(NotSupportedError, msg):
            Number.objects.update(integer=F("integer").bitxor(48))

    def test_right_hand_addition(self):
        # Right hand operators
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
        """
        Tests the division of an integer and a float by using the right hand side division in a database query.

        Verifies that the division operation is applied correctly to the integer and float fields of a Number object,
        and that the results match the expected values.

        """
        Number.objects.filter(pk=self.n.pk).update(
            integer=640 / F("integer"), float=42.7 / F("float")
        )

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 15)
        self.assertEqual(
            Number.objects.get(pk=self.n.pk).float, Approximate(2.755, places=3)
        )

    def test_right_hand_modulo(self):
        # RH Modulo arithmetic on integers
        """

        Tests the application of the modulo operator with the right-hand side being a database field.

        This test case verifies that the modulo operation is correctly applied when the right-hand operand is a database field, 
        and the result is updated in the database. The test checks that the calculated result is correct and matches the expected value.

        """
        Number.objects.filter(pk=self.n.pk).update(integer=69 % F("integer"))

        self.assertEqual(Number.objects.get(pk=self.n.pk).integer, 27)

    def test_righthand_power(self):
        # RH Power arithmetic operation on floats and integers
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
        Sets up test data for experiments, creating a set of Experiment objects with varying durations, start times, and completion dates.
        The function initializes several class attributes, including:
        - `sday` and `stime`: a specific date and datetime used as a reference point for experiment creation.
        - `deltas`: a list of time deltas representing the duration of each experiment.
        - `delays`: a list of time deltas representing the delay between the assigned date and start time of each experiment.
        - `days_long`: a list of time deltas representing the duration between the assigned date and completion date of each experiment.
        - `expnames`: a list of experiment names.
        The function creates a total of 6 Experiment objects with diverse characteristics, including different assigned dates, start times, end times, and estimated durations.
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
        queryset = Experiment.objects.filter(
            end__lt=F("start") + datetime.timedelta(hours=1)
        )
        q1 = str(queryset.query)
        q2 = str(queryset.query)
        self.assertEqual(q1, q2)

    def test_query_clone(self):
        # Ticket #21643 - Crash when compiling query more than once
        qs = Experiment.objects.filter(end__lt=F("start") + datetime.timedelta(hours=1))
        qs2 = qs.all()
        list(qs)
        list(qs2)
        # Intentionally no assert

    def test_delta_add(self):
        """
        ```    
        \"\"\"
        Tests the addition of a delta to filter experiments.

        This method checks if the addition of a delta (time interval) to the start
        of an experiment correctly filters experiments that have ended within 
        that interval. It tests three different scenarios: 
        less than, less than or equal to, and equivalent expressions for 
        less than with swapped operands.

        The function iterates over a list of deltas and for each delta, it verifies 
        that the filtered experiments match the expected set of experiment names.
        \"\"\"
        ```
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
        Tests the delta subtraction functionality by iterating through a list of deltas.

        This function checks the correctness of date range filtering by comparing the results
        of experiment queries with expected outcomes. It verifies that experiments are 
        correctly included or excluded based on their start times relative to their end times 
        minus a given delta.

        Two scenarios are tested: strict inequality (greater than) and non-strict inequality 
        (greater than or equal to). The function ensures that the results of these queries 
        match the expected set of experiment names for each delta value.

        The function relies on pre-defined delta values and expected experiment names stored 
        in instance variables, and uses these to drive the test cases and verify the 
        correctness of the delta subtraction logic.
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
        Tests the exclude functionality of Experiment queries by filtering out experiments 
        that end before or at a certain time delta from their start time.

        This test case iterates over a set of predefined time deltas and checks that the 
        returned experiment names match the expected results. It verifies that experiments 
        are correctly excluded based on the specified time delta, ensuring that the 
        exclusion criteria are applied correctly for both less than and less than or equal to 
        time delta conditions.
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
        test_set = Experiment.objects.annotate(
            estimated_end=F("start") + F("estimated_time")
        )
        self.assertEqual(
            [e.estimated_end for e in test_set],
            [e.start + e.estimated_time for e in test_set],
        )

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_datetime_subtraction_with_annotate_and_no_output_field(self):
        test_set = Experiment.objects.annotate(
            calculated_duration=F("end") - F("start")
        )
        self.assertEqual(
            [e.calculated_duration for e in test_set],
            [e.end - e.start for e in test_set],
        )

    def test_mixed_comparisons1(self):
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
        with self.assertRaises(DatabaseError):
            list(Experiment.objects.filter(start=F("start") * datetime.timedelta(0)))

    def test_durationfield_add(self):
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
        """
        Tests the subtraction of a date subquery from a date field in a Django queryset.

        This test verifies that a queryset can be filtered to include instances where the 
        difference between a date retrieved from a subquery and a date field is zero. It 
        checks for the existence of results in the queryset, ensuring that the subtraction 
        operation is performed correctly and that the resulting filtered queryset is not empty.

        The test is only executed if the database backend supports temporal subtraction.
        """
        subquery = Experiment.objects.filter(pk=OuterRef("pk")).values("completed")
        queryset = Experiment.objects.annotate(
            difference=subquery - F("completed"),
        ).filter(difference=datetime.timedelta())
        self.assertTrue(queryset.exists())

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_date_case_subtraction(self):
        """

        Tests that a Django ORM query can correctly subtract two date values and filter on the result being equal to a zero timedelta.

        This test case ensures that Django's ORM supports temporal subtraction when the database backend does, and that it can be used in conjunction with the Case expression and annotations to perform complex date-based queries.

        """
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
        """
        Test the subtraction of time objects.

        This test case verifies the functionality of subtracting time objects from
        each other. It checks the result of subtracting a specific time from a stored
        time object, ensuring that the resulting time difference is correctly calculated.

        Additionally, it tests the behavior when subtracting a null value from a time
        object, verifying that the result is None.

        The test covers various aspects of time subtraction, including:

        * Subtracting a specific time from a stored time object
        * Subtracting a null value from a time object

        The expected results are verified to ensure that the time subtraction functionality
        is working as expected.
        """
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
        """

        Tests the subtraction of a subquery from a datetime field in a query.

        This test case creates a Time object with a specific time and then uses a subquery
        to subtract this time from itself. The test checks if the resulting queryset
        contains at least one object, which is expected since the subtraction of a time
        from itself should yield a zero timedelta.

        The test requires a database feature that supports temporal subtraction.

        """
        Time.objects.create(time=datetime.time(12, 30, 15, 2345))
        subquery = Time.objects.filter(pk=OuterRef("pk")).values("time")
        queryset = Time.objects.annotate(
            difference=subquery - F("time"),
        ).filter(difference=datetime.timedelta())
        self.assertTrue(queryset.exists())

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_datetime_subtraction(self):
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
        subquery = Experiment.objects.filter(pk=OuterRef("pk")).values("start")
        queryset = Experiment.objects.annotate(
            difference=subquery - F("start"),
        ).filter(difference=datetime.timedelta())
        self.assertTrue(queryset.exists())

    @skipUnlessDBFeature("supports_temporal_subtraction")
    def test_datetime_subtraction_microseconds(self):
        """
        Tests the subtraction of datetime objects in the database, specifically verifying that the database correctly handles the subtraction of two datetime objects and returns the expected timedelta object, including cases where the difference is in microseconds. The test also checks the annotation of queryset objects with calculated datetime differences.
        """
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

        Check if the function correctly filters experiments where the completion time exceeds the estimated time.

        This test verifies that the query correctly identifies experiments that took longer than expected to complete.
        It checks if the returned QuerySet contains the expected experiment names, which are 'e3', 'e4', and 'e5'.
        The test excludes experiment 'e1' and uses the completion time and estimated time to determine which experiments exceeded their estimated duration.

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

        Tests the update functionality of the TimeField model, specifically verifying that 
        it can be updated using the Value function from Django's database api. 

        This test case checks that a TimeField instance can be created, updated with a 
        new time value, and then retrieves the updated value to ensure it matches the 
        expected time.

        """
        Time.objects.create()
        Time.objects.update(time=Value(datetime.time(1), output_field=TimeField()))
        self.assertEqual(Time.objects.get().time, datetime.time(1))

    def test_update_UUIDField_using_Value(self):
        """

        Tests the update functionality of a UUIDField in the database.

        This test case verifies that a UUIDField can be successfully updated with a new UUID value.
        It ensures that the updated value is correctly stored in the database and can be retrieved.

        The test involves creating a new UUID object, updating its UUID field with a specific value, 
        and then asserting that the retrieved UUID object has the expected value. 

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
        value = Value("name")
        path, args, kwargs = value.deconstruct()
        self.assertEqual(path, "django.db.models.Value")
        self.assertEqual(args, (value.value,))
        self.assertEqual(kwargs, {})

    def test_deconstruct_output_field(self):
        """
        Tests the deconstruction of a Value object with an output field.

        The deconstruction process involves breaking down the Value object into its constituent parts, including the path, arguments, and keyword arguments.

        This test case verifies that the deconstructed path matches the expected path, the arguments match the expected value, and the keyword arguments contain the expected output field.
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

        Tests the string representation of the Value class.

        Verifies that the repr() function returns the expected string for various input types, 
        including None, strings, booleans, integers, dates, and decimal numbers.

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
        d = {Value("name"): "Bob"}
        self.assertIn(Value("name"), d)
        self.assertEqual(d[Value("name")], "Bob")

    def test_equal_output_field(self):
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
        Tests that a FieldError is raised when the output_field for a Value object cannot be resolved.

        Checks that attempting to access the output_field attribute of a Value object
        with an expression type that cannot be resolved results in a FieldError with
        a specific error message.

        This test case verifies the proper error handling behavior in situations where
        the output field type is unknown or cannot be determined.
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
        manager = Manager.objects.create()
        qs = Manager.objects.annotate(
            not_exists=~Exists(Manager.objects.none())
        ).filter(pk=manager.pk)
        self.assertSequenceEqual(qs, [manager])
        self.assertIs(qs.get().not_exists, True)

    def test_filter_by_empty_exists(self):
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

        Set up test data for the class.

        This method creates the necessary data for testing purposes, including a standardized date and time, 
        and an experiment instance (\"Experiment 1\") with predefined attributes such as name, assignment, 
        completion, estimated time, start, and end times. 

        The data created by this method is stored as class attributes and can be accessed by other methods 
        in the class for testing purposes.

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

        Tests the string representation of various database functions.

        This method verifies that the repr() method of several database functions 
        (Coalesce, Concat, Length, Lower, Substr, Upper) returns the expected string 
        format. The tested functions are used to build database queries and this test 
        ensures that they are correctly formatted as strings.

        """
        self.assertEqual(repr(Coalesce("a", "b")), "Coalesce(F(a), F(b))")
        self.assertEqual(repr(Concat("a", "b")), "Concat(ConcatPair(F(a), F(b)))")
        self.assertEqual(repr(Length("a")), "Length(F(a))")
        self.assertEqual(repr(Lower("a")), "Lower(F(a))")
        self.assertEqual(repr(Substr("a", 1, 3)), "Substr(F(a), Value(1), Value(3))")
        self.assertEqual(repr(Upper("a")), "Upper(F(a))")

    def test_aggregates(self):
        """
        Tests the string representation of aggregate functions.

        The test verifies that the repr method of aggregate functions such as
        Avg, Count, Max, Min, StdDev, Sum, and Variance returns the expected
        string. The aggregate functions are tested with different field names
        and the expected output is compared to the actual representation.

        This ensures that the aggregate functions can be correctly represented
        as strings, which is useful for debugging and logging purposes. The
        test covers various aggregate functions and field names to provide
        comprehensive coverage of the functionality.

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
        self.assertEqual(repr(Count("a", distinct=True)), "Count(F(a), distinct=True)")
        self.assertEqual(repr(Count("*", distinct=True)), "Count('*', distinct=True)")

    def test_filtered_aggregates(self):
        """
        Tests the string representation of aggregate functions with filters.

        These tests verify that the `repr` method returns the correct string
        representation for various aggregate functions, including Avg, Count, Max, Min,
        StdDev, Sum, and Variance, when a filter is applied. The tests cover different
        scenarios, such as applying a filter, using distinct values, and specifying
        sample vs population for StdDev and Variance calculations.

        The expected output of each test case is a string that represents the aggregate
        function with its filter, which can be used for logging, debugging, or other
        purposes. The tests ensure that the `repr` method returns a correctly formatted
        string that reflects the aggregate function and its filter, which is essential
        for understanding and working with the results of these functions in various
        contexts.
        """
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
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            Combinable() & Combinable()

    def test_or(self):
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            Combinable() | Combinable()

    def test_xor(self):
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            Combinable() ^ Combinable()

    def test_reversed_and(self):
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            object() & Combinable()

    def test_reversed_or(self):
        """

        Tests that the bitwise OR operation between an object and an instance of Combinable raises a NotImplementedError with the expected error message.

        This function verifies that the bitwise OR operator is not implemented for Combinable, which is expected to raise a NotImplementedError with a specific message.

        """
        with self.assertRaisesMessage(NotImplementedError, self.bitwise_msg):
            object() | Combinable()

    def test_reversed_xor(self):
        """
        Tests that attempting to use the bitwise XOR operator (^) with a Combinable object and an incompatible type raises a NotImplementedError with an expected message.
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

        Tests the resolution of the output field for a combined expression involving null values.

        The function verifies that the `output_field` method of a `CombinedExpression` raises a `FieldError` when
        one of the expression's operands is a null value. The test cases cover various field types, including
        numeric, date, and time fields, as well as different combinable operations (addition and subtraction).

        The function uses a set of predefined test cases, each specifying the left-hand side field type, the
        combinable operation, and the right-hand side field type (which is a null value). It then constructs a
        `CombinedExpression` for each test case and attempts to resolve its output field, asserting that a
        `FieldError` is raised with a message indicating that the type of the expression cannot be inferred.

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
        Tests that the output field of a CombinedExpression is correctly resolved when the values are None.

        The function checks the output field of a CombinedExpression with various combinations of numeric values (floats, integers, decimals) 
        and None, using different connectors (addition, subtraction, multiplication, division, modulo, power). It ensures that the 
        output field type is correctly determined, regardless of whether the left-hand side, right-hand side, or both are None. 

        It covers a range of test cases, including different combinations of numeric types and connectors, to verify the robustness of 
        the output field resolution logic in the presence of null values.
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

        Sets up test data for the class.

        This method creates a test CEO and two companies with different attributes, 
        one based in the EU and the other not. The created test data is stored as 
        class attributes for use in subsequent tests.

        The companies have the following characteristics:
        - eu_company: A large company based in the EU, with 2300 employees and 5 chairs.
        - non_eu_company: A small company not based in the EU, with 3 employees and 4 chairs.
        Both companies are created with the same CEO.

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
        """

        Tests the inversion of an expression using the bitwise NOT operator (~).

        This test case verifies that inverting an expression results in a NegatedExpression
        object, and that double inverting the expression returns the original expression.
        It also checks that double inverting does not return the same object instance as
        the original expression, but rather an equivalent expression.

        """
        f = F("field")
        self.assertEqual(~f, NegatedExpression(f))
        self.assertIsNot(~~f, f)
        self.assertEqual(~~f, f)

    def test_filter(self):
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
        msg = "nulls_first and nulls_last values must be True or None."
        with self.assertRaisesMessage(ValueError, msg):
            OrderBy(F("field"), nulls_first=False)
        with self.assertRaisesMessage(ValueError, msg):
            OrderBy(F("field"), nulls_last=False)
        with self.assertRaisesMessage(ValueError, msg):
            F("field").asc(nulls_first=False)
        with self.assertRaisesMessage(ValueError, msg):
            F("field").desc(nulls_last=False)
