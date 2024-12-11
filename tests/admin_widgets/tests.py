import gettext
import os
import re
import zoneinfo
from datetime import datetime, timedelta
from importlib import import_module
from unittest import skipUnless

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import widgets
from django.contrib.admin.tests import AdminSeleniumTestCase
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import (
    CharField,
    DateField,
    DateTimeField,
    ForeignKey,
    ManyToManyField,
    UUIDField,
)
from django.test import SimpleTestCase, TestCase, ignore_warnings, override_settings
from django.test.utils import requires_tz_support
from django.urls import reverse
from django.utils import translation
from django.utils.deprecation import RemovedInDjango60Warning

from .models import (
    Advisor,
    Album,
    Band,
    Bee,
    Car,
    Company,
    Event,
    Honeycomb,
    Image,
    Individual,
    Inventory,
    Member,
    MyFileField,
    Profile,
    ReleaseEvent,
    School,
    Student,
    UnsafeLimitChoicesTo,
    VideoStream,
)
from .widgetadmin import site as widget_admin_site


class TestDataMixin:
    @classmethod
    def setUpTestData(cls):
        """

        Set up initial test data for the application.

        This method creates a superuser and a regular user with predefined credentials,
        as well as two cars associated with these users. The data is intended to be used
        as a starting point for tests, providing a consistent and predictable environment.

        The created data includes:

        * A superuser with the username 'super' and password 'secret'
        * A regular user with the username 'testser' and password 'secret'
        * Two cars: one owned by the superuser (Volkswagen Passat) and one owned by the regular user (BMW M3)

        This method is a class method, meaning it can be called on the class itself rather
        than on an instance of the class. It is intended to be used in the context of
        setting up test data for the application.

        """
        cls.superuser = User.objects.create_superuser(
            username="super", password="secret", email=None
        )
        cls.u2 = User.objects.create_user(username="testser", password="secret")
        Car.objects.create(owner=cls.superuser, make="Volkswagen", model="Passat")
        Car.objects.create(owner=cls.u2, make="BMW", model="M3")


class AdminFormfieldForDBFieldTests(SimpleTestCase):
    """
    Tests for correct behavior of ModelAdmin.formfield_for_dbfield
    """

    def assertFormfield(self, model, fieldname, widgetclass, **admin_overrides):
        """
        Helper to call formfield_for_dbfield for a given model and field name
        and verify that the returned formfield is appropriate.
        """

        # Override any settings on the model admin
        class MyModelAdmin(admin.ModelAdmin):
            pass

        for k in admin_overrides:
            setattr(MyModelAdmin, k, admin_overrides[k])

        # Construct the admin, and ask it for a formfield
        ma = MyModelAdmin(model, admin.site)
        ff = ma.formfield_for_dbfield(model._meta.get_field(fieldname), request=None)

        # "unwrap" the widget wrapper, if needed
        if isinstance(ff.widget, widgets.RelatedFieldWidgetWrapper):
            widget = ff.widget.widget
        else:
            widget = ff.widget

        self.assertIsInstance(widget, widgetclass)

        # Return the formfield so that other tests can continue
        return ff

    def test_DateField(self):
        self.assertFormfield(Event, "start_date", widgets.AdminDateWidget)

    def test_DateTimeField(self):
        self.assertFormfield(Member, "birthdate", widgets.AdminSplitDateTime)

    def test_TimeField(self):
        self.assertFormfield(Event, "start_time", widgets.AdminTimeWidget)

    def test_TextField(self):
        self.assertFormfield(Event, "description", widgets.AdminTextareaWidget)

    @ignore_warnings(category=RemovedInDjango60Warning)
    def test_URLField(self):
        self.assertFormfield(Event, "link", widgets.AdminURLFieldWidget)

    def test_IntegerField(self):
        self.assertFormfield(Event, "min_age", widgets.AdminIntegerFieldWidget)

    def test_CharField(self):
        self.assertFormfield(Member, "name", widgets.AdminTextInputWidget)

    def test_EmailField(self):
        self.assertFormfield(Member, "email", widgets.AdminEmailInputWidget)

    def test_FileField(self):
        self.assertFormfield(Album, "cover_art", widgets.AdminFileWidget)

    def test_ForeignKey(self):
        self.assertFormfield(Event, "main_band", forms.Select)

    def test_raw_id_ForeignKey(self):
        self.assertFormfield(
            Event,
            "main_band",
            widgets.ForeignKeyRawIdWidget,
            raw_id_fields=["main_band"],
        )

    def test_radio_fields_ForeignKey(self):
        ff = self.assertFormfield(
            Event,
            "main_band",
            widgets.AdminRadioSelect,
            radio_fields={"main_band": admin.VERTICAL},
        )
        self.assertIsNone(ff.empty_label)

    def test_radio_fields_foreignkey_formfield_overrides_empty_label(self):
        class MyModelAdmin(admin.ModelAdmin):
            radio_fields = {"parent": admin.VERTICAL}
            formfield_overrides = {
                ForeignKey: {"empty_label": "Custom empty label"},
            }

        ma = MyModelAdmin(Inventory, admin.site)
        ff = ma.formfield_for_dbfield(Inventory._meta.get_field("parent"), request=None)
        self.assertEqual(ff.empty_label, "Custom empty label")

    def test_many_to_many(self):
        self.assertFormfield(Band, "members", forms.SelectMultiple)

    def test_raw_id_many_to_many(self):
        self.assertFormfield(
            Band, "members", widgets.ManyToManyRawIdWidget, raw_id_fields=["members"]
        )

    def test_filtered_many_to_many(self):
        self.assertFormfield(
            Band, "members", widgets.FilteredSelectMultiple, filter_vertical=["members"]
        )

    def test_formfield_overrides(self):
        self.assertFormfield(
            Event,
            "start_date",
            forms.TextInput,
            formfield_overrides={DateField: {"widget": forms.TextInput}},
        )

    def test_formfield_overrides_widget_instances(self):
        """
        Widget instances in formfield_overrides are not shared between
        different fields. (#19423)
        """

        class BandAdmin(admin.ModelAdmin):
            formfield_overrides = {
                CharField: {"widget": forms.TextInput(attrs={"size": "10"})}
            }

        ma = BandAdmin(Band, admin.site)
        f1 = ma.formfield_for_dbfield(Band._meta.get_field("name"), request=None)
        f2 = ma.formfield_for_dbfield(Band._meta.get_field("style"), request=None)
        self.assertNotEqual(f1.widget, f2.widget)
        self.assertEqual(f1.widget.attrs["maxlength"], "100")
        self.assertEqual(f2.widget.attrs["maxlength"], "20")
        self.assertEqual(f2.widget.attrs["size"], "10")

    def test_formfield_overrides_m2m_filter_widget(self):
        """
        The autocomplete_fields, raw_id_fields, filter_vertical, and
        filter_horizontal widgets for ManyToManyFields may be overridden by
        specifying a widget in formfield_overrides.
        """

        class BandAdmin(admin.ModelAdmin):
            filter_vertical = ["members"]
            formfield_overrides = {
                ManyToManyField: {"widget": forms.CheckboxSelectMultiple},
            }

        ma = BandAdmin(Band, admin.site)
        field = ma.formfield_for_dbfield(Band._meta.get_field("members"), request=None)
        self.assertIsInstance(field.widget.widget, forms.CheckboxSelectMultiple)

    def test_formfield_overrides_for_datetime_field(self):
        """
        Overriding the widget for DateTimeField doesn't overrides the default
        form_class for that field (#26449).
        """

        class MemberAdmin(admin.ModelAdmin):
            formfield_overrides = {
                DateTimeField: {"widget": widgets.AdminSplitDateTime}
            }

        ma = MemberAdmin(Member, admin.site)
        f1 = ma.formfield_for_dbfield(Member._meta.get_field("birthdate"), request=None)
        self.assertIsInstance(f1.widget, widgets.AdminSplitDateTime)
        self.assertIsInstance(f1, forms.SplitDateTimeField)

    def test_formfield_overrides_for_custom_field(self):
        """
        formfield_overrides works for a custom field class.
        """

        class AlbumAdmin(admin.ModelAdmin):
            formfield_overrides = {MyFileField: {"widget": forms.TextInput()}}

        ma = AlbumAdmin(Member, admin.site)
        f1 = ma.formfield_for_dbfield(
            Album._meta.get_field("backside_art"), request=None
        )
        self.assertIsInstance(f1.widget, forms.TextInput)

    def test_field_with_choices(self):
        self.assertFormfield(Member, "gender", forms.Select)

    def test_choices_with_radio_fields(self):
        self.assertFormfield(
            Member,
            "gender",
            widgets.AdminRadioSelect,
            radio_fields={"gender": admin.VERTICAL},
        )

    def test_inheritance(self):
        self.assertFormfield(Album, "backside_art", widgets.AdminFileWidget)

    def test_m2m_widgets(self):
        """m2m fields help text as it applies to admin app (#9321)."""

        class AdvisorAdmin(admin.ModelAdmin):
            filter_vertical = ["companies"]

        self.assertFormfield(
            Advisor,
            "companies",
            widgets.FilteredSelectMultiple,
            filter_vertical=["companies"],
        )
        ma = AdvisorAdmin(Advisor, admin.site)
        f = ma.formfield_for_dbfield(Advisor._meta.get_field("companies"), request=None)
        self.assertEqual(
            f.help_text,
            "Hold down “Control”, or “Command” on a Mac, to select more than one.",
        )

    def test_m2m_widgets_no_allow_multiple_selected(self):
        """

        Tests the behavior of Many-to-Many fields in admin forms when the 
        `allow_multiple_selected` attribute is set to False.

        Verifies that the form field for a Many-to-Many relationship is rendered 
        as a FilteredSelectMultiple widget when the `filter_vertical` attribute 
        is specified in the ModelAdmin class, and that the form field's help text 
        is empty.

        """
        class NoAllowMultipleSelectedWidget(forms.SelectMultiple):
            allow_multiple_selected = False

        class AdvisorAdmin(admin.ModelAdmin):
            filter_vertical = ["companies"]
            formfield_overrides = {
                ManyToManyField: {"widget": NoAllowMultipleSelectedWidget},
            }

        self.assertFormfield(
            Advisor,
            "companies",
            widgets.FilteredSelectMultiple,
            filter_vertical=["companies"],
        )
        ma = AdvisorAdmin(Advisor, admin.site)
        f = ma.formfield_for_dbfield(Advisor._meta.get_field("companies"), request=None)
        self.assertEqual(f.help_text, "")


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class AdminFormfieldForDBFieldWithRequestTests(TestDataMixin, TestCase):
    def test_filter_choices_by_request_user(self):
        """
        Ensure the user can only see their own cars in the foreign key dropdown.
        """
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:admin_widgets_cartire_add"))
        self.assertNotContains(response, "BMW M3")
        self.assertContains(response, "Volkswagen Passat")


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class AdminForeignKeyWidgetChangeList(TestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.superuser)

    def test_changelist_ForeignKey(self):
        """
        Tests the changelist view for ForeignKey fields in the admin interface.

        Verifies that the changelist page for the Car model contains a link to add a new User, 
        indicating that the ForeignKey relationship is correctly rendered in the admin interface.

        Checks for the presence of a specific URL pattern in the response content, 
        confirming that the link to add a new User is correctly included in the changelist page.
        """
        response = self.client.get(reverse("admin:admin_widgets_car_changelist"))
        self.assertContains(response, "/auth/user/add/")


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class AdminForeignKeyRawIdWidget(TestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.superuser)

    @ignore_warnings(category=RemovedInDjango60Warning)
    def test_nonexistent_target_id(self):
        """

        Tests the behavior of the admin widgets event add view when a nonexistent target ID is provided.

        Verifies that when a deleted object's primary key is passed as the main band ID,
        the view returns an error message indicating that the choice is not valid.

        """
        band = Band.objects.create(name="Bogey Blues")
        pk = band.pk
        band.delete()
        post_data = {
            "main_band": str(pk),
        }
        # Try posting with a nonexistent pk in a raw id field: this
        # should result in an error message, not a server exception.
        response = self.client.post(reverse("admin:admin_widgets_event_add"), post_data)
        self.assertContains(
            response,
            "Select a valid choice. That choice is not one of the available choices.",
        )

    @ignore_warnings(category=RemovedInDjango60Warning)
    def test_invalid_target_id(self):
        """

        Tests the admin widget event add view with invalid target IDs.

        Checks that the view correctly handles and displays an error message when an invalid
        target ID is provided. This includes testing with a variety of invalid inputs, such as
        non-integer strings and negative integers.

        """
        for test_str in ("Iñtërnâtiônàlizætiøn", "1234'", -1234):
            # This should result in an error message, not a server exception.
            response = self.client.post(
                reverse("admin:admin_widgets_event_add"), {"main_band": test_str}
            )

            self.assertContains(
                response,
                "Select a valid choice. That choice is not one of the available "
                "choices.",
            )

    def test_url_params_from_lookup_dict_any_iterable(self):
        """

        Tests the function that converts a lookup dictionary into URL parameters, specifically handling the case where the value is an iterable.

        This function ensures that the output of the url_params_from_lookup_dict function is consistent, regardless of whether the iterable in the lookup dictionary is a tuple or a list. It verifies that the resulting URL parameter is a string with comma-separated values.

        The test checks for the correct transformation of the lookup dictionary into URL parameters, ensuring that the 'in' lookup type is correctly handled and the resulting string is properly formatted.

        """
        lookup1 = widgets.url_params_from_lookup_dict({"color__in": ("red", "blue")})
        lookup2 = widgets.url_params_from_lookup_dict({"color__in": ["red", "blue"]})
        self.assertEqual(lookup1, {"color__in": "red,blue"})
        self.assertEqual(lookup1, lookup2)

    def test_url_params_from_lookup_dict_callable(self):
        """
        .Tests that url_params_from_lookup_dict handles callable values in the lookup dictionary by comparing 
        the output when a callable is passed directly versus when its return value is passed. 
        This ensures the function correctly handles and invokes callable values, allowing for dynamic 
        parameter determination.
        """
        def my_callable():
            return "works"

        lookup1 = widgets.url_params_from_lookup_dict({"myfield": my_callable})
        lookup2 = widgets.url_params_from_lookup_dict({"myfield": my_callable()})
        self.assertEqual(lookup1, lookup2)

    def test_label_and_url_for_value_invalid_uuid(self):
        """
        Tests the functionality of the `label_and_url_for_value` method when provided with an invalid UUID value.

        The test case verifies that the method returns an empty string for both the label and the URL when given an invalid UUID, ensuring that the widget behaves correctly in such scenarios.

        This test is crucial to guarantee the robustness and reliability of the application when handling invalid or malformed UUIDs, preventing potential errors or unexpected behavior.
        """
        field = Bee._meta.get_field("honeycomb")
        self.assertIsInstance(field.target_field, UUIDField)
        widget = widgets.ForeignKeyRawIdWidget(field.remote_field, admin.site)
        self.assertEqual(widget.label_and_url_for_value("invalid-uuid"), ("", ""))


