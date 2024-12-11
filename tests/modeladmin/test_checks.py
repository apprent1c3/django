from django import forms
from django.contrib import admin
from django.contrib.admin import BooleanFieldListFilter, SimpleListFilter
from django.contrib.admin.options import VERTICAL, ModelAdmin, TabularInline
from django.contrib.admin.sites import AdminSite
from django.core.checks import Error
from django.db.models import CASCADE, F, Field, ForeignKey, ManyToManyField, Model
from django.db.models.functions import Upper
from django.forms.models import BaseModelFormSet
from django.test import SimpleTestCase
from django.test.utils import isolate_apps

from .models import Band, Song, User, ValidationTestInlineModel, ValidationTestModel


class CheckTestCase(SimpleTestCase):
    def assertIsInvalid(
        self,
        model_admin,
        model,
        msg,
        id=None,
        hint=None,
        invalid_obj=None,
        admin_site=None,
    ):
        if admin_site is None:
            admin_site = AdminSite()
        invalid_obj = invalid_obj or model_admin
        admin_obj = model_admin(model, admin_site)
        self.assertEqual(
            admin_obj.check(), [Error(msg, hint=hint, obj=invalid_obj, id=id)]
        )

    def assertIsInvalidRegexp(
        self, model_admin, model, msg, id=None, hint=None, invalid_obj=None
    ):
        """
        Same as assertIsInvalid but treats the given msg as a regexp.
        """
        invalid_obj = invalid_obj or model_admin
        admin_obj = model_admin(model, AdminSite())
        errors = admin_obj.check()
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(error.hint, hint)
        self.assertEqual(error.obj, invalid_obj)
        self.assertEqual(error.id, id)
        self.assertRegex(error.msg, msg)

    def assertIsValid(self, model_admin, model, admin_site=None):
        if admin_site is None:
            admin_site = AdminSite()
        admin_obj = model_admin(model, admin_site)
        self.assertEqual(admin_obj.check(), [])


class RawIdCheckTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            raw_id_fields = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'raw_id_fields' must be a list or tuple.",
            "admin.E001",
        )

    def test_missing_field(self):
        class TestModelAdmin(ModelAdmin):
            raw_id_fields = ["non_existent_field"]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'raw_id_fields[0]' refers to 'non_existent_field', "
            "which is not a field of 'modeladmin.ValidationTestModel'.",
            "admin.E002",
        )

    def test_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            raw_id_fields = ("name",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'raw_id_fields[0]' must be a foreign key or a "
            "many-to-many field.",
            "admin.E003",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            raw_id_fields = ("users",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_field_attname(self):
        class TestModelAdmin(ModelAdmin):
            raw_id_fields = ["band_id"]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'raw_id_fields[0]' refers to 'band_id', which is "
            "not a field of 'modeladmin.ValidationTestModel'.",
            "admin.E002",
        )


class FieldsetsCheckTests(CheckTestCase):
    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = (("General", {"fields": ("name",)}),)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets' must be a list or tuple.",
            "admin.E007",
        )

    def test_non_iterable_item(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = ({},)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets[0]' must be a list or tuple.",
            "admin.E008",
        )

    def test_item_not_a_pair(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = ((),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets[0]' must be of length 2.",
            "admin.E009",
        )

    def test_second_element_of_item_not_a_dict(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = (("General", ()),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets[0][1]' must be a dictionary.",
            "admin.E010",
        )

    def test_missing_fields_key(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = (("General", {}),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets[0][1]' must contain the key 'fields'.",
            "admin.E011",
        )

        class TestModelAdmin(ModelAdmin):
            fieldsets = (("General", {"fields": ("name",)}),)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_specified_both_fields_and_fieldsets(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = (("General", {"fields": ("name",)}),)
            fields = ["name"]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "Both 'fieldsets' and 'fields' are specified.",
            "admin.E005",
        )

    def test_duplicate_fields(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = [(None, {"fields": ["name", "name"]})]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "There are duplicate field(s) in 'fieldsets[0][1]'.",
            "admin.E012",
        )

    def test_duplicate_fields_in_fieldsets(self):
        class TestModelAdmin(ModelAdmin):
            fieldsets = [
                (None, {"fields": ["name"]}),
                (None, {"fields": ["name"]}),
            ]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "There are duplicate field(s) in 'fieldsets[1][1]'.",
            "admin.E012",
        )

    def test_fieldsets_with_custom_form_validation(self):
        class BandAdmin(ModelAdmin):
            fieldsets = (("Band", {"fields": ("name",)}),)

        self.assertIsValid(BandAdmin, Band)


class FieldsCheckTests(CheckTestCase):
    def test_duplicate_fields_in_fields(self):
        class TestModelAdmin(ModelAdmin):
            fields = ["name", "name"]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fields' contains duplicate field(s).",
            "admin.E006",
        )

    def test_inline(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            fields = 10

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fields' must be a list or tuple.",
            "admin.E004",
            invalid_obj=ValidationTestInline,
        )


class FormCheckTests(CheckTestCase):
    def test_invalid_type(self):
        class FakeForm:
            pass

        class TestModelAdmin(ModelAdmin):
            form = FakeForm

        class TestModelAdminWithNoForm(ModelAdmin):
            form = "not a form"

        for model_admin in (TestModelAdmin, TestModelAdminWithNoForm):
            with self.subTest(model_admin):
                self.assertIsInvalid(
                    model_admin,
                    ValidationTestModel,
                    "The value of 'form' must inherit from 'BaseModelForm'.",
                    "admin.E016",
                )

    def test_fieldsets_with_custom_form_validation(self):
        class BandAdmin(ModelAdmin):
            fieldsets = (("Band", {"fields": ("name",)}),)

        self.assertIsValid(BandAdmin, Band)

    def test_valid_case(self):
        class AdminBandForm(forms.ModelForm):
            delete = forms.BooleanField()

        class BandAdmin(ModelAdmin):
            form = AdminBandForm
            fieldsets = (("Band", {"fields": ("name", "bio", "sign_date", "delete")}),)

        self.assertIsValid(BandAdmin, Band)


class FilterVerticalCheckTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            filter_vertical = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'filter_vertical' must be a list or tuple.",
            "admin.E017",
        )

    def test_missing_field(self):
        """
        Tests that a ModelAdmin with a non-existent field in filter_vertical raises a validation error.

        This test case ensures that the validation system correctly identifies and reports an error when a field specified in the filter_vertical attribute does not exist in the model.

        The expected error message includes the name of the non-existent field and the corresponding error code (admin.E019).
        """
        class TestModelAdmin(ModelAdmin):
            filter_vertical = ("non_existent_field",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'filter_vertical[0]' refers to 'non_existent_field', "
            "which is not a field of 'modeladmin.ValidationTestModel'.",
            "admin.E019",
        )

    def test_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            filter_vertical = ("name",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'filter_vertical[0]' must be a many-to-many field.",
            "admin.E020",
        )

    @isolate_apps("modeladmin")
    def test_invalid_reverse_m2m_field_with_related_name(self):
        class Contact(Model):
            pass

        class Customer(Model):
            contacts = ManyToManyField("Contact", related_name="customers")

        class TestModelAdmin(ModelAdmin):
            filter_vertical = ["customers"]

        self.assertIsInvalid(
            TestModelAdmin,
            Contact,
            "The value of 'filter_vertical[0]' must be a many-to-many field.",
            "admin.E020",
        )

    @isolate_apps("modeladmin")
    def test_invalid_m2m_field_with_through(self):
        class Artist(Model):
            bands = ManyToManyField("Band", through="BandArtist")

        class BandArtist(Model):
            artist = ForeignKey("Artist", on_delete=CASCADE)
            band = ForeignKey("Band", on_delete=CASCADE)

        class TestModelAdmin(ModelAdmin):
            filter_vertical = ["bands"]

        self.assertIsInvalid(
            TestModelAdmin,
            Artist,
            "The value of 'filter_vertical[0]' cannot include the ManyToManyField "
            "'bands', because that field manually specifies a relationship model.",
            "admin.E013",
        )

    def test_valid_case(self):
        """

        Tests that the ModelAdmin instance is valid when 'filter_vertical' contains a valid field.

        This test checks that the ValidationTestModel can be correctly validated with a ModelAdmin 
        that has 'filter_vertical' set to a tuple containing 'users'. 

        The purpose of this test is to ensure that the validation logic correctly handles 
        the 'filter_vertical' attribute when it contains a field that exists in the model.

        """
        class TestModelAdmin(ModelAdmin):
            filter_vertical = ("users",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class FilterHorizontalCheckTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            filter_horizontal = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'filter_horizontal' must be a list or tuple.",
            "admin.E018",
        )

    def test_missing_field(self):
        class TestModelAdmin(ModelAdmin):
            filter_horizontal = ("non_existent_field",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'filter_horizontal[0]' refers to 'non_existent_field', "
            "which is not a field of 'modeladmin.ValidationTestModel'.",
            "admin.E019",
        )

    def test_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            filter_horizontal = ("name",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'filter_horizontal[0]' must be a many-to-many field.",
            "admin.E020",
        )

    @isolate_apps("modeladmin")
    def test_invalid_reverse_m2m_field_with_related_name(self):
        """
        Tests that invalid configuration of ModelAdmin's filter_horizontal attribute raises an exception when there is a many-to-many field with a related name that does not match the model field name.

        Specifically, this test case checks that the 'filter_horizontal' attribute cannot be set to a many-to-many field that has a related name defined, but the related name does not match the actual field name in the model. If such configuration is provided, an error should be raised, indicating that the 'filter_horizontal' attribute value must be a many-to-many field without a related name or matching the actual field name in the model.

        The expected error message is 'The value of 'filter_horizontal[0]' must be a many-to-many field.' with the error code 'admin.E020'.
        """
        class Contact(Model):
            pass

        class Customer(Model):
            contacts = ManyToManyField("Contact", related_name="customers")

        class TestModelAdmin(ModelAdmin):
            filter_horizontal = ["customers"]

        self.assertIsInvalid(
            TestModelAdmin,
            Contact,
            "The value of 'filter_horizontal[0]' must be a many-to-many field.",
            "admin.E020",
        )

    @isolate_apps("modeladmin")
    def test_invalid_m2m_field_with_through(self):
        class Artist(Model):
            bands = ManyToManyField("Band", through="BandArtist")

        class BandArtist(Model):
            artist = ForeignKey("Artist", on_delete=CASCADE)
            band = ForeignKey("Band", on_delete=CASCADE)

        class TestModelAdmin(ModelAdmin):
            filter_horizontal = ["bands"]

        self.assertIsInvalid(
            TestModelAdmin,
            Artist,
            "The value of 'filter_horizontal[0]' cannot include the ManyToManyField "
            "'bands', because that field manually specifies a relationship model.",
            "admin.E013",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            filter_horizontal = ("users",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class RadioFieldsCheckTests(CheckTestCase):
    def test_not_dictionary(self):
        class TestModelAdmin(ModelAdmin):
            radio_fields = ()

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'radio_fields' must be a dictionary.",
            "admin.E021",
        )

    def test_missing_field(self):
        class TestModelAdmin(ModelAdmin):
            radio_fields = {"non_existent_field": VERTICAL}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'radio_fields' refers to 'non_existent_field', "
            "which is not a field of 'modeladmin.ValidationTestModel'.",
            "admin.E022",
        )

    def test_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            radio_fields = {"name": VERTICAL}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'radio_fields' refers to 'name', which is not an instance "
            "of ForeignKey, and does not have a 'choices' definition.",
            "admin.E023",
        )

    def test_invalid_value(self):
        """
        Tests that ModelAdmin validation fails when the 'radio_fields' dictionary contains an invalid value, specifically when the value is neither admin.HORIZONTAL nor admin.VERTICAL, resulting in the error code 'admin.E024'.
        """
        class TestModelAdmin(ModelAdmin):
            radio_fields = {"state": None}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'radio_fields[\"state\"]' must be either admin.HORIZONTAL or "
            "admin.VERTICAL.",
            "admin.E024",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            radio_fields = {"state": VERTICAL}

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class PrepopulatedFieldsCheckTests(CheckTestCase):
    def test_not_list_or_tuple(self):
        class TestModelAdmin(ModelAdmin):
            prepopulated_fields = {"slug": "test"}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'prepopulated_fields[\"slug\"]' must be a list or tuple.",
            "admin.E029",
        )

    def test_not_dictionary(self):
        class TestModelAdmin(ModelAdmin):
            prepopulated_fields = ()

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'prepopulated_fields' must be a dictionary.",
            "admin.E026",
        )

    def test_missing_field(self):
        class TestModelAdmin(ModelAdmin):
            prepopulated_fields = {"non_existent_field": ("slug",)}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'prepopulated_fields' refers to 'non_existent_field', "
            "which is not a field of 'modeladmin.ValidationTestModel'.",
            "admin.E027",
        )

    def test_missing_field_again(self):
        class TestModelAdmin(ModelAdmin):
            prepopulated_fields = {"slug": ("non_existent_field",)}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'prepopulated_fields[\"slug\"][0]' refers to "
            "'non_existent_field', which is not a field of "
            "'modeladmin.ValidationTestModel'.",
            "admin.E030",
        )

    def test_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            prepopulated_fields = {"users": ("name",)}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'prepopulated_fields' refers to 'users', which must not be "
            "a DateTimeField, a ForeignKey, a OneToOneField, or a ManyToManyField.",
            "admin.E028",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            prepopulated_fields = {"slug": ("name",)}

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_one_to_one_field(self):
        class TestModelAdmin(ModelAdmin):
            prepopulated_fields = {"best_friend": ("name",)}

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'prepopulated_fields' refers to 'best_friend', which must "
            "not be a DateTimeField, a ForeignKey, a OneToOneField, or a "
            "ManyToManyField.",
            "admin.E028",
        )


class ListDisplayTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            list_display = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display' must be a list or tuple.",
            "admin.E107",
        )

    def test_missing_field(self):
        class TestModelAdmin(ModelAdmin):
            list_display = ("non_existent_field",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display[0]' refers to 'non_existent_field', "
            "which is not a callable or attribute of 'TestModelAdmin', "
            "or an attribute, method, or field on 'modeladmin.ValidationTestModel'.",
            "admin.E108",
        )

    def test_missing_related_field(self):
        class TestModelAdmin(ModelAdmin):
            list_display = ("band__non_existent_field",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display[0]' refers to 'band__non_existent_field', "
            "which is not a callable or attribute of 'TestModelAdmin', "
            "or an attribute, method, or field on 'modeladmin.ValidationTestModel'.",
            "admin.E108",
        )

    def test_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            list_display = ("users",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display[0]' must not be a many-to-many field or a "
            "reverse foreign key.",
            "admin.E109",
        )

    def test_invalid_reverse_related_field(self):
        class TestModelAdmin(ModelAdmin):
            list_display = ["song_set"]

        self.assertIsInvalid(
            TestModelAdmin,
            Band,
            "The value of 'list_display[0]' must not be a many-to-many field or a "
            "reverse foreign key.",
            "admin.E109",
        )

    def test_invalid_related_field(self):
        class TestModelAdmin(ModelAdmin):
            list_display = ["song"]

        self.assertIsInvalid(
            TestModelAdmin,
            Band,
            "The value of 'list_display[0]' must not be a many-to-many field or a "
            "reverse foreign key.",
            "admin.E109",
        )

    def test_invalid_m2m_related_name(self):
        class TestModelAdmin(ModelAdmin):
            list_display = ["featured"]

        self.assertIsInvalid(
            TestModelAdmin,
            Band,
            "The value of 'list_display[0]' must not be a many-to-many field or a "
            "reverse foreign key.",
            "admin.E109",
        )

    def test_valid_case(self):
        @admin.display
        def a_callable(obj):
            pass

        class TestModelAdmin(ModelAdmin):
            @admin.display
            def a_method(self, obj):
                pass

            list_display = ("name", "decade_published_in", "a_method", a_callable)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_field_accessible_via_instance(self):
        class PositionField(Field):
            """Custom field accessible only via instance."""

            def contribute_to_class(self, cls, name):
                """
                Contributes the descriptor to the given class, making it accessible as a class attribute.

                The contribution process involves setting up the descriptor on the class, allowing it to be accessed via the class namespace.

                This method is typically called automatically when the descriptor is assigned to a class attribute, and should not be invoked manually unless you are implementing a custom descriptor or metaclass.

                :param cls: The class to which the descriptor will be contributed
                :param name: The name under which the descriptor will be accessible on the class
                """
                super().contribute_to_class(cls, name)
                setattr(cls, self.name, self)

            def __get__(self, instance, owner):
                if instance is None:
                    raise AttributeError()

        class TestModel(Model):
            field = PositionField()

        class TestModelAdmin(ModelAdmin):
            list_display = ("field",)

        self.assertIsValid(TestModelAdmin, TestModel)


class ListDisplayLinksCheckTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            list_display_links = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display_links' must be a list, a tuple, or None.",
            "admin.E110",
        )

    def test_missing_field(self):
        """
        Checks if a ModelAdmin instance is valid when a field referenced in 'list_display_links' does not exist in 'list_display', ensuring that all linked fields are properly defined. This test helps prevent potential errors in the admin interface by verifying the consistency of field links.
        """
        class TestModelAdmin(ModelAdmin):
            list_display_links = ("non_existent_field",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            (
                "The value of 'list_display_links[0]' refers to "
                "'non_existent_field', which is not defined in 'list_display'."
            ),
            "admin.E111",
        )

    def test_missing_in_list_display(self):
        class TestModelAdmin(ModelAdmin):
            list_display_links = ("name",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display_links[0]' refers to 'name', which is not "
            "defined in 'list_display'.",
            "admin.E111",
        )

    def test_valid_case(self):
        @admin.display
        def a_callable(obj):
            pass

        class TestModelAdmin(ModelAdmin):
            @admin.display
            def a_method(self, obj):
                pass

            list_display = ("name", "decade_published_in", "a_method", a_callable)
            list_display_links = ("name", "decade_published_in", "a_method", a_callable)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_None_is_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            list_display_links = None

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_list_display_links_check_skipped_if_get_list_display_overridden(self):
        """
        list_display_links check is skipped if get_list_display() is overridden.
        """

        class TestModelAdmin(ModelAdmin):
            list_display_links = ["name", "subtitle"]

            def get_list_display(self, request):
                pass

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_list_display_link_checked_for_list_tuple_if_get_list_display_overridden(
        self,
    ):
        """
        list_display_links is checked for list/tuple/None even if
        get_list_display() is overridden.
        """

        class TestModelAdmin(ModelAdmin):
            list_display_links = "non-list/tuple"

            def get_list_display(self, request):
                pass

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display_links' must be a list, a tuple, or None.",
            "admin.E110",
        )


