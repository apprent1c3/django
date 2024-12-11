from datetime import date

from django import forms
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.admin.options import (
    HORIZONTAL,
    VERTICAL,
    ModelAdmin,
    TabularInline,
    get_content_type_for_model,
)
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.widgets import (
    AdminDateWidget,
    AdminRadioSelect,
    AutocompleteSelect,
    AutocompleteSelectMultiple,
)
from django.contrib.auth.models import User
from django.db import models
from django.forms.widgets import Select
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import isolate_apps
from django.utils.deprecation import RemovedInDjango60Warning

from .models import Band, Concert, Song


class MockRequest:
    pass


class MockSuperUser:
    def has_perm(self, perm, obj=None):
        return True


request = MockRequest()
request.user = MockSuperUser()


class ModelAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.band = Band.objects.create(
            name="The Doors",
            bio="",
            sign_date=date(1965, 1, 1),
        )

    def setUp(self):
        self.site = AdminSite()

    def test_modeladmin_str(self):
        """

        Tests the string representation of a ModelAdmin instance.

        Ensures that the string representation of a ModelAdmin object, which is typically
        used for identification or logging purposes, is correctly formatted as expected.
        The test checks that the string representation of the ModelAdmin returns the
        expected class name, providing a basic sanity check for the ModelAdmin's
        construction and identification.

        """
        ma = ModelAdmin(Band, self.site)
        self.assertEqual(str(ma), "modeladmin.ModelAdmin")

    def test_default_attributes(self):
        """
        Tests that a ModelAdmin instance has the expected default attributes when created.

        Specifically, this test verifies that the :attr:`actions` and :attr:`inlines` attributes are initialized as empty tuples by default, indicating that no custom actions or inlines have been defined.
        """
        ma = ModelAdmin(Band, self.site)
        self.assertEqual(ma.actions, ())
        self.assertEqual(ma.inlines, ())

    # form/fields/fieldsets interaction ##############################

    def test_default_fields(self):
        ma = ModelAdmin(Band, self.site)
        self.assertEqual(
            list(ma.get_form(request).base_fields), ["name", "bio", "sign_date"]
        )
        self.assertEqual(list(ma.get_fields(request)), ["name", "bio", "sign_date"])
        self.assertEqual(
            list(ma.get_fields(request, self.band)), ["name", "bio", "sign_date"]
        )
        self.assertIsNone(ma.get_exclude(request, self.band))

    def test_default_fieldsets(self):
        # fieldsets_add and fieldsets_change should return a special data structure that
        # is used in the templates. They should generate the "right thing" whether we
        # have specified a custom form, the fields argument, or nothing at all.
        #
        # Here's the default case. There are no custom form_add/form_change methods,
        # no fields argument, and no fieldsets argument.
        ma = ModelAdmin(Band, self.site)
        self.assertEqual(
            ma.get_fieldsets(request),
            [(None, {"fields": ["name", "bio", "sign_date"]})],
        )
        self.assertEqual(
            ma.get_fieldsets(request, self.band),
            [(None, {"fields": ["name", "bio", "sign_date"]})],
        )

    def test_get_fieldsets(self):
        # get_fieldsets() is called when figuring out form fields (#18681).
        """

        Tests the get_fieldsets method in ModelAdmin and Inline model classes.

        Checks if the fieldsets returned by this method are correctly reflected in the 
        form and formset fields. Specifically, it verifies that the fields specified in 
        the get_fieldsets method match the fields present in the form metadata.

        This test covers both the ModelAdmin and Inline model classes, ensuring that 
        the get_fieldsets method behaves as expected in different administrative 
        interface contexts.

        """
        class BandAdmin(ModelAdmin):
            def get_fieldsets(self, request, obj=None):
                return [(None, {"fields": ["name", "bio"]})]

        ma = BandAdmin(Band, self.site)
        form = ma.get_form(None)
        self.assertEqual(form._meta.fields, ["name", "bio"])

        class InlineBandAdmin(TabularInline):
            model = Concert
            fk_name = "main_band"
            can_delete = False

            def get_fieldsets(self, request, obj=None):
                return [(None, {"fields": ["day", "transport"]})]

        ma = InlineBandAdmin(Band, self.site)
        form = ma.get_formset(None).form
        self.assertEqual(form._meta.fields, ["day", "transport"])

    def test_lookup_allowed_allows_nonexistent_lookup(self):
        """
        A lookup_allowed allows a parameter whose field lookup doesn't exist.
        (#21129).
        """

        class BandAdmin(ModelAdmin):
            fields = ["name"]

        ma = BandAdmin(Band, self.site)
        self.assertIs(
            ma.lookup_allowed("name__nonexistent", "test_value", request),
            True,
        )

    @isolate_apps("modeladmin")
    def test_lookup_allowed_onetoone(self):
        """

        Tests that lookup is allowed on one-to-one fields in the ModelAdmin.

        This test case verifies that the `lookup_allowed` method returns True for lookups 
        on one-to-one fields, such as 'employee__employeeinfo__description' and 
        'employee__department__code', in the EmployeeProfileAdmin instance.

        The test covers the scenario where the ModelAdmin defines a list_filter that 
        includes a one-to-one field, ensuring that the lookup is permitted.

        """
        class Department(models.Model):
            code = models.CharField(max_length=4, unique=True)

        class Employee(models.Model):
            department = models.ForeignKey(Department, models.CASCADE, to_field="code")

        class EmployeeProfile(models.Model):
            employee = models.OneToOneField(Employee, models.CASCADE)

        class EmployeeInfo(models.Model):
            employee = models.OneToOneField(Employee, models.CASCADE)
            description = models.CharField(max_length=100)

        class EmployeeProfileAdmin(ModelAdmin):
            list_filter = [
                "employee__employeeinfo__description",
                "employee__department__code",
            ]

        ma = EmployeeProfileAdmin(EmployeeProfile, self.site)
        # Reverse OneToOneField
        self.assertIs(
            ma.lookup_allowed(
                "employee__employeeinfo__description", "test_value", request
            ),
            True,
        )
        # OneToOneField and ForeignKey
        self.assertIs(
            ma.lookup_allowed("employee__department__code", "test_value", request),
            True,
        )

    @isolate_apps("modeladmin")
    def test_lookup_allowed_for_local_fk_fields(self):
        """

        Tests that foreign key fields on local models are allowed lookups in the model admin interface.

        This test case covers various lookup types and values for foreign key fields, including exact matches, 
        id-based lookups, and null checks. It ensures that the model admin interface permits these lookups 
        for local foreign key fields, which is essential for filtering and searching functionality.

        :raises AssertionError: If any of the tested lookup cases are not allowed by the model admin interface.

        """
        class Country(models.Model):
            pass

        class Place(models.Model):
            country = models.ForeignKey(Country, models.CASCADE)

        class PlaceAdmin(ModelAdmin):
            pass

        ma = PlaceAdmin(Place, self.site)

        cases = [
            ("country", "1"),
            ("country__exact", "1"),
            ("country__id", "1"),
            ("country__id__exact", "1"),
            ("country__isnull", True),
            ("country__isnull", False),
            ("country__id__isnull", False),
        ]
        for lookup, lookup_value in cases:
            with self.subTest(lookup=lookup):
                self.assertIs(ma.lookup_allowed(lookup, lookup_value, request), True)

    @isolate_apps("modeladmin")
    def test_lookup_allowed_non_autofield_primary_key(self):
        """

        Tests whether a lookup is allowed for a non-auto field primary key in the model admin interface.

        This function checks if the model admin allows filtering by a primary key that is not an auto field.
        It creates a test model with a custom primary key field and a foreign key to this model, 
        then uses the model admin to test if the lookup is allowed.

        The test covers the case where the primary key is a non-auto field, 
        such as a character field, and verifies that the lookup is allowed as expected.

        """
        class Country(models.Model):
            id = models.CharField(max_length=2, primary_key=True)

        class Place(models.Model):
            country = models.ForeignKey(Country, models.CASCADE)

        class PlaceAdmin(ModelAdmin):
            list_filter = ["country"]

        ma = PlaceAdmin(Place, self.site)
        self.assertIs(ma.lookup_allowed("country__id__exact", "DE", request), True)

    @isolate_apps("modeladmin")
    def test_lookup_allowed_foreign_primary(self):
        """

        Tests that the lookup on a Foreign Key relationship spanning multiple levels is allowed in the ModelAdmin interface.

        This test case verifies that the lookup filter on a model's admin interface can traverse multiple levels of Foreign Key relationships
        and filter objects based on attributes of related models. It checks for exact and non-exact lookups on the related model's attributes.

        """
        class Country(models.Model):
            name = models.CharField(max_length=256)

        class Place(models.Model):
            country = models.ForeignKey(Country, models.CASCADE)

        class Restaurant(models.Model):
            place = models.OneToOneField(Place, models.CASCADE, primary_key=True)

        class Waiter(models.Model):
            restaurant = models.ForeignKey(Restaurant, models.CASCADE)

        class WaiterAdmin(ModelAdmin):
            list_filter = [
                "restaurant__place__country",
                "restaurant__place__country__name",
            ]

        ma = WaiterAdmin(Waiter, self.site)
        self.assertIs(
            ma.lookup_allowed("restaurant__place__country", "1", request),
            True,
        )
        self.assertIs(
            ma.lookup_allowed("restaurant__place__country__id__exact", "1", request),
            True,
        )
        self.assertIs(
            ma.lookup_allowed(
                "restaurant__place__country__name", "test_value", request
            ),
            True,
        )

    def test_lookup_allowed_considers_dynamic_list_filter(self):
        class ConcertAdmin(ModelAdmin):
            list_filter = ["main_band__sign_date"]

            def get_list_filter(self, request):
                """
                Returns the list of fields to filter on for the admin interface.

                The returned list includes the default filters defined in `list_filter`. If the
                current request is associated with an authenticated user, an additional filter
                for the main band name is also included, allowing for more fine-grained filtering
                of data based on user privileges.

                :return: A list of field names to filter on
                :rtype: list
                """
                if getattr(request, "user", None):
                    return self.list_filter + ["main_band__name"]
                return self.list_filter

        model_admin = ConcertAdmin(Concert, self.site)
        request_band_name_filter = RequestFactory().get(
            "/", {"main_band__name": "test"}
        )
        self.assertIs(
            model_admin.lookup_allowed(
                "main_band__sign_date", "?", request_band_name_filter
            ),
            True,
        )
        self.assertIs(
            model_admin.lookup_allowed(
                "main_band__name", "?", request_band_name_filter
            ),
            False,
        )
        request_with_superuser = request
        self.assertIs(
            model_admin.lookup_allowed(
                "main_band__sign_date", "?", request_with_superuser
            ),
            True,
        )
        self.assertIs(
            model_admin.lookup_allowed("main_band__name", "?", request_with_superuser),
            True,
        )

    def test_lookup_allowed_without_request_deprecation(self):
        class ConcertAdmin(ModelAdmin):
            list_filter = ["main_band__sign_date"]

            def get_list_filter(self, request):
                return self.list_filter + ["main_band__name"]

            def lookup_allowed(self, lookup, value):
                return True

        model_admin = ConcertAdmin(Concert, self.site)
        msg = (
            "`request` must be added to the signature of ModelAdminTests."
            "test_lookup_allowed_without_request_deprecation.<locals>."
            "ConcertAdmin.lookup_allowed()."
        )
        request_band_name_filter = RequestFactory().get(
            "/", {"main_band__name": "test"}
        )
        request_band_name_filter.user = User.objects.create_superuser(
            username="bob", email="bob@test.com", password="test"
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            changelist = model_admin.get_changelist_instance(request_band_name_filter)
            filterspec = changelist.get_filters(request_band_name_filter)[0][0]
            self.assertEqual(filterspec.title, "sign date")
            filterspec = changelist.get_filters(request_band_name_filter)[0][1]
            self.assertEqual(filterspec.title, "name")
            self.assertSequenceEqual(filterspec.lookup_choices, [self.band.name])

    def test_field_arguments(self):
        # If fields is specified, fieldsets_add and fieldsets_change should
        # just stick the fields into a formsets structure and return it.
        class BandAdmin(ModelAdmin):
            fields = ["name"]

        ma = BandAdmin(Band, self.site)

        self.assertEqual(list(ma.get_fields(request)), ["name"])
        self.assertEqual(list(ma.get_fields(request, self.band)), ["name"])
        self.assertEqual(ma.get_fieldsets(request), [(None, {"fields": ["name"]})])
        self.assertEqual(
            ma.get_fieldsets(request, self.band), [(None, {"fields": ["name"]})]
        )

    def test_field_arguments_restricted_on_form(self):
        # If fields or fieldsets is specified, it should exclude fields on the
        # Form class to the fields specified. This may cause errors to be
        # raised in the db layer if required model fields aren't in fields/
        # fieldsets, but that's preferable to ghost errors where a field in the
        # Form class isn't being displayed because it's not in fields/fieldsets.

        # Using `fields`.
        """
        Tests that field arguments are restricted on the admin form.

        This test ensures that the fields displayed on the admin form are correctly
        limited based on the `fields`, `fieldsets`, and `exclude` attributes defined
        on the ModelAdmin class. It checks that the correct fields are displayed for
        both the add and change forms, and that the `fields` and `exclude` arguments
        are applied as expected, even when used in combination.

        The test covers various scenarios, including specifying fields explicitly,
        defining fieldsets, excluding fields, and using both `fields` and `exclude`
        together to restrict the displayed fields. The goal is to verify that the
        admin form only shows the intended fields, while hiding the rest, and that
        the restrictions are enforced consistently across different admin forms.
        """
        class BandAdmin(ModelAdmin):
            fields = ["name"]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["name"])
        self.assertEqual(list(ma.get_form(request, self.band).base_fields), ["name"])

        # Using `fieldsets`.
        class BandAdmin(ModelAdmin):
            fieldsets = [(None, {"fields": ["name"]})]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["name"])
        self.assertEqual(list(ma.get_form(request, self.band).base_fields), ["name"])

        # Using `exclude`.
        class BandAdmin(ModelAdmin):
            exclude = ["bio"]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["name", "sign_date"])

        # You can also pass a tuple to `exclude`.
        class BandAdmin(ModelAdmin):
            exclude = ("bio",)

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["name", "sign_date"])

        # Using `fields` and `exclude`.
        class BandAdmin(ModelAdmin):
            fields = ["name", "bio"]
            exclude = ["bio"]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["name"])

    def test_custom_form_meta_exclude_with_readonly(self):
        """
        The custom ModelForm's `Meta.exclude` is respected when used in
        conjunction with `ModelAdmin.readonly_fields` and when no
        `ModelAdmin.exclude` is defined (#14496).
        """

        # With ModelAdmin
        class AdminBandForm(forms.ModelForm):
            class Meta:
                model = Band
                exclude = ["bio"]

        class BandAdmin(ModelAdmin):
            readonly_fields = ["name"]
            form = AdminBandForm

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["sign_date"])

        # With InlineModelAdmin
        class AdminConcertForm(forms.ModelForm):
            class Meta:
                model = Concert
                exclude = ["day"]

        class ConcertInline(TabularInline):
            readonly_fields = ["transport"]
            form = AdminConcertForm
            fk_name = "main_band"
            model = Concert

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(
            list(list(ma.get_formsets_with_inlines(request))[0][0]().forms[0].fields),
            ["main_band", "opening_band", "id", "DELETE"],
        )

    def test_custom_formfield_override_readonly(self):
        """

        Test that a custom form field can be overridden to be read-only in the admin interface.

        This test verifies that the admin form for the Band model will exclude fields marked as read-only
        from the base fields, but will still include them in the fields and fieldsets lists.

        The test checks the following:

        * The base fields of the admin form exclude the read-only field ('name')
        * The fields list of the admin form includes both editable and read-only fields
        * The fieldsets list of the admin form includes all fields, including the read-only field

        """
        class AdminBandForm(forms.ModelForm):
            name = forms.CharField()

            class Meta:
                exclude = ()
                model = Band

        class BandAdmin(ModelAdmin):
            form = AdminBandForm
            readonly_fields = ["name"]

        ma = BandAdmin(Band, self.site)

        # `name` shouldn't appear in base_fields because it's part of
        # readonly_fields.
        self.assertEqual(list(ma.get_form(request).base_fields), ["bio", "sign_date"])
        # But it should appear in get_fields()/fieldsets() so it can be
        # displayed as read-only.
        self.assertEqual(list(ma.get_fields(request)), ["bio", "sign_date", "name"])
        self.assertEqual(
            list(ma.get_fieldsets(request)),
            [(None, {"fields": ["bio", "sign_date", "name"]})],
        )

    def test_custom_form_meta_exclude(self):
        """
        The custom ModelForm's `Meta.exclude` is overridden if
        `ModelAdmin.exclude` or `InlineModelAdmin.exclude` are defined (#14496).
        """

        # With ModelAdmin
        class AdminBandForm(forms.ModelForm):
            class Meta:
                model = Band
                exclude = ["bio"]

        class BandAdmin(ModelAdmin):
            exclude = ["name"]
            form = AdminBandForm

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["bio", "sign_date"])

        # With InlineModelAdmin
        class AdminConcertForm(forms.ModelForm):
            class Meta:
                model = Concert
                exclude = ["day"]

        class ConcertInline(TabularInline):
            exclude = ["transport"]
            form = AdminConcertForm
            fk_name = "main_band"
            model = Concert

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(
            list(list(ma.get_formsets_with_inlines(request))[0][0]().forms[0].fields),
            ["main_band", "opening_band", "day", "id", "DELETE"],
        )

    def test_overriding_get_exclude(self):
        """

        Checks if the get_exclude method is properly overridden in a ModelAdmin subclass.

        This test verifies that when get_exclude is implemented in a ModelAdmin subclass,
        it correctly excludes the specified fields from the form. The test ensures that
        the overridden method supersedes the default behavior, allowing for customizable
        field exclusion in the admin interface.

        """
        class BandAdmin(ModelAdmin):
            def get_exclude(self, request, obj=None):
                return ["name"]

        self.assertEqual(
            list(BandAdmin(Band, self.site).get_form(request).base_fields),
            ["bio", "sign_date"],
        )

    def test_get_exclude_overrides_exclude(self):
        class BandAdmin(ModelAdmin):
            exclude = ["bio"]

            def get_exclude(self, request, obj=None):
                return ["name"]

        self.assertEqual(
            list(BandAdmin(Band, self.site).get_form(request).base_fields),
            ["bio", "sign_date"],
        )

    def test_get_exclude_takes_obj(self):
        """

        Tests the get_exclude method of a ModelAdmin class to ensure it correctly 
        excludes fields based on the presence of an object.

        The get_exclude method should return a list of field names to exclude from 
        the form when the method is called. If an object is provided, it should 
        exclude the 'sign_date' field; otherwise, it should exclude the 'name' field.

        This test case verifies that the get_exclude method behaves as expected 
        when an object is present, by checking the fields that are included in 
        the form. The test checks that the 'name' and 'bio' fields are present 
        in the form when an object is provided, demonstrating that 'sign_date' 
        is correctly excluded.

        """
        class BandAdmin(ModelAdmin):
            def get_exclude(self, request, obj=None):
                """
                Returns a list of field names to exclude from the model.

                The set of excluded fields depends on the presence of an object (`obj`).
                If an object is provided, the function excludes the 'sign_date' field.
                Otherwise, it excludes the 'name' field.

                :param request: The current request
                :param obj: Optional object to determine the excluded fields
                :returns: List of field names to exclude
                """
                if obj:
                    return ["sign_date"]
                return ["name"]

        self.assertEqual(
            list(BandAdmin(Band, self.site).get_form(request, self.band).base_fields),
            ["name", "bio"],
        )

    def test_custom_form_validation(self):
        # If a form is specified, it should use it allowing custom validation
        # to work properly. This won't break any of the admin widgets or media.
        """

        Tests the validation of a custom form used in the BandAdmin model.

        Verifies that the form contains the expected fields, including name, bio, sign_date, and a delete checkbox.
        Additionally, checks that the sign_date field is rendered using the AdminDateWidget.

        """
        class AdminBandForm(forms.ModelForm):
            delete = forms.BooleanField()

        class BandAdmin(ModelAdmin):
            form = AdminBandForm

        ma = BandAdmin(Band, self.site)
        self.assertEqual(
            list(ma.get_form(request).base_fields),
            ["name", "bio", "sign_date", "delete"],
        )
        self.assertEqual(
            type(ma.get_form(request).base_fields["sign_date"].widget), AdminDateWidget
        )

    def test_form_exclude_kwarg_override(self):
        """
        The `exclude` kwarg passed to `ModelAdmin.get_form()` overrides all
        other declarations (#8999).
        """

        class AdminBandForm(forms.ModelForm):
            class Meta:
                model = Band
                exclude = ["name"]

        class BandAdmin(ModelAdmin):
            exclude = ["sign_date"]
            form = AdminBandForm

            def get_form(self, request, obj=None, **kwargs):
                """

                Retrieves a form instance, optionally bound to an existing object.

                The form returned by this method excludes the 'bio' field. This allows for 
                more fine-grained control over the data collected by the form.

                :param request: The current request object.
                :param obj: An optional object to bind the form to. If provided, the form 
                            will be populated with the object's data.
                :param kwargs: Additional keyword arguments to pass to the form constructor.

                :return: A form instance, either bound to the provided object or unbound.

                """
                kwargs["exclude"] = ["bio"]
                return super().get_form(request, obj, **kwargs)

        ma = BandAdmin(Band, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["name", "sign_date"])

    def test_formset_exclude_kwarg_override(self):
        """
        The `exclude` kwarg passed to `InlineModelAdmin.get_formset()`
        overrides all other declarations (#8999).
        """

        class AdminConcertForm(forms.ModelForm):
            class Meta:
                model = Concert
                exclude = ["day"]

        class ConcertInline(TabularInline):
            exclude = ["transport"]
            form = AdminConcertForm
            fk_name = "main_band"
            model = Concert

            def get_formset(self, request, obj=None, **kwargs):
                """
                Get a formset for the current object, modifying the default formset to exclude the 'opening_band' field.

                :param request: The current request object.
                :param obj: The object instance for which the formset is being retrieved, defaults to None.
                :param kwargs: Additional keyword arguments to be passed to the parent class's get_formset method.
                :return: A formset instance with the 'opening_band' field excluded.
                """
                kwargs["exclude"] = ["opening_band"]
                return super().get_formset(request, obj, **kwargs)

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(
            list(list(ma.get_formsets_with_inlines(request))[0][0]().forms[0].fields),
            ["main_band", "day", "transport", "id", "DELETE"],
        )

    def test_formset_overriding_get_exclude_with_form_fields(self):
        class AdminConcertForm(forms.ModelForm):
            class Meta:
                model = Concert
                fields = ["main_band", "opening_band", "day", "transport"]

        class ConcertInline(TabularInline):
            form = AdminConcertForm
            fk_name = "main_band"
            model = Concert

            def get_exclude(self, request, obj=None):
                return ["opening_band"]

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(
            list(list(ma.get_formsets_with_inlines(request))[0][0]().forms[0].fields),
            ["main_band", "day", "transport", "id", "DELETE"],
        )

    def test_formset_overriding_get_exclude_with_form_exclude(self):
        class AdminConcertForm(forms.ModelForm):
            class Meta:
                model = Concert
                exclude = ["day"]

        class ConcertInline(TabularInline):
            form = AdminConcertForm
            fk_name = "main_band"
            model = Concert

            def get_exclude(self, request, obj=None):
                return ["opening_band"]

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(
            list(list(ma.get_formsets_with_inlines(request))[0][0]().forms[0].fields),
            ["main_band", "day", "transport", "id", "DELETE"],
        )

    def test_raw_id_fields_widget_override(self):
        """
        The autocomplete_fields, raw_id_fields, and radio_fields widgets may
        overridden by specifying a widget in get_formset().
        """

        class ConcertInline(TabularInline):
            model = Concert
            fk_name = "main_band"
            raw_id_fields = ("opening_band",)

            def get_formset(self, request, obj=None, **kwargs):
                kwargs["widgets"] = {"opening_band": Select}
                return super().get_formset(request, obj, **kwargs)

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, self.site)
        band_widget = (
            list(ma.get_formsets_with_inlines(request))[0][0]()
            .forms[0]
            .fields["opening_band"]
            .widget
        )
        # Without the override this would be ForeignKeyRawIdWidget.
        self.assertIsInstance(band_widget, Select)

    def test_queryset_override(self):
        # If the queryset of a ModelChoiceField in a custom form is overridden,
        # RelatedFieldWidgetWrapper doesn't mess that up.
        """
        Tests the override of a queryset for a field in a ModelAdmin form.

        This test case verifies that a custom queryset can be applied to a field in a ModelAdmin form,
        overriding the default queryset provided by Django. It checks that the custom queryset is used
        to populate the field's options in the form, and that only the instances specified in the
        queryset are included in the form.

        The test covers two scenarios: the default queryset and a custom queryset. In the former,
        it checks that all instances are displayed in the form, while in the latter, it verifies that
        only the instances specified in the custom queryset are included in the form options.
        """
        band2 = Band.objects.create(
            name="The Beatles", bio="", sign_date=date(1962, 1, 1)
        )

        ma = ModelAdmin(Concert, self.site)
        form = ma.get_form(request)()

        self.assertHTMLEqual(
            str(form["main_band"]),
            '<div class="related-widget-wrapper" data-model-ref="band">'
            '<select data-context="available-source" '
            'name="main_band" id="id_main_band" required>'
            '<option value="" selected>---------</option>'
            '<option value="%d">The Beatles</option>'
            '<option value="%d">The Doors</option>'
            "</select></div>" % (band2.id, self.band.id),
        )

        class AdminConcertForm(forms.ModelForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["main_band"].queryset = Band.objects.filter(
                    name="The Doors"
                )

        class ConcertAdminWithForm(ModelAdmin):
            form = AdminConcertForm

        ma = ConcertAdminWithForm(Concert, self.site)
        form = ma.get_form(request)()

        self.assertHTMLEqual(
            str(form["main_band"]),
            '<div class="related-widget-wrapper" data-model-ref="band">'
            '<select data-context="available-source" '
            'name="main_band" id="id_main_band" required>'
            '<option value="" selected>---------</option>'
            '<option value="%d">The Doors</option>'
            "</select></div>" % self.band.id,
        )

    def test_regression_for_ticket_15820(self):
        """
        `obj` is passed from `InlineModelAdmin.get_fieldsets()` to
        `InlineModelAdmin.get_formset()`.
        """

        class CustomConcertForm(forms.ModelForm):
            class Meta:
                model = Concert
                fields = ["day"]

        class ConcertInline(TabularInline):
            model = Concert
            fk_name = "main_band"

            def get_formset(self, request, obj=None, **kwargs):
                """
                Returns a formset for the current view, allowing for the creation or editing of objects.

                The returned formset is customized based on whether an object is being edited. If an object is provided, the formset will utilize a :class:`CustomConcertForm` to validate and process user input. Otherwise, the default form will be used.

                :param request: The current HTTP request.
                :param obj: The object being edited, or None if a new object is being created.
                :param kwargs: Additional keyword arguments to be passed to the parent class's get_formset method.
                :return: A formset instance.
                """
                if obj:
                    kwargs["form"] = CustomConcertForm
                return super().get_formset(request, obj, **kwargs)

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        Concert.objects.create(main_band=self.band, opening_band=self.band, day=1)
        ma = BandAdmin(Band, self.site)
        inline_instances = ma.get_inline_instances(request)
        fieldsets = list(inline_instances[0].get_fieldsets(request))
        self.assertEqual(
            fieldsets[0][1]["fields"], ["main_band", "opening_band", "day", "transport"]
        )
        fieldsets = list(
            inline_instances[0].get_fieldsets(request, inline_instances[0].model)
        )
        self.assertEqual(fieldsets[0][1]["fields"], ["day"])

    # radio_fields behavior ###########################################

    def test_default_foreign_key_widget(self):
        # First, without any radio_fields specified, the widgets for ForeignKey
        # and fields with choices specified ought to be a basic Select widget.
        # ForeignKey widgets in the admin are wrapped with RelatedFieldWidgetWrapper so
        # they need to be handled properly when type checking. For Select fields, all of
        # the choices lists have a first entry of dashes.
        cma = ModelAdmin(Concert, self.site)
        cmafa = cma.get_form(request)

        self.assertEqual(type(cmafa.base_fields["main_band"].widget.widget), Select)
        self.assertEqual(
            list(cmafa.base_fields["main_band"].widget.choices),
            [("", "---------"), (self.band.id, "The Doors")],
        )

        self.assertEqual(type(cmafa.base_fields["opening_band"].widget.widget), Select)
        self.assertEqual(
            list(cmafa.base_fields["opening_band"].widget.choices),
            [("", "---------"), (self.band.id, "The Doors")],
        )
        self.assertEqual(type(cmafa.base_fields["day"].widget), Select)
        self.assertEqual(
            list(cmafa.base_fields["day"].widget.choices),
            [("", "---------"), (1, "Fri"), (2, "Sat")],
        )
        self.assertEqual(type(cmafa.base_fields["transport"].widget), Select)
        self.assertEqual(
            list(cmafa.base_fields["transport"].widget.choices),
            [("", "---------"), (1, "Plane"), (2, "Train"), (3, "Bus")],
        )

    def test_foreign_key_as_radio_field(self):
        # Now specify all the fields as radio_fields.  Widgets should now be
        # RadioSelect, and the choices list should have a first entry of 'None' if
        # blank=True for the model field.  Finally, the widget should have the
        # 'radiolist' attr, and 'inline' as well if the field is specified HORIZONTAL.
        class ConcertAdmin(ModelAdmin):
            radio_fields = {
                "main_band": HORIZONTAL,
                "opening_band": VERTICAL,
                "day": VERTICAL,
                "transport": HORIZONTAL,
            }

        cma = ConcertAdmin(Concert, self.site)
        cmafa = cma.get_form(request)

        self.assertEqual(
            type(cmafa.base_fields["main_band"].widget.widget), AdminRadioSelect
        )
        self.assertEqual(
            cmafa.base_fields["main_band"].widget.attrs,
            {"class": "radiolist inline", "data-context": "available-source"},
        )
        self.assertEqual(
            list(cmafa.base_fields["main_band"].widget.choices),
            [(self.band.id, "The Doors")],
        )

        self.assertEqual(
            type(cmafa.base_fields["opening_band"].widget.widget), AdminRadioSelect
        )
        self.assertEqual(
            cmafa.base_fields["opening_band"].widget.attrs,
            {"class": "radiolist", "data-context": "available-source"},
        )
        self.assertEqual(
            list(cmafa.base_fields["opening_band"].widget.choices),
            [("", "None"), (self.band.id, "The Doors")],
        )
        self.assertEqual(type(cmafa.base_fields["day"].widget), AdminRadioSelect)
        self.assertEqual(cmafa.base_fields["day"].widget.attrs, {"class": "radiolist"})
        self.assertEqual(
            list(cmafa.base_fields["day"].widget.choices), [(1, "Fri"), (2, "Sat")]
        )

        self.assertEqual(type(cmafa.base_fields["transport"].widget), AdminRadioSelect)
        self.assertEqual(
            cmafa.base_fields["transport"].widget.attrs, {"class": "radiolist inline"}
        )
        self.assertEqual(
            list(cmafa.base_fields["transport"].widget.choices),
            [("", "None"), (1, "Plane"), (2, "Train"), (3, "Bus")],
        )

        class AdminConcertForm(forms.ModelForm):
            class Meta:
                model = Concert
                exclude = ("transport",)

        class ConcertAdmin(ModelAdmin):
            form = AdminConcertForm

        ma = ConcertAdmin(Concert, self.site)
        self.assertEqual(
            list(ma.get_form(request).base_fields), ["main_band", "opening_band", "day"]
        )

        class AdminConcertForm(forms.ModelForm):
            extra = forms.CharField()

            class Meta:
                model = Concert
                fields = ["extra", "transport"]

        class ConcertAdmin(ModelAdmin):
            form = AdminConcertForm

        ma = ConcertAdmin(Concert, self.site)
        self.assertEqual(list(ma.get_form(request).base_fields), ["extra", "transport"])

        class ConcertInline(TabularInline):
            form = AdminConcertForm
            model = Concert
            fk_name = "main_band"
            can_delete = True

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, self.site)
        self.assertEqual(
            list(list(ma.get_formsets_with_inlines(request))[0][0]().forms[0].fields),
            ["extra", "transport", "id", "DELETE", "main_band"],
        )

    def test_log_actions(self):
        """
        Tests the logging of actions for a ModelAdmin instance.

        Verifies that the log_addition and log_change methods correctly create LogEntry
        objects with the expected attributes. The test covers various scenarios, including
        adding and changing objects, and checks that the LogEntry objects contain the
        correct information about the action, including the action flag, content type,
        object ID, user, change message, and object representation.

        The test ensures that the logging functionality works as expected, providing a
        mechanism for tracking changes to model instances.

        """
        ma = ModelAdmin(Band, self.site)
        mock_request = MockRequest()
        mock_request.user = User.objects.create(username="bill")
        content_type = get_content_type_for_model(self.band)
        tests = (
            (ma.log_addition, ADDITION, {"added": {}}),
            (ma.log_change, CHANGE, {"changed": {"fields": ["name", "bio"]}}),
        )
        for method, flag, message in tests:
            with self.subTest(name=method.__name__):
                created = method(mock_request, self.band, message)
                fetched = LogEntry.objects.filter(action_flag=flag).latest("id")
                self.assertEqual(created, fetched)
                self.assertEqual(fetched.action_flag, flag)
                self.assertEqual(fetched.content_type, content_type)
                self.assertEqual(fetched.object_id, str(self.band.pk))
                self.assertEqual(fetched.user, mock_request.user)
                self.assertEqual(fetched.change_message, str(message))
                self.assertEqual(fetched.object_repr, str(self.band))

    def test_log_deletions(self):
        """

        Tests the logging of deletions performed by the ModelAdmin.

        Verifies that when a queryset of objects is deleted, a log entry is created 
        for each object, containing the user who performed the deletion, the type of 
        object deleted, and the object's identifier.

        The test ensures that the log entries are created with a single database query 
        and that their contents match the expected values.

        """
        ma = ModelAdmin(Band, self.site)
        mock_request = MockRequest()
        mock_request.user = User.objects.create(username="akash")
        content_type = get_content_type_for_model(self.band)
        Band.objects.create(
            name="The Beatles",
            bio="A legendary rock band from Liverpool.",
            sign_date=date(1962, 1, 1),
        )
        Band.objects.create(
            name="Mohiner Ghoraguli",
            bio="A progressive rock band from Calcutta.",
            sign_date=date(1975, 1, 1),
        )
        queryset = Band.objects.all().order_by("-id")[:3]
        self.assertEqual(len(queryset), 3)
        with self.assertNumQueries(1):
            ma.log_deletions(mock_request, queryset)
        logs = (
            LogEntry.objects.filter(action_flag=DELETION)
            .order_by("id")
            .values_list(
                "user_id",
                "content_type",
                "object_id",
                "object_repr",
                "action_flag",
                "change_message",
            )
        )
        expected_log_values = [
            (
                mock_request.user.id,
                content_type.id,
                str(obj.pk),
                str(obj),
                DELETION,
                "",
            )
            for obj in queryset
        ]
        self.assertSequenceEqual(logs, expected_log_values)

    # RemovedInDjango60Warning.
    def test_log_deletion(self):
        """

        Test the log_deletion method of the ModelAdmin class.

        This test case checks the functionality of logging when a model instance is deleted.
        It verifies that a LogEntry is created with the correct attributes, including action flag,
        content type, object ID, user, and object representation.

        It also tests for a deprecation warning, as the log_deletion method is deprecated
        in favor of log_deletions.

        The test ensures that the created LogEntry matches the latest LogEntry fetched from
        the database, confirming that the log_deletion method behaves as expected.

        """
        ma = ModelAdmin(Band, self.site)
        mock_request = MockRequest()
        mock_request.user = User.objects.create(username="bill")
        content_type = get_content_type_for_model(self.band)
        msg = "ModelAdmin.log_deletion() is deprecated. Use log_deletions() instead."
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            created = ma.log_deletion(mock_request, self.band, str(self.band))
        fetched = LogEntry.objects.filter(action_flag=DELETION).latest("id")
        self.assertEqual(created, fetched)
        self.assertEqual(fetched.action_flag, DELETION)
        self.assertEqual(fetched.content_type, content_type)
        self.assertEqual(fetched.object_id, str(self.band.pk))
        self.assertEqual(fetched.user, mock_request.user)
        self.assertEqual(fetched.change_message, "")
        self.assertEqual(fetched.object_repr, str(self.band))

    # RemovedInDjango60Warning.
    def test_log_deletion_fallback(self):
        """
        Tests the fallback behavior of the log_deletion method when the log_deletions method 
        is not implemented.

        This test checks that when log_deletions is called but not implemented, 
        it falls back to calling log_deletion for each object in the queryset, 
        and all the deletion logs are recorded successfully. It also verifies 
        that the correct deprecation warning is raised.

        The test covers the following scenarios:

        - Successful creation of log entries for deleted objects
        - Deprecation warning is raised when log_deletion is used
        - Log entries contain the correct information about the deleted objects
        """
        class InheritedModelAdmin(ModelAdmin):
            def log_deletion(self, request, obj, object_repr):
                return super().log_deletion(request, obj, object_repr)

        ima = InheritedModelAdmin(Band, self.site)
        mock_request = MockRequest()
        mock_request.user = User.objects.create(username="akash")
        content_type = get_content_type_for_model(self.band)
        Band.objects.create(
            name="The Beatles",
            bio="A legendary rock band from Liverpool.",
            sign_date=date(1962, 1, 1),
        )
        Band.objects.create(
            name="Mohiner Ghoraguli",
            bio="A progressive rock band from Calcutta.",
            sign_date=date(1975, 1, 1),
        )
        queryset = Band.objects.all().order_by("-id")[:3]
        self.assertEqual(len(queryset), 3)
        msg = (
            "The usage of log_deletion() is deprecated. Implement log_deletions() "
            "instead."
        )
        with self.assertNumQueries(3):
            with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
                ima.log_deletions(mock_request, queryset)
        logs = (
            LogEntry.objects.filter(action_flag=DELETION)
            .order_by("id")
            .values_list(
                "user_id",
                "content_type",
                "object_id",
                "object_repr",
                "action_flag",
                "change_message",
            )
        )
        expected_log_values = [
            (
                mock_request.user.id,
                content_type.id,
                str(obj.pk),
                str(obj),
                DELETION,
                "",
            )
            for obj in queryset
        ]
        self.assertSequenceEqual(logs, expected_log_values)

    def test_get_autocomplete_fields(self):
        class NameAdmin(ModelAdmin):
            search_fields = ["name"]

        class SongAdmin(ModelAdmin):
            autocomplete_fields = ["featuring"]
            fields = ["featuring", "band"]

        class OtherSongAdmin(SongAdmin):
            def get_autocomplete_fields(self, request):
                return ["band"]

        self.site.register(Band, NameAdmin)
        try:
            # Uses autocomplete_fields if not overridden.
            model_admin = SongAdmin(Song, self.site)
            form = model_admin.get_form(request)()
            self.assertIsInstance(
                form.fields["featuring"].widget.widget, AutocompleteSelectMultiple
            )
            # Uses overridden get_autocomplete_fields
            model_admin = OtherSongAdmin(Song, self.site)
            form = model_admin.get_form(request)()
            self.assertIsInstance(form.fields["band"].widget.widget, AutocompleteSelect)
        finally:
            self.site.unregister(Band)

    def test_get_deleted_objects(self):
        """

        Tests the get_deleted_objects method of the ModelAdmin class.

        This test case checks the accuracy of the get_deleted_objects method in handling the deletion of objects.
        It verifies that the method correctly identifies the objects to be deleted, the model count, permissions needed, and protected objects.
        The test creates a mock request with a superuser and registers the Band model with the ModelAdmin class.
        It then retrieves the ModelAdmin instance for the Band model and calls the get_deleted_objects method with a list of objects to be deleted.
        The test asserts that the method returns the expected results, including the list of deletable objects, model count, permissions needed, and protected objects.

        """
        mock_request = MockRequest()
        mock_request.user = User.objects.create_superuser(
            username="bob", email="bob@test.com", password="test"
        )
        self.site.register(Band, ModelAdmin)
        ma = self.site.get_model_admin(Band)
        (
            deletable_objects,
            model_count,
            perms_needed,
            protected,
        ) = ma.get_deleted_objects([self.band], request)
        self.assertEqual(deletable_objects, ["Band: The Doors"])
        self.assertEqual(model_count, {"bands": 1})
        self.assertEqual(perms_needed, set())
        self.assertEqual(protected, [])

    def test_get_deleted_objects_with_custom_has_delete_permission(self):
        """
        ModelAdmin.get_deleted_objects() uses ModelAdmin.has_delete_permission()
        for permissions checking.
        """
        mock_request = MockRequest()
        mock_request.user = User.objects.create_superuser(
            username="bob", email="bob@test.com", password="test"
        )

        class TestModelAdmin(ModelAdmin):
            def has_delete_permission(self, request, obj=None):
                return False

        self.site.register(Band, TestModelAdmin)
        ma = self.site.get_model_admin(Band)
        (
            deletable_objects,
            model_count,
            perms_needed,
            protected,
        ) = ma.get_deleted_objects([self.band], request)
        self.assertEqual(deletable_objects, ["Band: The Doors"])
        self.assertEqual(model_count, {"bands": 1})
        self.assertEqual(perms_needed, {"band"})
        self.assertEqual(protected, [])

    def test_modeladmin_repr(self):
        ma = ModelAdmin(Band, self.site)
        self.assertEqual(
            repr(ma),
            "<ModelAdmin: model=Band site=AdminSite(name='admin')>",
        )