class FilteredSelectMultipleWidgetTest(SimpleTestCase):
    def test_render(self):
        # Backslash in verbose_name to ensure it is JavaScript escaped.
        w = widgets.FilteredSelectMultiple("test\\", False)
        self.assertHTMLEqual(
            w.render("test", "test"),
            '<select multiple name="test" class="selectfilter" '
            'data-field-name="test\\" data-is-stacked="0">\n</select>',
        )

    def test_stacked_render(self):
        # Backslash in verbose_name to ensure it is JavaScript escaped.
        """

        Tests the rendering of a stacked FilteredSelectMultiple widget.

        Verifies that the widget is correctly rendered as a multiple select HTML element
        with the specified attributes, including the name, class, data-field-name, and
        data-is-stacked properties.

        The test case checks that the rendered HTML matches the expected output when the
        widget is rendered with the given name and value.

        """
        w = widgets.FilteredSelectMultiple("test\\", True)
        self.assertHTMLEqual(
            w.render("test", "test"),
            '<select multiple name="test" class="selectfilterstacked" '
            'data-field-name="test\\" data-is-stacked="1">\n</select>',
        )


class AdminDateWidgetTest(SimpleTestCase):
    def test_attrs(self):
        """

        Tests the rendering of AdminDateWidget with default and custom attributes.

        Verifies that the widget correctly renders an HTML input field for date input,
        including the input's value, name, and other relevant attributes. Also checks
        that custom attributes, such as size and class, can be passed to the widget and
        are properly applied to the rendered HTML.

        """
        w = widgets.AdminDateWidget()
        self.assertHTMLEqual(
            w.render("test", datetime(2007, 12, 1, 9, 30)),
            '<p class="date">'
            '<input value="2007-12-01" type="text" class="vDateField" name="test" '
            'size="10"></p>',
        )
        # pass attrs to widget
        w = widgets.AdminDateWidget(attrs={"size": 20, "class": "myDateField"})
        self.assertHTMLEqual(
            w.render("test", datetime(2007, 12, 1, 9, 30)),
            '<p class="date">'
            '<input value="2007-12-01" type="text" class="myDateField" name="test" '
            'size="20"></p>',
        )


class AdminTimeWidgetTest(SimpleTestCase):
    def test_attrs(self):
        """

        Tests the rendering of AdminTimeWidget with default and custom attributes.

        Verifies that the widget correctly renders an input field for a given datetime
        value, both with default attributes and with custom attributes such as size and class.

        The test checks that the rendered HTML matches the expected output, ensuring that
        the widget is properly formatted and functional.

        """
        w = widgets.AdminTimeWidget()
        self.assertHTMLEqual(
            w.render("test", datetime(2007, 12, 1, 9, 30)),
            '<p class="time">'
            '<input value="09:30:00" type="text" class="vTimeField" name="test" '
            'size="8"></p>',
        )
        # pass attrs to widget
        w = widgets.AdminTimeWidget(attrs={"size": 20, "class": "myTimeField"})
        self.assertHTMLEqual(
            w.render("test", datetime(2007, 12, 1, 9, 30)),
            '<p class="time">'
            '<input value="09:30:00" type="text" class="myTimeField" name="test" '
            'size="20"></p>',
        )


class AdminSplitDateTimeWidgetTest(SimpleTestCase):
    def test_render(self):
        w = widgets.AdminSplitDateTime()
        self.assertHTMLEqual(
            w.render("test", datetime(2007, 12, 1, 9, 30)),
            '<p class="datetime">'
            'Date: <input value="2007-12-01" type="text" class="vDateField" '
            'name="test_0" size="10"><br>'
            'Time: <input value="09:30:00" type="text" class="vTimeField" '
            'name="test_1" size="8"></p>',
        )

    def test_localization(self):
        """
        Tests the localization of an AdminSplitDateTime widget.

        Verifies that the widget correctly renders a date and time input field with the
        properly formatted values and labels when the locale is set to German (Austria).

        The test covers the rendering of the widget with a specific date and time, and
        asserts that the output matches the expected HTML structure and content.

        Args: None

        Returns: None
        """
        w = widgets.AdminSplitDateTime()

        with translation.override("de-at"):
            w.is_localized = True
            self.assertHTMLEqual(
                w.render("test", datetime(2007, 12, 1, 9, 30)),
                '<p class="datetime">'
                'Datum: <input value="01.12.2007" type="text" '
                'class="vDateField" name="test_0"size="10"><br>'
                'Zeit: <input value="09:30:00" type="text" class="vTimeField" '
                'name="test_1" size="8"></p>',
            )


