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

        Asserts that a given model is valid in the context of the provided model admin.

        This method verifies that the model admin's validation checks pass for the given model.
        It creates an instance of the model admin with the provided model and admin site, 
        then checks that the admin object's validation results in no errors.

        :param model_admin: The model admin class to use for validation.
        :param model: The model instance to be validated.
        :param admin_site: The admin site to use, defaults to a new instance of AdminSite if not provided.

        """
        if admin_site is None:
            admin_site = AdminSite()
        admin_obj = model_admin(model, admin_site)
        self.assertEqual(admin_obj.check(), [])


class RawIdCheckTests(CheckTestCase):
    def test_not_iterable(self):
        """
        Tests that the 'raw_id_fields' attribute in a ModelAdmin class must be a list or tuple, ensuring proper validation of admin interfaces. 

        The function checks for the validity of the 'raw_id_fields' setting by instantiating a test ModelAdmin class with an invalid 'raw_id_fields' value, then asserts that the validation error 'admin.E001' is raised, indicating that 'raw_id_fields' should be an iterable (list or tuple) rather than any other data type.
        """
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
        """
        Tests that the 'fieldsets' attribute in a ModelAdmin class validates correctly when its first element is not an iterable item. 
        The function checks for the case when the first element of 'fieldsets' is neither a list nor a tuple, 
        and verifies that it raises the expected validation error with the correct error code ('admin.E008').
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
        """
        Tests that a ModelAdmin's fieldsets tuple contains valid pairs of values.

        A fieldset is considered valid if it has exactly two elements: a field name and a field description.

        The test fails if a fieldset does not meet this criteria, raising a validation error with code 'admin.E009' and a message indicating the fieldset that failed validation.
        """
        class TestModelAdmin(ModelAdmin):
            fieldsets = ((),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets[0]' must be of length 2.",
            "admin.E009",
        )

    def test_second_element_of_item_not_a_dict(self):
        """

        Tests that the second element of each item in the ModelAdmin 'fieldsets' tuple must be a dictionary.

        The function asserts that an error is raised when the fieldset's second element is not a dictionary, 
        ensuring that the fieldsets are defined correctly for proper admin functionality.

        Raises:
            AssertionError: If the validation error is not raised with the expected error message and code 'admin.E010'.

        """
        class TestModelAdmin(ModelAdmin):
            fieldsets = (("General", ()),)

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'fieldsets[0][1]' must be a dictionary.",
            "admin.E010",
        )

    def test_missing_fields_key(self):
        """
        Verifies that the 'fields' key is present in the fieldsets dictionary.

        Checks if a ModelAdmin instance contains the required 'fields' key within its fieldsets. 
        A valid fieldset should be a tuple or list containing a string for the fieldset's name and a dictionary with the 'fields' key. 
        If 'fields' key is missing or if the fieldsets do not meet these conditions, the test fails with an 'admin.E011' error.

        This test ensures that ModelAdmin instances are correctly configured to handle fieldsets in the Django admin interface, 
        preventing potential errors when displaying models in the admin interface. 

        Args: 
            None

        Returns: 
            None
        """
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
        """
        Tests if the ModelAdmin validation fails when duplicate fields are defined in the fieldsets.

        This test case checks for the presence of duplicate field names within a fieldset,
        verifying that the validation correctly identifies and reports the error, providing
        an error message and code ('admin.E012') when such a duplicate is found. The test
        ensures the integrity of the ModelAdmin configuration by preventing the use of
        multiple instances of the same field within the same fieldset, promoting
        consistency and preventing potential data inconsistencies or errors in the admin
        interface. 
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
        """

        Tests that admin interface fieldsets with custom form validation function correctly.

        This test case verifies that fieldsets defined in a ModelAdmin class are valid when 
        used with a custom form validation. The test checks if the provided ModelAdmin 
        class with fieldsets for the 'Band' model is valid, ensuring that the custom 
        validation rules are applied correctly.

        """
        class BandAdmin(ModelAdmin):
            fieldsets = (("Band", {"fields": ("name",)}),)

        self.assertIsValid(BandAdmin, Band)


class FieldsCheckTests(CheckTestCase):
    def test_duplicate_fields_in_fields(self):
        """
        Tests that the ModelAdmin validation raises an error when the 'fields' attribute contains duplicate field names.

        This test ensures that the validation checks for duplicate field names in the 'fields' list, preventing potential errors and inconsistencies in the model admin interface. It verifies that a ValidationTestModel instance with duplicate fields in the ModelAdmin's 'fields' attribute is correctly identified as invalid and raises the expected error message with code 'admin.E006'.
        """
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

        Checks that the 'fields' attribute in a TabularInline class is a list or tuple.

        This test ensures that the 'fields' attribute is properly configured to prevent
        runtime errors when using the ModelAdmin interface. It verifies that an invalid
        configuration, where 'fields' is set to an integer, raises the correct error
        message and error code.

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
        """

        Tests that a valid BandAdmin form can be rendered and validated.

        This test case ensures that the BandAdmin form, which includes a delete checkbox,
        can be successfully instantiated and validated using the ModelAdmin interface.
        The form includes fields for the band's name, bio, sign date, and deletion status.

        The test verifies that the form is valid when used with the Band model.

        """
        class AdminBandForm(forms.ModelForm):
            delete = forms.BooleanField()

        class BandAdmin(ModelAdmin):
            form = AdminBandForm
            fieldsets = (("Band", {"fields": ("name", "bio", "sign_date", "delete")}),)

        self.assertIsValid(BandAdmin, Band)


class FilterVerticalCheckTests(CheckTestCase):
    def test_not_iterable(self):
        """
        Tests that the filter_vertical attribute in ModelAdmin is validated as iterable.

        Verifies that a non-iterable value assigned to filter_vertical raises an appropriate validation error.
        The test ensures the error message 'The value of 'filter_vertical' must be a list or tuple.' is returned with code 'admin.E017' when an invalid value is provided.
        """
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
        Verifies that a ValueError is raised when a field referenced in the filter_vertical attribute of ModelAdmin does not exist in the model.

        Checks that validation correctly identifies and reports a non-existent field in the model, ensuring that the filter_vertical option only references valid fields of the model, and provides an informative error message in case of an invalid reference.
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
        Tests that the ModelAdmin validation correctly identifies an invalid field type when 'filter_vertical' is set to a non many-to-many field. 

        The function checks that setting 'filter_vertical' to a field that is not a many-to-many field (in this case a single field 'name') raises an error 'admin.E020' with a specific error message, ensuring that the validation correctly prevents the use of invalid field types in 'filter_vertical'.
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
        """
        Tests that a ModelAdmin instance raises an error when a many-to-many field 
        with a related name is specified in filter_vertical but is not defined on the 
        model being administered.

        Verifies that the test case fails with the expected error message 
        when attempting to create a ModelAdmin instance with an invalid filter_vertical 
        setting, specifically when referencing a field that exists on the related model 
        but not on the primary model. This ensures that ModelAdmin validation correctly 
        identifies and reports such configuration issues.
        """
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

        This check ensures that 'filter_horizontal' is either a list or a tuple, as required by Django.
        An invalid 'filter_horizontal' value will raise a validation error with the code 'admin.E018'.

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
        Test that a ModelAdmin definition is invalid when it attempts to use a non-existent field in the filter_horizontal attribute.

        The function verifies that a ValidationTestModel instance fails validation when the filter_horizontal attribute of a TestModelAdmin instance contains a field that does not exist in the model. This test ensures that the validation system correctly identifies and reports the error, providing a specific error message and code (admin.E019).
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

        Checks if a field specified in filter_horizontal is not a many-to-many field.

        If a field in filter_horizontal does not exist as a many-to-many field in the model, 
        this test will fail and raise an error with code 'admin.E020'.

        Raises:
            AssertionError: If the field specified in filter_horizontal is invalid.

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
        Tests that a ModelAdmin's filter_horizontal attribute does not include a ManyToManyField 
        with a through model specified, as this is an invalid configuration.

        The test validates that attempting to use filter_horizontal with a ManyToManyField 
        that has an explicit through model defined raises an error. This ensures that 
        the ModelAdmin is correctly configured to handle ManyToManyFields.

        The expected error message indicates that the filter_horizontal attribute cannot 
        include a ManyToManyField that manually specifies a relationship model, and 
        it provides the specific error code 'admin.E013' for reference.
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

        Tests the validation of a ModelAdmin instance with a valid filter_horizontal configuration.

        This test case verifies that the validation process succeeds when the filter_horizontal
        attribute is correctly set to a tuple of related model field names. The test uses a
        ValidationTestModel as the model being administered.

        """
        class TestModelAdmin(ModelAdmin):
            filter_horizontal = ("users",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class RadioFieldsCheckTests(CheckTestCase):
    def test_not_dictionary(self):
        """
        Checks that the 'radio_fields' attribute in a ModelAdmin instance is a dictionary.

        This test case validates the configuration of a ModelAdmin instance by verifying that 
        the 'radio_fields' attribute is properly defined as a dictionary. If the attribute 
        is not a dictionary, the test will fail and report an error with code 'admin.E021'.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the 'radio_fields' attribute is not a dictionary.

        """
        class TestModelAdmin(ModelAdmin):
            radio_fields = ()

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'radio_fields' must be a dictionary.",
            "admin.E021",
        )

    def test_missing_field(self):
        """
        Tests that a ModelAdmin fails validation when its radio_fields attribute references a non-existent field in the model, resulting in an 'admin.E022' error message.
        """
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
        Tests that an error is raised when the 'radio_fields' attribute in a ModelAdmin class refers to a field that is not a ForeignKey and does not have 'choices' defined.

        Checks the validation of ModelAdmin instances, ensuring that fields specified in 'radio_fields' meet the necessary criteria of being either a ForeignKey or having 'choices' defined. This validation helps prevent incorrect configuration of admin interfaces.

        Raises a validation error with code 'admin.E023' if the 'radio_fields' attribute is invalidly configured.
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
        """
        Tests that a ModelAdmin instance with an invalid radio_fields setting raises a validation error, specifically when the value is not either admin.HORIZONTAL or admin.VERTICAL, resulting in an 'admin.E024' error with a message indicating the valid value options.
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
        """
        Tests the validity of a ModelAdmin instance with a valid 'radio_fields' configuration.

        Verifies that the ModelAdmin instance is correctly validated when 'radio_fields' is properly set, 
        ensuring that the validation process succeeds as expected. 

        :raises AssertionError: If the ModelAdmin instance is not valid.

        """
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
        """
        Tests that a ModelAdmin with prepopulated fields referencing non-existent model fields raises an error.

        Verifies that when the prepopulated_fields dictionary contains a key that points to a field not present in the model,
        the validation correctly identifies this discrepancy and reports it with the appropriate error code (admin.E030).
        """
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
        """
        Tests that the prepopulated_fields attribute in ModelAdmin does not reference a field of an invalid type, specifically DateTimeField, ForeignKey, OneToOneField, or ManyToManyField. This validation ensures that only fields capable of being automatically populated are included in the prepopulated_fields dictionary, helping to prevent runtime errors.
        """
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

        Tests a valid case of ModelAdmin configuration.

        Verifies that a ModelAdmin instance with prepopulated fields is correctly validated.
        The test checks the compatibility of the ModelAdmin instance with a specific model.

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
        """

        Tests that a ModelAdmin raises an error when a related field specified in list_display does not exist.

        This test case checks that when a field specified in list_display references a related model field that does not exist,
        a validation error is raised with the appropriate error message and code.

        """
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
        """
        Tests that the list_display attribute in ModelAdmin does not contain a many-to-many field or a reverse foreign key.

        This test ensures that an InvalidAdminError is raised when attempting to use a reverse related field in the list_display attribute of a ModelAdmin class. It checks for the specific error message 'The value of 'list_display[0]' must not be a many-to-many field or a reverse foreign key.' and error code 'admin.E109' to confirm that the error is correctly handled.

        The test uses a custom TestModelAdmin class and the built-in Band model to simulate this scenario and verify the expected behavior.
        """
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
        """
        Tests that a ModelAdmin instance raising an error when the 'list_display' attribute contains a many-to-many field or a reverse foreign key.

        This test case verifies that the ModelAdmin validation correctly identifies and rejects an invalid configuration where the 'list_display' attribute references a many-to-many field or a reverse foreign key, which is not supported.

        The test expects the validation to raise an error with the specific code 'admin.E109' and a descriptive error message indicating the problem with the 'list_display' configuration.
        """
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
        """
        Tests the validity of a ModelAdmin class with custom display methods.

        This test case verifies that a ModelAdmin instance with custom display methods,
        both as callables and instance methods, can be successfully validated against a
        test model. The custom display methods are decorated with the @admin.display
        decorator, which is typically used to customize the display of model fields in
        the admin interface.

        The test case checks if the ModelAdmin instance is valid when it includes a mix
        of built-in field names and custom display methods in its list_display attribute.

        Validates the ModelAdmin instance against the ValidationTestModel model, ensuring
        that the combination of custom display methods and built-in field names does not
        raise any validation errors.
        """
        def a_callable(obj):
            pass

        class TestModelAdmin(ModelAdmin):
            @admin.display
            def a_method(self, obj):
                pass

            list_display = ("name", "decade_published_in", "a_method", a_callable)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_field_accessible_via_instance(self):
        """
        .. function:: test_valid_field_accessible_via_instance

           Tests that a valid field which is only accessible via an instance can be used as a display field in the admin interface.

           This test case covers the scenario where a custom field class overrides the default behavior of contributing to its parent class, 
           allowing it to only be accessed through an instance of the model. The test verifies that the `ModelAdmin` can successfully use 
           such a field in its `list_display` configuration without raising any errors.
        """
        class PositionField(Field):
            """Custom field accessible only via instance."""

            def contribute_to_class(self, cls, name):
                super().contribute_to_class(cls, name)
                setattr(cls, self.name, self)

            def __get__(self, instance, owner):
                """
                Descriptor protocol getter method.

                This method is invoked when an attribute is accessed on a class or instance.
                It raises an AttributeError if the attribute is accessed on the class itself (i.e., instance is None),
                indicating that the attribute is instance-specific and cannot be accessed at the class level.

                :param instance: The instance of the class, or None if accessed on the class
                :param owner: The owner class of the attribute
                :raises AttributeError: If the attribute is accessed on the class itself
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

        Checks that the 'list_display_links' attribute of ModelAdmin is a valid iterable.

        Valid values include lists, tuples, or None. If an invalid type is provided, 
        the function asserts that the corresponding validation error is raised with code 'admin.E110'.

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
        """
        Tests that a ModelAdmin instance raises a validation error when a field specified in 'list_display_links' does not exist in 'list_display'.
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
        """

        Tests that the first item in list_display_links is also present in list_display.

        This test case validates that the ModelAdmin class does not contain a 
        list_display_links item that is not defined in list_display, by checking 
        if the first item in list_display_links exists in list_display.

        Raises:
            AssertionError: If the first item in list_display_links does not exist in list_display.


        """
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
        """

        Tests a valid case for ModelAdmin validation.

        This test ensures that a ModelAdmin instance with a mix of callable and method 
        references in the list_display and list_display_links attributes is valid.

        The test case includes both a callable function and an instance method with the
        @admin.display decorator, assigned to the list_display and list_display_links
        attributes of the TestModelAdmin class.

        The test passes if the validation of the TestModelAdmin instance with the 
        ValidationTestModel does not raise any errors.

        """
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
        Verifies that a None value for list_display_links in a ModelAdmin class is a valid configuration.

        This test case checks if setting list_display_links to None does not raise any validation errors when used with a ValidationTestModel. It confirms that None is an acceptable value for this attribute, allowing for flexibility in the model administration interface.
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
        """

        Tests that the 'list_filter' attribute in a ModelAdmin class is validated correctly.

        Validates that the 'list_filter' attribute must be a list or tuple, and raises a
        validation error if it is not. This ensures that the 'list_filter' functionality
        in the admin interface works as expected.

        :raises AssertionError: If the 'list_filter' attribute is not a list or tuple.

        """
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
        Test that a ModelAdmin's list_filter attribute does not contain references to non-Field classes.

            Verifies that the 'list_filter' option in a ModelAdmin class only includes
            valid Field classes. If a non-Field class is referenced, the test fails and
            returns a validation error with code 'admin.E116'. This ensures that only
            legitimate Field classes are used for filtering in the admin interface.

            Raises:
                AssertionError: If the list_filter attribute contains invalid references.

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
        """
        Tests that the values in the list_filter attribute of a ModelAdmin class 
        must be subclasses of ListFilter. 

        If a class that does not inherit from ListFilter is used, the validation 
        should fail with the error code 'admin.E113' and a corresponding message 
        indicating the incorrect class used in the list_filter attribute.
        """
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

        Tests that the 'list_filter' attribute in ModelAdmin does not accept 
        a value that does not inherit from FieldListFilter.

        This test case checks for the specific error 'admin.E115' when the 
        value provided for 'list_filter' is an invalid class that does not 
        inherit from FieldListFilter, ensuring that only proper 
        FieldListFilter instances are used in the 'list_filter' setting.

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
        """
        Tests that a filter in the ModelAdmin list_filter tuple does not accept a filter that does not inherit from FieldListFilter.

        This test case checks the validation of the list_filter attribute in the ModelAdmin class.
        It ensures that the filter used in the list_filter tuple must be a subclass of FieldListFilter.
        If the filter does not inherit from FieldListFilter, the test will raise an error with the code 'admin.E115'.

        The test uses a custom filter class AwesomeFilter that does not inherit from FieldListFilter to simulate this scenario.
        The test result is then verified to ensure that the correct error is raised when the list_filter is invalid.
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
        """
        Tests the valid case for Django ModelAdmin list filter configuration.

        Verifies that the ModelAdmin instance with custom list filters, including 
        a simple list filter and a boolean field list filter, is successfully validated 
        against the specified test model. The validation ensures that the list filters 
        are properly applied to the test model's queryset, allowing for correct filtering 
        of model instances based on specified conditions.

        The test covers a custom filter 'awesomeness' with predefined choices, 
        in addition to built-in filters for 'is_active' field, demonstrating the 
        flexibility of list filter configuration in Django ModelAdmin instances.

        Validates the correct functionality of the ModelAdmin instance with 
        the provided test model, ensuring that the custom filters are applied 
        correctly to the model's instances.

        The test is successful if the ModelAdmin instance with the specified 
        list filters is validated without any errors, indicating that the 
        filter configuration is correct and functional.
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
        """
        Tests that the list_per_page attribute in ModelAdmin is an integer.

            This function checks that the list_per_page value is a valid integer.
            If the value is not an integer, it raises a validation error with code 'admin.E118'.
            The error message indicates that the list_per_page value must be an integer.

            :raises AssertionError: If the test fails to validate the list_per_page attribute.

        """
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

        Tests that a valid ModelAdmin class passes validation.

        This test case checks that a ModelAdmin class with valid configuration is correctly validated.
        The validation process verifies that the ModelAdmin class correctly implements the required
        interface to manage a specific model, in this case ValidationTestModel.

        The test creates a TestModelAdmin class with a list_per_page attribute set to 100, which is a valid configuration.
        The test then asserts that the TestModelAdmin class is valid when used with ValidationTestModel.

        """
        class TestModelAdmin(ModelAdmin):
            list_per_page = 100

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class ListMaxShowAllCheckTests(CheckTestCase):
    def test_not_integer(self):
        """

        Tests that the 'list_max_show_all' attribute in ModelAdmin is validated to be an integer.

        This test case checks if the validation mechanism correctly identifies and reports
        non-integer values assigned to the 'list_max_show_all' attribute, ensuring it follows
        the required data type to maintain proper functionality.

        The test verifies the expected error message and code are raised when the attribute
        is set to a non-integer value, providing assurance that the validation process works
        as intended to prevent incorrect configuration of the ModelAdmin.

        """
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
        """
        Tests if a ModelAdmin instance with an invalid field type specified for date_hierarchy raises a validation error.

        The function checks that when a ModelAdmin class has a date_hierarchy attribute set to a field that is not a DateField or DateTimeField, it correctly raises an error with the specified validation message and code.
        """
        class TestModelAdmin(ModelAdmin):
            date_hierarchy = "name"

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'date_hierarchy' must be a DateField or DateTimeField.",
            "admin.E128",
        )

    def test_valid_case(self):
        """
        Tests that a valid ModelAdmin configuration for date hierarchy is correctly validated.

            This test case checks if a ModelAdmin class with a 'date_hierarchy' attribute set 
            to a valid date field ('pub_date') on the model is considered valid when checked 
            against a test model (ValidationTestModel).
        """
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
        Tests that a ModelAdmin instance with a valid random case for the ordering attribute is correctly validated.

        The test case checks if a ModelAdmin subclass with a tuple containing a single '?' as the ordering attribute is successfully validated against a ValidationTestModel.

        """
        class TestModelAdmin(ModelAdmin):
            ordering = ("?",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_complex_case(self):
        """

        Tests the validation of a ModelAdmin instance in a complex scenario.

        This test case checks if the ModelAdmin class is valid when used in conjunction with a ValidationTestModel. 
        It verifies that the ordering attribute is correctly set, which in this case is based on the 'name' attribute of the related 'band' model.
        The test passes if the ModelAdmin instance is deemed valid, indicating that its configuration is correct and compatible with the ValidationTestModel.

        """
        class TestModelAdmin(ModelAdmin):
            ordering = ("band__name",)

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_valid_case(self):
        """
        Tests that the ValidationTestModel is valid when used with a ModelAdmin that defines ordering.

        This test case ensures that the ValidationTestModel is correctly validated when its ModelAdmin subclass, 
        TestModelAdmin, specifies an ordering of fields. The test verifies that the ValidationTestModel 
        meets the necessary requirements for validation, given the ordering defined in the ModelAdmin.

        :raises AssertionError: If the ValidationTestModel is not valid with the given ModelAdmin ordering
        """
        class TestModelAdmin(ModelAdmin):
            ordering = ("name", "pk")

        self.assertIsValid(TestModelAdmin, ValidationTestModel)

    def test_invalid_expression(self):
        """

        Test that an invalid expression in the ModelAdmin ordering attribute raises an error.

        This test case verifies that when a non-existent field is referenced in the ordering
        tuple, a validation error is raised with a descriptive message and the correct error code.

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
        """
        Tests that a :class:`ModelAdmin` instance raises a validation error when the ``list_select_related`` attribute is set to an invalid type.

        The ``list_select_related`` attribute should be a boolean, tuple or list. If it is set to any other type, a validation error with code 'admin.E117' should be raised.

        :raises AssertionError: If the validation error is not raised as expected.

        """
        class TestModelAdmin(ModelAdmin):
            list_select_related = 1

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'list_select_related' must be a boolean, tuple or list.",
            "admin.E117",
        )

    def test_valid_case(self):
        """

        Tests the validity of a ModelAdmin instance when list_select_related is set to False.

        Verifies that the ModelAdmin class can be successfully validated against ValidationTestModel 
        when list_select_related is disabled, ensuring proper functionality in this specific configuration.

        """
        class TestModelAdmin(ModelAdmin):
            list_select_related = False

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class SaveAsCheckTests(CheckTestCase):
    def test_not_boolean(self):
        """

        Test the validation of the 'save_as' attribute in the ModelAdmin class.

        This test checks that the 'save_as' attribute is validated to be a boolean value.
        If a non-boolean value is provided, a validation error with code 'admin.E101' is expected,
        with a message indicating that the 'save_as' value must be a boolean.

        """
        class TestModelAdmin(ModelAdmin):
            save_as = 1

        self.assertIsInvalid(
            TestModelAdmin,
            ValidationTestModel,
            "The value of 'save_as' must be a boolean.",
            "admin.E101",
        )

    def test_valid_case(self):
        """

        Verifies that a valid ModelAdmin case is correctly identified.

        This test checks that a ModelAdmin instance with 'save_as' set to True 
        is recognized as valid when paired with a ValidationTestModel.

        Args:
            None

        Returns:
            None

        Note:
            The validity of the ModelAdmin is determined by its compatibility 
            with the specified ValidationTestModel.

        """
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
        """

        Tests the validity of a ModelAdmin class with the save_on_top attribute set to True.

        This test checks if the ModelAdmin class is valid when the save_on_top option is enabled, 
        using the ValidationTestModel as the test model. The test passes if the ModelAdmin class 
        is deemed valid under these conditions.

        """
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
        """

        Tests that the 'inlines' attribute in ModelAdmin contains valid InlineModelAdmin instances.

        The function checks for the correct inheritance of InlineModelAdmin in the 'inlines' list.
        It verifies that attempting to register an inline that does not inherit from InlineModelAdmin results in an E104 error.

        """
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
        Tests that an Inline model must have a 'model' attribute.

        This test case ensures that the ModelAdmin validation checks for the presence of a 'model' attribute
        in Inline models, raising an error (admin.E105) if it is missing.

        The test verifies that the validation correctly identifies the missing 'model' attribute in the
        ValidationTestInline class, resulting in an invalidation of the TestModelAdmin configuration.

        Parameters: None
        Returns: None
        Raises: AssertionError if the validation does not correctly identify the missing 'model' attribute.

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
        """
        Tests that the model type specified in a TabularInline instance is valid.
        Checks that a ModelAdmin instance is invalid when its inline model is not a subclass of Model.
        The test case verifies that the validation error message matches the expected regular expression and error code (admin.E106).
        """
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
        """
        Tests that a ModelAdmin instance with an invalid inline specification raises a validation error. 
        Specifically, it checks that the inline must inherit from InlineModelAdmin. 
        The test creates a ModelAdmin class with an inline that does not meet this requirement and verifies that the expected error message is generated.
        """
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
        """
        Tests the validity of a model admin configuration where a TabularInline 
        instance is correctly defined within a ModelAdmin class.

        This test case verifies that the specified ModelAdmin class, which 
        includes an inline model instance, is properly validated against 
        the provided validation model, ensuring correct functionality and 
        setup of the admin interface.

        The validation process involves checking the inline model configuration, 
        including its association with the ModelAdmin class, to guarantee 
        that the admin interface operates as expected.

        :param None:
        :returns: None
        :raises: Assertion error if the validation fails
        """
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class FkNameCheckTests(CheckTestCase):
    def test_missing_field(self):
        """
        Tests that a ValidationTestInlineModel with a non-existent foreign key field raises an error.

        This test case verifies that a ValidationTestInlineModel instance with a foreign key field that does not exist in the model raises a validation error.
        The expected error message indicates that the 'non_existent_field' field does not exist in the ValidationTestInlineModel.

        The specific error code 'admin.E202' is expected, which signifies a foreign key field error in the model admin configuration.

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
        """
        Tests the functionality of a proxy model in the context of Django admin inlines.

        This test case verifies that a model admin with inlines referencing a proxy model
        can be successfully validated. The proxy model is used to create a special case
        of an existing model, with no changes to the underlying database table.

        The test setup includes a `Reporter` model, a `ProxyJournalist` model that proxies
        `Reporter`, and an `Article` model that has a foreign key to `ProxyJournalist`.
        The `ReporterAdmin` model admin is then defined with an inline referencing `Article`.

        The test ensures that the `ReporterAdmin` instance is valid when used with the
        `Reporter` model, demonstrating the correct use of proxy models with admin inlines.
        """
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
        Tests that the 'extra' attribute of a TabularInline class must be an integer.

        Verifies that setting a non-integer value for 'extra' results in a validation error.
        The check ensures that the 'extra' value is correctly validated to prevent potential issues
        in the Django admin interface.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the validation error is not raised as expected.

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
        """

        Tests the validity of an admin interface containing an inline formset with a valid configuration.

        This test case ensures that a ModelAdmin instance with an inline tabular formset 
        defined by ValidationTestInline, containing ValidationTestInlineModel instances, 
        is correctly validated. The inline formset has an extra 2 forms available for 
        additional instances. The test verifies that the TestModelAdmin configuration is 
        valid when used with the ValidationTestModel.

        """
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
        """
        Tests that the ValidationTestModel is valid when used with the TestModelAdmin, which includes a TabularInline for ValidationTestInlineModel with a limited number of instances.
        """
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            max_num = 2

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class MinNumCheckTests(CheckTestCase):
    def test_not_integer(self):
        """
        Tests that the 'min_num' attribute of a TabularInline class must be an integer.

        Verifies that setting 'min_num' to a non-integer value raises a validation error.
        The error message indicates that the value of 'min_num' must be an integer and is categorized as 'admin.E205'.
        """
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
        Tests the validity of a model admin with inlines.

        This function checks if a model admin instance with an inline model is valid.
        It creates a test model admin with a specified inline and then asserts its validity.

        The test case includes a validation test inline model with a minimum number of instances.
        The model admin is expected to be valid if the inline model meets the required criteria.

        Parameters:
            None

        Returns:
            None

        Raises:
            AssertionError: If the model admin instance is not valid.

        """
        class ValidationTestInline(TabularInline):
            model = ValidationTestInlineModel
            min_num = 2

        class TestModelAdmin(ModelAdmin):
            inlines = [ValidationTestInline]

        self.assertIsValid(TestModelAdmin, ValidationTestModel)


