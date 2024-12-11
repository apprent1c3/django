import time
import unittest
from datetime import date, datetime

from django.core.exceptions import FieldError
from django.db import connection, models
from django.db.models.fields.related_lookups import RelatedGreaterThan
from django.db.models.lookups import EndsWith, StartsWith
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import register_lookup
from django.utils import timezone

from .models import Article, Author, MySQLUnixTimestamp


class Div3Lookup(models.Lookup):
    lookup_name = "div3"

    def as_sql(self, compiler, connection):
        """
        Generates the SQL representation of the current query expression.

        This method constructs a SQL string by processing the left-hand side (LHS) and right-hand side (RHS) components of the query expression, combining their parameter lists, and then formatting the results into a complete SQL query.

        The resulting SQL string takes the form of \"(LHS) % 3 = RHS\", where '%' is the modulo operator and '3' is the remainder value being matched against.

        Returns a 2-tuple containing the formatted SQL string and the combined list of parameters required for the query execution.
        """
        lhs, params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params.extend(rhs_params)
        return "(%s) %%%% 3 = %s" % (lhs, rhs), params

    def as_oracle(self, compiler, connection):
        """
        Returns a SQL expression equivalent to the Oracle MOD function, 
        calculating the remainder of the integer division of the left-hand 
        side value by the right-hand side value, with the result modulo 3.
        The function returns a tuple containing the compiled SQL expression 
        and the parameters to be bound to it.
        """
        lhs, params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params.extend(rhs_params)
        return "mod(%s, 3) = %s" % (lhs, rhs), params


class Div3Transform(models.Transform):
    lookup_name = "div3"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = compiler.compile(self.lhs)
        return "(%s) %%%% 3" % lhs, lhs_params

    def as_oracle(self, compiler, connection, **extra_context):
        """
        Registers the object as Oracle instance in the query compiler.

        This method compiles the left-hand side of a query and returns a modified SQL expression that applies the modulo operation with a divisor of 3, along with the associated parameters.

        :param compiler: The query compiler instance
        :param connection: The database connection
        :param extra_context: Additional context for the compilation process
        :return: A tuple containing the compiled SQL expression and parameters
        """
        lhs, lhs_params = compiler.compile(self.lhs)
        return "mod(%s, 3)" % lhs, lhs_params


class Div3BilateralTransform(Div3Transform):
    bilateral = True


class Mult3BilateralTransform(models.Transform):
    bilateral = True
    lookup_name = "mult3"

    def as_sql(self, compiler, connection):
        """
        Returns a SQL representation of the given expression, specifically multiplying the left-hand side (LHS) by 3. 

        The function takes no explicit parameters other than those provided by the compiler and connection objects, 
        which are used to compile the LHS of the expression into a valid SQL string and parameters. 

        The resulting SQL string and parameters are then returned as a tuple, allowing for further processing or execution.
        """
        lhs, lhs_params = compiler.compile(self.lhs)
        return "3 * (%s)" % lhs, lhs_params


class LastDigitTransform(models.Transform):
    lookup_name = "lastdigit"

    def as_sql(self, compiler, connection):
        """
        Extract a single character from the last position of a string representation of a value.

        This function is used to generate SQL for extracting the last character from a two-character string. 
        It returns a tuple containing the generated SQL and the parameters required for the query. 
        The generated SQL uses the SUBSTR function to extract the last character, 
        assuming the input value is first cast to a two-character string.
        """
        lhs, lhs_params = compiler.compile(self.lhs)
        return "SUBSTR(CAST(%s AS CHAR(2)), 2, 1)" % lhs, lhs_params


class UpperBilateralTransform(models.Transform):
    bilateral = True
    lookup_name = "upper"

    def as_sql(self, compiler, connection):
        """
        Generates the SQL representation of the upper case operation.

        This method compiles the left hand side of the operation using the provided compiler
        and wraps the resulting SQL in an UPPER function call. The compiled parameters
        are also returned.

        :returns: A tuple containing the SQL string and the parameters for the UPPER operation
        :rtype: tuple
        """
        lhs, lhs_params = compiler.compile(self.lhs)
        return "UPPER(%s)" % lhs, lhs_params


class YearTransform(models.Transform):
    # Use a name that avoids collision with the built-in year lookup.
    lookup_name = "testyear"

    def as_sql(self, compiler, connection):
        """
        Return a SQL expression that extracts the year from the left-hand side of this object.

        This method is used to generate SQL code for extracting the year from a date or datetime field.
        It relies on the database backend's implementation of date extraction operations, allowing for
        database-agnostic year extraction.

        :param compiler: The compiler object used to build the SQL expression.
        :param connection: The database connection object.
        :returns: A SQL string that extracts the year from the left-hand side, along with any required parameters.

        """
        lhs_sql, params = compiler.compile(self.lhs)
        return connection.ops.date_extract_sql("year", lhs_sql, params)

    @property
    def output_field(self):
        return models.IntegerField()


