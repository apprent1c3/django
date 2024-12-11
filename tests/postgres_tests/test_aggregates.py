from django.db import transaction
from django.db.models import (
    CharField,
    F,
    Func,
    IntegerField,
    JSONField,
    OuterRef,
    Q,
    Subquery,
    Value,
    Window,
)
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast, Concat, LPad, Substr
from django.test.utils import Approximate
from django.utils import timezone

from . import PostgreSQLTestCase
from .models import AggregateTestModel, HotelReservation, Room, StatTestModel

try:
    from django.contrib.postgres.aggregates import (
        ArrayAgg,
        BitAnd,
        BitOr,
        BitXor,
        BoolAnd,
        BoolOr,
        Corr,
        CovarPop,
        JSONBAgg,
        RegrAvgX,
        RegrAvgY,
        RegrCount,
        RegrIntercept,
        RegrR2,
        RegrSlope,
        RegrSXX,
        RegrSXY,
        RegrSYY,
        StatAggregate,
        StringAgg,
    )
    from django.contrib.postgres.fields import ArrayField
except ImportError:
    pass  # psycopg2 is not installed


class TestGeneralAggregate(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.aggs = AggregateTestModel.objects.bulk_create(
            [
                AggregateTestModel(
                    boolean_field=True,
                    char_field="Foo1",
                    text_field="Text1",
                    integer_field=0,
                ),
                AggregateTestModel(
                    boolean_field=False,
                    char_field="Foo2",
                    text_field="Text2",
                    integer_field=1,
                    json_field={"lang": "pl"},
                ),
                AggregateTestModel(
                    boolean_field=False,
                    char_field="Foo4",
                    text_field="Text4",
                    integer_field=2,
                    json_field={"lang": "en"},
                ),
                AggregateTestModel(
                    boolean_field=True,
                    char_field="Foo3",
                    text_field="Text3",
                    integer_field=0,
                    json_field={"breed": "collie"},
                ),
            ]
        )

    def test_empty_result_set(self):
        """

        Tests the behavior of various aggregate functions when applied to an empty result set.

        Verifies that when using the :func:`aggregate` method on an empty :class:`~django.db.models.QuerySet` (i.e., :func:`~django.db.models.Manager.none`), 
        all tested aggregate functions (ArrayAgg, BitAnd, BitOr, BitXor, BoolAnd, BoolOr, JSONBAgg, StringAgg) 
        return `None` as the aggregated value, without executing any database queries.

        Additionally, it checks the same aggregate functions when applied to an empty :class:`~django.db.models.QuerySet` obtained from the database,
        confirming that a single database query is executed and the aggregated value is still `None`.

        """
        AggregateTestModel.objects.all().delete()
        tests = [
            ArrayAgg("char_field"),
            ArrayAgg("integer_field"),
            ArrayAgg("boolean_field"),
            BitAnd("integer_field"),
            BitOr("integer_field"),
            BoolAnd("boolean_field"),
            BoolOr("boolean_field"),
            JSONBAgg("integer_field"),
            StringAgg("char_field", delimiter=";"),
            BitXor("integer_field"),
        ]
        for aggregation in tests:
            with self.subTest(aggregation=aggregation):
                # Empty result with non-execution optimization.
                with self.assertNumQueries(0):
                    values = AggregateTestModel.objects.none().aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": None})
                # Empty result when query must be executed.
                with self.assertNumQueries(1):
                    values = AggregateTestModel.objects.aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": None})

    def test_default_argument(self):
        """

        Tests the behavior of aggregation functions with default arguments.

        This test case checks the output of various aggregation functions (e.g. ArrayAgg, BitAnd, JSONBAgg, StringAgg)
        when applied to an empty queryset and a non-empty queryset, using the default values specified in the function.
        The test ensures that the default values are returned when the queryset is empty and that the aggregation functions
        produce the expected results when the queryset contains data.

        The test covers a range of aggregation functions, including those that operate on different data types (e.g. char, integer, boolean).
        It also checks the behavior of the aggregation functions with different default values, including strings, integers, and JSON values.

        """
        AggregateTestModel.objects.all().delete()
        tests = [
            (ArrayAgg("char_field", default=["<empty>"]), ["<empty>"]),
            (ArrayAgg("integer_field", default=[0]), [0]),
            (ArrayAgg("boolean_field", default=[False]), [False]),
            (BitAnd("integer_field", default=0), 0),
            (BitOr("integer_field", default=0), 0),
            (BoolAnd("boolean_field", default=False), False),
            (BoolOr("boolean_field", default=False), False),
            (JSONBAgg("integer_field", default=["<empty>"]), ["<empty>"]),
            (
                JSONBAgg("integer_field", default=Value(["<empty>"], JSONField())),
                ["<empty>"],
            ),
            (StringAgg("char_field", delimiter=";", default="<empty>"), "<empty>"),
            (
                StringAgg("char_field", delimiter=";", default=Value("<empty>")),
                "<empty>",
            ),
            (BitXor("integer_field", default=0), 0),
        ]
        for aggregation, expected_result in tests:
            with self.subTest(aggregation=aggregation):
                # Empty result with non-execution optimization.
                with self.assertNumQueries(0):
                    values = AggregateTestModel.objects.none().aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": expected_result})
                # Empty result when query must be executed.
                with transaction.atomic(), self.assertNumQueries(1):
                    values = AggregateTestModel.objects.aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": expected_result})

    def test_array_agg_charfield(self):
        """
        Tests the array aggregation functionality on a character field in a database table.

        This test case aggregates the values of a character field from a collection of objects 
        and verifies that the resulting array contains the expected values in the correct order. 
        The purpose of this test is to ensure that the array aggregation functionality works 
        as expected for character fields, returning a list of values that can be used for 
        further processing or analysis.
        """
        values = AggregateTestModel.objects.aggregate(arrayagg=ArrayAgg("char_field"))
        self.assertEqual(values, {"arrayagg": ["Foo1", "Foo2", "Foo4", "Foo3"]})

    def test_array_agg_charfield_ordering(self):
        ordering_test_cases = (
            (F("char_field").desc(), ["Foo4", "Foo3", "Foo2", "Foo1"]),
            (F("char_field").asc(), ["Foo1", "Foo2", "Foo3", "Foo4"]),
            (F("char_field"), ["Foo1", "Foo2", "Foo3", "Foo4"]),
            (
                [F("boolean_field"), F("char_field").desc()],
                ["Foo4", "Foo2", "Foo3", "Foo1"],
            ),
            (
                (F("boolean_field"), F("char_field").desc()),
                ["Foo4", "Foo2", "Foo3", "Foo1"],
            ),
            ("char_field", ["Foo1", "Foo2", "Foo3", "Foo4"]),
            ("-char_field", ["Foo4", "Foo3", "Foo2", "Foo1"]),
            (Concat("char_field", Value("@")), ["Foo1", "Foo2", "Foo3", "Foo4"]),
            (Concat("char_field", Value("@")).desc(), ["Foo4", "Foo3", "Foo2", "Foo1"]),
            (
                (
                    Substr("char_field", 1, 1),
                    F("integer_field"),
                    Substr("char_field", 4, 1).desc(),
                ),
                ["Foo3", "Foo1", "Foo2", "Foo4"],
            ),
        )
        for ordering, expected_output in ordering_test_cases:
            with self.subTest(ordering=ordering, expected_output=expected_output):
                values = AggregateTestModel.objects.aggregate(
                    arrayagg=ArrayAgg("char_field", ordering=ordering)
                )
                self.assertEqual(values, {"arrayagg": expected_output})

    def test_array_agg_integerfield(self):
        """
        Tests the usage of the ArrayAgg function with an IntegerField.

        Verifies that the ArrayAgg function correctly aggregates the integer_field 
        values from the AggregateTestModel instances into a list.

        The expected output is a dictionary containing a single key 'arrayagg' 
        with a list of aggregated integer values, in this case [0, 1, 2, 0].
        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field")
        )
        self.assertEqual(values, {"arrayagg": [0, 1, 2, 0]})

    def test_array_agg_integerfield_ordering(self):
        """
        .. docstring::

            Tests the functionality of the `ArrayAgg` aggregation function when used with an `IntegerField` and ordering.

            This test case verifies that the `ArrayAgg` aggregation function correctly aggregates a list of integer values from a model field, 
            and that the values are ordered in descending order as specified. The test checks that the resulting aggregated list matches the 
            expected ordered values.
        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field", ordering=F("integer_field").desc())
        )
        self.assertEqual(values, {"arrayagg": [2, 1, 0, 0]})

    def test_array_agg_booleanfield(self):
        """

        Tests the aggregation of boolean fields using the ArrayAgg function.

        This function checks if the ArrayAgg function correctly aggregates boolean fields 
        from the AggregateTestModel, returning all unique values in an array. The test 
        verifies that the aggregated array matches the expected result.

        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("boolean_field")
        )
        self.assertEqual(values, {"arrayagg": [True, False, False, True]})

    def test_array_agg_booleanfield_ordering(self):
        ordering_test_cases = (
            (F("boolean_field").asc(), [False, False, True, True]),
            (F("boolean_field").desc(), [True, True, False, False]),
            (F("boolean_field"), [False, False, True, True]),
        )
        for ordering, expected_output in ordering_test_cases:
            with self.subTest(ordering=ordering, expected_output=expected_output):
                values = AggregateTestModel.objects.aggregate(
                    arrayagg=ArrayAgg("boolean_field", ordering=ordering)
                )
                self.assertEqual(values, {"arrayagg": expected_output})

    def test_array_agg_jsonfield(self):
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg(
                KeyTransform("lang", "json_field"),
                filter=Q(json_field__lang__isnull=False),
            ),
        )
        self.assertEqual(values, {"arrayagg": ["pl", "en"]})

    def test_array_agg_jsonfield_ordering(self):
        """
        Test the ordering of ArrayAgg aggregation on a JSONField.

        This test case verifies that the ArrayAgg function correctly aggregates and orders values from a JSONField.
        The function checks if the ArrayAgg aggregation orders the values in the 'lang' key within the 'json_field' based on the 'lang' value itself.
        It also filters out any records where 'lang' is null.
        The expected output is a list of language codes, in this case 'en' and 'pl', which are ordered as specified by the KeyTransform.
        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg(
                KeyTransform("lang", "json_field"),
                filter=Q(json_field__lang__isnull=False),
                ordering=KeyTransform("lang", "json_field"),
            ),
        )
        self.assertEqual(values, {"arrayagg": ["en", "pl"]})

    def test_array_agg_filter_and_ordering_params(self):
        """

        Tests the functionality of the ArrayAgg aggregation function with filtering and ordering parameters.

        This function aggregates values from a model's field, filtering results based on the presence of a key in a JSON field, 
        and applying a custom ordering using the LPad function to pad integer values with leading zeros.

        The test verifies that the aggregation produces the expected output, ensuring that the filtering and ordering parameters 
        are correctly applied to the result.

        Returns:
            None

        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg(
                "char_field",
                filter=Q(json_field__has_key="lang"),
                ordering=LPad(Cast("integer_field", CharField()), 2, Value("0")),
            )
        )
        self.assertEqual(values, {"arrayagg": ["Foo2", "Foo4"]})

    def test_array_agg_filter(self):
        """
        Tests the filtering functionality of ArrayAgg aggregation.

        This test case ensures that the ArrayAgg function correctly filters the values
        from the 'integer_field' of AggregateTestModel instances, only including values
        that are greater than 0 in the resulting array.

        The expected output is a dictionary containing a single key-value pair, where the
        key is 'arrayagg' and the value is a list of integers that meet the specified
        filter condition.

        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field", filter=Q(integer_field__gt=0)),
        )
        self.assertEqual(values, {"arrayagg": [1, 2]})

    def test_array_agg_lookups(self):
        aggr1 = AggregateTestModel.objects.create()
        aggr2 = AggregateTestModel.objects.create()
        StatTestModel.objects.create(related_field=aggr1, int1=1, int2=0)
        StatTestModel.objects.create(related_field=aggr1, int1=2, int2=0)
        StatTestModel.objects.create(related_field=aggr2, int1=3, int2=0)
        StatTestModel.objects.create(related_field=aggr2, int1=4, int2=0)
        qs = (
            StatTestModel.objects.values("related_field")
            .annotate(array=ArrayAgg("int1"))
            .filter(array__overlap=[2])
            .values_list("array", flat=True)
        )
        self.assertCountEqual(qs.get(), [1, 2])

    def test_array_agg_filter_index(self):
        aggr1 = AggregateTestModel.objects.create(integer_field=1)
        aggr2 = AggregateTestModel.objects.create(integer_field=2)
        StatTestModel.objects.bulk_create(
            [
                StatTestModel(related_field=aggr1, int1=1, int2=0),
                StatTestModel(related_field=aggr1, int1=2, int2=1),
                StatTestModel(related_field=aggr2, int1=3, int2=0),
                StatTestModel(related_field=aggr2, int1=4, int2=1),
            ]
        )
        qs = (
            AggregateTestModel.objects.filter(pk__in=[aggr1.pk, aggr2.pk])
            .annotate(
                array=ArrayAgg("stattestmodel__int1", filter=Q(stattestmodel__int2=0))
            )
            .annotate(array_value=F("array__0"))
            .values_list("array_value", flat=True)
        )
        self.assertCountEqual(qs, [1, 3])

    def test_array_agg_filter_slice(self):
        aggr1 = AggregateTestModel.objects.create(integer_field=1)
        aggr2 = AggregateTestModel.objects.create(integer_field=2)
        StatTestModel.objects.bulk_create(
            [
                StatTestModel(related_field=aggr1, int1=1, int2=0),
                StatTestModel(related_field=aggr1, int1=2, int2=1),
                StatTestModel(related_field=aggr2, int1=3, int2=0),
                StatTestModel(related_field=aggr2, int1=4, int2=1),
                StatTestModel(related_field=aggr2, int1=5, int2=0),
            ]
        )
        qs = (
            AggregateTestModel.objects.filter(pk__in=[aggr1.pk, aggr2.pk])
            .annotate(
                array=ArrayAgg("stattestmodel__int1", filter=Q(stattestmodel__int2=0))
            )
            .annotate(array_value=F("array__1_2"))
            .values_list("array_value", flat=True)
        )
        self.assertCountEqual(qs, [[], [5]])

    def test_bit_and_general(self):
        """
        Tests the BitAnd aggregation function by filtering AggregateTestModel objects with integer_field values of 0 or 1 and verifying that the bitwise AND operation returns 0.
        """
        values = AggregateTestModel.objects.filter(integer_field__in=[0, 1]).aggregate(
            bitand=BitAnd("integer_field")
        )
        self.assertEqual(values, {"bitand": 0})

    def test_bit_and_on_only_true_values(self):
        """
        Tests that the BitAnd aggregation function correctly performs a bitwise AND operation on a queryset of models, 
        returning the expected result of 1 when all integer_field values are 1.
        """
        values = AggregateTestModel.objects.filter(integer_field=1).aggregate(
            bitand=BitAnd("integer_field")
        )
        self.assertEqual(values, {"bitand": 1})

    def test_bit_and_on_only_false_values(self):
        """
        Tests that the BitAnd aggregation function correctly handles a query set containing only false values. 
        It verifies that when all values in the 'integer_field' of AggregateTestModel are 0 (i.e., false in a bitwise context), 
        the result of the BitAnd operation is also 0, as expected from the properties of bitwise AND operation.
        """
        values = AggregateTestModel.objects.filter(integer_field=0).aggregate(
            bitand=BitAnd("integer_field")
        )
        self.assertEqual(values, {"bitand": 0})

    def test_bit_or_general(self):
        values = AggregateTestModel.objects.filter(integer_field__in=[0, 1]).aggregate(
            bitor=BitOr("integer_field")
        )
        self.assertEqual(values, {"bitor": 1})

    def test_bit_or_on_only_true_values(self):
        values = AggregateTestModel.objects.filter(integer_field=1).aggregate(
            bitor=BitOr("integer_field")
        )
        self.assertEqual(values, {"bitor": 1})

    def test_bit_or_on_only_false_values(self):
        """
        Tests the behavior of the BitOr aggregation function when applied to a queryset containing only falsey values.

        The test verifies that the BitOr aggregation function correctly returns 0 when all values in the specified field are 0, as expected when performing a bitwise OR operation on zero values.
        """
        values = AggregateTestModel.objects.filter(integer_field=0).aggregate(
            bitor=BitOr("integer_field")
        )
        self.assertEqual(values, {"bitor": 0})

    def test_bit_xor_general(self):
        AggregateTestModel.objects.create(integer_field=3)
        values = AggregateTestModel.objects.filter(
            integer_field__in=[1, 3],
        ).aggregate(bitxor=BitXor("integer_field"))
        self.assertEqual(values, {"bitxor": 2})

    def test_bit_xor_on_only_true_values(self):
        """

        Verifies the correct functionality of the BitXor aggregation function when applied to a set of true values.

        This test case checks if the bit XOR operation is correctly performed on a set of non-zero values and returns the expected result.

        The purpose of this test is to ensure that the BitXor function correctly handles cases where all input values are non-zero, confirming its reliability in various scenarios.

        """
        values = AggregateTestModel.objects.filter(
            integer_field=1,
        ).aggregate(bitxor=BitXor("integer_field"))
        self.assertEqual(values, {"bitxor": 1})

    def test_bit_xor_on_only_false_values(self):
        values = AggregateTestModel.objects.filter(
            integer_field=0,
        ).aggregate(bitxor=BitXor("integer_field"))
        self.assertEqual(values, {"bitxor": 0})

    def test_bool_and_general(self):
        values = AggregateTestModel.objects.aggregate(booland=BoolAnd("boolean_field"))
        self.assertEqual(values, {"booland": False})

    def test_bool_and_q_object(self):
        """

        Tests the BoolAnd function in conjunction with a Q object.

        This function verifies that the BoolAnd function returns the correct boolean result
        when used in conjunction with a Q object to filter values in a database query.
        The test checks that the function correctly evaluates the specified condition
        and returns False when no rows match the given criteria.

        """
        values = AggregateTestModel.objects.aggregate(
            booland=BoolAnd(Q(integer_field__gt=2)),
        )
        self.assertEqual(values, {"booland": False})

    def test_bool_or_general(self):
        values = AggregateTestModel.objects.aggregate(boolor=BoolOr("boolean_field"))
        self.assertEqual(values, {"boolor": True})

    def test_bool_or_q_object(self):
        """
        Tests the BoolOr aggregate function in combination with a Q object.

        This test case verifies the correct application of the BoolOr aggregate function
        when used in conjunction with a Q object condition. The function aggregates 
        boolean values from the database based on the given condition (in this case, 
        values greater than 2) and returns True if at least one condition is met, 
        otherwise returns False.

        In this specific test scenario, since there are no integer field values greater 
        than 2, the expected result is False. The test asserts that the aggregated 
        value matches this expectation, ensuring the BoolOr function behaves correctly 
        with the specified Q object condition.
        """
        values = AggregateTestModel.objects.aggregate(
            boolor=BoolOr(Q(integer_field__gt=2)),
        )
        self.assertEqual(values, {"boolor": False})

    def test_string_agg_requires_delimiter(self):
        """

        Tests that the StringAgg aggregation function requires a delimiter.

        Verifies that a TypeError is raised when attempting to use StringAgg without 
        specifying a delimiter, ensuring that the function is used correctly and 
        preventing potential errors in query results.

        """
        with self.assertRaises(TypeError):
            AggregateTestModel.objects.aggregate(stringagg=StringAgg("char_field"))

    def test_string_agg_delimiter_escaping(self):
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("char_field", delimiter="'")
        )
        self.assertEqual(values, {"stringagg": "Foo1'Foo2'Foo4'Foo3"})

    def test_string_agg_charfield(self):
        """
        Tests the aggregation of a CharField using the StringAgg function.

        This function verifies that the StringAgg function correctly concatenates the values
        of a CharField from a queryset of AggregateTestModel objects, separated by a
        delimiter. The result is expected to be a single string containing all the
        char_field values joined by the specified delimiter.

        The test checks that the aggregated string matches the expected output, ensuring
        that the StringAgg function is working correctly and producing the desired result.
        """
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("char_field", delimiter=";")
        )
        self.assertEqual(values, {"stringagg": "Foo1;Foo2;Foo4;Foo3"})

    def test_string_agg_default_output_field(self):
        """
        Tests the default output field of the StringAgg aggregation function.

        This test case verifies that the StringAgg function correctly aggregates text fields
        from a queryset and returns the result as a string, separated by a specified delimiter.

        The default output field is expected to be a string containing all aggregated values,
        in the order they appear in the database. The test checks that the resulting string
        matches the expected output, confirming that the StringAgg function behaves as expected.

        The test uses the AggregateTestModel to create a queryset and applies the StringAgg
        function to the 'text_field' attribute, with ';' as the delimiter. The result is then
        compared to the expected output to ensure correctness.
        """
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("text_field", delimiter=";"),
        )
        self.assertEqual(values, {"stringagg": "Text1;Text2;Text4;Text3"})

    def test_string_agg_charfield_ordering(self):
        """
        Tests the functionality of the StringAgg database function in conjunction with ordering, ensuring correct aggregation and concatenation of CharField values.

            The function evaluates the StringAgg function under various ordering scenarios, including ascending, descending, and default orderings, as well as with concatenated values.

            It verifies that the aggregated string produced by the StringAgg function matches the expected output for each specified ordering case. This ensures that the ordering parameter of the StringAgg function correctly influences the resulting aggregated string.
        """
        ordering_test_cases = (
            (F("char_field").desc(), "Foo4;Foo3;Foo2;Foo1"),
            (F("char_field").asc(), "Foo1;Foo2;Foo3;Foo4"),
            (F("char_field"), "Foo1;Foo2;Foo3;Foo4"),
            ("char_field", "Foo1;Foo2;Foo3;Foo4"),
            ("-char_field", "Foo4;Foo3;Foo2;Foo1"),
            (Concat("char_field", Value("@")), "Foo1;Foo2;Foo3;Foo4"),
            (Concat("char_field", Value("@")).desc(), "Foo4;Foo3;Foo2;Foo1"),
        )
        for ordering, expected_output in ordering_test_cases:
            with self.subTest(ordering=ordering, expected_output=expected_output):
                values = AggregateTestModel.objects.aggregate(
                    stringagg=StringAgg("char_field", delimiter=";", ordering=ordering)
                )
                self.assertEqual(values, {"stringagg": expected_output})

    def test_string_agg_jsonfield_ordering(self):
        """
        Tests the aggregation of a JSONField using the StringAgg function with ordering.

        The function verifies that the StringAgg function correctly aggregates the 'lang' key from the 'json_field' in the AggregateTestModel, 
        delimiting the results with a semicolon and ordering them based on the 'lang' value. The expected output is a string containing the aggregated values in the correct order.
        """
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg(
                KeyTextTransform("lang", "json_field"),
                delimiter=";",
                ordering=KeyTextTransform("lang", "json_field"),
                output_field=CharField(),
            ),
        )
        self.assertEqual(values, {"stringagg": "en;pl"})

    def test_string_agg_filter(self):
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg(
                "char_field",
                delimiter=";",
                filter=Q(char_field__endswith="3") | Q(char_field__endswith="1"),
            )
        )
        self.assertEqual(values, {"stringagg": "Foo1;Foo3"})

    def test_orderable_agg_alternative_fields(self):
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field", ordering=F("char_field").asc())
        )
        self.assertEqual(values, {"arrayagg": [0, 1, 0, 2]})

    def test_jsonb_agg(self):
        """

        Tests the aggregation of a JSONB field using the jsonb_agg function.

        This test case verifies that the jsonb_agg function correctly aggregates the values 
        from the 'char_field' of the AggregateTestModel objects into a list.

        The expected result is a dictionary with a single key 'jsonbagg' containing a list 
        of strings, representing the aggregated values from the 'char_field' of all 
        AggregateTestModel objects.

        """
        values = AggregateTestModel.objects.aggregate(jsonbagg=JSONBAgg("char_field"))
        self.assertEqual(values, {"jsonbagg": ["Foo1", "Foo2", "Foo4", "Foo3"]})

    def test_jsonb_agg_charfield_ordering(self):
        """

        Tests the JSONB aggregation function with a character field ordering.

        This test function checks the behavior of the JSONB aggregation function when 
        used with different ordering parameters on a character field. It verifies that 
        the aggregated output is ordered according to the specified ordering (ascending 
        or descending) and that the output matches the expected results.

        The test covers various ordering scenarios, including ascending and descending 
        order, default ordering, and ordering with concatenated fields. It ensures that 
        the JSONB aggregation function behaves correctly in each of these scenarios.

         Parameters:
            None

         Returns:
            None, but asserts that the aggregated output matches the expected results.

        """
        ordering_test_cases = (
            (F("char_field").desc(), ["Foo4", "Foo3", "Foo2", "Foo1"]),
            (F("char_field").asc(), ["Foo1", "Foo2", "Foo3", "Foo4"]),
            (F("char_field"), ["Foo1", "Foo2", "Foo3", "Foo4"]),
            ("char_field", ["Foo1", "Foo2", "Foo3", "Foo4"]),
            ("-char_field", ["Foo4", "Foo3", "Foo2", "Foo1"]),
            (Concat("char_field", Value("@")), ["Foo1", "Foo2", "Foo3", "Foo4"]),
            (Concat("char_field", Value("@")).desc(), ["Foo4", "Foo3", "Foo2", "Foo1"]),
        )
        for ordering, expected_output in ordering_test_cases:
            with self.subTest(ordering=ordering, expected_output=expected_output):
                values = AggregateTestModel.objects.aggregate(
                    jsonbagg=JSONBAgg("char_field", ordering=ordering),
                )
                self.assertEqual(values, {"jsonbagg": expected_output})

    def test_jsonb_agg_integerfield_ordering(self):
        """
        Tests the functionality of the JSONB aggregation function for ordering IntegerField values in descending order.

        This test case verifies that the JSONB aggregation function correctly aggregates IntegerField values from a model instance,
        orders them in descending order, and returns the result in a JSONB format.

        The expected output is a dictionary containing the aggregated values, which should match the predefined expected result.

        """
        values = AggregateTestModel.objects.aggregate(
            jsonbagg=JSONBAgg("integer_field", ordering=F("integer_field").desc()),
        )
        self.assertEqual(values, {"jsonbagg": [2, 1, 0, 0]})

    def test_jsonb_agg_booleanfield_ordering(self):
        """
        Tests the JSONB aggregation functionality on a boolean field with different ordering options.

        This test case verifies that the JSONB aggregation function correctly aggregates boolean field values in the specified order.

        The test covers the following ordering scenarios:
        - Ascending order
        - Descending order
        - Default ordering (which is equivalent to ascending order)

        For each scenario, the test compares the aggregated output with the expected result to ensure that the JSONB aggregation function is working as intended.
        """
        ordering_test_cases = (
            (F("boolean_field").asc(), [False, False, True, True]),
            (F("boolean_field").desc(), [True, True, False, False]),
            (F("boolean_field"), [False, False, True, True]),
        )
        for ordering, expected_output in ordering_test_cases:
            with self.subTest(ordering=ordering, expected_output=expected_output):
                values = AggregateTestModel.objects.aggregate(
                    jsonbagg=JSONBAgg("boolean_field", ordering=ordering),
                )
                self.assertEqual(values, {"jsonbagg": expected_output})

    def test_jsonb_agg_jsonfield_ordering(self):
        """
        Tests the behavior of the JSONB aggregation function when ordering results by a JSON field and filtering out null values.

        This test case verifies that the JSONBAgg function correctly aggregates the 'lang' values from the 'json_field' of the AggregateTestModel instances, 
        while ordering the results and excluding instances where the 'lang' value is null. 

        The test asserts that the aggregated result is as expected, with the values ordered accordingly.
        """
        values = AggregateTestModel.objects.aggregate(
            jsonbagg=JSONBAgg(
                KeyTransform("lang", "json_field"),
                filter=Q(json_field__lang__isnull=False),
                ordering=KeyTransform("lang", "json_field"),
            ),
        )
        self.assertEqual(values, {"jsonbagg": ["en", "pl"]})

    def test_jsonb_agg_key_index_transforms(self):
        room101 = Room.objects.create(number=101)
        room102 = Room.objects.create(number=102)
        datetimes = [
            timezone.datetime(2018, 6, 20),
            timezone.datetime(2018, 6, 24),
            timezone.datetime(2018, 6, 28),
        ]
        HotelReservation.objects.create(
            datespan=(datetimes[0].date(), datetimes[1].date()),
            start=datetimes[0],
            end=datetimes[1],
            room=room102,
            requirements={"double_bed": True, "parking": True},
        )
        HotelReservation.objects.create(
            datespan=(datetimes[1].date(), datetimes[2].date()),
            start=datetimes[1],
            end=datetimes[2],
            room=room102,
            requirements={"double_bed": False, "sea_view": True, "parking": False},
        )
        HotelReservation.objects.create(
            datespan=(datetimes[0].date(), datetimes[2].date()),
            start=datetimes[0],
            end=datetimes[2],
            room=room101,
            requirements={"sea_view": False},
        )
        values = (
            Room.objects.annotate(
                requirements=JSONBAgg(
                    "hotelreservation__requirements",
                    ordering="-hotelreservation__start",
                )
            )
            .filter(requirements__0__sea_view=True)
            .values("number", "requirements")
        )
        self.assertSequenceEqual(
            values,
            [
                {
                    "number": 102,
                    "requirements": [
                        {"double_bed": False, "sea_view": True, "parking": False},
                        {"double_bed": True, "parking": True},
                    ],
                },
            ],
        )

    def test_string_agg_array_agg_ordering_in_subquery(self):
        """

        Tests the ordering of ArrayAgg and StringAgg aggregations within a subquery.

        Verifies that the results are ordered correctly based on the specified field and
        delimiter. The test creates a set of related objects, performs the aggregations,
        and asserts that the output matches the expected results.

        The test covers two aggregation cases:

        * ArrayAgg with ordering
        * StringAgg with ordering and a specified delimiter

        Each case is executed as a separate subtest to ensure accurate error reporting.

        """
        stats = []
        for i, agg in enumerate(AggregateTestModel.objects.order_by("char_field")):
            stats.append(StatTestModel(related_field=agg, int1=i, int2=i + 1))
            stats.append(StatTestModel(related_field=agg, int1=i + 1, int2=i))
        StatTestModel.objects.bulk_create(stats)

        for aggregate, expected_result in (
            (
                ArrayAgg("stattestmodel__int1", ordering="-stattestmodel__int2"),
                [
                    ("Foo1", [0, 1]),
                    ("Foo2", [1, 2]),
                    ("Foo3", [2, 3]),
                    ("Foo4", [3, 4]),
                ],
            ),
            (
                StringAgg(
                    Cast("stattestmodel__int1", CharField()),
                    delimiter=";",
                    ordering="-stattestmodel__int2",
                ),
                [("Foo1", "0;1"), ("Foo2", "1;2"), ("Foo3", "2;3"), ("Foo4", "3;4")],
            ),
        ):
            with self.subTest(aggregate=aggregate.__class__.__name__):
                subquery = (
                    AggregateTestModel.objects.filter(
                        pk=OuterRef("pk"),
                    )
                    .annotate(agg=aggregate)
                    .values("agg")
                )
                values = (
                    AggregateTestModel.objects.annotate(
                        agg=Subquery(subquery),
                    )
                    .order_by("char_field")
                    .values_list("char_field", "agg")
                )
                self.assertEqual(list(values), expected_result)

    def test_string_agg_array_agg_filter_in_subquery(self):
        StatTestModel.objects.bulk_create(
            [
                StatTestModel(related_field=self.aggs[0], int1=0, int2=5),
                StatTestModel(related_field=self.aggs[0], int1=1, int2=4),
                StatTestModel(related_field=self.aggs[0], int1=2, int2=3),
            ]
        )
        for aggregate, expected_result in (
            (
                ArrayAgg("stattestmodel__int1", filter=Q(stattestmodel__int2__gt=3)),
                [("Foo1", [0, 1]), ("Foo2", None)],
            ),
            (
                StringAgg(
                    Cast("stattestmodel__int2", CharField()),
                    delimiter=";",
                    filter=Q(stattestmodel__int1__lt=2),
                ),
                [("Foo1", "5;4"), ("Foo2", None)],
            ),
        ):
            with self.subTest(aggregate=aggregate.__class__.__name__):
                subquery = (
                    AggregateTestModel.objects.filter(
                        pk=OuterRef("pk"),
                    )
                    .annotate(agg=aggregate)
                    .values("agg")
                )
                values = (
                    AggregateTestModel.objects.annotate(
                        agg=Subquery(subquery),
                    )
                    .filter(
                        char_field__in=["Foo1", "Foo2"],
                    )
                    .order_by("char_field")
                    .values_list("char_field", "agg")
                )
                self.assertEqual(list(values), expected_result)

    def test_string_agg_filter_in_subquery_with_exclude(self):
        subquery = (
            AggregateTestModel.objects.annotate(
                stringagg=StringAgg(
                    "char_field",
                    delimiter=";",
                    filter=Q(char_field__endswith="1"),
                )
            )
            .exclude(stringagg="")
            .values("id")
        )
        self.assertSequenceEqual(
            AggregateTestModel.objects.filter(id__in=Subquery(subquery)),
            [self.aggs[0]],
        )

    def test_ordering_isnt_cleared_for_array_subquery(self):
        """

        Tests that the ordering of a subquery is preserved when used within an array aggregation.

        This test ensures that when an ordered subquery is used to populate an array
        field in a QuerySet, the ordering is maintained in the resulting array.

        The test checks that the array of integers returned by the subquery matches
        the ordered values from the subquery, confirming that the ordering is not
        cleared during the array aggregation process.

        """
        inner_qs = AggregateTestModel.objects.order_by("-integer_field")
        qs = AggregateTestModel.objects.annotate(
            integers=Func(
                Subquery(inner_qs.values("integer_field")),
                function="ARRAY",
                output_field=ArrayField(base_field=IntegerField()),
            ),
        )
        self.assertSequenceEqual(
            qs.first().integers,
            inner_qs.values_list("integer_field", flat=True),
        )

    def test_window(self):
        self.assertCountEqual(
            AggregateTestModel.objects.annotate(
                integers=Window(
                    expression=ArrayAgg("char_field"),
                    partition_by=F("integer_field"),
                )
            ).values("integers", "char_field"),
            [
                {"integers": ["Foo1", "Foo3"], "char_field": "Foo1"},
                {"integers": ["Foo1", "Foo3"], "char_field": "Foo3"},
                {"integers": ["Foo2"], "char_field": "Foo2"},
                {"integers": ["Foo4"], "char_field": "Foo4"},
            ],
        )

    def test_values_list(self):
        tests = [ArrayAgg("integer_field"), JSONBAgg("integer_field")]
        for aggregation in tests:
            with self.subTest(aggregation=aggregation):
                self.assertCountEqual(
                    AggregateTestModel.objects.values_list(aggregation),
                    [([0],), ([1],), ([2],), ([0],)],
                )