class AdminURLWidgetTest(SimpleTestCase):
    def test_get_context_validates_url(self):
        w = widgets.AdminURLFieldWidget()
        for invalid in ["", "/not/a/full/url/", 'javascript:alert("Danger XSS!")']:
            with self.subTest(url=invalid):
                self.assertFalse(w.get_context("name", invalid, {})["url_valid"])
        self.assertTrue(w.get_context("name", "http://example.com", {})["url_valid"])

    def test_render(self):
        """
        Tests the rendering of the AdminURLFieldWidget.

        This test case verifies that the widget correctly renders both empty and populated
        URL fields. It checks that the resulting HTML matches the expected output, ensuring
        that the widget produces the correct markup for display and editing of URLs.

        The test covers two scenarios: rendering an empty URL field, which should result in
        a basic URL input field, and rendering a populated URL field, which should display
        the current URL and provide an input field to change it.
        """
        w = widgets.AdminURLFieldWidget()
        self.assertHTMLEqual(
            w.render("test", ""), '<input class="vURLField" name="test" type="url">'
        )
        self.assertHTMLEqual(
            w.render("test", "http://example.com"),
            '<p class="url">Currently:<a href="http://example.com">'
            "http://example.com</a><br>"
            'Change:<input class="vURLField" name="test" type="url" '
            'value="http://example.com"></p>',
        )

    def test_render_idn(self):
        """
        Tests the rendering of an IDN (Internationalized Domain Name) URL field.

        This test ensures that the AdminURLFieldWidget correctly renders a URL with non-ASCII characters, 
        converting it to its Punycode equivalent in the HTML output, while displaying the original IDN in the input field.

        The rendered HTML output includes a paragraph with a link to the original URL, as well as a text input field 
        for editing the URL, with the original URL as its initial value. The test verifies that the rendered HTML 
        matches the expected output format.\"\"\"

        or in a more direct form:

        \"\"\"Tests the rendering of an IDN URL field, verifying correct conversion to Punycode and display of the original IDN.
        """
        w = widgets.AdminURLFieldWidget()
        self.assertHTMLEqual(
            w.render("test", "http://example-äüö.com"),
            '<p class="url">Currently: <a href="http://xn--example--7za4pnc.com">'
            "http://example-äüö.com</a><br>"
            'Change:<input class="vURLField" name="test" type="url" '
            'value="http://example-äüö.com"></p>',
        )

    def test_render_quoting(self):
        """
        WARNING: This test doesn't use assertHTMLEqual since it will get rid
        of some escapes which are tested here!
        """
        HREF_RE = re.compile('href="([^"]+)"')
        VALUE_RE = re.compile('value="([^"]+)"')
        TEXT_RE = re.compile("<a[^>]+>([^>]+)</a>")
        w = widgets.AdminURLFieldWidget()
        output = w.render("test", "http://example.com/<sometag>some-text</sometag>")
        self.assertEqual(
            HREF_RE.search(output)[1],
            "http://example.com/%3Csometag%3Esome-text%3C/sometag%3E",
        )
        self.assertEqual(
            TEXT_RE.search(output)[1],
            "http://example.com/&lt;sometag&gt;some-text&lt;/sometag&gt;",
        )
        self.assertEqual(
            VALUE_RE.search(output)[1],
            "http://example.com/&lt;sometag&gt;some-text&lt;/sometag&gt;",
        )
        output = w.render("test", "http://example-äüö.com/<sometag>some-text</sometag>")
        self.assertEqual(
            HREF_RE.search(output)[1],
            "http://xn--example--7za4pnc.com/%3Csometag%3Esome-text%3C/sometag%3E",
        )
        self.assertEqual(
            TEXT_RE.search(output)[1],
            "http://example-äüö.com/&lt;sometag&gt;some-text&lt;/sometag&gt;",
        )
        self.assertEqual(
            VALUE_RE.search(output)[1],
            "http://example-äüö.com/&lt;sometag&gt;some-text&lt;/sometag&gt;",
        )
        output = w.render(
            "test", 'http://www.example.com/%C3%A4"><script>alert("XSS!")</script>"'
        )
        self.assertEqual(
            HREF_RE.search(output)[1],
            "http://www.example.com/%C3%A4%22%3E%3Cscript%3Ealert(%22XSS!%22)"
            "%3C/script%3E%22",
        )
        self.assertEqual(
            TEXT_RE.search(output)[1],
            "http://www.example.com/%C3%A4&quot;&gt;&lt;script&gt;"
            "alert(&quot;XSS!&quot;)&lt;/script&gt;&quot;",
        )
        self.assertEqual(
            VALUE_RE.search(output)[1],
            "http://www.example.com/%C3%A4&quot;&gt;&lt;script&gt;"
            "alert(&quot;XSS!&quot;)&lt;/script&gt;&quot;",
        )