@YearTransform.register_lookup
class YearExact(models.lookups.Lookup):
    lookup_name = "exact"

    def as_sql(self, compiler, connection):
        # We will need to skip the extract part, and instead go
        # directly with the originating field, that is self.lhs.lhs
        """
        Generates SQL expression to filter dates within a given year.

        This function takes the left-hand side (LHS) and right-hand side (RHS) of a comparison, 
        compiles them into SQL strings, and combines them into a date range query. 
        The query checks if the LHS date falls within the year specified by the RHS. 
        The year filter is applied by appending '-01-01' and '-12-31' to the RHS year, 
        effectively creating a date range spanning the entire year. 

        The function returns a tuple containing the generated SQL expression and a list of parameters to be used with the query.
        """
        lhs_sql, lhs_params = self.process_lhs(compiler, connection, self.lhs.lhs)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        # Note that we must be careful so that we have params in the
        # same order as we have the parts in the SQL.
        params = lhs_params + rhs_params + lhs_params + rhs_params
        # We use PostgreSQL specific SQL here. Note that we must do the
        # conversions in SQL instead of in Python to support F() references.
        return (
            "%(lhs)s >= (%(rhs)s || '-01-01')::date "
            "AND %(lhs)s <= (%(rhs)s || '-12-31')::date"
            % {"lhs": lhs_sql, "rhs": rhs_sql},
            params,
        )


@YearTransform.register_lookup
class YearLte(models.lookups.LessThanOrEqual):
    """
    The purpose of this lookup is to efficiently compare the year of the field.
    """

    def as_sql(self, compiler, connection):
        # Skip the YearTransform above us (no possibility for efficient
        # lookup otherwise).
        real_lhs = self.lhs.lhs
        lhs_sql, params = self.process_lhs(compiler, connection, real_lhs)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        params.extend(rhs_params)
        # Build SQL where the integer year is concatenated with last month
        # and day, then convert that to date. (We try to have SQL like:
        #     WHERE somecol <= '2013-12-31')
        # but also make it work if the rhs_sql is field reference.
        return "%s <= (%s || '-12-31')::date" % (lhs_sql, rhs_sql), params


class Exactly(models.lookups.Exact):
    """
    This lookup is used to test lookup registration.
    """

    lookup_name = "exactly"

    def get_rhs_op(self, connection, rhs):
        return connection.operators["exact"] % rhs


class SQLFuncMixin:
    def as_sql(self, compiler, connection):
        return "%s()" % self.name, []

    @property
    def output_field(self):
        return CustomField()


class SQLFuncLookup(SQLFuncMixin, models.Lookup):
    def __init__(self, name, *args, **kwargs):
        """
        Initializes a new instance of the class.

        :param name: The name of the instance.
        :param args: Variable length argument list passed to the parent class constructor.
        :param kwargs: Arbitrary keyword arguments passed to the parent class constructor.

        Initializes the instance with the given name and passes any additional arguments to the parent class constructor. The name is stored as an instance attribute for later use.
        """
        super().__init__(*args, **kwargs)
        self.name = name


class SQLFuncTransform(SQLFuncMixin, models.Transform):
    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name


class SQLFuncFactory:
    def __init__(self, key, name):
        self.key = key
        self.name = name

    def __call__(self, *args, **kwargs):
        """

        Invoke the decorator to create either an SQL function lookup or transformation object.

        This method determines whether to create an SQLFuncLookup or SQLFuncTransform object based on the key, 
        then returns the created object with the provided arguments.

        The type of object created depends on the key attribute: 'lookupfunc' results in a lookup object, 
        while any other key results in a transform object.

        :param args: Variable number of positional arguments to pass to the created object.
        :param kwargs: Variable number of keyword arguments to pass to the created object.
        :return: An SQLFuncLookup or SQLFuncTransform object.

        """
        if self.key == "lookupfunc":
            return SQLFuncLookup(self.name, *args, **kwargs)
        return SQLFuncTransform(self.name, *args, **kwargs)


class CustomField(models.TextField):
    def get_lookup(self, lookup_name):
        """
        Get a lookup object by its name.

        This method retrieves a lookup object based on the provided lookup name.
        If the lookup name starts with 'lookupfunc_', it creates an SQL function lookup
        using the SQLFuncFactory. Otherwise, it delegates the lookup retrieval to
        the parent class.

        Args:
            lookup_name (str): The name of the lookup to retrieve.

        Returns:
            The lookup object associated with the given lookup name.

        """
        if lookup_name.startswith("lookupfunc_"):
            key, name = lookup_name.split("_", 1)
            return SQLFuncFactory(key, name)
        return super().get_lookup(lookup_name)

    def get_transform(self, lookup_name):
        """
        Override of the get_transform method to handle custom transformation functions.

        This method retrieves a transformation function based on the provided lookup name.
        If the lookup name starts with 'transformfunc_', it creates a SQLFuncFactory instance
        with the specified key and name. Otherwise, it delegates to the parent class's
        get_transform method to handle the lookup.

        :param lookup_name: The name of the transformation function to retrieve
        :return: The transformation function or a SQLFuncFactory instance
        """
        if lookup_name.startswith("transformfunc_"):
            key, name = lookup_name.split("_", 1)
            return SQLFuncFactory(key, name)
        return super().get_transform(lookup_name)


class CustomModel(models.Model):
    field = CustomField()


# We will register this class temporarily in the test method.


class InMonth(models.lookups.Lookup):
    """
    InMonth matches if the column's month is the same as value's month.
    """

    lookup_name = "inmonth"

    def as_sql(self, compiler, connection):
        """

        Generates the SQL representation of a comparison between two dates.

        This function takes into account the current compiler and database connection, 
        and returns a string representing the SQL query with the necessary parameters.

        The resulting SQL statement checks if the left-hand side date falls within the month of the right-hand side date.

        """
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        # We need to be careful so that we get the params in right
        # places.
        params = lhs_params + rhs_params + lhs_params + rhs_params
        return (
            "%s >= date_trunc('month', %s) and "
            "%s < date_trunc('month', %s) + interval '1 months'" % (lhs, rhs, lhs, rhs),
            params,
        )


