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
        """

        Asserts that a model is valid when checked through a model admin instance.

        This method creates an instance of the model admin with the given model and 
        admin site, then checks the model using the admin's check method. The assertion 
        passes if no errors are reported by the check method.

        :param model_admin: The model admin class to use for validation
        :param model: The model instance to validate
        :param admin_site: The admin site to use, defaults to a new AdminSite instance

        """
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
        """
        Checks if the 'raw_id_fields' attribute in a ModelAdmin class refers to valid fields in its associated model. 

        It verifies that each field specified in 'raw_id_fields' exists as a field in the model, raising a validation error if any field does not exist. This ensures that the ModelAdmin's raw ID fields configuration is consistent with the underlying model's structure.
        """
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
        """
        Test that the 'fieldsets' attribute in a ModelAdmin class must be an iterable (list or tuple).

            This test case checks if a ModelAdmin class with a non-iterable 'fieldsets' value raises the correct error message.

            :raises AssertionError: If the test does not pass.
            :raises ValidationError: From the ModelAdmin validation, with error code 'admin.E007'.
        """
        class TestModelAdmin(ModelAdmin):
            fieldsets = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets' must be a list or tuple.",
            "admin.E007",
        )

    def test_non_iterable_item(self):
        """
        Tests the validation of a ModelAdmin instance when 'fieldsets' contains a non-iterable item.

        Checks that the validation correctly identifies and reports an error when the value of the first fieldset in 'fieldsets' is not a list or tuple.

        The expected error message is 'The value of 'fieldsets[0]' must be a list or tuple.' with error code 'admin.E008'.
        """
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
        """
        Tests that specifying both 'fieldsets' and 'fields' in a ModelAdmin instance raises an appropriate validation error.

        This validation test checks that a ModelAdmin instance does not define both 'fieldsets' and 'fields', as this can lead to ambiguous configuration. The test verifies that attempting to define both 'fieldsets' and 'fields' results in a validation error with the correct error code (admin.E005).
        """
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
        """

        Tests that the model admin validation catches duplicate fields in fieldsets.

        This test ensures that the validation system correctly identifies and reports
        when a field is listed multiple times within a fieldset in the ModelAdmin
        configuration. It verifies that the error message and code are correctly
        returned when duplicate fields are detected.

        """
        class TestModelAdmin(ModelAdmin):
            fieldsets = [(None, {"fields": ["name", "name"]})]

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "There are duplicate field(s) in 'fieldsets[0][1]'.",
            "admin.E012",
        )

    def test_duplicate_fields_in_fieldsets(self):
        """
        Checks if a ModelAdmin instance has duplicate fields in its fieldsets. 
        This test ensures that each field in the fieldsets is unique, as duplicate fields can lead to unexpected behavior in the admin interface. 
        It verifies that the model admin is invalid if duplicate fields are found and returns a specific validation error message with code 'admin.E012'.
        """
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
        """
        Checks that the 'fields' attribute in a TabularInline model administration class is correctly validated, 
        raising an error if it is not set to a list or tuple, ensuring proper configuration of inline models for admin interfaces.
        """
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
        Checks if a ModelAdmin raises an error when a field specified in filter_vertical does not exist in the model. Validates that the error message correctly identifies the non-existent field and corresponds to the expected error code.
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
        """

        Tests that an invalid field type is used in the filter_vertical attribute of a ModelAdmin instance.

        The function checks that a Validation error is raised when a non-many-to-many field is specified in the filter_vertical attribute.
        It verifies that the error message and code are correctly reported, ensuring that the ModelAdmin instance is properly validated.

        The test case covers the scenario where the filter_vertical attribute contains a field that is not a ManyToManyField, resulting in an error with code 'admin.E020'.

        """
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
        class TestModelAdmin(ModelAdmin):
            filter_vertical = ("users",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class FilterHorizontalCheckTests(CheckTestCase):
    def test_not_iterable(self):
        """
        Tests that the 'filter_horizontal' attribute in a ModelAdmin class is a valid iterable.

        The 'filter_horizontal' attribute is used to specify many-to-many fields that should be displayed as a filter in the admin interface.
        This test checks that the value assigned to 'filter_horizontal' is either a list or a tuple, as required by the Django admin framework.

        A validation error with code 'admin.E018' is expected to be raised if the value is not a valid iterable, with a message indicating that the value must be a list or tuple.
        """
        class TestModelAdmin(ModelAdmin):
            filter_horizontal = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'filter_horizontal' must be a list or tuple.",
            "admin.E018",
        )

    def test_missing_field(self):
        """

        Test that a ModelAdmin instance fails validation when a field specified in filter_horizontal does not exist in the model.

        This test case ensures that the validation mechanism correctly identifies and reports an error when a non-existent field is referenced in the filter_horizontal attribute of a ModelAdmin class. The expected error message includes the name of the invalid field and the corresponding error code. 

        Args: None

        Returns: None

        Raises: AssertionError if the ModelAdmin instance does not fail validation as expected.

        """
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
        """
        Tests that ModelAdmin raises an error when filter_horizontal refers to an invalid field type.

        Checks that the ModelAdmin instance is correctly validated, and an error is raised when
        a field specified in filter_horizontal is not a many-to-many field. The test verifies
        that the correct error code and message are returned in this invalid scenario.
        """
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

        Tests the validation of ModelAdmin when specifying an invalid many-to-many field with a related name in the filter_horizontal attribute.

        This test checks that a ModelAdmin instance is correctly invalidated when it tries to use a many-to-many field with a related name that does not belong to the model being administered.

        The test expects the validation error code 'admin.E020' to be raised, with an error message indicating that the specified field is not a many-to-many field.

        The test case involves a scenario where a ModelAdmin instance is defined for a model that has a many-to-many relationship with another model, and the related name of that relationship is incorrectly used in the filter_horizontal attribute.

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
        """
        Tests that a ModelAdmin with a ManyToManyField using an intermediate model cannot use filter_horizontal to display the relationship.

        The test checks for the case where a ManyToManyField has a through attribute set, which specifies a model that manually defines the relationship between the two models.

        It verifies that an error is raised when attempting to use filter_horizontal with such a field, as this is not a supported configuration.
        """
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
        """
        Tests that a ModelAdmin instance with a valid filter_horizontal configuration is properly validated against a ValidationTestModel.
        """
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
        """

        Tests that an InvalidFieldError is raised when the 'radio_fields' attribute 
        in a ModelAdmin refers to a field that is not a ForeignKey and does not have 
        'choices' defined, ensuring valid radio field configurations.

        This check verifies the correctness of 'radio_fields' definitions, preventing 
        potential errors in the admin interface. The validation error is raised with 
        the specific error code 'admin.E023', providing a clear indication of the issue.

        """
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
        """
        Tests that the 'prepopulated_fields' dictionary values are either a list or tuple for a ModelAdmin class.

            This test ensures that the 'prepopulated_fields' attribute in a ModelAdmin class is correctly validated. 
            It checks for the type of the value for a given field, raising an error if it is not a list or tuple.
            The error is identified by the admin.E029 code.

            :raises AssertionError: If the validation fails
        """
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
        """
        Tests the validation of a ModelAdmin class with prepopulated fields, specifically verifying that the admin interface correctly populates the slug field based on the name field of a ValidationTestModel instance.
        """
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
        """
        Tests the validation of the list_display attribute in a ModelAdmin class to ensure it does not reference a many-to-many field or a reverse foreign key. 

        Verifies that attempting to include an invalid related field in the list display raises the correct error message and code, specifically 'admin.E109', which is raised when the field is a many-to-many field or a reverse foreign key.
        """
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
                Contributes this instance to a class, allowing it to be accessed as a class attribute.

                This method is used to register the instance with the class, making it available
                for use by other parts of the class. It builds upon the functionality provided
                by its parent class, ensuring proper initialization and integration.

                :param cls: The class to which the instance is being contributed.
                :param name: The name under which the instance will be made available on the class.

                """
                super().contribute_to_class(cls, name)
                setattr(cls, self.name, self)

            def __get__(self, instance, owner):
                """
                Implements the getter protocol for a descriptor, handling access to the descriptor on a class or instance.

                When accessed on a class, this method raises an AttributeError since descriptors are meant to be accessed on instances.

                :param instance: The instance of the class that this descriptor is attached to, or None if accessed on the class itself.
                :param owner: The class that this descriptor is attached to.
                :raises AttributeError: If the descriptor is accessed on a class rather than an instance.
                """
                if instance is None:
                    raise AttributeError()

        class TestModel(Model):
            field = PositionField()

        class TestModelAdmin(ModelAdmin):
            list_display = ("field",)

        self.assertIsValid(TestModelAdmin, TestModel)


class ListDisplayLinksCheckTests(CheckTestCase):
    def test_not_iterable(self):
        """

        Tests that ModelAdmin.list_display_links raises an error when set to a non-iterable value.

        Ensures that the validation checks correctly handle the case where list_display_links
        is assigned a single integer value, which is not a valid iterable. The expected error
        message and code are verified to ensure proper handling of this invalid configuration.

        """
        class TestModelAdmin(ModelAdmin):
            list_display_links = 10

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_display_links' must be a list, a tuple, or None.",
            "admin.E110",
        )

    def test_missing_field(self):
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
        """
        Tests that a None value for list_display_links in a ModelAdmin is considered a valid case.

        This test ensures that when no links are specified for the list display, the validation does not fail, allowing for ModelAdmin instances with no explicit list display links to be correctly validated against a test model.

        :raises: AssertionError if the validation of TestModelAdmin with list_display_links set to None fails
        """
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
        """
        Tests the validation of the list_filter attribute in ModelAdmin.

        This function checks that the value of the list_filter attribute refers to a valid Field.
        If the value does not refer to a Field, the test asserts that a validation error is raised with code 'admin.E116'.

        The validation ensures that only valid Fields can be used for filtering, preventing potential errors in the admin interface.

        Args:
            None

        Raises:
            AssertionError: If the validation does not raise the expected error code 'admin.E116'
        """
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
        """
        Tests that the list_filter attribute in ModelAdmin classes only accepts callables that inherit from ListFilter.

            Verifies that an InvalidAdminError is raised when a non-compliant callable is provided.
            The test ensures that the validation check for list_filter callables enforces the expected inheritance hierarchy.

        """
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
        """

        Tests that list_filter items in a ModelAdmin instance are callables.

        This test verifies that the second item in each list_filter tuple must
        inherit from FieldListFilter. If not, it raises a validation error with code 'admin.E115'.

        """
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
        """

        Tests that a custom list filter must inherit from FieldListFilter.

        This test case verifies that a ValueError is raised when a custom filter
        defined in the 'list_filter' attribute of a ModelAdmin class does not
        inherit from FieldListFilter. The test uses a custom filter called
        AwesomeFilter, which does not inherit from FieldListFilter, and checks
        that the expected error message is generated.

        """
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
        """
        Tests that a ModelAdmin instance with a valid configuration is considered valid.

        This test case checks that a ModelAdmin subclass with a list_per_page attribute
        set to a valid integer value is successfully validated against a ValidationTestModel.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the ModelAdmin instance is not considered valid.

        """
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
        """
        Tests the validation of a ModelAdmin instance with a valid configuration.

        This test case checks if the ModelAdmin instance is valid when the list_max_show_all
        attribute is set to a reasonable value. It verifies that the validation process
        completes without errors when using a TestModelAdmin instance with 
        ValidationTestModel.

        The purpose of this test is to ensure that the validation mechanism correctly
        identifies valid ModelAdmin configurations, providing a foundation for more
        complex validation scenarios.
        """
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
        """

        Tests that a ModelAdmin instance is invalid when the 'date_hierarchy' attribute refers to a field that does not exist in the model.

        The test verifies that the validation process correctly identifies and reports the error when a non-existent field is specified for date hierarchy.

        """
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

        Tests if a ModelAdmin instance with a random marker '?' in its ordering is valid.

        This case checks if the framework correctly handles the random marker in the ModelAdmin's ordering attribute.
        The TestModelAdmin class is used as a test model, and its validity is asserted in combination with ValidationTestModel.

        """
        class TestModelAdmin(ModelAdmin):
            ordering = ("?",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_complex_case(self):
        """
        Tests the validation of a complex ModelAdmin case with a nested ordering attribute.

        The function checks if a ModelAdmin subclass with an ordering attribute referencing
        a related model field is considered valid when paired with a specific validation test model.

        It verifies that the validation process correctly handles the nested relationship
        defined in the ordering attribute, ensuring that the ModelAdmin instance is properly validated.
        """
        class TestModelAdmin(ModelAdmin):
            ordering = ("band__name",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_case(self):
        class TestModelAdmin(ModelAdmin):
            ordering = ("name", "pk")

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_invalid_expression(self):
        """
        Tests that a ModelAdmin instance with invalid ordering is correctly identified.

        The function checks that a Validation error is raised when the ordering attribute refers to a non-existent field in the model.

        :raises: AssertionError if the invalid expression does not raise the expected Validation error.
        :raises: Validation error with code 'admin.E033' when the ordering attribute refers to a non-existent field.
        """
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
        """
        Tests that the 'inlines' attribute in ModelAdmin is valid by checking it is a list or tuple. 
        It verifies that an incorrect assignment, such as an integer, results in a validation error with the corresponding error code 'admin.E103'.
        """
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
        """
        Tests that a ModelAdmin's inlines attribute contains classes that inherit from InlineModelAdmin.

        This test case checks if the inlines defined in a ModelAdmin class are valid by ensuring they inherit from InlineModelAdmin.
        It verifies that an error is raised when an inline class does not meet this requirement, specifically triggering the 'admin.E104' error.

        The test uses a sample model admin class (TestModelAdmin) and a validation test inline class (ValidationTestInline) to demonstrate this validation.
        If the inline class does not inherit from InlineModelAdmin, the test expects an Invalid error message indicating that the inline class must inherit from InlineModelAdmin, matching the 'admin.E104' error code.

        """
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
        """
        Tests that a validation error is raised when a TabularInline instance references a foreign key field that does not exist on its model. The test verifies that the correct error message and code are returned, specifically 'admin.E202', when an inline model attempts to reference a non-existent field.
        """
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
        """

        Tests that the 'extra' attribute in a TabularInline class must be an integer.

        Verifies that attempting to set 'extra' to a non-integer value will result in a validation error.
        The test checks that the error message is correctly generated with the expected error code 'admin.E203'.

        """
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
        """

        Tests that the 'max_num' attribute in a TabularInline instance must be an integer.

        This test case validates the administrative interface by checking that an error is raised when a non-integer value is assigned to 'max_num', ensuring the correct data type is used.

        The expected error message is \"The value of 'max_num' must be an integer.\" with error code 'admin.E204', and the invalid object is the ValidationTestInline instance.

        The test case covers a specific validation rule for admin interface configuration, preventing potential errors that could occur when setting up the admin interface with invalid data types.

        """
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
        """

        Tests a valid case for inline validation.

        This test ensures that the ValidationTestInlineModel is properly validated when 
        used as an inline within the TestModelAdmin. It verifies that the TestModelAdmin 
        instance, which includes the ValidationTestInline, is valid when checked against 
        the ValidationTestModel.

        The test setup involves creating a ValidationTestInline instance with a minimum 
        number of required instances, and then checking the validity of the 
        TestModelAdmin instance.

        """
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
        Checks that a TabularInline class without a valid formset class results in an error.

        This test function validates that a ModelAdmin class containing an inline class
        with an invalid formset specification (i.e., not inheriting from BaseModelFormSet)
        correctly raises an E206 error, indicating that the formset must inherit from 
        BaseModelFormSet. The error message includes the specific object causing the 
        invalidation.
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
        """
        Tests validation for a valid case, verifying that the model administration and inline configurations are properly set up.

        This test ensures that the combination of a custom formset (`RealModelFormSet`) and a tabular inline (`ValidationTestInline`) within a model administration class (`TestModelAdmin`) is valid for the `ValidationTestModel`.

        The test checks the integration of these components, confirming that the custom formset and inline configurations do not introduce any validation errors.

        Validation is performed using the `assertIsValid` method, which verifies that the provided model administration class and model are properly configured and compatible.

        This test case provides a basic validation scenario, serving as a foundation for more complex testing and ensuring the correct setup of model administration and inline configurations in the application.
        """
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
        """
        Tests that the 'autocomplete_fields' attribute in a ModelAdmin class correctly validates the existence of referenced fields in the model, raising an E037 error when a nonexistent field is specified.
        """
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
        Checks if an admin for a referenced model is registered when using autocomplete_fields in the ModelAdmin class.

        This test case ensures that when an admin class references another model using the autocomplete_fields attribute, the referenced model has a registered admin class. The test fails if the referenced model's admin class is not registered, raising an error with a message indicating the requirement for the referenced model's admin registration. The error is identified by the id 'admin.E039'.
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
        """
        Tests that AdminSite validation fails when ModelAdmin subclasses define autocomplete fields referencing fields not included in search fields, as required by the search backend. 

        Specifically, this test ensures that a ModelAdmin instance using autocomplete fields must also define the referenced fields in its search fields for proper lookup functionality, and raises an appropriate validation error if this condition is not met.
        """
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