class ListFilterTests(CheckTestCase):
    def test_list_filter_validation(self):
        class TestModelAdmin(ModelAdmin):
            list_filter = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter' must be a list or tuple.",
            "admin.E112",
        )

    def test_not_list_filter_class(self):
        class TestModelAdmin(ModelAdmin):
            list_filter = ["RandomClass"]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0]' refers to 'RandomClass', which "
            "does not refer to a Field.",
            "admin.E116",
        )

    def test_callable(self):
        def random_callable():
            pass

        class TestModelAdmin(ModelAdmin):
            list_filter = [random_callable]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0]' must inherit from 'ListFilter'.",
            "admin.E113",
        )

    def test_not_callable(self):
        class TestModelAdmin(ModelAdmin):
            list_filter = [[42, 42]]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0][1]' must inherit from 'FieldListFilter'.",
            "admin.E115",
        )

    def test_missing_field(self):
        class TestModelAdmin(ModelAdmin):
            list_filter = ("non_existent_field",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0]' refers to 'non_existent_field', "
            "which does not refer to a Field.",
            "admin.E116",
        )

    def test_not_filter(self):
        class RandomClass:
            pass

        class TestModelAdmin(ModelAdmin):
            list_filter = (RandomClass,)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0]' must inherit from 'ListFilter'.",
            "admin.E113",
        )

    def test_not_filter_again(self):
        """
        .. method:: test_not_filter_again

           Tests that the list_filter value in a ModelAdmin instance is valid.

           Specifically, this test checks that the second value in each tuple of the list_filter attribute is a subclass of FieldListFilter.
           It verifies that providing a class that does not inherit from FieldListFilter results in an error with the specified validation message and code.
        """
        class RandomClass:
            pass

        class TestModelAdmin(ModelAdmin):
            list_filter = (("is_active", RandomClass),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0][1]' must inherit from 'FieldListFilter'.",
            "admin.E115",
        )

    def test_not_filter_again_again(self):
        class AwesomeFilter(SimpleListFilter):
            def get_title(self):
                return "awesomeness"

            def get_choices(self, request):
                return (("bit", "A bit awesome"), ("very", "Very awesome"))

            def get_queryset(self, cl, qs):
                return qs

        class TestModelAdmin(ModelAdmin):
            list_filter = (("is_active", AwesomeFilter),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0][1]' must inherit from 'FieldListFilter'.",
            "admin.E115",
        )

    def test_list_filter_is_func(self):
        def get_filter():
            pass

        class TestModelAdmin(ModelAdmin):
            list_filter = [get_filter]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0]' must inherit from 'ListFilter'.",
            "admin.E113",
        )

    def test_not_associated_with_field_name(self):
        class TestModelAdmin(ModelAdmin):
            list_filter = (BooleanFieldListFilter,)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_filter[0]' must not inherit from 'FieldListFilter'.",
            "admin.E114",
        )

    def test_valid_case(self):
        """

        Tests the validity of a ModelAdmin class with custom list filters.

        This test case checks if a ModelAdmin instance with a custom filter class
        (AwesomeFilter) and other filter types (BooleanFieldListFilter, string) is valid.
        The AwesomeFilter class is expected to provide a title, choices, and a queryset.
        The test ensures that the ModelAdmin instance can be validated successfully
        with a given model (ValidationTestModel).

        """
        class AwesomeFilter(SimpleListFilter):
            def get_title(self):
                return "awesomeness"

            def get_choices(self, request):
                return (("bit", "A bit awesome"), ("very", "Very awesome"))

            def get_queryset(self, cl, qs):
                return qs

        class TestModelAdmin(ModelAdmin):
            list_filter = (
                "is_active",
                AwesomeFilter,
                ("is_active", BooleanFieldListFilter),
                "no",
            )

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class ListPerPageCheckTests(CheckTestCase):
    def test_not_integer(self):
        class TestModelAdmin(ModelAdmin):
            list_per_page = "hello"

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_per_page' must be an integer.",
            "admin.E118",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            list_per_page = 100

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class ListMaxShowAllCheckTests(CheckTestCase):
    def test_not_integer(self):
        class TestModelAdmin(ModelAdmin):
            list_max_show_all = "hello"

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_max_show_all' must be an integer.",
            "admin.E119",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            list_max_show_all = 200

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class SearchFieldsCheckTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            search_fields = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'search_fields' must be a list or tuple.",
            "admin.E126",
        )


class DateHierarchyCheckTests(CheckTestCase):
    def test_missing_field(self):
        class TestModelAdmin(ModelAdmin):
            date_hierarchy = "non_existent_field"

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'date_hierarchy' refers to 'non_existent_field', "
            "which does not refer to a Field.",
            "admin.E127",
        )

    def test_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            date_hierarchy = "name"

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'date_hierarchy' must be a DateField or DateTimeField.",
            "admin.E128",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            date_hierarchy = "pub_date"

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_related_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            date_hierarchy = "band__sign_date"

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_related_invalid_field_type(self):
        class TestModelAdmin(ModelAdmin):
            date_hierarchy = "band__name"

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'date_hierarchy' must be a DateField or DateTimeField.",
            "admin.E128",
        )


class OrderingCheckTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            ordering = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'ordering' must be a list or tuple.",
            "admin.E031",
        )

        class TestModelAdmin(ModelAdmin):
            ordering = ("non_existent_field",)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'ordering[0]' refers to 'non_existent_field', "
            "which is not a field of 'modeladmin.ValidationTestModel'.",
            "admin.E033",
        )

    def test_random_marker_not_alone(self):
        class TestModelAdmin(ModelAdmin):
            ordering = ("?", "name")

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'ordering' has the random ordering marker '?', but contains "
            "other fields as well.",
            "admin.E032",
            hint='Either remove the "?", or remove the other fields.',
        )

    def test_valid_random_marker_case(self):
        """
        Tests whether a ModelAdmin instance with a random marker in the ordering field is considered valid when paired with a ValidationTestModel. 

         This validation check ensures that the ModelAdmin class correctly handles random sorting on a model, and that the ValidationTestModel is properly configured to test this functionality.
        """
        class TestModelAdmin(ModelAdmin):
            ordering = ("?",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_complex_case(self):
        class TestModelAdmin(ModelAdmin):
            ordering = ("band__name",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            ordering = ("name", "pk")

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_invalid_expression(self):
        class TestModelAdmin(ModelAdmin):
            ordering = (F("nonexistent"),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'ordering[0]' refers to 'nonexistent', which is not "
            "a field of 'modeladmin.ValidationTestModel'.",
            "admin.E033",
        )

    def test_valid_expression(self):
        class TestModelAdmin(ModelAdmin):
            ordering = (Upper("name"), Upper("band__name").desc())

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class ListSelectRelatedCheckTests(CheckTestCase):
    def test_invalid_type(self):
        class TestModelAdmin(ModelAdmin):
            list_select_related = 1

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_select_related' must be a boolean, tuple or list.",
            "admin.E117",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            list_select_related = False

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class SaveAsCheckTests(CheckTestCase):
    def test_not_boolean(self):
        class TestModelAdmin(ModelAdmin):
            save_as = 1

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'save_as' must be a boolean.",
            "admin.E101",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            save_as = True

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class SaveOnTopCheckTests(CheckTestCase):
    def test_not_boolean(self):
        """
        Tests that the 'save_on_top' attribute in a ModelAdmin class must be a boolean value.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the 'save_on_top' attribute is not a boolean value.

        Note:
            This test ensures that the 'save_on_top' attribute is validated correctly, verifying that it raises an error with code 'admin.E102' when a non-boolean value is provided.
        """
        class TestModelAdmin(ModelAdmin):
            save_on_top = 1

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'save_on_top' must be a boolean.",
            "admin.E102",
        )

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            save_on_top = True

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class InlinesCheckTests(CheckTestCase):
    def test_not_iterable(self):
        class TestModelAdmin(ModelAdmin):
            inlines = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'inlines' must be a list or tuple.",
            "admin.E103",
        )

    def test_not_correct_inline_field(self):
        class TestModelAdmin(ModelAdmin):
            inlines = [42]

        self.assertIsInvalidRegexp(
            TestModelAdmin,
            ValidationTestModel,
            r"'.*\.TestModelAdmin' must inherit from 'InlineModelAdmin'\.",
            "admin.E104",
        )

    def test_not_model_admin(self):
        class ValidationTestInline:
            pass

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalidRegexp(
            TestModelAdmin,
            ValidationTestModel,
            r"'.*\.ValidationTestInline' must inherit from 'InlineModelAdmin'\.",
            "admin.E104",
        )

    def test_missing_model_field(self):
        """
        Tests that a TabularInline class defined within a ModelAdmin must have a 'model' attribute.

            Checks that the validation for ModelAdmin inlines correctly identifies and reports
            the error when a 'model' attribute is missing from an inline class.

            The test expects an error message with code 'admin.E105' to be raised, indicating
            that the ValidationTestInline class is missing the required 'model' attribute.

            This validation is essential to ensure that the inline classes are properly
            configured and can function correctly within the admin interface.

            :raises AssertionError: If the validation error is not correctly reported
            :return: None
        """
        class ValidationTestInline(TabularInline):
            pass

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalidRegexp(
            TestModelAdmin,
            ValidationTestModel,
            r"'.*\.ValidationTestInline' must have a 'model' attribute\.",
            "admin.E105",
        )

    def test_invalid_model_type(self):
        class SomethingBad:
            pass

        class ValidationTestInline(TabularInline):
            model = SomethingBad

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalidRegexp(
            TestModelAdmin,
            ValidationTestModel,
            r"The value of '.*\.ValidationTestInline.model' must be a Model\.",
            "admin.E106",
        )

    def test_invalid_model(self):
        class ValidationTestInline(TabularInline):
            model = "Not a class"

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalidRegexp(
            TestModelAdmin,
            ValidationTestModel,
            r"The value of '.*\.ValidationTestInline.model' must be a Model\.",
            "admin.E106",
        )

    def test_invalid_callable(self):
        def random_obj():
            pass

        class TestModelAdmin(ModelAdmin):
            inlines = [random_obj]

        self.assertIsInvalidRegexp(
            TestModelAdmin,
            ValidationTestModel,
            r"'.*\.random_obj' must inherit from 'InlineModelAdmin'\.",
            "admin.E104",
        )

    def test_valid_case(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class FkNameCheckTests(CheckTestCase):
    def test_missing_field(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            fk_name = "non_existent_field"

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "'modeladmin.ValidationTestInlineModel' has no field named "
            "'non_existent_field'.",
            "admin.E202",
            invalid_obj=ValidationTestInline,
        )

    def test_valid_case(self):
        """
        Tests that a valid case is correctly validated when using an inline model admin with a tabular inline. 

        This test case verifies the validity of the `TestModelAdmin` when used in conjunction with the `ValidationTestInlineModel` through the `ValidationTestInline` tabular inline admin interface, ensuring that the `parent` foreign key relationship is properly validated.
        """
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            fk_name = "parent"

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_proxy_model(self):
        class Reporter(Model):
            pass

        class ProxyJournalist(Reporter):
            class Meta:
                proxy = True

        class Article(Model):
            reporter = ForeignKey(ProxyJournalist, on_delete=CASCADE)

        class ArticleInline(admin.TabularInline):
            model = Article

        class ReporterAdmin(admin.ModelAdmin):
            inlines = [ArticleInline]

        self.assertIsValid(ReporterAdmin, Reporter)

    def test_proxy_model_fk_name(self):
        class ReporterFkName(Model):
            pass

        class ProxyJournalistFkName(ReporterFkName):
            class Meta:
                proxy = True

        class ArticleFkName(Model):
            reporter = ForeignKey(ProxyJournalistFkName, on_delete=CASCADE)

        class ArticleInline(admin.TabularInline):
            model = ArticleFkName
            fk_name = "reporter"

        class ReporterAdmin(admin.ModelAdmin):
            inlines = [ArticleInline]

        self.assertIsValid(ReporterAdmin, ReporterFkName)

    def test_proxy_model_parent(self):
        class Parent(Model):
            pass

        class ProxyChild(Parent):
            class Meta:
                proxy = True

        class ProxyProxyChild(ProxyChild):
            class Meta:
                proxy = True

        class Related(Model):
            proxy_child = ForeignKey(ProxyChild, on_delete=CASCADE)

        class InlineFkName(admin.TabularInline):
            model = Related
            fk_name = "proxy_child"

        class InlineNoFkName(admin.TabularInline):
            model = Related

        class ProxyProxyChildAdminFkName(admin.ModelAdmin):
            inlines = [InlineFkName, InlineNoFkName]

        self.assertIsValid(ProxyProxyChildAdminFkName, ProxyProxyChild)


class ExtraCheckTests(CheckTestCase):
    def test_not_integer(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            extra = "hello"

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'extra' must be an integer.",
            "admin.E203",
            invalid_obj=ValidationTestInline,
        )

    def test_valid_case(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            extra = 2

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class MaxNumCheckTests(CheckTestCase):
    def test_not_integer(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            max_num = "hello"

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'max_num' must be an integer.",
            "admin.E204",
            invalid_obj=ValidationTestInline,
        )

    def test_valid_case(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            max_num = 2

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class MinNumCheckTests(CheckTestCase):
    def test_not_integer(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            min_num = "hello"

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'min_num' must be an integer.",
            "admin.E205",
            invalid_obj=ValidationTestInline,
        )

    def test_valid_case(self):
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            min_num = 2

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class FormsetCheckTests(CheckTestCase):
    def test_invalid_type(self):
        class FakeFormSet:
            pass

        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            formset = FakeFormSet

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'formset' must inherit from 'BaseModelFormSet'.",
            "admin.E206",
            invalid_obj=ValidationTestInline,
        )

    def test_inline_without_formset_class(self):
        """
        Tests that an exception is raised when an inline admin class does not define a valid formset class.

        The test verifies that a ModelAdmin instance with an inline class is invalid if the inline class specifies a 'formset' attribute that does not inherit from 'BaseModelFormSet'.

        The expected error message indicates that the 'formset' attribute must inherit from 'BaseModelFormSet', and the error is reported with the code 'admin.E206'.
        """
        class ValidationTestInlineWithoutFormsetClass(TabularInline):
            model = ValidationTestInlineModel
            formset = "Not a FormSet Class"

        class TestModelAdminWithoutFormsetClass(ModelAdmin):
            inlines = [ValidationTestInlineWithoutFormsetClass]

        self.assertIsInvalid(
            TestModelAdminWithoutFormsetClass,
            ValidationTestModel,
            "The value of 'formset' must inherit from 'BaseModelFormSet'.",
            "admin.E206",
            invalid_obj=ValidationTestInlineWithoutFormsetClass,
        )

    def test_valid_case(self):
        class RealModelFormSet(BaseModelFormSet):
            pass

        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            formset = RealModelFormSet

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class ListDisplayEditableTests(CheckTestCase):
    def test_list_display_links_is_none(self):
        """
        list_display and list_editable can contain the same values
        when list_display_links is None
        """

        class ProductAdmin(ModelAdmin):
            list_display = ["name", "slug", "pub_date"]
            list_editable = list_display
            list_display_links = None

        self.assertIsValid(ProductAdmin, ValidationTestModel)

    def test_list_display_first_item_same_as_list_editable_first_item(self):
        """
        The first item in list_display can be the same as the first in
        list_editable.
        """

        class ProductAdmin(ModelAdmin):
            list_display = ["name", "slug", "pub_date"]
            list_editable = ["name", "slug"]
            list_display_links = ["pub_date"]

        self.assertIsValid(ProductAdmin, ValidationTestModel)

    def test_list_display_first_item_in_list_editable(self):
        """
        The first item in list_display can be in list_editable as long as
        list_display_links is defined.
        """

        class ProductAdmin(ModelAdmin):
            list_display = ["name", "slug", "pub_date"]
            list_editable = ["slug", "name"]
            list_display_links = ["pub_date"]

        self.assertIsValid(ProductAdmin, ValidationTestModel)

    def test_list_display_first_item_same_as_list_editable_no_list_display_links(self):
        """
        The first item in list_display cannot be the same as the first item
        in list_editable if list_display_links is not defined.
        """

        class ProductAdmin(ModelAdmin):
            list_display = ["name"]
            list_editable = ["name"]

        self.assertIsInvalid(
            ProductAdmin,
            ValidationTestModel,
            "The value of 'list_editable[0]' refers to the first field "
            "in 'list_display' ('name'), which cannot be used unless "
            "'list_display_links' is set.",
            id="admin.E124",
        )

    def test_list_display_first_item_in_list_editable_no_list_display_links(self):
        """
        The first item in list_display cannot be in list_editable if
        list_display_links isn't defined.
        """

        class ProductAdmin(ModelAdmin):
            list_display = ["name", "slug", "pub_date"]
            list_editable = ["slug", "name"]

        self.assertIsInvalid(
            ProductAdmin,
            ValidationTestModel,
            "The value of 'list_editable[1]' refers to the first field "
            "in 'list_display' ('name'), which cannot be used unless "
            "'list_display_links' is set.",
            id="admin.E124",
        )

    def test_both_list_editable_and_list_display_links(self):
        class ProductAdmin(ModelAdmin):
            list_editable = ("name",)
            list_display = ("name",)
            list_display_links = ("name",)

        self.assertIsInvalid(
            ProductAdmin,
            ValidationTestModel,
            "The value of 'name' cannot be in both 'list_editable' and "
            "'list_display_links'.",
            id="admin.E123",
        )


class AutocompleteFieldsTests(CheckTestCase):
    def test_autocomplete_e036(self):
        class Admin(ModelAdmin):
            autocomplete_fields = "name"

        self.assertIsInvalid(
            Admin,
            Band,
            msg="The value of 'autocomplete_fields' must be a list or tuple.",
            id="admin.E036",
            invalid_obj=Admin,
        )

    def test_autocomplete_e037(self):
        class Admin(ModelAdmin):
            autocomplete_fields = ("nonexistent",)

        self.assertIsInvalid(
            Admin,
            ValidationTestModel,
            msg=(
                "The value of 'autocomplete_fields[0]' refers to 'nonexistent', "
                "which is not a field of 'modeladmin.ValidationTestModel'."
            ),
            id="admin.E037",
            invalid_obj=Admin,
        )

    def test_autocomplete_e38(self):
        class Admin(ModelAdmin):
            autocomplete_fields = ("name",)

        self.assertIsInvalid(
            Admin,
            ValidationTestModel,
            msg=(
                "The value of 'autocomplete_fields[0]' must be a foreign "
                "key or a many-to-many field."
            ),
            id="admin.E038",
            invalid_obj=Admin,
        )

    def test_autocomplete_e039(self):
        """
        Tests that an admin for a model referenced in autocomplete_fields is registered.

        Checks if attempting to use a model in the autocomplete_fields attribute of a ModelAdmin class
        without registering an admin for that model results in an error. This ensures that the
        autocomplete functionality can properly resolve the referenced model.

        The test covers error code 'admin.E039' and verifies the correct error message is raised when
        the model is not registered.

         Raises:
            AssertionError: If the expected error is not raised when an admin is not registered for the model.


        """
        class Admin(ModelAdmin):
            autocomplete_fields = ("band",)

        self.assertIsInvalid(
            Admin,
            Song,
            msg=(
                'An admin for model "Band" has to be registered '
                "to be referenced by Admin.autocomplete_fields."
            ),
            id="admin.E039",
            invalid_obj=Admin,
        )

    def test_autocomplete_e040(self):
        class NoSearchFieldsAdmin(ModelAdmin):
            pass

        class AutocompleteAdmin(ModelAdmin):
            autocomplete_fields = ("featuring",)

        site = AdminSite()
        site.register(Band, NoSearchFieldsAdmin)
        self.assertIsInvalid(
            AutocompleteAdmin,
            Song,
            msg=(
                'NoSearchFieldsAdmin must define "search_fields", because '
                "it's referenced by AutocompleteAdmin.autocomplete_fields."
            ),
            id="admin.E040",
            invalid_obj=AutocompleteAdmin,
            admin_site=site,
        )

    def test_autocomplete_is_valid(self):
        class SearchFieldsAdmin(ModelAdmin):
            search_fields = "name"

        class AutocompleteAdmin(ModelAdmin):
            autocomplete_fields = ("featuring",)

        site = AdminSite()
        site.register(Band, SearchFieldsAdmin)
        self.assertIsValid(AutocompleteAdmin, Song, admin_site=site)

    def test_autocomplete_is_onetoone(self):
        class UserAdmin(ModelAdmin):
            search_fields = ("name",)

        class Admin(ModelAdmin):
            autocomplete_fields = ("best_friend",)

        site = AdminSite()
        site.register(User, UserAdmin)
        self.assertIsValid(Admin, ValidationTestModel, admin_site=site)


class ActionsCheckTests(CheckTestCase):
    def test_custom_permissions_require_matching_has_method(self):
        @admin.action(permissions=["custom"])
        def custom_permission_action(modeladmin, request, queryset):
            pass

        class BandAdmin(ModelAdmin):
            actions = (custom_permission_action,)

        self.assertIsInvalid(
            BandAdmin,
            Band,
            "BandAdmin must define a has_custom_permission() method for the "
            "custom_permission_action action.",
            id="admin.E129",
        )

    def test_actions_not_unique(self):
        @admin.action
        def action(modeladmin, request, queryset):
            pass

        class BandAdmin(ModelAdmin):
            actions = (action, action)

        self.assertIsInvalid(
            BandAdmin,
            Band,
            "__name__ attributes of actions defined in BandAdmin must be "
            "unique. Name 'action' is not unique.",
            id="admin.E130",
        )

    def test_actions_unique(self):
        @admin.action
        def action1(modeladmin, request, queryset):
            pass

        @admin.action
        def action2(modeladmin, request, queryset):
            pass

        class BandAdmin(ModelAdmin):
            actions = (action1, action2)

        self.assertIsValid(BandAdmin, Band)