class ModelAdminPermissionTests(SimpleTestCase):
    class MockUser:
        def has_module_perms(self, app_label):
            return app_label == "modeladmin"

    class MockViewUser(MockUser):
        def has_perm(self, perm, obj=None):
            return perm == "modeladmin.view_band"

    class MockAddUser(MockUser):
        def has_perm(self, perm, obj=None):
            return perm == "modeladmin.add_band"

    class MockChangeUser(MockUser):
        def has_perm(self, perm, obj=None):
            return perm == "modeladmin.change_band"

    class MockDeleteUser(MockUser):
        def has_perm(self, perm, obj=None):
            return perm == "modeladmin.delete_band"

    def test_has_view_permission(self):
        """
        has_view_permission() returns True for users who can view objects and
        False for users who can't.
        """
        ma = ModelAdmin(Band, AdminSite())
        request = MockRequest()
        request.user = self.MockViewUser()
        self.assertIs(ma.has_view_permission(request), True)
        request.user = self.MockAddUser()
        self.assertIs(ma.has_view_permission(request), False)
        request.user = self.MockChangeUser()
        self.assertIs(ma.has_view_permission(request), True)
        request.user = self.MockDeleteUser()
        self.assertIs(ma.has_view_permission(request), False)

    def test_has_add_permission(self):
        """
        has_add_permission returns True for users who can add objects and
        False for users who can't.
        """
        ma = ModelAdmin(Band, AdminSite())
        request = MockRequest()
        request.user = self.MockViewUser()
        self.assertFalse(ma.has_add_permission(request))
        request.user = self.MockAddUser()
        self.assertTrue(ma.has_add_permission(request))
        request.user = self.MockChangeUser()
        self.assertFalse(ma.has_add_permission(request))
        request.user = self.MockDeleteUser()
        self.assertFalse(ma.has_add_permission(request))

    def test_inline_has_add_permission_uses_obj(self):
        """

        Tests the has_add_permission method of an inline admin interface.

        This test validates that when the has_add_permission method of an inline 
        class returns False (i.e., when the object being edited does not exist), 
        the inline instances are not returned by the model admin. Conversely, 
        when the object exists and has_add_permission returns True, the inline 
        instances are correctly returned. The test specifically checks this 
        behavior in the context of a BandAdmin with ConcertInline instances.

        The test covers the following scenarios:

        * When no object is being edited, the inline instances are not returned.
        * When an object is being edited and has_add_permission returns True, 
          the inline instances are returned.

        The purpose of this test is to ensure that the has_add_permission method 
        of an inline class is correctly used to determine whether to display 
        the inline instances in the admin interface.

        """
        class ConcertInline(TabularInline):
            model = Concert

            def has_add_permission(self, request, obj):
                return bool(obj)

        class BandAdmin(ModelAdmin):
            inlines = [ConcertInline]

        ma = BandAdmin(Band, AdminSite())
        request = MockRequest()
        request.user = self.MockAddUser()
        self.assertEqual(ma.get_inline_instances(request), [])
        band = Band(name="The Doors", bio="", sign_date=date(1965, 1, 1))
        inline_instances = ma.get_inline_instances(request, band)
        self.assertEqual(len(inline_instances), 1)
        self.assertIsInstance(inline_instances[0], ConcertInline)

    def test_has_change_permission(self):
        """
        has_change_permission returns True for users who can edit objects and
        False for users who can't.
        """
        ma = ModelAdmin(Band, AdminSite())
        request = MockRequest()
        request.user = self.MockViewUser()
        self.assertIs(ma.has_change_permission(request), False)
        request.user = self.MockAddUser()
        self.assertFalse(ma.has_change_permission(request))
        request.user = self.MockChangeUser()
        self.assertTrue(ma.has_change_permission(request))
        request.user = self.MockDeleteUser()
        self.assertFalse(ma.has_change_permission(request))

    def test_has_delete_permission(self):
        """
        has_delete_permission returns True for users who can delete objects and
        False for users who can't.
        """
        ma = ModelAdmin(Band, AdminSite())
        request = MockRequest()
        request.user = self.MockViewUser()
        self.assertIs(ma.has_delete_permission(request), False)
        request.user = self.MockAddUser()
        self.assertFalse(ma.has_delete_permission(request))
        request.user = self.MockChangeUser()
        self.assertFalse(ma.has_delete_permission(request))
        request.user = self.MockDeleteUser()
        self.assertTrue(ma.has_delete_permission(request))

    def test_has_module_permission(self):
        """
        as_module_permission returns True for users who have any permission
        for the module and False for users who don't.
        """
        ma = ModelAdmin(Band, AdminSite())
        request = MockRequest()
        request.user = self.MockViewUser()
        self.assertIs(ma.has_module_permission(request), True)
        request.user = self.MockAddUser()
        self.assertTrue(ma.has_module_permission(request))
        request.user = self.MockChangeUser()
        self.assertTrue(ma.has_module_permission(request))
        request.user = self.MockDeleteUser()
        self.assertTrue(ma.has_module_permission(request))

        original_app_label = ma.opts.app_label
        ma.opts.app_label = "anotherapp"
        try:
            request.user = self.MockViewUser()
            self.assertIs(ma.has_module_permission(request), False)
            request.user = self.MockAddUser()
            self.assertFalse(ma.has_module_permission(request))
            request.user = self.MockChangeUser()
            self.assertFalse(ma.has_module_permission(request))
            request.user = self.MockDeleteUser()
            self.assertFalse(ma.has_module_permission(request))
        finally:
            ma.opts.app_label = original_app_label