class DateTimeTransform(models.Transform):
    lookup_name = "as_datetime"

    @property
    def output_field(self):
        return models.DateTimeField()

    def as_sql(self, compiler, connection):
        """
        Render the left-hand side (LHS) expression as a SQL string using the FROM_UNIXTIME function, which converts a Unix timestamp to a datetime.

        :param compiler: The SQL compiler instance used for expression compilation.
        :param connection: The database connection instance.
        :return: A tuple containing the compiled SQL string and a list of parameter values.
        """
        lhs, params = compiler.compile(self.lhs)
        return "from_unixtime({})".format(lhs), params


class CustomStartsWith(StartsWith):
    lookup_name = "sw"


class CustomEndsWith(EndsWith):
    lookup_name = "ew"


class RelatedMoreThan(RelatedGreaterThan):
    lookup_name = "rmt"


class LookupTests(TestCase):
    def test_custom_name_lookup(self):
        """

        Tests the custom name lookup functionality on the Author model's birthdate field.

        The function verifies that custom lookup names can be registered and used to filter 
        querysets based on the year of a DateField. It checks that the lookup names can be 
        used with different transform classes, such as YearTransform and Exactly, to 
        achieve the same result.

        Specifically, it tests that authors born in a specific year can be retrieved using 
        custom lookup names 'testyear' and 'justtheyear' with the 'exactly' and 'isactually' 
        transforms, respectively.

        """
        a1 = Author.objects.create(name="a1", birthdate=date(1981, 2, 16))
        Author.objects.create(name="a2", birthdate=date(2012, 2, 29))
        with (
            register_lookup(models.DateField, YearTransform),
            register_lookup(models.DateField, YearTransform, lookup_name="justtheyear"),
            register_lookup(YearTransform, Exactly),
            register_lookup(YearTransform, Exactly, lookup_name="isactually"),
        ):
            qs1 = Author.objects.filter(birthdate__testyear__exactly=1981)
            qs2 = Author.objects.filter(birthdate__justtheyear__isactually=1981)
            self.assertSequenceEqual(qs1, [a1])
            self.assertSequenceEqual(qs2, [a1])

    def test_custom_exact_lookup_none_rhs(self):
        """
        __exact=None is transformed to __isnull=True if a custom lookup class
        with lookup_name != 'exact' is registered as the `exact` lookup.
        """
        field = Author._meta.get_field("birthdate")
        OldExactLookup = field.get_lookup("exact")
        author = Author.objects.create(name="author", birthdate=None)
        try:
            field.register_lookup(Exactly, "exact")
            self.assertEqual(Author.objects.get(birthdate__exact=None), author)
        finally:
            field.register_lookup(OldExactLookup, "exact")

    def test_basic_lookup(self):
        a1 = Author.objects.create(name="a1", age=1)
        a2 = Author.objects.create(name="a2", age=2)
        a3 = Author.objects.create(name="a3", age=3)
        a4 = Author.objects.create(name="a4", age=4)
        with register_lookup(models.IntegerField, Div3Lookup):
            self.assertSequenceEqual(Author.objects.filter(age__div3=0), [a3])
            self.assertSequenceEqual(
                Author.objects.filter(age__div3=1).order_by("age"), [a1, a4]
            )
            self.assertSequenceEqual(Author.objects.filter(age__div3=2), [a2])
            self.assertSequenceEqual(Author.objects.filter(age__div3=3), [])

    @unittest.skipUnless(
        connection.vendor == "postgresql", "PostgreSQL specific SQL used"
    )
    def test_birthdate_month(self):
        a1 = Author.objects.create(name="a1", birthdate=date(1981, 2, 16))
        a2 = Author.objects.create(name="a2", birthdate=date(2012, 2, 29))
        a3 = Author.objects.create(name="a3", birthdate=date(2012, 1, 31))
        a4 = Author.objects.create(name="a4", birthdate=date(2012, 3, 1))
        with register_lookup(models.DateField, InMonth):
            self.assertSequenceEqual(
                Author.objects.filter(birthdate__inmonth=date(2012, 1, 15)), [a3]
            )
            self.assertSequenceEqual(
                Author.objects.filter(birthdate__inmonth=date(2012, 2, 1)), [a2]
            )
            self.assertSequenceEqual(
                Author.objects.filter(birthdate__inmonth=date(1981, 2, 28)), [a1]
            )
            self.assertSequenceEqual(
                Author.objects.filter(birthdate__inmonth=date(2012, 3, 12)), [a4]
            )
            self.assertSequenceEqual(
                Author.objects.filter(birthdate__inmonth=date(2012, 4, 1)), []
            )

    def test_div3_extract(self):
        """
        Tests the Div3Transform lookup functionality.

        This test case exercises various filters using the 'div3' lookup, 
        including exact, less than or equal to, in, greater than or equal to, 
        and range comparisons. The 'div3' lookup is applied to the 'age' 
        field of Author objects, which is divided by 3 to produce a quotient 
        used for filtering.

        The test creates a set of Author objects with ages from 1 to 4 and 
        verifies that the filters produce the expected results, demonstrating 
        the correct application of the Div3Transform lookup in different 
        scenarios.
        """
        with register_lookup(models.IntegerField, Div3Transform):
            a1 = Author.objects.create(name="a1", age=1)
            a2 = Author.objects.create(name="a2", age=2)
            a3 = Author.objects.create(name="a3", age=3)
            a4 = Author.objects.create(name="a4", age=4)
            baseqs = Author.objects.order_by("name")
            self.assertSequenceEqual(baseqs.filter(age__div3=2), [a2])
            self.assertSequenceEqual(baseqs.filter(age__div3__lte=3), [a1, a2, a3, a4])
            self.assertSequenceEqual(baseqs.filter(age__div3__in=[0, 2]), [a2, a3])
            self.assertSequenceEqual(baseqs.filter(age__div3__in=[2, 4]), [a2])
            self.assertSequenceEqual(baseqs.filter(age__div3__gte=3), [])
            self.assertSequenceEqual(
                baseqs.filter(age__div3__range=(1, 2)), [a1, a2, a4]
            )

    def test_foreignobject_lookup_registration(self):
        """

        Test foreign object lookup registration for the 'Article' model.

        This test case verifies the registration of a lookup type ('exactly') for a
        foreign object field ('author') in the 'Article' model. It checks that the
        lookup type is correctly registered for the foreign object and not for other
        field types, ensuring proper lookup functionality for foreign object fields.

        """
        field = Article._meta.get_field("author")

        with register_lookup(models.ForeignObject, Exactly):
            self.assertIs(field.get_lookup("exactly"), Exactly)

        # ForeignObject should ignore regular Field lookups
        with register_lookup(models.Field, Exactly):
            self.assertIsNone(field.get_lookup("exactly"))

    def test_lookups_caching(self):
        """
        Tests the caching behavior of model field lookups, specifically when a custom lookup type is registered and then deregistered. 
        Verifies that the custom lookup 'exactly' is not available by default, becomes available after registration, and is no longer available after registration is removed.
        """
        field = Article._meta.get_field("author")

        # clear and re-cache
        field.get_class_lookups.cache_clear()
        self.assertNotIn("exactly", field.get_lookups())

        # registration should bust the cache
        with register_lookup(models.ForeignObject, Exactly):
            # getting the lookups again should re-cache
            self.assertIn("exactly", field.get_lookups())
        # Unregistration should bust the cache.
        self.assertNotIn("exactly", field.get_lookups())


