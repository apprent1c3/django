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
        values = AggregateTestModel.objects.aggregate(arrayagg=ArrayAgg("char_field"))
        self.assertEqual(values, {"arrayagg": ["Foo1", "Foo2", "Foo4", "Foo3"]})

    def test_array_agg_charfield_ordering(self):
        """

        Tests the ArrayAgg aggregation function with various ordering options for a CharField.

        Verifies that the ArrayAgg function correctly aggregates and orders the results based on the provided ordering arguments.
        The test covers a range of scenarios, including ascending and descending ordering, multiple fields, 
        and using database functions such as Concat and Substr.

        :param ordering: The ordering arguments to test, including field names, F expressions, and database functions.
        :param expected_output: The expected aggregated and ordered results for each test case.

        :raises AssertionError: If the actual aggregated and ordered results do not match the expected output.

        """
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
        Tests the use of the ArrayAgg aggregation function on an IntegerField to collect values from a queryset into an array.

        The function verifies that the ArrayAgg function correctly aggregates values from the 'integer_field' of a model instance, returning them as a list. 

        It checks that the resulting array matches the expected output, ensuring the aggregation is accurate and in the correct order.
        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field")
        )
        self.assertEqual(values, {"arrayagg": [0, 1, 2, 0]})

    def test_array_agg_integerfield_ordering(self):
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field", ordering=F("integer_field").desc())
        )
        self.assertEqual(values, {"arrayagg": [2, 1, 0, 0]})

    def test_array_agg_booleanfield(self):
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
        """
        Aggregate an array of 'lang' values from 'json_field' for objects with non-null 'lang' in their 'json_field', testing the functionality of ArrayAgg with KeyTransform in the context of a JSONField. 

        This test case checks that the aggregation produces the expected output, verifying the correctness of the array aggregation operation. 

        It ensures the arrayagg function can correctly extract specific values from a JSON field, filter out objects with null values, and return the resulting list of 'lang' values.
        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg(
                KeyTransform("lang", "json_field"),
                filter=Q(json_field__lang__isnull=False),
            ),
        )
        self.assertEqual(values, {"arrayagg": ["pl", "en"]})

    def test_array_agg_jsonfield_ordering(self):
        """
        Tests the ArrayAgg aggregation function with a JSONField to ensure correct ordering.

        This test verifies that the ArrayAgg function can properly aggregate JSON field values based on a specific key,
         filters out null values, and maintains the correct order of the aggregated values.

        The test case checks if the aggregated values are returned in the expected order, 
        which in this case is ['en', 'pl'], to validate the correctness of the ArrayAgg function 
        when used with JSONField and KeyTransform ordering. 

        :raises AssertionError: if the aggregated values do not match the expected output. 
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
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg(
                "char_field",
                filter=Q(json_field__has_key="lang"),
                ordering=LPad(Cast("integer_field", CharField()), 2, Value("0")),
            )
        )
        self.assertEqual(values, {"arrayagg": ["Foo2", "Foo4"]})

    def test_array_agg_filter(self):
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field", filter=Q(integer_field__gt=0)),
        )
        self.assertEqual(values, {"arrayagg": [1, 2]})

    def test_array_agg_lookups(self):
        """

        Tests the usage of array aggregation lookup for filtering.

        This test checks that the ArrayAgg lookup is correctly applied when used with the 
        overlap lookup type, to find related objects where the aggregated array of values 
        overlaps with the specified value.

        The test creates related objects with different integer values, applies array 
        aggregation to group these values by a foreign key, filters the aggregated arrays 
        for overlap with a specific value, and then verifies that the resulting array 
        matches the expected values.

        """
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
        Tests the general functionality of the BitAnd aggregation function.

        Verifies that when applied to a set of values containing 0 and 1, the result of a bitwise AND operation is correctly calculated as 0, ensuring the function behaves as expected in a typical use case.
        """
        values = AggregateTestModel.objects.filter(integer_field__in=[0, 1]).aggregate(
            bitand=BitAnd("integer_field")
        )
        self.assertEqual(values, {"bitand": 0})

    def test_bit_and_on_only_true_values(self):
        values = AggregateTestModel.objects.filter(integer_field=1).aggregate(
            bitand=BitAnd("integer_field")
        )
        self.assertEqual(values, {"bitand": 1})

    def test_bit_and_on_only_false_values(self):
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
        Tests that the bitwise XOR aggregation function correctly handles a set of values where all values are true (i.e., equal to 1). 
        Verifies that the result of the XOR operation on these values is 1, as expected due to the properties of bitwise XOR, 
        where 1 XOR 1 equals 0, but since XOR is commutative and associative, and 1 XOR 1 XOR 1 equals 1, the result here confirms the function's correctness 
        when dealing with a specific aggregate query on the `integer_field` of `AggregateTestModel` instances.
        """
        values = AggregateTestModel.objects.filter(
            integer_field=1,
        ).aggregate(bitxor=BitXor("integer_field"))
        self.assertEqual(values, {"bitxor": 1})

    def test_bit_xor_on_only_false_values(self):
        """
        Tests the bit xor aggregation function on a set of values where all integer_field values are 0.

        This test case ensures that the bit xor operation returns the expected result when all input values are false (i.e., 0).

        The test verifies that the aggregated result is 0, as expected when performing a bit xor operation on a set of identical false values.
        """
        values = AggregateTestModel.objects.filter(
            integer_field=0,
        ).aggregate(bitxor=BitXor("integer_field"))
        self.assertEqual(values, {"bitxor": 0})

    def test_bool_and_general(self):
        """
        Tests the BoolAnd aggregation function on a queryset.

        This test case verifies that the BoolAnd function correctly aggregates boolean values 
        from a model's field and returns the expected result. The test checks if the aggregated 
        result is False, which indicates that at least one of the boolean values in the field is False.

        The test is useful for ensuring the correct behavior of the aggregation function, 
        especially when dealing with large datasets or complex queries. 

        :raises AssertionError: If the aggregated result does not match the expected value.
        """
        values = AggregateTestModel.objects.aggregate(booland=BoolAnd("boolean_field"))
        self.assertEqual(values, {"booland": False})

    def test_bool_and_q_object(self):
        values = AggregateTestModel.objects.aggregate(
            booland=BoolAnd(Q(integer_field__gt=2)),
        )
        self.assertEqual(values, {"booland": False})

    def test_bool_or_general(self):
        values = AggregateTestModel.objects.aggregate(boolor=BoolOr("boolean_field"))
        self.assertEqual(values, {"boolor": True})

    def test_bool_or_q_object(self):
        values = AggregateTestModel.objects.aggregate(
            boolor=BoolOr(Q(integer_field__gt=2)),
        )
        self.assertEqual(values, {"boolor": False})

    def test_string_agg_requires_delimiter(self):
        with self.assertRaises(TypeError):
            AggregateTestModel.objects.aggregate(stringagg=StringAgg("char_field"))

    def test_string_agg_delimiter_escaping(self):
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("char_field", delimiter="'")
        )
        self.assertEqual(values, {"stringagg": "Foo1'Foo2'Foo4'Foo3"})

    def test_string_agg_charfield(self):
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("char_field", delimiter=";")
        )
        self.assertEqual(values, {"stringagg": "Foo1;Foo2;Foo4;Foo3"})

    def test_string_agg_default_output_field(self):
        """
        Tests the default output field of the string aggregation function.

        Verifies that the StringAgg function aggregates text fields from a queryset 
        and returns the result as a single string with a specified delimiter. The 
        function checks if the aggregated string matches the expected output, 
        ensuring the correct functionality of the StringAgg function.

        Returns:
            None

        Raises:
            AssertionError: If the aggregated string does not match the expected output.
        """
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("text_field", delimiter=";"),
        )
        self.assertEqual(values, {"stringagg": "Text1;Text2;Text4;Text3"})

    def test_string_agg_charfield_ordering(self):
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
        """
        Tests the use of an alternative field in an orderable aggregate operation.

        This test case verifies that the ArrayAgg aggregation function can be used with a field other than the one being aggregated to determine the order of the resulting array. The test checks if the arrayagg function, when applied to 'integer_field', returns the correct ordered array when ordered by 'char_field' in ascending order.
        """
        values = AggregateTestModel.objects.aggregate(
            arrayagg=ArrayAgg("integer_field", ordering=F("char_field").asc())
        )
        self.assertEqual(values, {"arrayagg": [0, 1, 0, 2]})

    def test_jsonb_agg(self):
        values = AggregateTestModel.objects.aggregate(jsonbagg=JSONBAgg("char_field"))
        self.assertEqual(values, {"jsonbagg": ["Foo1", "Foo2", "Foo4", "Foo3"]})

    def test_jsonb_agg_charfield_ordering(self):
        """

        Tests the ordering functionality of the JSONBAgg aggregation function on a character field.

        This function verifies that the JSONBAgg aggregation function correctly orders the aggregated values
        according to the specified ordering, whether it be ascending, descending, or a custom ordering.

        It checks the ordering of the aggregated values for various test cases, including:
        - Ascending and descending ordering using a model field
        - Ascending and descending ordering using a string representation of a model field
        - Ordering using a database function (e.g., Concat)
        - Ordering using a database function with a descending modifier

        Each test case compares the resulting aggregated values with an expected output to ensure the correct ordering.

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
        values = AggregateTestModel.objects.aggregate(
            jsonbagg=JSONBAgg("integer_field", ordering=F("integer_field").desc()),
        )
        self.assertEqual(values, {"jsonbagg": [2, 1, 0, 0]})

    def test_jsonb_agg_booleanfield_ordering(self):
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
        values = AggregateTestModel.objects.aggregate(
            jsonbagg=JSONBAgg(
                KeyTransform("lang", "json_field"),
                filter=Q(json_field__lang__isnull=False),
                ordering=KeyTransform("lang", "json_field"),
            ),
        )
        self.assertEqual(values, {"jsonbagg": ["en", "pl"]})

    def test_jsonb_agg_key_index_transforms(self):
        """

        Tests that the JSONB aggregation of hotel reservation requirements transforms the requirements in the correct order.

        This test creates multiple hotel reservations for different rooms with varying requirements, 
        and checks that the aggregation of these requirements for each room, ordered by start date in descending order, 
        produces the expected output. It specifically verifies that the most recent requirements are returned first.

        The requirements are aggregated as a list of dictionaries, where each dictionary contains the requirements for a specific reservation.
        The test checks that the aggregated requirements are correctly filtered based on a specific condition (in this case, sea view).

        """
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
        Tests the ordering of aggregate functions ArrayAgg and StringAgg when used in a subquery.

        This function creates sample data, comprising AggregateTestModel instances and their related StatTestModel instances.
        It then verifies that the results of ArrayAgg and StringAgg aggregate functions, applied to the sample data, 
        match the expected output when ordered by a specific field in a subquery. The test covers both ascending and descending ordering scenarios.

        The function checks that the aggregate functions return the correct values for each AggregateTestModel instance,
        and that these values are ordered correctly according to the specified ordering criteria.

        Parameters:
        None

        Returns:
        None

        Raises:
        AssertionError: If the results of the aggregate functions do not match the expected output.

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
        Tests the string aggregation function with distinct values set to True.

        This test case verifies that the StringAgg function correctly aggregates
        distinct string values from a set of objects, separated by a specified delimiter.

        The test expects the aggregated string to contain each distinct value only once,
        regardless of how many times it appears in the original data. The test checks
        for the presence of specific values ('Foo' and 'Bar') in the aggregated string,
        confirming that they appear exactly once.
        """
        values = AggregateTestModel.objects.aggregate(
            stringagg=StringAgg("char_field", delimiter=" ", distinct=True)
        )
        self.assertEqual(values["stringagg"].count("Foo"), 1)
        self.assertEqual(values["stringagg"].count("Bar"), 1)

    def test_array_agg_distinct_false(self):
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
        """

        Sets up test data for the class.

        This method creates a set of StatTestModel instances with predefined values, 
        each related to an AggregateTestModel instance. The test data is used as 
        a fixture to support testing of the class's functionality.

        The created StatTestModel instances have the following attribute values:
        - int1: integer values (1, 2, 3)
        - int2: integer values (3, 2, 1)
        - related_field: related AggregateTestModel instances with integer_field values (0, 1, 2)

        """
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
        with self.assertRaisesMessage(ValueError, "Both y and x must be provided."):
            StatAggregate(x=None, y=None)

    def test_correct_source_expressions(self):
        """
        Tests that the source expressions for a StatAggregate function are correctly identified and typed.

        The function verifies that the source expressions in a StatAggregate instance contain a Value and a Field (represented by F), which are essential for specifying the data to be aggregated and analyzed.
        """
        func = StatAggregate(x="test", y=13)
        self.assertIsInstance(func.source_expressions[0], Value)
        self.assertIsInstance(func.source_expressions[1], F)

    def test_alias_is_required(self):
        """
        Tests that using a complex aggregate function without specifying an alias raises a TypeError. The test case verifies that the error message correctly indicates the requirement of an alias for complex aggregates.
        """
        class SomeFunc(StatAggregate):
            function = "TEST"

        with self.assertRaisesMessage(TypeError, "Complex aggregates require an alias"):
            StatTestModel.objects.aggregate(SomeFunc(y="int2", x="int1"))

    # Test aggregates

    def test_empty_result_set(self):
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
        values = StatTestModel.objects.aggregate(corr=Corr(y="int2", x="int1"))
        self.assertEqual(values, {"corr": -1.0})

    def test_covar_pop_general(self):
        values = StatTestModel.objects.aggregate(covarpop=CovarPop(y="int2", x="int1"))
        self.assertEqual(values, {"covarpop": Approximate(-0.66, places=1)})

    def test_covar_pop_sample(self):
        """
        Tests the calculation of population covariance for a sample dataset using the CovarPop aggregation function.

        The function aggregates data from the StatTestModel, computing the covariance between 'int1' and 'int2' with the specification that this is a sample of the population.

        It then asserts that the calculated covariance matches the expected value of -1.0.
        """
        values = StatTestModel.objects.aggregate(
            covarpop=CovarPop(y="int2", x="int1", sample=True)
        )
        self.assertEqual(values, {"covarpop": -1.0})

    def test_regr_avgx_general(self):
        values = StatTestModel.objects.aggregate(regravgx=RegrAvgX(y="int2", x="int1"))
        self.assertEqual(values, {"regravgx": 2.0})

    def test_regr_avgy_general(self):
        """
        Tests the regression average y (RegrAvgY) functionality for general cases.

        Verifies that the calculated average y value from a linear regression 
        analysis is correctly computed and matches the expected result.

        The test checks the average y value based on the 'int2' and 'int1' fields 
        in the StatTestModel, ensuring the output is as anticipated.
        """
        values = StatTestModel.objects.aggregate(regravgy=RegrAvgY(y="int2", x="int1"))
        self.assertEqual(values, {"regravgy": 2.0})

    def test_regr_count_general(self):
        """
        Tests the regression count functionality.

        Verifies that the function correctly calculates the count of regression values 
        based on the provided y and x values. The test checks that the output matches 
        the expected count of 3. This is done by aggregating data from the StatTestModel 
        using the RegrCount method and comparing the result with the known expected value.
        """
        values = StatTestModel.objects.aggregate(
            regrcount=RegrCount(y="int2", x="int1")
        )
        self.assertEqual(values, {"regrcount": 3})

    def test_regr_count_default(self):
        """
        Tests that creating a RegrCount object with a default value raises a TypeError, as default values are not permitted for this object type.
        """
        msg = "RegrCount does not allow default."
        with self.assertRaisesMessage(TypeError, msg):
            RegrCount(y="int2", x="int1", default=0)

    def test_regr_intercept_general(self):
        values = StatTestModel.objects.aggregate(
            regrintercept=RegrIntercept(y="int2", x="int1")
        )
        self.assertEqual(values, {"regrintercept": 4})

    def test_regr_r2_general(self):
        values = StatTestModel.objects.aggregate(regrr2=RegrR2(y="int2", x="int1"))
        self.assertEqual(values, {"regrr2": 1})

    def test_regr_slope_general(self):
        values = StatTestModel.objects.aggregate(
            regrslope=RegrSlope(y="int2", x="int1")
        )
        self.assertEqual(values, {"regrslope": -1})

    def test_regr_sxx_general(self):
        values = StatTestModel.objects.aggregate(regrsxx=RegrSXX(y="int2", x="int1"))
        self.assertEqual(values, {"regrsxx": 2.0})

    def test_regr_sxy_general(self):
        values = StatTestModel.objects.aggregate(regrsxy=RegrSXY(y="int2", x="int1"))
        self.assertEqual(values, {"regrsxy": -2.0})

    def test_regr_syy_general(self):
        """
        Tests the calculation of the regression sum of squared errors (SYY) for a general case.

        This test case verifies that the RegrSYY aggregation function correctly computes the sum of squared errors between the predicted and actual values, using 'int1' as the independent variable (x) and 'int2' as the dependent variable (y), and checks that the result matches the expected value of 2.0.
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