class AdminUUIDWidgetTests(SimpleTestCase):
    def test_attrs(self):
        """
        Tests the rendering of the AdminUUIDInputWidget with and without custom attributes.

        This test covers two scenarios: the default rendering of the widget and the rendering with custom attributes.
        The default rendering checks if the widget is rendered correctly with the expected HTML attributes.
        The custom attribute rendering checks if the provided attributes, such as class, are correctly applied to the rendered HTML input field.

        The test ensures that the widget correctly handles UUID input values and renders them as expected in an HTML input field.
        """
        w = widgets.AdminUUIDInputWidget()
        self.assertHTMLEqual(
            w.render("test", "550e8400-e29b-41d4-a716-446655440000"),
            '<input value="550e8400-e29b-41d4-a716-446655440000" type="text" '
            'class="vUUIDField" name="test">',
        )
        w = widgets.AdminUUIDInputWidget(attrs={"class": "myUUIDInput"})
        self.assertHTMLEqual(
            w.render("test", "550e8400-e29b-41d4-a716-446655440000"),
            '<input value="550e8400-e29b-41d4-a716-446655440000" type="text" '
            'class="myUUIDInput" name="test">',
        )


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class AdminFileWidgetTests(TestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        band = Band.objects.create(name="Linkin Park")
        cls.album = band.album_set.create(
            name="Hybrid Theory", cover_art=r"albums\hybrid_theory.jpg"
        )

    def test_render(self):
        w = widgets.AdminFileWidget()
        self.assertHTMLEqual(
            w.render("test", self.album.cover_art),
            '<p class="file-upload">Currently: <a href="%(STORAGE_URL)salbums/'
            r'hybrid_theory.jpg">albums\hybrid_theory.jpg</a> '
            '<span class="clearable-file-input">'
            '<input type="checkbox" name="test-clear" id="test-clear_id"> '
            '<label for="test-clear_id">Clear</label></span><br>'
            'Change: <input type="file" name="test"></p>'
            % {
                "STORAGE_URL": default_storage.url(""),
            },
        )
        self.assertHTMLEqual(
            w.render("test", SimpleUploadedFile("test", b"content")),
            '<input type="file" name="test">',
        )

    def test_render_with_attrs_id(self):
        storage_url = default_storage.url("")
        w = widgets.AdminFileWidget()
        self.assertHTMLEqual(
            w.render("test", self.album.cover_art, attrs={"id": "test_id"}),
            f'<p class="file-upload">Currently: <a href="{storage_url}albums/'
            r'hybrid_theory.jpg">albums\hybrid_theory.jpg</a> '
            '<span class="clearable-file-input">'
            '<input type="checkbox" name="test-clear" id="test-clear_id"> '
            '<label for="test-clear_id">Clear</label></span><br>'
            'Change: <input type="file" name="test" id="test_id"></p>',
        )

    def test_render_required(self):
        """

        Render the widget as an HTML string when the field is required.

        This method tests the rendering of the AdminFileWidget when its is_required attribute is set to True. 
        It verifies that the rendered HTML includes the current file and a file input field for uploading a new file.
        The expected output includes a paragraph with a link to the current file and a file input field for changing the file.

        """
        widget = widgets.AdminFileWidget()
        widget.is_required = True
        self.assertHTMLEqual(
            widget.render("test", self.album.cover_art),
            '<p class="file-upload">Currently: <a href="%(STORAGE_URL)salbums/'
            r'hybrid_theory.jpg">albums\hybrid_theory.jpg</a><br>'
            'Change: <input type="file" name="test"></p>'
            % {
                "STORAGE_URL": default_storage.url(""),
            },
        )

    def test_render_disabled(self):
        """

        Tests the rendering of a disabled AdminFileWidget.

        This test case verifies that the widget is rendered correctly when its 'disabled' attribute is set to True.
        It checks that the rendered HTML matches the expected output, including the disabled state of the file input field and the clear checkbox.

        The test case covers a specific scenario where the widget is used to display and potentially update a file, such as an album cover art.
        It ensures that the widget's disabled state is properly reflected in the rendered HTML, preventing user interaction.

        """
        widget = widgets.AdminFileWidget(attrs={"disabled": True})
        self.assertHTMLEqual(
            widget.render("test", self.album.cover_art),
            '<p class="file-upload">Currently: <a href="%(STORAGE_URL)salbums/'
            r'hybrid_theory.jpg">albums\hybrid_theory.jpg</a> '
            '<span class="clearable-file-input">'
            '<input type="checkbox" name="test-clear" id="test-clear_id" disabled>'
            '<label for="test-clear_id">Clear</label></span><br>'
            'Change: <input type="file" name="test" disabled></p>'
            % {
                "STORAGE_URL": default_storage.url(""),
            },
        )

    def test_render_checked(self):
        """
        Tests the rendering of the file widget when it is marked as checked.

        Verifies that the widget correctly displays the currently uploaded file,
        includes a clear checkbox, and provides a field for uploading a new file.
        The test case ensures that the widget's HTML output matches the expected format,
        including the display of the file's URL and the correct state of the clear checkbox.

        """
        storage_url = default_storage.url("")
        widget = widgets.AdminFileWidget()
        widget.checked = True
        self.assertHTMLEqual(
            widget.render("test", self.album.cover_art),
            f'<p class="file-upload">Currently: <a href="{storage_url}albums/'
            r'hybrid_theory.jpg">albums\hybrid_theory.jpg</a> '
            '<span class="clearable-file-input">'
            '<input type="checkbox" name="test-clear" id="test-clear_id" checked>'
            '<label for="test-clear_id">Clear</label></span><br>'
            'Change: <input type="file" name="test" checked></p>',
        )

    def test_readonly_fields(self):
        """
        File widgets should render as a link when they're marked "read only."
        """
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("admin:admin_widgets_album_change", args=(self.album.id,))
        )
        self.assertContains(
            response,
            '<div class="readonly"><a href="%(STORAGE_URL)salbums/hybrid_theory.jpg">'
            r"albums\hybrid_theory.jpg</a></div>"
            % {"STORAGE_URL": default_storage.url("")},
            html=True,
        )
        self.assertNotContains(
            response,
            '<input type="file" name="cover_art" id="id_cover_art">',
            html=True,
        )
        response = self.client.get(reverse("admin:admin_widgets_album_add"))
        self.assertContains(
            response,
            '<div class="readonly">-</div>',
            html=True,
        )


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class ForeignKeyRawIdWidgetTest(TestCase):
    def test_render(self):
        """
        Tests the rendering of ForeignKeyRawIdWidget for band and album models.

        Verifies that the widget correctly renders the input field and lookup link for 
        existing and non-existing foreign key relationships. The test covers both the 
        display of the related object's name and the generation of the correct URLs 
        for the lookup action and the related object's admin page.

        This test is crucial to ensure the proper functioning of the admin interface, 
        where these widgets are used to facilitate the selection of related objects 
        in the database. It checks for the correct rendering of the widget in both 
        cases where the foreign key field has a value and where it is empty, 
        thus validating its behavior under different scenarios. 
        """
        band = Band.objects.create(name="Linkin Park")
        band.album_set.create(
            name="Hybrid Theory", cover_art=r"albums\hybrid_theory.jpg"
        )
        rel_uuid = Album._meta.get_field("band").remote_field
        w = widgets.ForeignKeyRawIdWidget(rel_uuid, widget_admin_site)
        self.assertHTMLEqual(
            w.render("test", band.uuid, attrs={}),
            '<input type="text" name="test" value="%(banduuid)s" '
            'class="vForeignKeyRawIdAdminField vUUIDField">'
            '<a href="/admin_widgets/band/?_to_field=uuid" class="related-lookup" '
            'id="lookup_id_test" title="Lookup"></a>&nbsp;<strong>'
            '<a href="/admin_widgets/band/%(bandpk)s/change/">Linkin Park</a>'
            "</strong>" % {"banduuid": band.uuid, "bandpk": band.pk},
        )

        rel_id = ReleaseEvent._meta.get_field("album").remote_field
        w = widgets.ForeignKeyRawIdWidget(rel_id, widget_admin_site)
        self.assertHTMLEqual(
            w.render("test", None, attrs={}),
            '<input type="text" name="test" class="vForeignKeyRawIdAdminField">'
            '<a href="/admin_widgets/album/?_to_field=id" class="related-lookup" '
            'id="lookup_id_test" title="Lookup"></a>',
        )

    def test_relations_to_non_primary_key(self):
        # ForeignKeyRawIdWidget works with fields which aren't related to
        # the model's primary key.
        apple = Inventory.objects.create(barcode=86, name="Apple")
        Inventory.objects.create(barcode=22, name="Pear")
        core = Inventory.objects.create(barcode=87, name="Core", parent=apple)
        rel = Inventory._meta.get_field("parent").remote_field
        w = widgets.ForeignKeyRawIdWidget(rel, widget_admin_site)
        self.assertHTMLEqual(
            w.render("test", core.parent_id, attrs={}),
            '<input type="text" name="test" value="86" '
            'class="vForeignKeyRawIdAdminField">'
            '<a href="/admin_widgets/inventory/?_to_field=barcode" '
            'class="related-lookup" id="lookup_id_test" title="Lookup"></a>'
            '&nbsp;<strong><a href="/admin_widgets/inventory/%(pk)s/change/">'
            "Apple</a></strong>" % {"pk": apple.pk},
        )

    def test_fk_related_model_not_in_admin(self):
        # FK to a model not registered with admin site. Raw ID widget should
        # have no magnifying glass link. See #16542
        """

        Tests that the foreign key related model is correctly displayed in the admin interface.

        This test case verifies that the ForeignKeyRawIdWidget correctly renders the foreign key
        value for a related model instance, in this case a Honeycomb object. It checks that the
        rendered HTML matches the expected format, which includes the primary key of the related
        object and a string representation of the object itself.

        """
        big_honeycomb = Honeycomb.objects.create(location="Old tree")
        big_honeycomb.bee_set.create()
        rel = Bee._meta.get_field("honeycomb").remote_field

        w = widgets.ForeignKeyRawIdWidget(rel, widget_admin_site)
        self.assertHTMLEqual(
            w.render("honeycomb_widget", big_honeycomb.pk, attrs={}),
            '<input type="text" name="honeycomb_widget" value="%(hcombpk)s">'
            "&nbsp;<strong>%(hcomb)s</strong>"
            % {"hcombpk": big_honeycomb.pk, "hcomb": big_honeycomb},
        )

    def test_fk_to_self_model_not_in_admin(self):
        # FK to self, not registered with admin site. Raw ID widget should have
        # no magnifying glass link. See #16542
        """
        Tests the rendering of a ForeignKeyRawIdWidget for a model with a foreign key to itself.

        Checks that the widget correctly renders an input field and a display text
        for the selected object. This test ensures that the widget can handle
        self-referential relationships, where a model has a foreign key to one of its
        own instances.

        The test case creates an 'Individual' object and a child object that references
        the parent, then verifies that the rendered HTML matches the expected output.

        """
        subject1 = Individual.objects.create(name="Subject #1")
        Individual.objects.create(name="Child", parent=subject1)
        rel = Individual._meta.get_field("parent").remote_field

        w = widgets.ForeignKeyRawIdWidget(rel, widget_admin_site)
        self.assertHTMLEqual(
            w.render("individual_widget", subject1.pk, attrs={}),
            '<input type="text" name="individual_widget" value="%(subj1pk)s">'
            "&nbsp;<strong>%(subj1)s</strong>"
            % {"subj1pk": subject1.pk, "subj1": subject1},
        )

    def test_proper_manager_for_label_lookup(self):
        # see #9258
        """

        Tests the proper rendering of a ForeignKeyRawIdWidget for an Inventory object 
        with a hidden parent, ensuring the lookup functionality is correctly represented 
        in the rendered HTML output, including a link to the related object's admin page.

        """
        rel = Inventory._meta.get_field("parent").remote_field
        w = widgets.ForeignKeyRawIdWidget(rel, widget_admin_site)

        hidden = Inventory.objects.create(barcode=93, name="Hidden", hidden=True)
        child_of_hidden = Inventory.objects.create(
            barcode=94, name="Child of hidden", parent=hidden
        )
        self.assertHTMLEqual(
            w.render("test", child_of_hidden.parent_id, attrs={}),
            '<input type="text" name="test" value="93" '
            '   class="vForeignKeyRawIdAdminField">'
            '<a href="/admin_widgets/inventory/?_to_field=barcode" '
            'class="related-lookup" id="lookup_id_test" title="Lookup"></a>'
            '&nbsp;<strong><a href="/admin_widgets/inventory/%(pk)s/change/">'
            "Hidden</a></strong>" % {"pk": hidden.pk},
        )

    def test_render_unsafe_limit_choices_to(self):
        """
        Tests the rendering of the ForeignKeyRawIdWidget for the band field in the UnsafeLimitChoicesTo model when there are unsafe characters in the lookup URL.

        Verifies that the rendered HTML is correct and secure, with the input field and related lookup link properly formatted and escaped to prevent XSS vulnerabilities.

        The test checks the widget's render method returns the expected HTML output, ensuring the correct handling of special characters in the lookup URL.
        """
        rel = UnsafeLimitChoicesTo._meta.get_field("band").remote_field
        w = widgets.ForeignKeyRawIdWidget(rel, widget_admin_site)
        self.assertHTMLEqual(
            w.render("test", None),
            '<input type="text" name="test" class="vForeignKeyRawIdAdminField">\n'
            '<a href="/admin_widgets/band/?name=%22%26%3E%3Cescapeme&amp;'
            '_to_field=artist_ptr" class="related-lookup" id="lookup_id_test" '
            'title="Lookup"></a>',
        )

    def test_render_fk_as_pk_model(self):
        """

        Tests the rendering of a foreign key as a primary key model.

        This test case ensures that the ForeignKeyRawIdWidget correctly renders a text input
        field and a lookup link for a foreign key field, specifically the 'release_event' field
        in the VideoStream model. The rendered HTML is verified to match the expected output.

        """
        rel = VideoStream._meta.get_field("release_event").remote_field
        w = widgets.ForeignKeyRawIdWidget(rel, widget_admin_site)
        self.assertHTMLEqual(
            w.render("test", None),
            '<input type="text" name="test" class="vForeignKeyRawIdAdminField">\n'
            '<a href="/admin_widgets/releaseevent/?_to_field=album" '
            'class="related-lookup" id="lookup_id_test" title="Lookup"></a>',
        )


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class ManyToManyRawIdWidgetTest(TestCase):
    def test_render(self):
        """
        Tests the rendering of a Many-To-Many Raw ID widget for a band's members.

        This test case verifies that the widget correctly displays the IDs of selected members
        and includes a link for looking up additional members.

        The test covers two scenarios: rendering the widget with multiple selected members and
        with a single selected member, ensuring that the output HTML is as expected in both cases.
        """
        band = Band.objects.create(name="Linkin Park")

        m1 = Member.objects.create(name="Chester")
        m2 = Member.objects.create(name="Mike")
        band.members.add(m1, m2)
        rel = Band._meta.get_field("members").remote_field

        w = widgets.ManyToManyRawIdWidget(rel, widget_admin_site)
        self.assertHTMLEqual(
            w.render("test", [m1.pk, m2.pk], attrs={}),
            (
                '<input type="text" name="test" value="%(m1pk)s,%(m2pk)s" '
                '   class="vManyToManyRawIdAdminField">'
                '<a href="/admin_widgets/member/" class="related-lookup" '
                '   id="lookup_id_test" title="Lookup"></a>'
            )
            % {"m1pk": m1.pk, "m2pk": m2.pk},
        )

        self.assertHTMLEqual(
            w.render("test", [m1.pk]),
            (
                '<input type="text" name="test" value="%(m1pk)s" '
                '   class="vManyToManyRawIdAdminField">'
                '<a href="/admin_widgets/member/" class="related-lookup" '
                '   id="lookup_id_test" title="Lookup"></a>'
            )
            % {"m1pk": m1.pk},
        )

    def test_m2m_related_model_not_in_admin(self):
        # M2M relationship with model not registered with admin site. Raw ID
        # widget should have no magnifying glass link. See #16542
        consultor1 = Advisor.objects.create(name="Rockstar Techie")

        c1 = Company.objects.create(name="Doodle")
        c2 = Company.objects.create(name="Pear")
        consultor1.companies.add(c1, c2)
        rel = Advisor._meta.get_field("companies").remote_field

        w = widgets.ManyToManyRawIdWidget(rel, widget_admin_site)
        self.assertHTMLEqual(
            w.render("company_widget1", [c1.pk, c2.pk], attrs={}),
            '<input type="text" name="company_widget1" value="%(c1pk)s,%(c2pk)s">'
            % {"c1pk": c1.pk, "c2pk": c2.pk},
        )

        self.assertHTMLEqual(
            w.render("company_widget2", [c1.pk]),
            '<input type="text" name="company_widget2" value="%(c1pk)s">'
            % {"c1pk": c1.pk},
        )


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class RelatedFieldWidgetWrapperTests(SimpleTestCase):
    def test_no_can_add_related(self):
        """
        Tests that the can_add_related attribute of a RelatedFieldWidgetWrapper is False.

        This test case verifies that the RelatedFieldWidgetWrapper correctly determines whether
        a related field can be added. The test checks the 'parent' field of the Individual model,
        which is assumed to be a foreign key or other relational field. The test ensures that the
        widget wrapper does not allow adding new related objects, as expected for this type of field.
        """
        rel = Individual._meta.get_field("parent").remote_field
        w = widgets.AdminRadioSelect()
        # Used to fail with a name error.
        w = widgets.RelatedFieldWidgetWrapper(w, rel, widget_admin_site)
        self.assertFalse(w.can_add_related)

    def test_select_multiple_widget_cant_change_delete_related(self):
        """
        Tests the behavior of a SelectMultiple widget in the context of a related field.

        This function verifies that when using a SelectMultiple widget to represent a many-to-one relationship, 
        the user is not allowed to change or delete related objects, despite the widget being configured to 
        permit these actions. The test focuses on the interaction between the widget and the underlying 
        relationship, ensuring that the expected limitations are enforced. The result of this test is a 
        confirmation that the related field is handled correctly in the administrative interface, with 
        addition being the only allowed operation for the related objects.
        """
        rel = Individual._meta.get_field("parent").remote_field
        widget = forms.SelectMultiple()
        wrapper = widgets.RelatedFieldWidgetWrapper(
            widget,
            rel,
            widget_admin_site,
            can_add_related=True,
            can_change_related=True,
            can_delete_related=True,
        )
        self.assertTrue(wrapper.can_add_related)
        self.assertFalse(wrapper.can_change_related)
        self.assertFalse(wrapper.can_delete_related)

    def test_on_delete_cascade_rel_cant_delete_related(self):
        """
        Tests the behavior of the RelatedFieldWidgetWrapper when an \"on_delete=cascade\" relationship is established, 
        verifying that the wrapper correctly disallows deletion of related objects despite the can_delete_related parameter 
        being set to True, due to the on_delete=cascade constraint on the soulmate field of the Individual model.
        """
        rel = Individual._meta.get_field("soulmate").remote_field
        widget = forms.Select()
        wrapper = widgets.RelatedFieldWidgetWrapper(
            widget,
            rel,
            widget_admin_site,
            can_add_related=True,
            can_change_related=True,
            can_delete_related=True,
        )
        self.assertTrue(wrapper.can_add_related)
        self.assertTrue(wrapper.can_change_related)
        self.assertFalse(wrapper.can_delete_related)

    def test_custom_widget_render(self):
        """

        Tests that a custom widget renders correctly within a RelatedFieldWidgetWrapper.

        This test case verifies that a custom widget's render method is called and its output is included in the final HTML output of the wrapper.
        It checks for the presence of the custom render output in the rendered HTML to ensure the widget is working as expected.

        The test covers a scenario where the custom widget is used to render a field in the admin interface, with options to add, change, and delete related objects.

        """
        class CustomWidget(forms.Select):
            def render(self, *args, **kwargs):
                return "custom render output"

        rel = Album._meta.get_field("band").remote_field
        widget = CustomWidget()
        wrapper = widgets.RelatedFieldWidgetWrapper(
            widget,
            rel,
            widget_admin_site,
            can_add_related=True,
            can_change_related=True,
            can_delete_related=True,
        )
        output = wrapper.render("name", "value")
        self.assertIn("custom render output", output)

    def test_widget_delegates_value_omitted_from_data(self):
        """
        Tests if the RelatedFieldWidgetWrapper correctly delegates the value_omitted_from_data method call to its wrapped widget.

        This test ensures that when the value_omitted_from_data method is called on the RelatedFieldWidgetWrapper, it properly calls the same method on the underlying widget, passing the provided data, files, and name. The test verifies this behavior with a custom widget that always returns False from value_omitted_from_data, and checks that the wrapper returns the same result.
        """
        class CustomWidget(forms.Select):
            def value_omitted_from_data(self, data, files, name):
                return False

        rel = Album._meta.get_field("band").remote_field
        widget = CustomWidget()
        wrapper = widgets.RelatedFieldWidgetWrapper(widget, rel, widget_admin_site)
        self.assertIs(wrapper.value_omitted_from_data({}, {}, "band"), False)

    def test_widget_is_hidden(self):
        rel = Album._meta.get_field("band").remote_field
        widget = forms.HiddenInput()
        widget.choices = ()
        wrapper = widgets.RelatedFieldWidgetWrapper(widget, rel, widget_admin_site)
        self.assertIs(wrapper.is_hidden, True)
        context = wrapper.get_context("band", None, {})
        self.assertIs(context["is_hidden"], True)
        output = wrapper.render("name", "value")
        # Related item links are hidden.
        self.assertNotIn("<a ", output)

    def test_widget_is_not_hidden(self):
        """
        ..: 
            Test that a widget for a related field is not hidden.

            This test case verifies that a RelatedFieldWidgetWrapper for an Album's 'band' field 
            does not render its widget as hidden. It checks the 'is_hidden' attribute of the wrapper 
            and the rendered context, and confirms that the rendered output contains a link.
        """
        rel = Album._meta.get_field("band").remote_field
        widget = forms.Select()
        wrapper = widgets.RelatedFieldWidgetWrapper(widget, rel, widget_admin_site)
        self.assertIs(wrapper.is_hidden, False)
        context = wrapper.get_context("band", None, {})
        self.assertIs(context["is_hidden"], False)
        output = wrapper.render("name", "value")
        # Related item links are present.
        self.assertIn("<a ", output)

    def test_data_model_ref_when_model_name_is_camel_case(self):
        """

        Test that RelatedFieldWidgetWrapper behaves correctly when the model name is in camel case.

        This test ensures that the widget wrapper can properly handle models with camel case names,
        and that it generates the correct context and HTML output. It verifies that the widget is not
        hidden, and that the model name is correctly converted to a suitable format for the HTML
        attributes. The test also checks that the rendered HTML matches the expected output.

        """
        rel = VideoStream._meta.get_field("release_event").remote_field
        widget = forms.Select()
        wrapper = widgets.RelatedFieldWidgetWrapper(widget, rel, widget_admin_site)
        self.assertIs(wrapper.is_hidden, False)
        context = wrapper.get_context("release_event", None, {})
        self.assertEqual(context["model"], "release event")
        self.assertEqual(context["model_name"], "releaseevent")
        output = wrapper.render("stream", "value")
        expected = """
        <div class="related-widget-wrapper" data-model-ref="releaseevent">
          <select name="stream" data-context="available-source">
          </select>
          <a class="related-widget-wrapper-link add-related" id="add_id_stream"
             data-popup="yes" title="Add another release event"
             href="/admin_widgets/releaseevent/add/?_to_field=album&amp;_popup=1">
            <img src="/static/admin/img/icon-addlink.svg" alt="" width="20" height="20">
          </a>
        </div>
        """
        self.assertHTMLEqual(output, expected)


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class AdminWidgetSeleniumTestCase(AdminSeleniumTestCase):
    available_apps = ["admin_widgets"] + AdminSeleniumTestCase.available_apps

    def setUp(self):
        self.u1 = User.objects.create_superuser(
            username="super", password="secret", email="super@example.com"
        )