class BilateralTransformTests(TestCase):
    def test_bilateral_upper(self):
        """

        Tests the functionality of the UpperBilateralTransform lookup within the context of CharField.

        This test case creates multiple authors with varying names and checks that the filter 
        query using the 'upper' lookup correctly returns authors with names in the same case, 
        ignoring the original case. Additionally, it verifies the 'contains' lookup with 'upper' 
        transform can find authors by partial name matches in a case-insensitive manner.

        The test ensures that the UpperBilateralTransform correctly handles case conversion, 
        enabling flexible and accurate filtering of CharField values in a database.

        """
        with register_lookup(models.CharField, UpperBilateralTransform):
            author1 = Author.objects.create(name="Doe")
            author2 = Author.objects.create(name="doe")
            author3 = Author.objects.create(name="Foo")
            self.assertCountEqual(
                Author.objects.filter(name__upper="doe"),
                [author1, author2],
            )
            self.assertSequenceEqual(
                Author.objects.filter(name__upper__contains="f"),
                [author3],
            )

    def test_bilateral_inner_qs(self):
        with register_lookup(models.CharField, UpperBilateralTransform):
            msg = "Bilateral transformations on nested querysets are not implemented."
            with self.assertRaisesMessage(NotImplementedError, msg):
                Author.objects.filter(
                    name__upper__in=Author.objects.values_list("name")
                )

    def test_bilateral_multi_value(self):
        with register_lookup(models.CharField, UpperBilateralTransform):
            Author.objects.bulk_create(
                [
                    Author(name="Foo"),
                    Author(name="Bar"),
                    Author(name="Ray"),
                ]
            )
            self.assertQuerySetEqual(
                Author.objects.filter(name__upper__in=["foo", "bar", "doe"]).order_by(
                    "name"
                ),
                ["Bar", "Foo"],
                lambda a: a.name,
            )

    def test_div3_bilateral_extract(self):
        """
        Tests the Div3BilateralTransform lookup for IntegerField.

        This function creates several Author objects with different ages and tests 
        various queries using the div3 lookup. The div3 lookup is applied to the age 
        field and is used to filter authors based on the result of the division of 
        their age by 3. 

        The function covers multiple scenarios including exact matching, less than or 
        equal to, in a list, greater than or equal to, and within a given range. 

        The tests verify that the lookup correctly applies the division transformation 
        and returns the expected authors for each query.

        """
        with register_lookup(models.IntegerField, Div3BilateralTransform):
            a1 = Author.objects.create(name="a1", age=1)
            a2 = Author.objects.create(name="a2", age=2)
            a3 = Author.objects.create(name="a3", age=3)
            a4 = Author.objects.create(name="a4", age=4)
            baseqs = Author.objects.order_by("name")
            self.assertSequenceEqual(baseqs.filter(age__div3=2), [a2])
            self.assertSequenceEqual(baseqs.filter(age__div3__lte=3), [a3])
            self.assertSequenceEqual(baseqs.filter(age__div3__in=[0, 2]), [a2, a3])
            self.assertSequenceEqual(baseqs.filter(age__div3__in=[2, 4]), [a1, a2, a4])
            self.assertSequenceEqual(baseqs.filter(age__div3__gte=3), [a1, a2, a3, a4])
            self.assertSequenceEqual(
                baseqs.filter(age__div3__range=(1, 2)), [a1, a2, a4]
            )

    def test_bilateral_order(self):
        """

        Test the bilateral order functionality, specifically the mult3 and div3 transformations applied to the 'age' field.

        This test case creates a set of authors with varying ages, then applies the mult3 and div3 transformations in different orders to verify the expected filtering results.
        The test checks that the bilateral order application yields the expected filtered sequence of authors, demonstrating the correct behavior of the Mult3BilateralTransform and Div3BilateralTransform classes.

        """
        with register_lookup(
            models.IntegerField, Mult3BilateralTransform, Div3BilateralTransform
        ):
            a1 = Author.objects.create(name="a1", age=1)
            a2 = Author.objects.create(name="a2", age=2)
            a3 = Author.objects.create(name="a3", age=3)
            a4 = Author.objects.create(name="a4", age=4)
            baseqs = Author.objects.order_by("name")

            # mult3__div3 always leads to 0
            self.assertSequenceEqual(
                baseqs.filter(age__mult3__div3=42), [a1, a2, a3, a4]
            )
            self.assertSequenceEqual(baseqs.filter(age__div3__mult3=42), [a3])

    def test_transform_order_by(self):
        """

        Test the application of a transformation to order Author objects by the last digit of their age.

        This test verifies that the LastDigitTransform function is correctly applied to the 'age' field
        in the Author model, allowing the authors to be ordered based on the last digit of their age.
        The ordering is verified by comparing the resulting queryset with an expected sequence of authors.

        """
        with register_lookup(models.IntegerField, LastDigitTransform):
            a1 = Author.objects.create(name="a1", age=11)
            a2 = Author.objects.create(name="a2", age=23)
            a3 = Author.objects.create(name="a3", age=32)
            a4 = Author.objects.create(name="a4", age=40)
            qs = Author.objects.order_by("age__lastdigit")
            self.assertSequenceEqual(qs, [a4, a1, a3, a2])

    def test_bilateral_fexpr(self):
        with register_lookup(models.IntegerField, Mult3BilateralTransform):
            a1 = Author.objects.create(name="a1", age=1, average_rating=3.2)
            a2 = Author.objects.create(name="a2", age=2, average_rating=0.5)
            a3 = Author.objects.create(name="a3", age=3, average_rating=1.5)
            a4 = Author.objects.create(name="a4", age=4)
            baseqs = Author.objects.order_by("name")
            self.assertSequenceEqual(
                baseqs.filter(age__mult3=models.F("age")), [a1, a2, a3, a4]
            )
            # Same as age >= average_rating
            self.assertSequenceEqual(
                baseqs.filter(age__mult3__gte=models.F("average_rating")), [a2, a3]
            )