class FormsetCheckTests(CheckTestCase):
    def test_invalid_type(self):
        """

        Test that an invalid formset type raises an error in the ModelAdmin.

        This test checks that a formset within a TabularInline does not inherit from BaseModelFormSet,
        ensuring that the admin interface correctly handles invalid input and raises a meaningful error message.

        """
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

        Tests the validity of a ModelAdmin instance with a specific inline formset.

        Verifies that the provided ModelAdmin instance is valid when used in conjunction
        with the specified model, and that the inline formset is properly configured.
        The test case ensures that the ModelAdmin instance can be successfully validated
        with the given model, and that no errors occur during the validation process.

        The validation check includes the examination of the inline formset, which is
        expected to be an instance of BaseModelFormSet, and the model associated with
        the inline formset, which should match the model being tested.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the ModelAdmin instance is not valid with the specified model.

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
        """

        Tests that a field cannot be in both 'list_editable' and 'list_display_links' in a ModelAdmin.

        Checks that an Admin Validation Error is raised when a field is specified in both 
        'list_editable' and 'list_display_links' attributes of a ModelAdmin class. This 
        prevents any potential ambiguity in the admin interface.

        The test verifies that the 'list_editable' and 'list_display_links' options are 
        mutually exclusive, ensuring that admin users can either edit a field in place or 
        use it as a link to the object's change page, but not both.

        """
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
        """
        Checks that the 'autocomplete_fields' attribute in a ModelAdmin class is a valid iterable, ensuring it is either a list or a tuple. This test case verifies that setting 'autocomplete_fields' to a non-iterable value, such as a string, will raise an error. The test validates the correctness of the 'autocomplete_fields' configuration to prevent potential issues with the autocomplete functionality in the admin interface.
        """
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
        Checks validation for an invalid 'autocomplete_fields' configuration in the ModelAdmin class, where the specified field does not exist in the associated model. 

        The test verifies that the validation correctly raises an error when an 'autocomplete_fields' entry does not correspond to a valid field in the model, ensuring that only existing fields can be used for autocomplete functionality.
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
        """
        /gtest_autocomplete_e38/test case for admin interface validation

        Tests that the `autocomplete_fields` attribute in the `ModelAdmin` class 
        is correctly validated to ensure it only contains foreign key or many-to-many fields. 

        Raises an AssertionError if the provided field is not a foreign key or many-to-many field.
        The test case checks for a specific validation error 'admin.E038' when 
        an invalid field is provided in 'autocomplete_fields'.
        """
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
        Checks that an admin for a model referenced by Admin.autocomplete_fields is registered, ensuring that the autocomplete functionality works as expected for the specified model fields. 

        :raises AssertionError: If an admin for the model is not registered, resulting in the specified error message and id.
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
        Tests that an :class:`~django.contrib.admin.ModelAdmin` with autocomplete fields 
        also requires the referenced model's admin to define search fields.

        Checks that attempting to use an autocomplete field in a model admin without 
        defining search fields in the referenced model's admin results in a validation error.

        The test aims to ensure that autocomplete functionality is correctly configured 
        by enforcing the necessary relationship between model admins for proper search 
        and suggestion functionality.

        This test corresponds to Django's specific error code admin.E040, validating 
        that models referenced by autocomplete fields have search fields defined in 
        their respective model admins, thus maintaining data integrity and proper 
        autocomplete functionality within the admin interface.
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
        """

        Tests that autocomplete fields in the admin interface behave as one-to-one relationships.

        This test case verifies that when a model has an autocomplete field, it correctly
        enforces a one-to-one relationship with the related model, ensuring data consistency.

        The test setup involves creating a custom admin site with a registered User model,
        configured with search fields for efficient lookup. An additional Admin model is
        defined with an autocomplete field referencing the User model. The test then
        validates the Admin model against the configured admin site, checking that the
        autocomplete field behaves as expected in a one-to-one relationship scenario.

        """
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
        """
        _testing_custom_permissions_require_matching_has_method_

        Checks if a custom admin action requires a matching has_permission method to be defined in the ModelAdmin class.

        This test ensures that when a custom action is defined with specific permissions, the corresponding has_permission method is implemented in the ModelAdmin class. The method verifies that the has_permission method is correctly linked to the custom action, preventing potential permission errors.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the ModelAdmin class does not define a has_permission method for the custom action, resulting in an 'admin.E129' error.
        """
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
