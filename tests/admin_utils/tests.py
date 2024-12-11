from datetime import datetime
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.utils import (
    NestedObjects,
    build_q_object_from_lookup_parameters,
    display_for_field,
    display_for_value,
    flatten,
    flatten_fieldsets,
    help_text_for_field,
    label_for_field,
    lookup_field,
    quote,
)
from django.core.validators import EMPTY_VALUES
from django.db import DEFAULT_DB_ALIAS, models
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils.formats import localize
from django.utils.safestring import mark_safe

from .models import Article, Car, Count, Event, EventGuide, Location, Site, Vehicle


class NestedObjectsTests(TestCase):
    """
    Tests for ``NestedObject`` utility collection.
    """

    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for a test class.

        This method is called once before running any tests in the class. It creates a set of 
        test objects to be used throughout the test suite. Specifically, it instantiates a 
        NestedObjects object and creates a list of five Count objects, each with a unique 
        identifier.

        """
        cls.n = NestedObjects(using=DEFAULT_DB_ALIAS)
        cls.objs = [Count.objects.create(num=i) for i in range(5)]

    def _check(self, target):
        self.assertEqual(self.n.nested(lambda obj: obj.num), target)

    def _connect(self, i, j):
        """
        Establishes a parent-child relationship between two objects.

        Sets the parent of the object at index `i` to the object at index `j` and saves the updated object.

        :param int i: The index of the child object.
        :param int j: The index of the parent object.

        """
        self.objs[i].parent = self.objs[j]
        self.objs[i].save()

    def _collect(self, *indices):
        self.n.collect([self.objs[i] for i in indices])

    def test_unrelated_roots(self):
        """

        Tests the scenario where two unrelated roots are collected and their target is checked.

        This test case verifies that when two roots are not related to each other, 
        the target of the collected roots is correctly identified.

        """
        self._connect(2, 1)
        self._collect(0)
        self._collect(1)
        self._check([0, 1, [2]])

    def test_siblings(self):
        self._connect(1, 0)
        self._connect(2, 0)
        self._collect(0)
        self._check([0, [1, 2]])

    def test_non_added_parent(self):
        self._connect(0, 1)
        self._collect(0)
        self._check([0])

    def test_cyclic(self):
        """
        Tests the functionality of handling cyclic connections in the system.

        This test case creates a cycle of connections between three entities and then
        collects data from one of them. It verifies that the collection process 
        correctly handles the cyclic nature of the connections, avoiding any potential 
        infinite loops or data corruption.

        The expected result is a hierarchical structure where the initial entity is at 
        the top, followed by its directly connected entities, and so on. The test 
        confirms that this structure is correctly collected and returned, providing a 
        basis for further validation of cyclic connection handling in the system.
        """
        self._connect(0, 2)
        self._connect(1, 0)
        self._connect(2, 1)
        self._collect(0)
        self._check([0, [1, [2]]])

    def test_queries(self):
        """

        Tests the execution of queries by establishing connections and verifying the number of queries collected.

        This method sets up two connections and then asserts that the total number of queries matches the expected count, 
        ensuring that queries are executed and collected as expected.

        """
        self._connect(1, 0)
        self._connect(2, 0)
        # 1 query to fetch all children of 0 (1 and 2)
        # 1 query to fetch all children of 1 and 2 (none)
        # Should not require additional queries to populate the nested graph.
        self.assertNumQueries(2, self._collect, 0)

    def test_on_delete_do_nothing(self):
        """
        The nested collector doesn't query for DO_NOTHING objects.
        """
        n = NestedObjects(using=DEFAULT_DB_ALIAS)
        objs = [Event.objects.create()]
        EventGuide.objects.create(event=objs[0])
        with self.assertNumQueries(2):
            # One for Location, one for Guest, and no query for EventGuide
            n.collect(objs)

    def test_relation_on_abstract(self):
        """
        NestedObjects.collect() doesn't trip (AttributeError) on the special
        notation for relations on abstract models (related_name that contains
        %(app_label)s and/or %(class)s) (#21846).
        """
        n = NestedObjects(using=DEFAULT_DB_ALIAS)
        Car.objects.create()
        n.collect([Vehicle.objects.first()])


class UtilsTests(SimpleTestCase):
    empty_value = "-empty-"

    def test_values_from_lookup_field(self):
        """
        Regression test for #12654: lookup_field
        """
        SITE_NAME = "example.com"
        TITLE_TEXT = "Some title"
        CREATED_DATE = datetime.min
        ADMIN_METHOD = "admin method"
        SIMPLE_FUNCTION = "function"
        INSTANCE_ATTRIBUTE = "attr"

        class MockModelAdmin:
            def get_admin_value(self, obj):
                return ADMIN_METHOD

        def simple_function(obj):
            return SIMPLE_FUNCTION

        site_obj = Site(domain=SITE_NAME)
        article = Article(
            site=site_obj,
            title=TITLE_TEXT,
            created=CREATED_DATE,
        )
        article.non_field = INSTANCE_ATTRIBUTE

        verifications = (
            ("site", SITE_NAME),
            ("created", localize(CREATED_DATE)),
            ("title", TITLE_TEXT),
            ("get_admin_value", ADMIN_METHOD),
            (simple_function, SIMPLE_FUNCTION),
            ("test_from_model", article.test_from_model()),
            ("non_field", INSTANCE_ATTRIBUTE),
            ("site__domain", SITE_NAME),
        )

        mock_admin = MockModelAdmin()
        for name, value in verifications:
            field, attr, resolved_value = lookup_field(name, article, mock_admin)

            if field is not None:
                resolved_value = display_for_field(
                    resolved_value, field, self.empty_value
                )

            self.assertEqual(value, resolved_value)

    def test_empty_value_display_for_field(self):
        """
        Checks the display value for various model fields when they contain an empty value, verifying that the display value matches the expected empty value representation. 

        This test iterates over multiple field types, including character, date, decimal, float, JSON, and time fields, and checks each of their respective empty values. It ensures consistency in how empty values are displayed across different field types, providing a standardized representation for empty data.
        """
        tests = [
            models.CharField(),
            models.DateField(),
            models.DecimalField(),
            models.FloatField(),
            models.JSONField(),
            models.TimeField(),
        ]
        for model_field in tests:
            for value in model_field.empty_values:
                with self.subTest(model_field=model_field, empty_value=value):
                    display_value = display_for_field(
                        value, model_field, self.empty_value
                    )
                    self.assertEqual(display_value, self.empty_value)

    def test_empty_value_display_choices(self):
        """
        Tests that an empty value is displayed correctly for a CharField with choices.

        This test verifies that when a field's value is empty, it is displayed as the
        human-readable name specified in the field's choices, rather than as an empty
        string. This ensures that users are presented with a meaningful display value
        even when the underlying value is None or empty.
        """
        model_field = models.CharField(choices=((None, "test_none"),))
        display_value = display_for_field(None, model_field, self.empty_value)
        self.assertEqual(display_value, "test_none")

    def test_empty_value_display_booleanfield(self):
        model_field = models.BooleanField(null=True)
        display_value = display_for_field(None, model_field, self.empty_value)
        expected = (
            f'<img src="{settings.STATIC_URL}admin/img/icon-unknown.svg" alt="None" />'
        )
        self.assertHTMLEqual(display_value, expected)

    def test_json_display_for_field(self):
        """

        Tests the display_for_field function with various JSON-compatible data types.

        This function ensures that the display_for_field function correctly formats different types of data, including nested dictionaries, lists, strings, and tuples, into a JSON-compatible string representation. It also verifies that non-ASCII characters are properly handled.

        The test cases cover a range of scenarios, including:

        * Nested dictionaries
        * Lists
        * Strings
        * Tuples with non-string keys
        * Non-ASCII characters

        Each test case compares the output of the display_for_field function with the expected JSON-compatible string representation.

        """
        tests = [
            ({"a": {"b": "c"}}, '{"a": {"b": "c"}}'),
            (["a", "b"], '["a", "b"]'),
            ("a", '"a"'),
            ({"a": "你好 世界"}, '{"a": "你好 世界"}'),
            ({("a", "b"): "c"}, "{('a', 'b'): 'c'}"),  # Invalid JSON.
        ]
        for value, display_value in tests:
            with self.subTest(value=value):
                self.assertEqual(
                    display_for_field(value, models.JSONField(), self.empty_value),
                    display_value,
                )

    def test_number_formats_display_for_field(self):
        """
        Tests the display formatting of numeric fields.

        Verifies that different numeric types (Float, Decimal, Integer) are correctly displayed as strings.
        Ensures that the displayed values match the expected numeric representation without any additional formatting.

        The test covers various numeric types to confirm that the display function behaves consistently across different field types.

        """
        display_value = display_for_field(
            12345.6789, models.FloatField(), self.empty_value
        )
        self.assertEqual(display_value, "12345.6789")

        display_value = display_for_field(
            Decimal("12345.6789"), models.DecimalField(), self.empty_value
        )
        self.assertEqual(display_value, "12345.6789")

        display_value = display_for_field(
            12345, models.IntegerField(), self.empty_value
        )
        self.assertEqual(display_value, "12345")

    @override_settings(USE_THOUSAND_SEPARATOR=True)
    def test_number_formats_with_thousand_separator_display_for_field(self):
        """
        [Test number formats with thousand separator display for field]

        Test the display of numbers with thousand separators when using the display_for_field function.

        This test checks that numbers with decimal places and integers are correctly formatted 
        with thousand separators when displaying values for FloatField and IntegerField types.
        """
        display_value = display_for_field(
            12345.6789, models.FloatField(), self.empty_value
        )
        self.assertEqual(display_value, "12,345.6789")

        display_value = display_for_field(
            Decimal("12345.6789"), models.DecimalField(), self.empty_value
        )
        self.assertEqual(display_value, "12,345.6789")

        display_value = display_for_field(
            12345, models.IntegerField(), self.empty_value
        )
        self.assertEqual(display_value, "12,345")

    def test_list_display_for_value(self):
        """

        Tests the display of a list using the display_for_value function.

        This test case verifies that the function correctly converts a list of values into a comma-separated string.
        It checks the display of lists containing both numeric and string values, ensuring that all elements are displayed as expected.
        The test covers two different scenarios: a list with only numeric values and a list with a mix of numeric and string values.
        The expected output is a string with all list elements joined by commas, without any additional formatting or escaping.

        """
        display_value = display_for_value([1, 2, 3], self.empty_value)
        self.assertEqual(display_value, "1, 2, 3")

        display_value = display_for_value(
            [1, 2, "buckle", "my", "shoe"], self.empty_value
        )
        self.assertEqual(display_value, "1, 2, buckle, my, shoe")

    @override_settings(USE_THOUSAND_SEPARATOR=True)
    def test_list_display_for_value_boolean(self):
        """
        Displays a given boolean value in a human-readable format, optionally with an icon.

        :param bool value: The boolean value to display.
        :param str field_name: The name of the field (not used in this function).
        :param bool boolean: If True, the function will return an HTML string containing an icon representing the boolean value.
        :returns: A string containing the displayed value. If boolean=True, the string will be an HTML image tag with a src attribute pointing to an icon representing the value. If boolean=False, the string will be a simple string representation of the value ('True' or 'False').
        """
        self.assertEqual(
            display_for_value(True, "", boolean=True),
            '<img src="/static/admin/img/icon-yes.svg" alt="True">',
        )
        self.assertEqual(
            display_for_value(False, "", boolean=True),
            '<img src="/static/admin/img/icon-no.svg" alt="False">',
        )
        self.assertEqual(display_for_value(True, ""), "True")
        self.assertEqual(display_for_value(False, ""), "False")

    def test_list_display_for_value_empty(self):
        """

        Tests the display of empty values in a list.

        Verifies that each value considered empty (e.g. None, '', etc.) is displayed as 
        specified by the empty value setting. This ensures consistency in how empty 
        values are represented in the list.

        Checks the following:
        - Each empty value is handled correctly
        - The display value matches the expected empty value representation

        The test covers various types of empty values to ensure the display functionality
        behaves as expected in all cases. 

        """
        for value in EMPTY_VALUES:
            with self.subTest(empty_value=value):
                display_value = display_for_value(value, self.empty_value)
                self.assertEqual(display_value, self.empty_value)

    def test_label_for_field(self):
        """
        Tests for label_for_field
        """
        self.assertEqual(label_for_field("title", Article), "title")
        self.assertEqual(label_for_field("hist", Article), "History")
        self.assertEqual(
            label_for_field("hist", Article, return_attr=True), ("History", None)
        )

        self.assertEqual(label_for_field("__str__", Article), "article")

        with self.assertRaisesMessage(
            AttributeError, "Unable to lookup 'unknown' on Article"
        ):
            label_for_field("unknown", Article)

        def test_callable(obj):
            return "nothing"

        self.assertEqual(label_for_field(test_callable, Article), "Test callable")
        self.assertEqual(
            label_for_field(test_callable, Article, return_attr=True),
            ("Test callable", test_callable),
        )

        self.assertEqual(label_for_field("test_from_model", Article), "Test from model")
        self.assertEqual(
            label_for_field("test_from_model", Article, return_attr=True),
            ("Test from model", Article.test_from_model),
        )
        self.assertEqual(
            label_for_field("test_from_model_with_override", Article),
            "not What you Expect",
        )

        self.assertEqual(label_for_field(lambda x: "nothing", Article), "--")
        self.assertEqual(label_for_field("site_id", Article), "Site id")
        # The correct name and attr are returned when `__` is in the field name.
        self.assertEqual(label_for_field("site__domain", Article), "Site  domain")
        self.assertEqual(
            label_for_field("site__domain", Article, return_attr=True),
            ("Site  domain", Site._meta.get_field("domain")),
        )

    def test_label_for_field_failed_lookup(self):
        msg = "Unable to lookup 'site__unknown' on Article"
        with self.assertRaisesMessage(AttributeError, msg):
            label_for_field("site__unknown", Article)

        class MockModelAdmin:
            @admin.display(description="not Really the Model")
            def test_from_model(self, obj):
                return "nothing"

        self.assertEqual(
            label_for_field("test_from_model", Article, model_admin=MockModelAdmin),
            "not Really the Model",
        )
        self.assertEqual(
            label_for_field(
                "test_from_model", Article, model_admin=MockModelAdmin, return_attr=True
            ),
            ("not Really the Model", MockModelAdmin.test_from_model),
        )

    def test_label_for_field_form_argument(self):
        """

        Returns the human-readable label for a given form field.

        This function resolves the label for a field by checking the form instance first, 
        then falls back to checking the model's field. If neither the form nor the model 
        has a field with the given name, it raises an AttributeError.

        The label is used to display the field's name in a user-friendly format, making 
        it easier to understand and interact with the form.

        Parameters:
            name (str): The name of the field to retrieve the label for.
            model (Model): The model instance that the field belongs to.
            form (Form): The form instance that the field belongs to.

        Returns:
            str: The human-readable label for the given field.

        Raises:
            AttributeError: If the field does not exist on either the model or the form.

        """
        class ArticleForm(forms.ModelForm):
            extra_form_field = forms.BooleanField()

            class Meta:
                fields = "__all__"
                model = Article

        self.assertEqual(
            label_for_field("extra_form_field", Article, form=ArticleForm()),
            "Extra form field",
        )
        msg = "Unable to lookup 'nonexistent' on Article or ArticleForm"
        with self.assertRaisesMessage(AttributeError, msg):
            label_for_field("nonexistent", Article, form=ArticleForm())

    def test_label_for_property(self):
        """
        Return a human-readable label for a given model field.

        The label is determined by the 'description' parameter of the @admin.display
        decorator if the field is a property, otherwise it defaults to the field's name.

        This function is useful for providing user-friendly labels in the admin interface.
        It allows for fields to have descriptive labels that are different from their
        technical names. The label can be then used for display purposes, such as column
        headers in a table or field labels in a form.

        :param str field_name: The name of the model field.
        :param Model model: The model that the field belongs to.
        :param ModelAdmin model_admin: The model admin instance.
        :return: The human-readable label for the given field.

        """
        class MockModelAdmin:
            @property
            @admin.display(description="property short description")
            def test_from_property(self):
                return "this if from property"

        self.assertEqual(
            label_for_field("test_from_property", Article, model_admin=MockModelAdmin),
            "property short description",
        )

    def test_help_text_for_field(self):
        tests = [
            ("article", ""),
            ("unknown", ""),
            ("hist", "History help text"),
        ]
        for name, help_text in tests:
            with self.subTest(name=name):
                self.assertEqual(help_text_for_field(name, Article), help_text)

    def test_related_name(self):
        """
        Regression test for #13963
        """
        self.assertEqual(
            label_for_field("location", Event, return_attr=True),
            ("location", None),
        )
        self.assertEqual(
            label_for_field("event", Location, return_attr=True),
            ("awesome event", None),
        )
        self.assertEqual(
            label_for_field("guest", Event, return_attr=True),
            ("awesome guest", None),
        )

    def test_safestring_in_field_label(self):
        # safestring should not be escaped
        class MyForm(forms.Form):
            text = forms.CharField(label=mark_safe("<i>text</i>"))
            cb = forms.BooleanField(label=mark_safe("<i>cb</i>"))

        form = MyForm()
        self.assertHTMLEqual(
            helpers.AdminField(form, "text", is_first=False).label_tag(),
            '<label for="id_text" class="required inline"><i>text</i>:</label>',
        )
        self.assertHTMLEqual(
            helpers.AdminField(form, "cb", is_first=False).label_tag(),
            '<label for="id_cb" class="vCheckboxLabel required inline">'
            "<i>cb</i></label>",
        )

        # normal strings needs to be escaped
        class MyForm(forms.Form):
            text = forms.CharField(label="&text")
            cb = forms.BooleanField(label="&cb")

        form = MyForm()
        self.assertHTMLEqual(
            helpers.AdminField(form, "text", is_first=False).label_tag(),
            '<label for="id_text" class="required inline">&amp;text:</label>',
        )
        self.assertHTMLEqual(
            helpers.AdminField(form, "cb", is_first=False).label_tag(),
            '<label for="id_cb" class="vCheckboxLabel required inline">&amp;cb</label>',
        )

    def test_flatten(self):
        """

        Tests the functionality of the flatten function.

        The flatten function takes a nested tuple or list structure as input and returns a flattened list.
        This test case covers various scenarios, including empty inputs, nested tuples, and lists of varying depths.
        It verifies that the function correctly returns a one-dimensional list containing all elements from the original input structure.

        """
        flat_all = ["url", "title", "content", "sites"]
        inputs = (
            ((), []),
            (("url", "title", ("content", "sites")), flat_all),
            (("url", "title", "content", "sites"), flat_all),
            ((("url", "title"), ("content", "sites")), flat_all),
        )
        for orig, expected in inputs:
            self.assertEqual(flatten(orig), expected)

    def test_flatten_fieldsets(self):
        """
        Regression test for #18051
        """
        fieldsets = ((None, {"fields": ("url", "title", ("content", "sites"))}),)
        self.assertEqual(
            flatten_fieldsets(fieldsets), ["url", "title", "content", "sites"]
        )

        fieldsets = ((None, {"fields": ("url", "title", ["content", "sites"])}),)
        self.assertEqual(
            flatten_fieldsets(fieldsets), ["url", "title", "content", "sites"]
        )

    def test_quote(self):
        self.assertEqual(quote("something\nor\nother"), "something_0Aor_0Aother")

    def test_build_q_object_from_lookup_parameters(self):
        parameters = {
            "title__in": [["Article 1", "Article 2"]],
            "hist__iexact": ["history"],
            "site__pk": [1, 2],
        }
        q_obj = build_q_object_from_lookup_parameters(parameters)
        self.assertEqual(
            q_obj,
            models.Q(title__in=["Article 1", "Article 2"])
            & models.Q(hist__iexact="history")
            & (models.Q(site__pk=1) | models.Q(site__pk=2)),
        )