@override_settings(USE_TZ=True)
class DateTimeLookupTests(TestCase):
    @unittest.skipUnless(connection.vendor == "mysql", "MySQL specific SQL used")
    def test_datetime_output_field(self):
        with register_lookup(models.PositiveIntegerField, DateTimeTransform):
            ut = MySQLUnixTimestamp.objects.create(timestamp=time.time())
            y2k = timezone.make_aware(datetime(2000, 1, 1))
            self.assertSequenceEqual(
                MySQLUnixTimestamp.objects.filter(timestamp__as_datetime__gt=y2k), [ut]
            )


class YearLteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating a set of authors with distinct names and birthdates.

        This method is used to establish a common set of data for use in testing, ensuring that each test starts with a consistent baseline.

        The created authors include:

        * a1, born February 16, 1981
        * a2, born February 29, 2012
        * a3, born January 31, 2012
        * a4, born March 1, 2012

        These authors can be accessed as class attributes for use in subsequent tests.
        """
        cls.a1 = Author.objects.create(name="a1", birthdate=date(1981, 2, 16))
        cls.a2 = Author.objects.create(name="a2", birthdate=date(2012, 2, 29))
        cls.a3 = Author.objects.create(name="a3", birthdate=date(2012, 1, 31))
        cls.a4 = Author.objects.create(name="a4", birthdate=date(2012, 3, 1))

    def setUp(self):
        """
        Sets up the necessary configuration for date field lookups by registering the YearTransform lookup type, and arranges for its automatic removal after the test is completed to prevent interference with other tests.
        """
        models.DateField.register_lookup(YearTransform)
        self.addCleanup(models.DateField._unregister_lookup, YearTransform)

    @unittest.skipUnless(
        connection.vendor == "postgresql", "PostgreSQL specific SQL used"
    )
    def test_year_lte(self):
        """

        Tests the filtering of authors by their birth year using the 'testyear' lookup type.

        The test checks that the 'testyear' lookup correctly filters authors based on their birth year.
        It verifies that the 'lte' and 'lt' modifiers work as expected, returning the correct authors
        when filtering by a specific year or range of years.

        This test is specific to PostgreSQL databases and checks that the generated SQL queries do not
        contain the 'BETWEEN' keyword when using the 'testyear' lookup.

        """
        baseqs = Author.objects.order_by("name")
        self.assertSequenceEqual(
            baseqs.filter(birthdate__testyear__lte=2012),
            [self.a1, self.a2, self.a3, self.a4],
        )
        self.assertSequenceEqual(
            baseqs.filter(birthdate__testyear=2012), [self.a2, self.a3, self.a4]
        )

        self.assertNotIn("BETWEEN", str(baseqs.filter(birthdate__testyear=2012).query))
        self.assertSequenceEqual(
            baseqs.filter(birthdate__testyear__lte=2011), [self.a1]
        )
        # The non-optimized version works, too.
        self.assertSequenceEqual(baseqs.filter(birthdate__testyear__lt=2012), [self.a1])

    @unittest.skipUnless(
        connection.vendor == "postgresql", "PostgreSQL specific SQL used"
    )
    def test_year_lte_fexpr(self):
        self.a2.age = 2011
        self.a2.save()
        self.a3.age = 2012
        self.a3.save()
        self.a4.age = 2013
        self.a4.save()
        baseqs = Author.objects.order_by("name")
        self.assertSequenceEqual(
            baseqs.filter(birthdate__testyear__lte=models.F("age")), [self.a3, self.a4]
        )
        self.assertSequenceEqual(
            baseqs.filter(birthdate__testyear__lt=models.F("age")), [self.a4]
        )

    def test_year_lte_sql(self):
        # This test will just check the generated SQL for __lte. This
        # doesn't require running on PostgreSQL and spots the most likely
        # error - not running YearLte SQL at all.
        """

        Tests that the SQL generated for a Django ORM query using the `lte` lookup
        on a custom `testyear` field includes the correct SQL expression.

        This test case checks that the generated SQL includes the test year value
        (2011) and the correct date format ('-12-31') to represent the end of the year.

        """
        baseqs = Author.objects.order_by("name")
        self.assertIn(
            "<= (2011 || ", str(baseqs.filter(birthdate__testyear__lte=2011).query)
        )
        self.assertIn("-12-31", str(baseqs.filter(birthdate__testyear__lte=2011).query))

    def test_postgres_year_exact(self):
        baseqs = Author.objects.order_by("name")
        self.assertIn("= (2011 || ", str(baseqs.filter(birthdate__testyear=2011).query))
        self.assertIn("-12-31", str(baseqs.filter(birthdate__testyear=2011).query))

    def test_custom_implementation_year_exact(self):
        """
        Tests the custom implementation of the year exact lookup.

        This test ensures that the custom implementation of the year exact lookup
        produces the correct SQL query by checking for the presence of a specific
        string in the query. It tests both the standard custom implementation
        and a custom implementation defined in a subclass.

        The test verifies that the custom implementation correctly converts the
        lookup expression into a SQL query that filters dates based on the exact
        year, using the str_to_date and concat functions to construct the
        start and end dates of the year.

        The test also checks that the custom implementation can be overridden
        in a subclass and still produce the correct SQL query.

        """
        try:
            # Two ways to add a customized implementation for different backends:
            # First is MonkeyPatch of the class.
            def as_custom_sql(self, compiler, connection):
                lhs_sql, lhs_params = self.process_lhs(
                    compiler, connection, self.lhs.lhs
                )
                rhs_sql, rhs_params = self.process_rhs(compiler, connection)
                params = lhs_params + rhs_params + lhs_params + rhs_params
                return (
                    "%(lhs)s >= "
                    "str_to_date(concat(%(rhs)s, '-01-01'), '%%%%Y-%%%%m-%%%%d') "
                    "AND %(lhs)s <= "
                    "str_to_date(concat(%(rhs)s, '-12-31'), '%%%%Y-%%%%m-%%%%d')"
                    % {"lhs": lhs_sql, "rhs": rhs_sql},
                    params,
                )

            setattr(YearExact, "as_" + connection.vendor, as_custom_sql)
            self.assertIn(
                "concat(", str(Author.objects.filter(birthdate__testyear=2012).query)
            )
        finally:
            delattr(YearExact, "as_" + connection.vendor)
        try:
            # The other way is to subclass the original lookup and register the
            # subclassed lookup instead of the original.
            class CustomYearExact(YearExact):
                # This method should be named "as_mysql" for MySQL,
                # "as_postgresql" for postgres and so on, but as we don't know
                # which DB we are running on, we need to use setattr.
                def as_custom_sql(self, compiler, connection):
                    """

                    Generates a custom SQL expression to match values in a date range.

                    This function creates a SQL query that checks if a date falls within a given year.
                    It takes the left-hand side (LHS) and right-hand side (RHS) of a comparison, 
                    and constructs a query that checks if the LHS date is within the year specified by the RHS.

                    The generated query uses the database's date functions to convert the RHS value to a date range,
                    from the first day of the year to the last day of the year.

                    The function returns a tuple containing the generated SQL expression and the parameters to be used with it.

                    The returned SQL expression can be used directly in a database query to filter dates based on the specified year.

                    """
                    lhs_sql, lhs_params = self.process_lhs(
                        compiler, connection, self.lhs.lhs
                    )
                    rhs_sql, rhs_params = self.process_rhs(compiler, connection)
                    params = lhs_params + rhs_params + lhs_params + rhs_params
                    return (
                        "%(lhs)s >= "
                        "str_to_date(CONCAT(%(rhs)s, '-01-01'), '%%%%Y-%%%%m-%%%%d') "
                        "AND %(lhs)s <= "
                        "str_to_date(CONCAT(%(rhs)s, '-12-31'), '%%%%Y-%%%%m-%%%%d')"
                        % {"lhs": lhs_sql, "rhs": rhs_sql},
                        params,
                    )

            setattr(
                CustomYearExact,
                "as_" + connection.vendor,
                CustomYearExact.as_custom_sql,
            )
            YearTransform.register_lookup(CustomYearExact)
            self.assertIn(
                "CONCAT(", str(Author.objects.filter(birthdate__testyear=2012).query)
            )
        finally:
            YearTransform._unregister_lookup(CustomYearExact)
            YearTransform.register_lookup(YearExact)


class TrackCallsYearTransform(YearTransform):
    # Use a name that avoids collision with the built-in year lookup.
    lookup_name = "testyear"
    call_order = []

    def as_sql(self, compiler, connection):
        lhs_sql, params = compiler.compile(self.lhs)
        return connection.ops.date_extract_sql("year", lhs_sql), params

    @property
    def output_field(self):
        return models.IntegerField()

    def get_lookup(self, lookup_name):
        """

        Retrieves a lookup object based on the provided lookup name.

        This method extends the parent class's functionality by tracking the call order,
        specifically appending 'lookup' to the call_order list before returning the lookup object.

        :param lookup_name: The name of the lookup object to retrieve
        :return: The lookup object associated with the given lookup name

        """
        self.call_order.append("lookup")
        return super().get_lookup(lookup_name)

    def get_transform(self, lookup_name):
        self.call_order.append("transform")
        return super().get_transform(lookup_name)


class LookupTransformCallOrderTests(SimpleTestCase):
    def test_call_order(self):
        """

        Tests the call order of the TrackCallsYearTransform when applied to a DateField.

        This test ensures that the transform and lookup are called in the expected order when
        used in a query. It also verifies that an unsupported lookup raises a FieldError with
        the correct message.

        The test scenarios cover the following cases:
        - An unsupported lookup ('junk') raises a FieldError.
        - Chained unsupported lookups ('junk__more_junk') raise a FieldError.
        - A valid lookup ('testyear') calls the lookup method in the expected order.
        - A valid lookup with an exact qualifier ('testyear__exact') calls the lookup method
          in the expected order.

        """
        with register_lookup(models.DateField, TrackCallsYearTransform):
            # junk lookup - tries lookup, then transform, then fails
            msg = (
                "Unsupported lookup 'junk' for IntegerField or join on the field not "
                "permitted."
            )
            with self.assertRaisesMessage(FieldError, msg):
                Author.objects.filter(birthdate__testyear__junk=2012)
            self.assertEqual(
                TrackCallsYearTransform.call_order, ["lookup", "transform"]
            )
            TrackCallsYearTransform.call_order = []
            # junk transform - tries transform only, then fails
            msg = (
                "Unsupported lookup 'junk__more_junk' for IntegerField or join"
                " on the field not permitted."
            )
            with self.assertRaisesMessage(FieldError, msg):
                Author.objects.filter(birthdate__testyear__junk__more_junk=2012)
            self.assertEqual(TrackCallsYearTransform.call_order, ["transform"])
            TrackCallsYearTransform.call_order = []
            # Just getting the year (implied __exact) - lookup only
            Author.objects.filter(birthdate__testyear=2012)
            self.assertEqual(TrackCallsYearTransform.call_order, ["lookup"])
            TrackCallsYearTransform.call_order = []
            # Just getting the year (explicit __exact) - lookup only
            Author.objects.filter(birthdate__testyear__exact=2012)
            self.assertEqual(TrackCallsYearTransform.call_order, ["lookup"])


class CustomisedMethodsTests(SimpleTestCase):
    def test_overridden_get_lookup(self):
        """
        Tests that the custom lookup function is correctly overridden and applied in a database query.

        This test case verifies that the 'lookupfunc_monkeys' lookup function is properly executed 
        when used in a filter operation on a CustomModel query set. It checks that the 
        generated SQL query includes the expected function call, ensuring that the custom 
        lookup is correctly integrated into the database query process.
        """
        q = CustomModel.objects.filter(field__lookupfunc_monkeys=3)
        self.assertIn("monkeys()", str(q.query))

    def test_overridden_get_transform(self):
        """

        Tests that a custom model's overridden get_transform method is correctly applied
        in a database query.

        Specifically, this test checks that when filtering on a custom field with a 
        transform function named 'transformfunc_banana', the query includes the expected
        'banana()' function call.

        The purpose of this test is to verify that the custom model's get_transform 
        method is overridden correctly and that it produces the expected SQL output.

        """
        q = CustomModel.objects.filter(field__transformfunc_banana=3)
        self.assertIn("banana()", str(q.query))

    def test_overridden_get_lookup_chain(self):
        q = CustomModel.objects.filter(
            field__transformfunc_banana__lookupfunc_elephants=3
        )
        self.assertIn("elephants()", str(q.query))

    def test_overridden_get_transform_chain(self):
        q = CustomModel.objects.filter(
            field__transformfunc_banana__transformfunc_pear=3
        )
        self.assertIn("pear()", str(q.query))


class SubqueryTransformTests(TestCase):
    def test_subquery_usage(self):
        """

        Tests the usage of a subquery in a Django ORM query.

        This test case checks if an Author object can be filtered based on a subquery
        that applies a custom transformation to the 'age' field. The transformation
        involves checking if the age is divisible by 3, but the test specifically
        verifies that an author with age 2 is returned. The test uses the 'Div3Transform'
        lookup and creates several Author objects to test the query.

        The test asserts that the filtered query returns the expected Author object,
        ordered by name, and checks that only one object is returned.

        """
        with register_lookup(models.IntegerField, Div3Transform):
            Author.objects.create(name="a1", age=1)
            a2 = Author.objects.create(name="a2", age=2)
            Author.objects.create(name="a3", age=3)
            Author.objects.create(name="a4", age=4)
            qs = Author.objects.order_by("name").filter(
                id__in=Author.objects.filter(age__div3=2)
            )
            self.assertSequenceEqual(qs, [a2])


class RegisterLookupTests(SimpleTestCase):
    def test_class_lookup(self):
        """
        Tests the lookup class registration for the Author model's 'name' field.

        Verifies that a custom lookup, CustomStartsWith, can be successfully registered for 
        the 'name' field of the Author model and retrieved using the 'sw' lookup name. 

        Also checks that the custom lookup is no longer available after the registration 
        context is exited, ensuring proper cleanup and avoiding potential conflicts with 
        other custom lookups.

        This test ensures that the dynamic lookup registration mechanism is working as 
        expected, allowing for flexible and customizable query capabilities in the ORM.
        """
        author_name = Author._meta.get_field("name")
        with register_lookup(models.CharField, CustomStartsWith):
            self.assertEqual(author_name.get_lookup("sw"), CustomStartsWith)
        self.assertIsNone(author_name.get_lookup("sw"))

    def test_instance_lookup(self):
        author_name = Author._meta.get_field("name")
        author_alias = Author._meta.get_field("alias")
        with register_lookup(author_name, CustomStartsWith):
            self.assertEqual(author_name.instance_lookups, {"sw": CustomStartsWith})
            self.assertEqual(author_name.get_lookup("sw"), CustomStartsWith)
            self.assertIsNone(author_alias.get_lookup("sw"))
        self.assertIsNone(author_name.get_lookup("sw"))
        self.assertEqual(author_name.instance_lookups, {})
        self.assertIsNone(author_alias.get_lookup("sw"))

    def test_instance_lookup_override_class_lookups(self):
        """

        Tests the instance lookup override mechanism for model fields.

        This function verifies that lookups can be overridden at the instance level,
        taking precedence over class-level lookups. It checks that the override is
        applied correctly and that it reverts to the original lookup after the override
        is removed.

        It specifically tests the `CustomStartsWith` and `CustomEndsWith` lookups,
        overriding the `st_end` lookup name on a `CharField` and an instance of the
        `Author` model's `alias` field.

        """
        author_name = Author._meta.get_field("name")
        author_alias = Author._meta.get_field("alias")
        with register_lookup(models.CharField, CustomStartsWith, lookup_name="st_end"):
            with register_lookup(author_alias, CustomEndsWith, lookup_name="st_end"):
                self.assertEqual(author_name.get_lookup("st_end"), CustomStartsWith)
                self.assertEqual(author_alias.get_lookup("st_end"), CustomEndsWith)
            self.assertEqual(author_name.get_lookup("st_end"), CustomStartsWith)
            self.assertEqual(author_alias.get_lookup("st_end"), CustomStartsWith)
        self.assertIsNone(author_name.get_lookup("st_end"))
        self.assertIsNone(author_alias.get_lookup("st_end"))

    def test_instance_lookup_override(self):
        """

        Tests if instance lookup can be overridden.

        This test case verifies that a custom lookup can be registered and used to
        override an existing lookup. The test checks if the custom lookup is correctly
        retrieved after registration and if it is properly cleaned up after the
        registration context is exited.

        The test specifically checks for the following scenarios:

        * Registration of a custom lookup with a specific lookup name
        * Retrieval of the custom lookup using the lookup name
        * Overriding of an existing lookup with a new custom lookup
        * Cleanup of the custom lookup after exiting the registration context

        """
        author_name = Author._meta.get_field("name")
        with register_lookup(author_name, CustomStartsWith, lookup_name="st_end"):
            self.assertEqual(author_name.get_lookup("st_end"), CustomStartsWith)
            author_name.register_lookup(CustomEndsWith, lookup_name="st_end")
            self.assertEqual(author_name.get_lookup("st_end"), CustomEndsWith)
        self.assertIsNone(author_name.get_lookup("st_end"))

    def test_lookup_on_transform(self):
        transform = Div3Transform
        with register_lookup(Div3Transform, CustomStartsWith):
            with register_lookup(Div3Transform, CustomEndsWith):
                self.assertEqual(
                    transform.get_lookups(),
                    {"sw": CustomStartsWith, "ew": CustomEndsWith},
                )
            self.assertEqual(transform.get_lookups(), {"sw": CustomStartsWith})
        self.assertEqual(transform.get_lookups(), {})

    def test_transform_on_field(self):
        author_name = Author._meta.get_field("name")
        author_alias = Author._meta.get_field("alias")
        with register_lookup(models.CharField, Div3Transform):
            self.assertEqual(author_alias.get_transform("div3"), Div3Transform)
            self.assertEqual(author_name.get_transform("div3"), Div3Transform)
        with register_lookup(author_alias, Div3Transform):
            self.assertEqual(author_alias.get_transform("div3"), Div3Transform)
            self.assertIsNone(author_name.get_transform("div3"))
        self.assertIsNone(author_alias.get_transform("div3"))
        self.assertIsNone(author_name.get_transform("div3"))

    def test_related_lookup(self):
        article_author = Article._meta.get_field("author")
        with register_lookup(models.Field, CustomStartsWith):
            self.assertIsNone(article_author.get_lookup("sw"))
        with register_lookup(models.ForeignKey, RelatedMoreThan):
            self.assertEqual(article_author.get_lookup("rmt"), RelatedMoreThan)

    def test_instance_related_lookup(self):
        """
        Tests that the RelatedMoreThan lookup can be registered and retrieved for the 'author' field of the Article model.

        The test case verifies that once the lookup is registered, it can be successfully retrieved using the 'rmt' lookup name, and that it is cleared after the registration context is exited.
        """
        article_author = Article._meta.get_field("author")
        with register_lookup(article_author, RelatedMoreThan):
            self.assertEqual(article_author.get_lookup("rmt"), RelatedMoreThan)
        self.assertIsNone(article_author.get_lookup("rmt"))