class DateTimePickerSeleniumTests(AdminWidgetSeleniumTestCase):
    def test_show_hide_date_time_picker_widgets(self):
        """
        Pressing the ESC key or clicking on a widget value closes the date and
        time picker widgets.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        self.admin_login(username="super", password="secret", login_url="/")
        # Open a page that has a date and time picker widgets
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_member_add")
        )

        # First, with the date picker widget ---------------------------------
        cal_icon = self.selenium.find_element(By.ID, "calendarlink0")
        # The date picker is hidden
        self.assertFalse(
            self.selenium.find_element(By.ID, "calendarbox0").is_displayed()
        )
        # Click the calendar icon
        cal_icon.click()
        # The date picker is visible
        self.assertTrue(
            self.selenium.find_element(By.ID, "calendarbox0").is_displayed()
        )
        # Press the ESC key
        self.selenium.find_element(By.TAG_NAME, "body").send_keys([Keys.ESCAPE])
        # The date picker is hidden again
        self.assertFalse(
            self.selenium.find_element(By.ID, "calendarbox0").is_displayed()
        )
        # Click the calendar icon, then on the 15th of current month
        cal_icon.click()
        self.selenium.find_element(By.XPATH, "//a[contains(text(), '15')]").click()
        self.assertFalse(
            self.selenium.find_element(By.ID, "calendarbox0").is_displayed()
        )
        self.assertEqual(
            self.selenium.find_element(By.ID, "id_birthdate_0").get_attribute("value"),
            datetime.today().strftime("%Y-%m-") + "15",
        )

        # Then, with the time picker widget ----------------------------------
        time_icon = self.selenium.find_element(By.ID, "clocklink0")
        # The time picker is hidden
        self.assertFalse(self.selenium.find_element(By.ID, "clockbox0").is_displayed())
        # Click the time icon
        time_icon.click()
        # The time picker is visible
        self.assertTrue(self.selenium.find_element(By.ID, "clockbox0").is_displayed())
        self.assertEqual(
            [
                x.text
                for x in self.selenium.find_elements(
                    By.XPATH, "//ul[@class='timelist']/li/a"
                )
            ],
            ["Now", "Midnight", "6 a.m.", "Noon", "6 p.m."],
        )
        # Press the ESC key
        self.selenium.find_element(By.TAG_NAME, "body").send_keys([Keys.ESCAPE])
        # The time picker is hidden again
        self.assertFalse(self.selenium.find_element(By.ID, "clockbox0").is_displayed())
        # Click the time icon, then select the 'Noon' value
        time_icon.click()
        self.selenium.find_element(By.XPATH, "//a[contains(text(), 'Noon')]").click()
        self.assertFalse(self.selenium.find_element(By.ID, "clockbox0").is_displayed())
        self.assertEqual(
            self.selenium.find_element(By.ID, "id_birthdate_1").get_attribute("value"),
            "12:00:00",
        )

    def test_calendar_nonday_class(self):
        """
        Ensure cells that are not days of the month have the `nonday` CSS class.
        Refs #4574.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")
        # Open a page that has a date and time picker widgets
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_member_add")
        )

        # fill in the birth date.
        self.selenium.find_element(By.ID, "id_birthdate_0").send_keys("2013-06-01")

        # Click the calendar icon
        self.selenium.find_element(By.ID, "calendarlink0").click()

        # get all the tds within the calendar
        calendar0 = self.selenium.find_element(By.ID, "calendarin0")
        tds = calendar0.find_elements(By.TAG_NAME, "td")

        # make sure the first and last 6 cells have class nonday
        for td in tds[:6] + tds[-6:]:
            self.assertEqual(td.get_attribute("class"), "nonday")

    def test_calendar_selected_class(self):
        """
        Ensure cell for the day in the input has the `selected` CSS class.
        Refs #4574.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")
        # Open a page that has a date and time picker widgets
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_member_add")
        )

        # fill in the birth date.
        self.selenium.find_element(By.ID, "id_birthdate_0").send_keys("2013-06-01")

        # Click the calendar icon
        self.selenium.find_element(By.ID, "calendarlink0").click()

        # get all the tds within the calendar
        calendar0 = self.selenium.find_element(By.ID, "calendarin0")
        tds = calendar0.find_elements(By.TAG_NAME, "td")

        # verify the selected cell
        selected = tds[6]
        self.assertEqual(selected.get_attribute("class"), "selected")

        self.assertEqual(selected.text, "1")

    def test_calendar_no_selected_class(self):
        """
        Ensure no cells are given the selected class when the field is empty.
        Refs #4574.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")
        # Open a page that has a date and time picker widgets
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_member_add")
        )

        # Click the calendar icon
        self.selenium.find_element(By.ID, "calendarlink0").click()

        # get all the tds within the calendar
        calendar0 = self.selenium.find_element(By.ID, "calendarin0")
        tds = calendar0.find_elements(By.TAG_NAME, "td")

        # verify there are no cells with the selected class
        selected = [td for td in tds if td.get_attribute("class") == "selected"]

        self.assertEqual(len(selected), 0)

    def test_calendar_show_date_from_input(self):
        """
        The calendar shows the date from the input field for every locale
        supported by Django.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")

        # Enter test data
        member = Member.objects.create(
            name="Bob", birthdate=datetime(1984, 5, 15), gender="M"
        )

        # Get month name translations for every locale
        month_string = "May"
        path = os.path.join(
            os.path.dirname(import_module("django.contrib.admin").__file__), "locale"
        )
        url = reverse("admin:admin_widgets_member_change", args=(member.pk,))
        with self.small_screen_size():
            for language_code, language_name in settings.LANGUAGES:
                try:
                    catalog = gettext.translation("djangojs", path, [language_code])
                except OSError:
                    continue
                if month_string in catalog._catalog:
                    month_name = catalog._catalog[month_string]
                else:
                    month_name = month_string

                # Get the expected caption.
                may_translation = month_name
                expected_caption = "{:s} {:d}".format(may_translation.upper(), 1984)

                # Every locale.
                with override_settings(LANGUAGE_CODE=language_code):
                    # Open a page that has a date picker widget.
                    self.selenium.get(self.live_server_url + url)
                    # Click on the calendar icon.
                    self.selenium.find_element(By.ID, "calendarlink0").click()
                    # The right month and year are displayed.
                    self.wait_for_text("#calendarin0 caption", expected_caption)


@requires_tz_support
@override_settings(TIME_ZONE="Asia/Singapore")
class DateTimePickerShortcutsSeleniumTests(AdminWidgetSeleniumTestCase):
    def test_date_time_picker_shortcuts(self):
        """
        date/time/datetime picker shortcuts work in the current time zone.
        Refs #20663.

        This test case is fairly tricky, it relies on selenium still running the browser
        in the default time zone "America/Chicago" despite `override_settings` changing
        the time zone to "Asia/Singapore".
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")

        error_margin = timedelta(seconds=10)

        # If we are neighbouring a DST, we add an hour of error margin.
        tz = zoneinfo.ZoneInfo("America/Chicago")
        utc_now = datetime.now(zoneinfo.ZoneInfo("UTC"))
        tz_yesterday = (utc_now - timedelta(days=1)).astimezone(tz).tzname()
        tz_tomorrow = (utc_now + timedelta(days=1)).astimezone(tz).tzname()
        if tz_yesterday != tz_tomorrow:
            error_margin += timedelta(hours=1)

        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_member_add")
        )

        self.selenium.find_element(By.ID, "id_name").send_keys("test")

        # Click on the "today" and "now" shortcuts.
        shortcuts = self.selenium.find_elements(
            By.CSS_SELECTOR, ".field-birthdate .datetimeshortcuts"
        )

        now = datetime.now()
        for shortcut in shortcuts:
            shortcut.find_element(By.TAG_NAME, "a").click()

        # There is a time zone mismatch warning.
        # Warning: This would effectively fail if the TIME_ZONE defined in the
        # settings has the same UTC offset as "Asia/Singapore" because the
        # mismatch warning would be rightfully missing from the page.
        self.assertCountSeleniumElements(".field-birthdate .timezonewarning", 1)

        # Submit the form.
        with self.wait_page_loaded():
            self.selenium.find_element(By.NAME, "_save").click()

        # Make sure that "now" in JavaScript is within 10 seconds
        # from "now" on the server side.
        member = Member.objects.get(name="test")
        self.assertGreater(member.birthdate, now - error_margin)
        self.assertLess(member.birthdate, now + error_margin)


