from datetime import datetime
from decimal import Decimal
from math import pi

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Case, F, FloatField, Value, When
from django.db.models.expressions import (
    Expression,
    ExpressionList,
    ExpressionWrapper,
    Func,
    OrderByList,
    RawSQL,
)
from django.db.models.functions import Collate
from django.db.models.lookups import GreaterThan
from django.test import SimpleTestCase, TestCase, skipIfDBFeature, skipUnlessDBFeature

from .models import (
    Article,
    DBArticle,
    DBDefaults,
    DBDefaultsFK,
    DBDefaultsFunction,
    DBDefaultsPK,
)


class DefaultTests(TestCase):
    def test_field_defaults(self):
        a = Article()
        now = datetime.now()
        a.save()

        self.assertIsInstance(a.id, int)
        self.assertEqual(a.headline, "Default headline")
        self.assertLess((now - a.pub_date).seconds, 5)

    @skipUnlessDBFeature(
        "can_return_columns_from_insert", "supports_expression_defaults"
    )
    def test_field_db_defaults_returning(self):
        """

        Tests that database defaults are correctly returned and set on the model instance
        after an insert operation.

        Verifies that the following default values are properly retrieved from the database:
        - Auto-incrementing primary key (ID)
        - Default string value (headline)
        - Default date value (publication date)
        - Default decimal value (cost)

        The test ensures that these default values are correctly set on the model instance
        and that their data types match the expected types.

        """
        a = DBArticle()
        a.save()
        self.assertIsInstance(a.id, int)
        self.assertEqual(a.headline, "Default headline")
        self.assertIsInstance(a.pub_date, datetime)
        self.assertEqual(a.cost, Decimal("3.33"))

    @skipIfDBFeature("can_return_columns_from_insert")
    @skipUnlessDBFeature("supports_expression_defaults")
    def test_field_db_defaults_refresh(self):
        a = DBArticle()
        a.save()
        a.refresh_from_db()
        self.assertIsInstance(a.id, int)
        self.assertEqual(a.headline, "Default headline")
        self.assertIsInstance(a.pub_date, datetime)
        self.assertEqual(a.cost, Decimal("3.33"))

    def test_null_db_default(self):
        """
        Tests database default behavior for null fields, specifically when a default value is set and when it is not. 

        Verifies that when creating an object with no explicit null value, the default value of 1.1 is used. 

        Also checks that when creating an object with an explicit null value of None, the null field is indeed set to None.
        """
        obj1 = DBDefaults.objects.create()
        if not connection.features.can_return_columns_from_insert:
            obj1.refresh_from_db()
        self.assertEqual(obj1.null, 1.1)

        obj2 = DBDefaults.objects.create(null=None)
        self.assertIsNone(obj2.null)

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_db_default_function(self):
        """

        Tests the database default functions for a model instance.

        Verifies that the database correctly applies default functions to model fields,
        including mathematical expressions and subfunctions, during object creation.
        The test checks the accuracy of the default values for numeric fields,
        as well as the correct evaluation of more complex expressions involving subfunctions.

        The test also accounts for differences in database capabilities, such as the ability
        to return columns from an insert statement, and adjusts its behavior accordingly.

        """
        m = DBDefaultsFunction.objects.create()
        if not connection.features.can_return_columns_from_insert:
            m.refresh_from_db()
        self.assertAlmostEqual(m.number, pi)
        self.assertEqual(m.year, datetime.now().year)
        self.assertAlmostEqual(m.added, pi + 4.5)
        self.assertEqual(m.multiple_subfunctions, 4.5)

    @skipUnlessDBFeature("insert_test_table_with_defaults")
    def test_both_default(self):
        """
        Tests the behavior of both fields in the DBDefaults model when they have default values.

        Verifies that the default values are applied correctly when an object is retrieved from
        the database after being inserted with default values, and when an object is created
        manually using the model's create method. Specifically, checks that the 'both' field
        has the expected values in both scenarios.

        Requires a database feature that supports inserting test tables with default values.\"\"\"
        ```
        """
        create_sql = connection.features.insert_test_table_with_defaults
        with connection.cursor() as cursor:
            cursor.execute(create_sql.format(DBDefaults._meta.db_table))
        obj1 = DBDefaults.objects.get()
        self.assertEqual(obj1.both, 2)

        obj2 = DBDefaults.objects.create()
        self.assertEqual(obj2.both, 1)

    def test_pk_db_default(self):
        obj1 = DBDefaultsPK.objects.create()
        if not connection.features.can_return_columns_from_insert:
            # refresh_from_db() cannot be used because that needs the pk to
            # already be known to Django.
            obj1 = DBDefaultsPK.objects.get(pk="en")
        self.assertEqual(obj1.pk, "en")
        self.assertEqual(obj1.language_code, "en")

        obj2 = DBDefaultsPK.objects.create(language_code="de")
        self.assertEqual(obj2.pk, "de")
        self.assertEqual(obj2.language_code, "de")

    def test_foreign_key_db_default(self):
        """
        Tests the behavior of foreign key fields with database defaults.

        This test case verifies that foreign key fields are correctly populated with the
        default values from the database. It covers two scenarios: one where the foreign
        key is not explicitly set, and another where it is explicitly set to a specific
        value. The test ensures that the foreign key values are correctly retrieved from
        the database and match the expected values.

        The test is aware of database backend limitations and adapts its behavior
        accordingly, using refresh_from_db() or get() methods as needed to retrieve the
        correct values from the database.

        By testing these scenarios, this function helps ensure the correctness and
        consistency of foreign key behavior in the application, regardless of the
        underlying database backend being used.
        """
        parent1 = DBDefaultsPK.objects.create(language_code="fr")
        child1 = DBDefaultsFK.objects.create()
        if not connection.features.can_return_columns_from_insert:
            child1.refresh_from_db()
        self.assertEqual(child1.language_code, parent1)

        parent2 = DBDefaultsPK.objects.create()
        if not connection.features.can_return_columns_from_insert:
            # refresh_from_db() cannot be used because that needs the pk to
            # already be known to Django.
            parent2 = DBDefaultsPK.objects.get(pk="en")
        child2 = DBDefaultsFK.objects.create(language_code=parent2)
        self.assertEqual(child2.language_code, parent2)

    @skipUnlessDBFeature(
        "can_return_columns_from_insert", "supports_expression_defaults"
    )
    def test_case_when_db_default_returning(self):
        m = DBDefaultsFunction.objects.create()
        self.assertEqual(m.case_when, 3)

    @skipIfDBFeature("can_return_columns_from_insert")
    @skipUnlessDBFeature("supports_expression_defaults")
    def test_case_when_db_default_no_returning(self):
        """
        Tests the functionality of the case when DB defaults.

        This test case checks if the case when expression default in the database 
        is correctly retrieved and matches the expected value.

        The test assumes that the database does not support returning columns 
        from an insert operation and supports expression defaults.

        It creates an instance of DBDefaultsFunction, refreshes it from the database, 
        and asserts that the case when attribute is set to the default value of 3.
        """
        m = DBDefaultsFunction.objects.create()
        m.refresh_from_db()
        self.assertEqual(m.case_when, 3)

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_bulk_create_all_db_defaults(self):
        articles = [DBArticle(), DBArticle()]
        DBArticle.objects.bulk_create(articles)

        headlines = DBArticle.objects.values_list("headline", flat=True)
        self.assertSequenceEqual(headlines, ["Default headline", "Default headline"])

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_bulk_create_all_db_defaults_one_field(self):
        """
        Tests the bulk creation of model instances with default field values provided by the database.

        The function verifies that all instances are correctly created and that the default values for certain fields are applied as expected by the database. 

        It checks the values of the 'headline', 'pub_date', and 'cost' fields after the bulk creation operation, ensuring they match the expected default or provided values. 

        This test requires a database that supports expression defaults to be available.
        """
        pub_date = datetime.now()
        articles = [DBArticle(pub_date=pub_date), DBArticle(pub_date=pub_date)]
        DBArticle.objects.bulk_create(articles)

        headlines = DBArticle.objects.values_list("headline", "pub_date", "cost")
        self.assertSequenceEqual(
            headlines,
            [
                ("Default headline", pub_date, Decimal("3.33")),
                ("Default headline", pub_date, Decimal("3.33")),
            ],
        )

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_bulk_create_mixed_db_defaults(self):
        """

        Tests the bulk creation of objects with mixed database defaults.

        This test ensures that when creating multiple objects in bulk, some of which
        have default values provided by the database and others with explicitly set
        values, the resulting objects are created correctly in the database.

        The test verifies that the default values are applied correctly when no
        explicit value is provided, and that explicit values take precedence over
        database defaults when both are present. This check is only performed on
        databases that support expression defaults.

        """
        articles = [DBArticle(), DBArticle(headline="Something else")]
        DBArticle.objects.bulk_create(articles)

        headlines = DBArticle.objects.values_list("headline", flat=True)
        self.assertCountEqual(headlines, ["Default headline", "Something else"])

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_bulk_create_mixed_db_defaults_function(self):
        """
        Tests the bulk creation of objects with mixed database defaults and user-specified values.

        This test verifies that database defaults are correctly applied to objects when 
        they are created in bulk, while also allowing users to specify custom values for 
        certain fields. Specifically, it checks that objects without a specified value 
        for the 'year' field will be assigned the current year, while objects with a 
        specified 'year' value will retain that value.

        The test ensures that the resulting objects in the database have the expected 
        'year' values, confirming that the bulk creation process handles mixed defaults 
        and user-specified values correctly.
        """
        instances = [DBDefaultsFunction(), DBDefaultsFunction(year=2000)]
        DBDefaultsFunction.objects.bulk_create(instances)

        years = DBDefaultsFunction.objects.values_list("year", flat=True)
        self.assertCountEqual(years, [2000, datetime.now().year])

    def test_full_clean(self):
        """

        Tests the full_clean method of the DBArticle model.

        This test case checks that the full_clean method correctly validates and saves 
        DBArticle objects. It covers the following scenarios:

        * Saving an object with default values
        * Saving an object with a custom headline
        * Attempting to save an object with an empty headline, which should raise a ValidationError.

        The test ensures that the full_clean method enforces the expected validation rules 
        and that the object's data is correctly persisted to the database.

        """
        obj = DBArticle()
        obj.full_clean()
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.headline, "Default headline")

        obj = DBArticle(headline="Other title")
        obj.full_clean()
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.headline, "Other title")

        obj = DBArticle(headline="")
        with self.assertRaises(ValidationError):
            obj.full_clean()


