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

        Tests the functionality of model fields with default database values.

        This test ensures that a model instance is correctly populated with default values
        returned from the database after insertion. It verifies that the model's fields
        are populated with the expected data types and values, which are set by the
        database defaults.

        Specifically, it checks that the model's primary key is set to an integer, 
        the headline is set to a default string, the publication date is a datetime object,
        and the cost is a decimal value. 

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
        obj1 = DBDefaults.objects.create()
        if not connection.features.can_return_columns_from_insert:
            obj1.refresh_from_db()
        self.assertEqual(obj1.null, 1.1)

        obj2 = DBDefaults.objects.create(null=None)
        self.assertIsNone(obj2.null)

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_db_default_function(self):
        m = DBDefaultsFunction.objects.create()
        if not connection.features.can_return_columns_from_insert:
            m.refresh_from_db()
        self.assertAlmostEqual(m.number, pi)
        self.assertEqual(m.year, datetime.now().year)
        self.assertAlmostEqual(m.added, pi + 4.5)
        self.assertEqual(m.multiple_subfunctions, 4.5)

    @skipUnlessDBFeature("insert_test_table_with_defaults")
    def test_both_default(self):
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

        Tests the behavior of the database when using a CASE WHEN expression as a default value 
        and the database does not support returning columns from an insert operation.

        Verifies that the correct value is retrieved from the database after creating a 
        DBDefaultsFunction object and refreshing it from the database.

        """
        m = DBDefaultsFunction.objects.create()
        m.refresh_from_db()
        self.assertEqual(m.case_when, 3)

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_bulk_create_all_db_defaults(self):
        """
        Tests the bulk creation of DBArticle objects with database-defined default values.

        This test verifies that when creating multiple DBArticle objects using bulk_create,
        database-defined default values are correctly applied to the created objects.
        Specifically, it checks that the 'headline' field of each created article is set to its default value.

        The test case covers the scenario where the database supports expression defaults,
        ensuring that the bulk creation operation behaves as expected in such environments.
        """
        articles = [DBArticle(), DBArticle()]
        DBArticle.objects.bulk_create(articles)

        headlines = DBArticle.objects.values_list("headline", flat=True)
        self.assertSequenceEqual(headlines, ["Default headline", "Default headline"])

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_bulk_create_all_db_defaults_one_field(self):
        """
        Tests the bulk creation of database articles, ensuring that database default values are applied when fields are not explicitly set. This test checks that the 'headline' and 'cost' fields receive their default values when the 'bulk_create' method is used to create new articles in the database. The test verifies that both the headline and cost defaults are correctly applied to all created articles.
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

        Verifies that when creating multiple objects in bulk, any missing default values
        are automatically applied by the database, while explicitly provided values
        are used instead.

        The test ensures that objects with and without predefined default values can
        be created together, and that the resulting objects have the expected values.

        """
        articles = [DBArticle(), DBArticle(headline="Something else")]
        DBArticle.objects.bulk_create(articles)

        headlines = DBArticle.objects.values_list("headline", flat=True)
        self.assertCountEqual(headlines, ["Default headline", "Something else"])

    @skipUnlessDBFeature("supports_expression_defaults")
    def test_bulk_create_mixed_db_defaults_function(self):
        instances = [DBDefaultsFunction(), DBDefaultsFunction(year=2000)]
        DBDefaultsFunction.objects.bulk_create(instances)

        years = DBDefaultsFunction.objects.values_list("year", flat=True)
        self.assertCountEqual(years, [2000, datetime.now().year])

    def test_full_clean(self):
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