class TestAggregateDistinct(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for aggregate testing.

        This method creates multiple instances of AggregateTestModel with duplicate and unique values in the char_field, 
        providing a foundation for testing aggregation operations.

        The created data consists of two instances with the char_field value 'Foo' and one instance with the char_field value 'Bar', 
        allowing for testing of aggregate functions across both duplicate and distinct values.

        """
        AggregateTestModel.objects.create(char_field="Foo")
        AggregateTestModel.objects.create(char_field="Foo")
        AggregateTestModel.objects.create(char_field="Bar")

    def test_string_agg_distinct_false(self):
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("char_field", delimiter=" ", distinct=False)
        )
        self.assertEqual(values["stringagg"].count("Foo"), 2)
        self.assertEqual(values["stringagg"].count("Bar"), 1)

    def test_string_agg_distinct_true(self):
        """
        Tests the aggregation of distinct string values using the StringAgg function.

        This test case verifies that when the `distinct` parameter is set to `True`, the 
        StringAgg function correctly aggregates the distinct string values from the 
        'char_field' of the AggregateTestModel objects, separated by a space delimiter.

        The test checks that each unique string value appears only once in the aggregated 
        result, ensuring that the `distinct` parameter is applied correctly.
        """
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("char_field", delimiter=" ", distinct=True)
        )
        self.assertEqual(values["stringagg"].count("Foo"), 1)
        self.assertEqual(values["stringagg"].count("Bar"), 1)

    def test_array_agg_distinct_false(self):
        """

        Tests the ArrayAgg function with the distinct parameter set to False.

        Verifies that the function aggregates all values from the 'char_field' of the 
        AggregateTestModel objects, including duplicates, into a single array. 

        The function checks if the resulting array contains the expected values in the 
        correct order, confirming the correctness of the ArrayAgg aggregation.

        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("char_field", distinct=False)
        )
        self.assertEqual(sorted(values["arrayagg"]), ["Bar", "Foo", "Foo"])

    def test_array_agg_distinct_true(self):
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("char_field", distinct=True)
        )
        self.assertEqual(sorted(values["arrayagg"]), ["Bar", "Foo"])

    def test_jsonb_agg_distinct_false(self):
        """

        Tests the JSONB Aggregation function with distinct=False.

        This test case verifies that when distinct=False, the JSONB Aggregation function 
        includes duplicate values in the aggregated result.

        The test uses a sample dataset with duplicate values and checks that the 
        resulting aggregated list contains all expected values, including duplicates.

        """
        values = AggregateTestModel.objects.aggregate(
            jsonbagg=JSONBAgg("char_field", distinct=False),
        )
        self.assertEqual(sorted(values["jsonbagg"]), ["Bar", "Foo", "Foo"])

    def test_jsonb_agg_distinct_true(self):
        values = AggregateTestModel.objects.aggregate(
            jsonbagg=JSONBAgg("char_field", distinct=True),
        )
        self.assertEqual(sorted(values["jsonbagg"]), ["Bar", "Foo"])