class AllowedDefaultTests(SimpleTestCase):
    def test_allowed(self):
        """
        Tests that various types of database expressions are allowed as default values.

        This test case checks a range of different expression types, including basic values,
        aggregate functions, raw SQL, arithmetic operations, expression lists, wrapped expressions,
        and conditional expressions, to ensure they can be used as default values in a database field.

        :raises AssertionError: If any of the tested expressions are not allowed as default values.
        """
        class Max(Func):
            function = "MAX"

        tests = [
            Value(10),
            Max(1, 2),
            RawSQL("Now()", ()),
            Value(10) + Value(7),  # Combined expression.
            ExpressionList(Value(1), Value(2)),
            ExpressionWrapper(Value(1), output_field=FloatField()),
            Case(When(GreaterThan(2, 1), then=3), default=4),
        ]
        for expression in tests:
            with self.subTest(expression=expression):
                self.assertIs(expression.allowed_default, True)

    def test_disallowed(self):
        """

        Tests that a variety of Django ORM expression objects are disallowed as default field values.

        This test case checks that the :attr:`allowed_default` attribute of different expression objects is set to :obj:`False`.
        The expressions tested include basic expressions, database functions, field references, and more complex constructs such as lists and wrapper objects.
        The purpose of this test is to ensure that only valid and safe values can be used as default field values.

        """
        class Max(Func):
            function = "MAX"

        tests = [
            Expression(),
            F("field"),
            Max(F("count"), 1),
            Value(10) + F("count"),  # Combined expression.
            ExpressionList(F("count"), Value(2)),
            ExpressionWrapper(F("count"), output_field=FloatField()),
            Collate(Value("John"), "nocase"),
            OrderByList("field"),
        ]
        for expression in tests:
            with self.subTest(expression=expression):
                self.assertIs(expression.allowed_default, False)