# The above tests run with Asia/Singapore which are on the positive side of
# UTC. Here we test with a timezone on the negative side.
@override_settings(TIME_ZONE="US/Eastern")
class DateTimePickerAltTimezoneSeleniumTests(DateTimePickerShortcutsSeleniumTests):
    pass


class HorizontalVerticalFilterSeleniumTests(AdminWidgetSeleniumTestCase):
    def setUp(self):
        """
        Setup method executed prior to running tests, responsible for initializing the test environment.

        It creates a set of predefined student objects (Lisa, John, Bob, Peter, Jenny, Jason, Cliff, and Arthur) 
        and a single school object (School of Awesome), providing a consistent base for subsequent tests to build upon.

        This method also calls the parent class's setUp method to ensure proper initialization of the test setup.
        """
        super().setUp()
        self.lisa = Student.objects.create(name="Lisa")
        self.john = Student.objects.create(name="John")
        self.bob = Student.objects.create(name="Bob")
        self.peter = Student.objects.create(name="Peter")
        self.jenny = Student.objects.create(name="Jenny")
        self.jason = Student.objects.create(name="Jason")
        self.cliff = Student.objects.create(name="Cliff")
        self.arthur = Student.objects.create(name="Arthur")
        self.school = School.objects.create(name="School of Awesome")

    def assertActiveButtons(
        self, mode, field_name, choose, remove, choose_all=None, remove_all=None
    ):
        choose_link = "#id_%s_add_link" % field_name
        choose_all_link = "#id_%s_add_all_link" % field_name
        remove_link = "#id_%s_remove_link" % field_name
        remove_all_link = "#id_%s_remove_all_link" % field_name
        self.assertEqual(self.has_css_class(choose_link, "active"), choose)
        self.assertEqual(self.has_css_class(remove_link, "active"), remove)
        if mode == "horizontal":
            self.assertEqual(self.has_css_class(choose_all_link, "active"), choose_all)
            self.assertEqual(self.has_css_class(remove_all_link, "active"), remove_all)

    def execute_basic_operations(self, mode, field_name):
        """
        Executes a series of basic operations on a dual select box widget.

        This method tests the functionality of a dual select box widget, which allows users to move options from one select box to another.
        It supports two modes of operation: 'horizontal' and 'vertical'.

        The method first verifies the initial state of the select boxes and the buttons.
        Then, it performs a series of operations, including moving all options from one box to the other, moving individual options, and verifying the state of the buttons after each operation.
        Finally, it checks the title and text attributes of the select options and verifies that the URL remains unchanged after all operations are completed.

        Args:
            mode (str): The mode of operation, either 'horizontal' or 'vertical'.
            field_name (str): The name of the field being tested.

        The method does not return any value, but it raises an AssertionError if any of the expected conditions are not met.

        """
        from selenium.webdriver.common.by import By

        original_url = self.selenium.current_url

        from_box = "#id_%s_from" % field_name
        to_box = "#id_%s_to" % field_name
        choose_link = "id_%s_add_link" % field_name
        choose_all_link = "id_%s_add_all_link" % field_name
        remove_link = "id_%s_remove_link" % field_name
        remove_all_link = "id_%s_remove_all_link" % field_name

        # Initial positions ---------------------------------------------------
        self.assertSelectOptions(
            from_box,
            [
                str(self.arthur.id),
                str(self.bob.id),
                str(self.cliff.id),
                str(self.jason.id),
                str(self.jenny.id),
                str(self.john.id),
            ],
        )
        self.assertSelectOptions(to_box, [str(self.lisa.id), str(self.peter.id)])
        self.assertActiveButtons(mode, field_name, False, False, True, True)

        # Click 'Choose all' --------------------------------------------------
        if mode == "horizontal":
            self.selenium.find_element(By.ID, choose_all_link).click()
        elif mode == "vertical":
            # There 's no 'Choose all' button in vertical mode, so individually
            # select all options and click 'Choose'.
            for option in self.selenium.find_elements(
                By.CSS_SELECTOR, from_box + " > option"
            ):
                option.click()
            self.selenium.find_element(By.ID, choose_link).click()
        self.assertSelectOptions(from_box, [])
        self.assertSelectOptions(
            to_box,
            [
                str(self.lisa.id),
                str(self.peter.id),
                str(self.arthur.id),
                str(self.bob.id),
                str(self.cliff.id),
                str(self.jason.id),
                str(self.jenny.id),
                str(self.john.id),
            ],
        )
        self.assertActiveButtons(mode, field_name, False, False, False, True)

        # Click 'Remove all' --------------------------------------------------
        if mode == "horizontal":
            self.selenium.find_element(By.ID, remove_all_link).click()
        elif mode == "vertical":
            # There 's no 'Remove all' button in vertical mode, so individually
            # select all options and click 'Remove'.
            for option in self.selenium.find_elements(
                By.CSS_SELECTOR, to_box + " > option"
            ):
                option.click()
            self.selenium.find_element(By.ID, remove_link).click()
        self.assertSelectOptions(
            from_box,
            [
                str(self.lisa.id),
                str(self.peter.id),
                str(self.arthur.id),
                str(self.bob.id),
                str(self.cliff.id),
                str(self.jason.id),
                str(self.jenny.id),
                str(self.john.id),
            ],
        )
        self.assertSelectOptions(to_box, [])
        self.assertActiveButtons(mode, field_name, False, False, True, False)

        # Choose some options ------------------------------------------------
        from_lisa_select_option = self.selenium.find_element(
            By.CSS_SELECTOR, '{} > option[value="{}"]'.format(from_box, self.lisa.id)
        )

        # Check the title attribute is there for tool tips: ticket #20821
        self.assertEqual(
            from_lisa_select_option.get_attribute("title"),
            from_lisa_select_option.get_attribute("text"),
        )

        self.select_option(from_box, str(self.lisa.id))
        self.select_option(from_box, str(self.jason.id))
        self.select_option(from_box, str(self.bob.id))
        self.select_option(from_box, str(self.john.id))
        self.assertActiveButtons(mode, field_name, True, False, True, False)
        self.selenium.find_element(By.ID, choose_link).click()
        self.assertActiveButtons(mode, field_name, False, False, True, True)

        self.assertSelectOptions(
            from_box,
            [
                str(self.peter.id),
                str(self.arthur.id),
                str(self.cliff.id),
                str(self.jenny.id),
            ],
        )
        self.assertSelectOptions(
            to_box,
            [
                str(self.lisa.id),
                str(self.bob.id),
                str(self.jason.id),
                str(self.john.id),
            ],
        )

        # Check the tooltip is still there after moving: ticket #20821
        to_lisa_select_option = self.selenium.find_element(
            By.CSS_SELECTOR, '{} > option[value="{}"]'.format(to_box, self.lisa.id)
        )
        self.assertEqual(
            to_lisa_select_option.get_attribute("title"),
            to_lisa_select_option.get_attribute("text"),
        )

        # Remove some options -------------------------------------------------
        self.select_option(to_box, str(self.lisa.id))
        self.select_option(to_box, str(self.bob.id))
        self.assertActiveButtons(mode, field_name, False, True, True, True)
        self.selenium.find_element(By.ID, remove_link).click()
        self.assertActiveButtons(mode, field_name, False, False, True, True)

        self.assertSelectOptions(
            from_box,
            [
                str(self.peter.id),
                str(self.arthur.id),
                str(self.cliff.id),
                str(self.jenny.id),
                str(self.lisa.id),
                str(self.bob.id),
            ],
        )
        self.assertSelectOptions(to_box, [str(self.jason.id), str(self.john.id)])

        # Choose some more options --------------------------------------------
        self.select_option(from_box, str(self.arthur.id))
        self.select_option(from_box, str(self.cliff.id))
        self.selenium.find_element(By.ID, choose_link).click()

        self.assertSelectOptions(
            from_box,
            [
                str(self.peter.id),
                str(self.jenny.id),
                str(self.lisa.id),
                str(self.bob.id),
            ],
        )
        self.assertSelectOptions(
            to_box,
            [
                str(self.jason.id),
                str(self.john.id),
                str(self.arthur.id),
                str(self.cliff.id),
            ],
        )

        # Choose some more options --------------------------------------------
        self.select_option(from_box, str(self.peter.id))
        self.select_option(from_box, str(self.lisa.id))

        # Confirm they're selected after clicking inactive buttons: ticket #26575
        self.assertSelectedOptions(from_box, [str(self.peter.id), str(self.lisa.id)])
        self.selenium.find_element(By.ID, remove_link).click()
        self.assertSelectedOptions(from_box, [str(self.peter.id), str(self.lisa.id)])

        # Unselect the options ------------------------------------------------
        self.deselect_option(from_box, str(self.peter.id))
        self.deselect_option(from_box, str(self.lisa.id))

        # Choose some more options --------------------------------------------
        self.select_option(to_box, str(self.jason.id))
        self.select_option(to_box, str(self.john.id))

        # Confirm they're selected after clicking inactive buttons: ticket #26575
        self.assertSelectedOptions(to_box, [str(self.jason.id), str(self.john.id)])
        self.selenium.find_element(By.ID, choose_link).click()
        self.assertSelectedOptions(to_box, [str(self.jason.id), str(self.john.id)])

        # Unselect the options ------------------------------------------------
        self.deselect_option(to_box, str(self.jason.id))
        self.deselect_option(to_box, str(self.john.id))

        # Pressing buttons shouldn't change the URL.
        self.assertEqual(self.selenium.current_url, original_url)

    def test_basic(self):
        """
        Tests basic functionality of the school admin page.

        This test case logs in as an admin, navigates to the school change page, and simulates interactions with the students and alumni widgets.
        It checks that after performing basic operations on these widgets, the school's students and alumni lists are updated correctly.

        The test is performed with a small screen size to cover responsive design scenarios.

        Asserts that the school's students and alumni are updated to include all the expected students after the test operations are completed.
        """
        from selenium.webdriver.common.by import By

        self.school.students.set([self.lisa, self.peter])
        self.school.alumni.set([self.lisa, self.peter])

        with self.small_screen_size():
            self.admin_login(username="super", password="secret", login_url="/")
            self.selenium.get(
                self.live_server_url
                + reverse("admin:admin_widgets_school_change", args=(self.school.id,))
            )

            self.wait_page_ready()
            self.execute_basic_operations("vertical", "students")
            self.execute_basic_operations("horizontal", "alumni")

            # Save, everything should be stored properly stored in the
            # database.
            self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()
            self.wait_page_ready()
        self.school = School.objects.get(id=self.school.id)  # Reload from database
        self.assertEqual(
            list(self.school.students.all()),
            [self.arthur, self.cliff, self.jason, self.john],
        )
        self.assertEqual(
            list(self.school.alumni.all()),
            [self.arthur, self.cliff, self.jason, self.john],
        )

    def test_filter(self):
        """
        Typing in the search box filters out options displayed in the 'from'
        box.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        self.school.students.set([self.lisa, self.peter])
        self.school.alumni.set([self.lisa, self.peter])

        with self.small_screen_size():
            self.admin_login(username="super", password="secret", login_url="/")
            self.selenium.get(
                self.live_server_url
                + reverse("admin:admin_widgets_school_change", args=(self.school.id,))
            )

            for field_name in ["students", "alumni"]:
                from_box = "#id_%s_from" % field_name
                to_box = "#id_%s_to" % field_name
                choose_link = "id_%s_add_link" % field_name
                remove_link = "id_%s_remove_link" % field_name
                input = self.selenium.find_element(By.ID, "id_%s_input" % field_name)
                # Initial values.
                self.assertSelectOptions(
                    from_box,
                    [
                        str(self.arthur.id),
                        str(self.bob.id),
                        str(self.cliff.id),
                        str(self.jason.id),
                        str(self.jenny.id),
                        str(self.john.id),
                    ],
                )
                # Typing in some characters filters out non-matching options.
                input.send_keys("a")
                self.assertSelectOptions(
                    from_box, [str(self.arthur.id), str(self.jason.id)]
                )
                input.send_keys("R")
                self.assertSelectOptions(from_box, [str(self.arthur.id)])
                # Clearing the text box makes the other options reappear.
                input.send_keys([Keys.BACK_SPACE])
                self.assertSelectOptions(
                    from_box, [str(self.arthur.id), str(self.jason.id)]
                )
                input.send_keys([Keys.BACK_SPACE])
                self.assertSelectOptions(
                    from_box,
                    [
                        str(self.arthur.id),
                        str(self.bob.id),
                        str(self.cliff.id),
                        str(self.jason.id),
                        str(self.jenny.id),
                        str(self.john.id),
                    ],
                )

                # Choosing a filtered option sends it properly to the 'to' box.
                input.send_keys("a")
                self.assertSelectOptions(
                    from_box, [str(self.arthur.id), str(self.jason.id)]
                )
                self.select_option(from_box, str(self.jason.id))
                self.selenium.find_element(By.ID, choose_link).click()
                self.assertSelectOptions(from_box, [str(self.arthur.id)])
                self.assertSelectOptions(
                    to_box,
                    [
                        str(self.lisa.id),
                        str(self.peter.id),
                        str(self.jason.id),
                    ],
                )

                self.select_option(to_box, str(self.lisa.id))
                self.selenium.find_element(By.ID, remove_link).click()
                self.assertSelectOptions(
                    from_box, [str(self.arthur.id), str(self.lisa.id)]
                )
                self.assertSelectOptions(
                    to_box, [str(self.peter.id), str(self.jason.id)]
                )

                input.send_keys([Keys.BACK_SPACE])  # Clear text box
                self.assertSelectOptions(
                    from_box,
                    [
                        str(self.arthur.id),
                        str(self.bob.id),
                        str(self.cliff.id),
                        str(self.jenny.id),
                        str(self.john.id),
                        str(self.lisa.id),
                    ],
                )
                self.assertSelectOptions(
                    to_box, [str(self.peter.id), str(self.jason.id)]
                )

                # Pressing enter on a filtered option sends it properly to
                # the 'to' box.
                self.select_option(to_box, str(self.jason.id))
                self.selenium.find_element(By.ID, remove_link).click()
                input.send_keys("ja")
                self.assertSelectOptions(from_box, [str(self.jason.id)])
                input.send_keys([Keys.ENTER])
                self.assertSelectOptions(
                    to_box, [str(self.peter.id), str(self.jason.id)]
                )
                input.send_keys([Keys.BACK_SPACE, Keys.BACK_SPACE])

            # Save, everything should be stored properly in the database.
            with self.wait_page_loaded():
                self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()
        self.school = School.objects.get(id=self.school.id)  # Reload from database
        self.assertEqual(list(self.school.students.all()), [self.jason, self.peter])
        self.assertEqual(list(self.school.alumni.all()), [self.jason, self.peter])

    def test_back_button_bug(self):
        """
        Some browsers had a bug where navigating away from the change page
        and then clicking the browser's back button would clear the
        filter_horizontal/filter_vertical widgets (#13614).
        """
        from selenium.webdriver.common.by import By

        self.school.students.set([self.lisa, self.peter])
        self.school.alumni.set([self.lisa, self.peter])
        self.admin_login(username="super", password="secret", login_url="/")
        change_url = reverse(
            "admin:admin_widgets_school_change", args=(self.school.id,)
        )
        self.selenium.get(self.live_server_url + change_url)
        # Navigate away and go back to the change form page.
        self.selenium.find_element(By.LINK_TEXT, "Home").click()
        self.selenium.back()
        expected_unselected_values = [
            str(self.arthur.id),
            str(self.bob.id),
            str(self.cliff.id),
            str(self.jason.id),
            str(self.jenny.id),
            str(self.john.id),
        ]
        expected_selected_values = [str(self.lisa.id), str(self.peter.id)]
        # Everything is still in place
        self.assertSelectOptions("#id_students_from", expected_unselected_values)
        self.assertSelectOptions("#id_students_to", expected_selected_values)
        self.assertSelectOptions("#id_alumni_from", expected_unselected_values)
        self.assertSelectOptions("#id_alumni_to", expected_selected_values)

    def test_refresh_page(self):
        """
        Horizontal and vertical filter widgets keep selected options on page
        reload (#22955).
        """
        self.school.students.add(self.arthur, self.jason)
        self.school.alumni.add(self.arthur, self.jason)

        self.admin_login(username="super", password="secret", login_url="/")
        change_url = reverse(
            "admin:admin_widgets_school_change", args=(self.school.id,)
        )
        self.selenium.get(self.live_server_url + change_url)

        self.assertCountSeleniumElements("#id_students_to > option", 2)

        # self.selenium.refresh() or send_keys(Keys.F5) does hard reload and
        # doesn't replicate what happens when a user clicks the browser's
        # 'Refresh' button.
        with self.wait_page_loaded():
            self.selenium.execute_script("location.reload()")

        self.assertCountSeleniumElements("#id_students_to > option", 2)


@ignore_warnings(category=RemovedInDjango60Warning)
class AdminRawIdWidgetSeleniumTests(AdminWidgetSeleniumTestCase):
    def setUp(self):
        """
        Sets up the initial state for testing by creating two predefined bands in the database.
        The bands are created with specific identifiers and names: \"Bogey Blues\" with id 42 and \"Green Potatoes\" with id 98.
        This setup provides a consistent foundation for testing band-related functionality.
        """
        super().setUp()
        Band.objects.create(id=42, name="Bogey Blues")
        Band.objects.create(id=98, name="Green Potatoes")

    def test_ForeignKey(self):
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_event_add")
        )
        main_window = self.selenium.current_window_handle

        # No value has been selected yet
        self.assertEqual(
            self.selenium.find_element(By.ID, "id_main_band").get_attribute("value"), ""
        )

        # Open the popup window and click on a band
        self.selenium.find_element(By.ID, "lookup_id_main_band").click()
        self.wait_for_and_switch_to_popup()
        link = self.selenium.find_element(By.LINK_TEXT, "Bogey Blues")
        self.assertIn("/band/42/", link.get_attribute("href"))
        link.click()

        # The field now contains the selected band's id
        self.selenium.switch_to.window(main_window)
        self.wait_for_value("#id_main_band", "42")

        # Reopen the popup window and click on another band
        self.selenium.find_element(By.ID, "lookup_id_main_band").click()
        self.wait_for_and_switch_to_popup()
        link = self.selenium.find_element(By.LINK_TEXT, "Green Potatoes")
        self.assertIn("/band/98/", link.get_attribute("href"))
        link.click()

        # The field now contains the other selected band's id
        self.selenium.switch_to.window(main_window)
        self.wait_for_value("#id_main_band", "98")

    def test_many_to_many(self):
        """

        Tests the many-to-many relationship functionality in the admin interface.

        This test case logs in as an admin user, navigates to the event add page, 
        and verifies the initial state of the supporting bands field. It then simulates 
        a user selecting multiple bands from the lookup popup, ensuring that the 
        selected bands are correctly added to the supporting bands field.

        Verifies that the selection of multiple bands is persisted and displayed 
        correctly, demonstrating the expected behavior of the many-to-many relationship 
        in the admin interface.

        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_event_add")
        )
        main_window = self.selenium.current_window_handle

        # No value has been selected yet
        self.assertEqual(
            self.selenium.find_element(By.ID, "id_supporting_bands").get_attribute(
                "value"
            ),
            "",
        )

        # Help text for the field is displayed
        self.assertEqual(
            self.selenium.find_element(
                By.CSS_SELECTOR, ".field-supporting_bands div.help"
            ).text,
            "Supporting Bands.",
        )

        # Open the popup window and click on a band
        self.selenium.find_element(By.ID, "lookup_id_supporting_bands").click()
        self.wait_for_and_switch_to_popup()
        link = self.selenium.find_element(By.LINK_TEXT, "Bogey Blues")
        self.assertIn("/band/42/", link.get_attribute("href"))
        link.click()

        # The field now contains the selected band's id
        self.selenium.switch_to.window(main_window)
        self.wait_for_value("#id_supporting_bands", "42")

        # Reopen the popup window and click on another band
        self.selenium.find_element(By.ID, "lookup_id_supporting_bands").click()
        self.wait_for_and_switch_to_popup()
        link = self.selenium.find_element(By.LINK_TEXT, "Green Potatoes")
        self.assertIn("/band/98/", link.get_attribute("href"))
        link.click()

        # The field now contains the two selected bands' ids
        self.selenium.switch_to.window(main_window)
        self.wait_for_value("#id_supporting_bands", "42,98")


class RelatedFieldWidgetSeleniumTests(AdminWidgetSeleniumTestCase):
    def test_ForeignKey_using_to_field(self):
        from selenium.webdriver import ActionChains
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select

        self.admin_login(username="super", password="secret", login_url="/")
        with self.wait_page_loaded():
            self.selenium.get(
                self.live_server_url + reverse("admin:admin_widgets_profile_add")
            )

        main_window = self.selenium.current_window_handle
        # Click the Add User button to add new
        self.selenium.find_element(By.ID, "add_id_user").click()
        self.wait_for_and_switch_to_popup()
        password_field = self.selenium.find_element(By.ID, "id_password")
        password_field.send_keys("password")

        username_field = self.selenium.find_element(By.ID, "id_username")
        username_value = "newuser"
        username_field.send_keys(username_value)

        save_button_css_selector = ".submit-row > input[type=submit]"
        self.selenium.find_element(By.CSS_SELECTOR, save_button_css_selector).click()
        self.selenium.switch_to.window(main_window)
        # The field now contains the new user
        self.selenium.find_element(By.CSS_SELECTOR, "#id_user option[value=newuser]")

        self.selenium.find_element(By.ID, "view_id_user").click()
        self.wait_for_value("#id_username", "newuser")
        self.selenium.back()

        # Chrome and Safari don't update related object links when selecting
        # the same option as previously submitted. As a consequence, the
        # "pencil" and "eye" buttons remain disable, so select "---------"
        # first.
        select = Select(self.selenium.find_element(By.ID, "id_user"))
        select.select_by_index(0)
        select.select_by_value("newuser")
        # Click the Change User button to change it
        self.selenium.find_element(By.ID, "change_id_user").click()
        self.wait_for_and_switch_to_popup()

        username_field = self.selenium.find_element(By.ID, "id_username")
        username_value = "changednewuser"
        username_field.clear()
        username_field.send_keys(username_value)

        save_button_css_selector = ".submit-row > input[type=submit]"
        self.selenium.find_element(By.CSS_SELECTOR, save_button_css_selector).click()
        self.selenium.switch_to.window(main_window)
        self.selenium.find_element(
            By.CSS_SELECTOR, "#id_user option[value=changednewuser]"
        )

        element = self.selenium.find_element(By.ID, "view_id_user")
        ActionChains(self.selenium).move_to_element(element).click(element).perform()
        self.wait_for_value("#id_username", "changednewuser")
        self.selenium.back()

        select = Select(self.selenium.find_element(By.ID, "id_user"))
        select.select_by_value("changednewuser")
        # Go ahead and submit the form to make sure it works
        self.selenium.find_element(By.CSS_SELECTOR, save_button_css_selector).click()
        self.wait_for_text(
            "li.success", "The profile “changednewuser” was added successfully."
        )
        profiles = Profile.objects.all()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].user.username, username_value)


