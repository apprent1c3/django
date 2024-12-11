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
        cls.n = NestedObjects(using=DEFAULT_DB_ALIAS)
        cls.objs = [Count.objects.create(num=i) for i in range(5)]

    def _check(self, target):
        self.assertEqual(self.n.nested(lambda obj: obj.num), target)

    def _connect(self, i, j):
        self.objs[i].parent = self.objs[j]
        self.objs[i].save()

    def _collect(self, *indices):
        self.n.collect([self.objs[i] for i in indices])

    def test_unrelated_roots(self):
        """

        Tests the scenario where roots are unrelated, verifying that the collection process correctly handles 
        disconnected objects. This test case specifically checks the structure where object 2 is connected to 
        objects 0 and 1, but objects 0 and 1 are not connected to each other.

        Checks that the collected objects match the expected structure, ensuring the correctness of the 
        collection mechanism in the presence of unrelated roots.

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
        """
        ..: Tests that a non-added parent node is correctly handled.

            This test case verifies the behavior when a parent node is not explicitly added to the collection. 
            It connects two nodes, collects data from the root node, and then checks the resulting collection to ensure it contains the expected node.
        """
        self._connect(0, 1)
        self._collect(0)
        self._check([0])

    def test_cyclic(self):
        self._connect(0, 2)
        self._connect(1, 0)
        self._connect(2, 1)
        self._collect(0)
        self._check([0, [1, [2]]])

    def test_queries(self):
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
        Automatically formats numeric field values for display.

        Tests that the display value of a given field is formatted correctly based on its type, which can be FloatField, DecimalField, or IntegerField. Verifies that both floating point numbers and integers are displayed as strings in their original numeric format without any additional formatting or rounding. The display value is also checked for Decimal type to ensure accurate and precise representation.
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
        Tests the display of list values.

        This test checks that a list of values is correctly formatted into a string.
        It verifies that the :func:`display_for_value` function can handle lists of
        different lengths and containing various data types, and that it returns a
        comma-separated string representation of the list.

        The test uses the :attr:`empty_value` attribute to handle empty or missing values,
        ensuring that the function behaves correctly in these cases.

        The expected output is a string where each element of the input list is separated
        by a comma, without any additional formatting or wrapping.”
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

        Displays the value as a boolean with optional formatting as an HTML image.

        If the boolean parameter is True, it returns an HTML image tag referencing either
        icon-yes.svg or icon-no.svg, depending on the input value.
        If the boolean parameter is False, it returns the string representation of the input value.
        This function is useful for customizing the display of boolean values in a list view.

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
        Return the label of a given field in a model, considering form fields if provided.

        This function retrieves the label of a specified field, first checking if it's 
        available in the provided form. If the field is not found in the form, the model 
        is checked. If the field still cannot be found, an AttributeError is raised.

        :param field_name: The name of the field for which to retrieve the label.
        :param model: The model in which to look up the field.
        :param form: An optional form to check for the field before falling back to the model.
        :raises AttributeError: If the specified field cannot be found in either the form or the model.
        :return: The label of the field.

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
        """

        Test that help text is correctly retrieved for specific fields.

        This test case checks the functionality of the help_text_for_field function by 
        verifying its output against a set of predefined field names and their 
        corresponding help texts. It covers both cases where a field has a specific help 
        text and where it does not.

        """
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
        """

        Build a Django ORM Q object from a dictionary of lookup parameters.

        This function takes a dictionary where keys are field lookups and values are lists of
        values to filter by. It constructs a Q object that represents the filter conditions
        combined using logical AND or OR operators, depending on the lookup type.

        The supported lookup types include:

        * Exact and case-insensitive lookups (e.g., 'field__iexact')
        * \"in\" lookups for filtering by a list of values (e.g., 'field__in')
        * Primary key lookups (e.g., 'field__pk') for filtering by specific IDs

        The function returns a Q object that can be used directly in Django ORM queries.


        """
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