class TestStatisticsAggregate(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        StatTestModel.objects.create(
            int1=1,
            int2=3,
            related_field=AggregateTestModel.objects.create(integer_field=0),
        )
        StatTestModel.objects.create(
            int1=2,
            int2=2,
            related_field=AggregateTestModel.objects.create(integer_field=1),
        )
        StatTestModel.objects.create(
            int1=3,
            int2=1,
            related_field=AggregateTestModel.objects.create(integer_field=2),
        )

    # Tests for base class (StatAggregate)

    def test_missing_arguments_raises_exception(self):
        """
        Tests that creating a StatAggregate instance without providing both x and y values raises a ValueError with a message indicating that both must be provided.
        """
        with self.assertRaisesMessage(ValueError, "Both y and x must be provided."):
            StatAggregate(x=None, y=None)

    def test_correct_source_expressions(self):
        """

        Tests that the source expressions in a StatAggregate object are correctly assigned.

        Verifies that the source expressions for 'x' and 'y' values are instances of Value and F respectively, 
        ensuring that the StatAggregate object is properly constructed with the given input parameters.

        """
        func = StatAggregate(x="test", y=13)
        self.assertIsInstance(func.source_expressions[0], Value)
        self.assertIsInstance(func.source_expressions[1], F)

    def test_alias_is_required(self):
        """
        Tests that using a complex aggregate function without an alias raises a TypeError.

        This test ensures that the StatAggregate class correctly enforces the requirement
        of specifying an alias when used in a query. It verifies that a TypeError is
        raised with a descriptive message when an alias is not provided.

        The test case covers the scenario where a complex aggregate function is used
        without assigning an alias, resulting in a TypeError with the message
        'Complex aggregates require an alias'.
        """
        class SomeFunc(StatAggregate):
            function = "TEST"

        with self.assertRaisesMessage(TypeError, "Complex aggregates require an alias"):
            StatTestModel.objects.aggregate(SomeFunc(y="int2", x="int1"))

    # Test aggregates

    def test_empty_result_set(self):
        """
        Tests statistical aggregations with an empty result set.

        This test case verifies the behavior of various statistical aggregations when
        applied to an empty set of data and a non-empty set of data with no results.
        It ensures that the aggregations return the expected results, which can be None
        or a specific value depending on the aggregation, when no data is present.

        The test covers a range of statistical aggregations, including correlation,
        covariance, and regression metrics, and checks their behavior with both an
        empty result set and a non-empty set of data with no results. This helps to
        validate the correctness and robustness of the statistical aggregation
        functionality in the presence of empty or missing data. 
        """
        StatTestModel.objects.all().delete()
        tests = [
            (Corr(y="int2", x="int1"), None),
            (CovarPop(y="int2", x="int1"), None),
            (CovarPop(y="int2", x="int1", sample=True), None),
            (RegrAvgX(y="int2", x="int1"), None),
            (RegrAvgY(y="int2", x="int1"), None),
            (RegrCount(y="int2", x="int1"), 0),
            (RegrIntercept(y="int2", x="int1"), None),
            (RegrR2(y="int2", x="int1"), None),
            (RegrSlope(y="int2", x="int1"), None),
            (RegrSXX(y="int2", x="int1"), None),
            (RegrSXY(y="int2", x="int1"), None),
            (RegrSYY(y="int2", x="int1"), None),
        ]
        for aggregation, expected_result in tests:
            with self.subTest(aggregation=aggregation):
                # Empty result with non-execution optimization.
                with self.assertNumQueries(0):
                    values = StatTestModel.objects.none().aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": expected_result})
                # Empty result when query must be executed.
                with self.assertNumQueries(1):
                    values = StatTestModel.objects.aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": expected_result})

    def test_default_argument(self):
        StatTestModel.objects.all().delete()
        tests = [
            (Corr(y="int2", x="int1", default=0), 0),
            (CovarPop(y="int2", x="int1", default=0), 0),
            (CovarPop(y="int2", x="int1", sample=True, default=0), 0),
            (RegrAvgX(y="int2", x="int1", default=0), 0),
            (RegrAvgY(y="int2", x="int1", default=0), 0),
            # RegrCount() doesn't support the default argument.
            (RegrIntercept(y="int2", x="int1", default=0), 0),
            (RegrR2(y="int2", x="int1", default=0), 0),
            (RegrSlope(y="int2", x="int1", default=0), 0),
            (RegrSXX(y="int2", x="int1", default=0), 0),
            (RegrSXY(y="int2", x="int1", default=0), 0),
            (RegrSYY(y="int2", x="int1", default=0), 0),
        ]
        for aggregation, expected_result in tests:
            with self.subTest(aggregation=aggregation):
                # Empty result with non-execution optimization.
                with self.assertNumQueries(0):
                    values = StatTestModel.objects.none().aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": expected_result})
                # Empty result when query must be executed.
                with self.assertNumQueries(1):
                    values = StatTestModel.objects.aggregate(
                        aggregation=aggregation,
                    )
                    self.assertEqual(values, {"aggregation": expected_result})

    def test_corr_general(self):
        """

        Tests the calculation of correlation between two integer fields using the StatTestModel.

        Verifies that the correlation value calculated between 'int1' and 'int2' fields is -1.0,
        indicating a perfect negative linear relationship between the two variables.

        This test case ensures the correctness of the correlation calculation in the StatTestModel.

        """
        values = StatTestModel.objects.aggregate(corr=Corr(y="int2", x="int1"))
        self.assertEqual(values, {"corr": -1.0})

    def test_covar_pop_general(self):
        values = StatTestModel.objects.aggregate(covarpop=CovarPop(y="int2", x="int1"))
        self.assertEqual(values, {"covarpop": Approximate(-0.66, places=1)})

    def test_covar_pop_sample(self):
        values = StatTestModel.objects.aggregate(
            covarpop=CovarPop(y="int2", x="int1", sample=True)
        )
        self.assertEqual(values, {"covarpop": -1.0})

    def test_regr_avgx_general(self):
        """
        Tests the regression average x (RegrAvgX) calculation for a general case.

        This test case verifies that the average x value is correctly calculated
        in a regression analysis. It checks if the result of the RegrAvgX
        aggregation function matches the expected value.

        The test scenario involves aggregating data from StatTestModel objects
        using the RegrAvgX function, with 'int2' as the dependent variable (y)
        and 'int1' as the independent variable (x). The expected average x value
        is 2.0.

        The test assertion checks for an exact match between the calculated and
        expected results, ensuring the correctness of the RegrAvgX calculation
        in this general case scenario.
        """
        values = StatTestModel.objects.aggregate(regravgx=RegrAvgX(y="int2", x="int1"))
        self.assertEqual(values, {"regravgx": 2.0})

    def test_regr_avgy_general(self):
        values = StatTestModel.objects.aggregate(regravgy=RegrAvgY(y="int2", x="int1"))
        self.assertEqual(values, {"regravgy": 2.0})

    def test_regr_count_general(self):
        """

        Tests the regression count calculation for a general case.

        This test case verifies that the RegrCount aggregation function returns the correct count of regression values.
        It checks if the output of the RegrCount function matches the expected result, which is 3 in this case.

        The test uses a StatTestModel object to aggregate data and applies the RegrCount function to 'int2' and 'int1' fields.
        The result is then compared to the expected value to ensure the correctness of the regression count calculation.

        """
        values = StatTestModel.objects.aggregate(
            regrcount=RegrCount(y="int2", x="int1")
        )
        self.assertEqual(values, {"regrcount": 3})

    def test_regr_count_default(self):
        """
        Tests that the RegrCount class raises a TypeError when a default value is provided.

        Verifies that the class implementation correctly enforces the requirement that default values are not allowed, 
        ensuring strict input validation and preventing potential errors that could arise from unintended default behavior.
        """
        msg = "RegrCount does not allow default."
        with self.assertRaisesMessage(TypeError, msg):
            RegrCount(y="int2", x="int1", default=0)

    def test_regr_intercept_general(self):
        """
        Tests the RegrIntercept statistic calculation in the general case. 
        Verifies that the regression intercept is correctly calculated 
        using data from the 'int2' and 'int1' fields of StatTestModel objects, 
        and that the result matches the expected value of 4.
        """
        values = StatTestModel.objects.aggregate(
            regrintercept=RegrIntercept(y="int2", x="int1")
        )
        self.assertEqual(values, {"regrintercept": 4})

    def test_regr_r2_general(self):
        values = StatTestModel.objects.aggregate(regrr2=RegrR2(y="int2", x="int1"))
        self.assertEqual(values, {"regrr2": 1})

    def test_regr_slope_general(self):
        """

        Tests the regression slope calculation for a general case.

        This test verifies that the regression slope is correctly calculated using the 
        RegrSlope aggregation function. It checks if the calculated slope matches the 
        expected value, which is -1 in this case.

        The test uses the StatTestModel and aggregates the data using the RegrSlope 
        function, where 'int2' is the dependent variable and 'int1' is the independent 
        variable.

        Returns:
            None

        Raises:
            AssertionError: If the calculated regression slope does not match the 
            expected value.

        """
        values = StatTestModel.objects.aggregate(
            regrslope=RegrSlope(y="int2", x="int1")
        )
        self.assertEqual(values, {"regrslope": -1})

    def test_regr_sxx_general(self):
        """
        Tests the RegrSXX regression calculation for a general case.

        The function uses a statistical model to calculate the regression sum of squares (SXX) 
        and verifies that the result matches the expected value. This ensures the correctness 
        of the regression calculation in the model.
        """
        values = StatTestModel.objects.aggregate(regrsxx=RegrSXX(y="int2", x="int1"))
        self.assertEqual(values, {"regrsxx": 2.0})

    def test_regr_sxy_general(self):
        """

        Tests the regression slope calculation using the RegrSXY method.

        This test case verifies that the regression slope calculation produces the expected result.
        It aggregates data from the StatTestModel using the RegrSXY method, 
        with 'int2' as the dependent variable (y) and 'int1' as the independent variable (x).
        The expected regression slope value is -2.0.

        """
        values = StatTestModel.objects.aggregate(regrsxy=RegrSXY(y="int2", x="int1"))
        self.assertEqual(values, {"regrsxy": -2.0})

    def test_regr_syy_general(self):
        """
        Tests the general case of regression sum of squares for the y variable (SYY) calculation.

        This test verifies that the RegrSYY aggregation function correctly calculates the sum of squares 
        for the y variable in a linear regression, ensuring the result matches the expected value.

        The function uses a StatTestModel object to perform the calculation, comparing the result 
        against a predefined expected value to validate the correctness of the aggregation function.

        The test case covers a general scenario to ensure the function behaves as expected under normal conditions.
        """
        values = StatTestModel.objects.aggregate(regrsyy=RegrSYY(y="int2", x="int1"))
        self.assertEqual(values, {"regrsyy": 2.0})

    def test_regr_avgx_with_related_obj_and_number_as_argument(self):
        """
        This is more complex test to check if JOIN on field and
        number as argument works as expected.
        """
        values = StatTestModel.objects.aggregate(
            complex_regravgx=RegrAvgX(y=5, x="related_field__integer_field")
        )
        self.assertEqual(values, {"complex_regravgx": 1.0})