@skipUnless(Image, "Pillow not installed")
class ImageFieldWidgetsSeleniumTests(AdminWidgetSeleniumTestCase):
    name_input_id = "id_name"
    photo_input_id = "id_photo"
    tests_files_folder = "%s/files" % os.getcwd()
    clear_checkbox_id = "photo-clear_id"

    def _submit_and_wait(self):
        """
        Submits the current page and waits for it to finish loading.

        This method simulates a click on the 'Save and continue editing' button,
        allowing the page to proceed to the next step. It ensures that the page
        has finished loading before continuing, providing a stable state for
        further interactions.

        Note: This method is intended for internal use and should not be called
        directly. Its functionality is part of a larger workflow and may not
        behave as expected when used in isolation.
        """
        from selenium.webdriver.common.by import By

        with self.wait_page_loaded():
            self.selenium.find_element(
                By.CSS_SELECTOR, "input[value='Save and continue editing']"
            ).click()

    def _run_image_upload_path(self):
        """
        Runs the image upload path for a student in the admin interface.

        This function logs in as an admin user, navigates to the student add page,
        enters a student name, uploads a test image, and submits the form.
        It then verifies that a new student object is created with the correct name
        and that the uploaded image is saved to the expected location.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret", login_url="/")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_widgets_student_add"),
        )
        # Add a student.
        name_input = self.selenium.find_element(By.ID, self.name_input_id)
        name_input.send_keys("Joe Doe")
        photo_input = self.selenium.find_element(By.ID, self.photo_input_id)
        photo_input.send_keys(f"{self.tests_files_folder}/test.png")
        self._submit_and_wait()
        student = Student.objects.last()
        self.assertEqual(student.name, "Joe Doe")
        self.assertRegex(student.photo.name, r"^photos\/(test|test_.+).png")

    def test_clearablefileinput_widget(self):
        """

        Tests that the clearable file input widget in the student form functions correctly.

        The test simulates the upload of an image, then clears the file input field using the clear checkbox.
        It verifies that the student's name remains unchanged, the photo field is cleared, and the UI
        reflects the cleared state by not showing the 'Currently' and 'Change' labels.

        """
        from selenium.webdriver.common.by import By

        self._run_image_upload_path()
        self.selenium.find_element(By.ID, self.clear_checkbox_id).click()
        self._submit_and_wait()
        student = Student.objects.last()
        self.assertEqual(student.name, "Joe Doe")
        self.assertEqual(student.photo.name, "")
        # "Currently" with "Clear" checkbox and "Change" are not shown.
        photo_field_row = self.selenium.find_element(By.CSS_SELECTOR, ".field-photo")
        self.assertNotIn("Currently", photo_field_row.text)
        self.assertNotIn("Change", photo_field_row.text)

    def test_clearablefileinput_widget_invalid_file(self):
        """

        Tests the ClearableFileInput widget's behavior when an invalid file is uploaded.

        Verifies that uploading a corrupted image file results in a validation error,
        displaying an appropriate error message. Additionally, checks that the widget
        still allows the user to change the uploaded file after an invalid upload attempt.

        The test case uses a pre-configured test environment and asserts the expected
        error message and widget state after submitting the form with an invalid image file.

        """
        from selenium.webdriver.common.by import By

        self._run_image_upload_path()
        # Uploading non-image files is not supported by Safari with Selenium,
        # so upload a broken one instead.
        photo_input = self.selenium.find_element(By.ID, self.photo_input_id)
        photo_input.send_keys(f"{self.tests_files_folder}/brokenimg.png")
        self._submit_and_wait()
        self.assertEqual(
            self.selenium.find_element(By.CSS_SELECTOR, ".errorlist li").text,
            (
                "Upload a valid image. The file you uploaded was either not an image "
                "or a corrupted image."
            ),
        )
        # "Currently" with "Clear" checkbox and "Change" still shown.
        photo_field_row = self.selenium.find_element(By.CSS_SELECTOR, ".field-photo")
        self.assertIn("Currently", photo_field_row.text)
        self.assertIn("Change", photo_field_row.text)

    def test_clearablefileinput_widget_preserve_clear_checkbox(self):
        from selenium.webdriver.common.by import By

        self._run_image_upload_path()
        # "Clear" is not checked by default.
        self.assertIs(
            self.selenium.find_element(By.ID, self.clear_checkbox_id).is_selected(),
            False,
        )
        # "Clear" was checked, but a validation error is raised.
        name_input = self.selenium.find_element(By.ID, self.name_input_id)
        name_input.clear()
        self.selenium.find_element(By.ID, self.clear_checkbox_id).click()
        self._submit_and_wait()
        self.assertEqual(
            self.selenium.find_element(By.CSS_SELECTOR, ".errorlist li").text,
            "This field is required.",
        )
        # "Clear" persists checked.
        self.assertIs(
            self.selenium.find_element(By.ID, self.clear_checkbox_id).is_selected(),
            True,
        )
