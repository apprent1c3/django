from django import forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase
from django.utils.functional import lazy

from . import ValidationAssertions
from .models import (
    Article,
    Author,
    GenericIPAddressTestModel,
    GenericIPAddrUnpackUniqueTest,
    ModelToValidate,
)


class BaseModelValidationTests(ValidationAssertions, TestCase):
    def test_missing_required_field_raises_error(self):
        mtv = ModelToValidate(f_with_custom_validator=42)
        self.assertFailsValidation(mtv.full_clean, ["name", "number"])

    def test_with_correct_value_model_validates(self):
        """
        Tests the validation of the ModelToValidate instance with a correct set of values.

        Verifies that when the model is provided with valid input data, the full clean method returns None, 
        indicating successful validation without any errors or warnings.
        """
        mtv = ModelToValidate(number=10, name="Some Name")
        self.assertIsNone(mtv.full_clean())

    def test_custom_validate_method(self):
        """

        Tests the custom validation method on the ModelToValidate instance.

        Checks if a ModelToValidate instance with an invalid 'name' field and a set 'number' field 
        correctly raises validation errors for both the 'name' field and non-field errors when 
        calling the full_clean method.

        The test case verifies that the custom validation rules are properly applied and 
         handled, ensuring data integrity and consistency in the model instance.

        """
        mtv = ModelToValidate(number=11)
        self.assertFailsValidation(mtv.full_clean, [NON_FIELD_ERRORS, "name"])

    def test_wrong_FK_value_raises_error(self):
        mtv = ModelToValidate(number=10, name="Some Name", parent_id=3)
        self.assertFieldFailsValidationWithMessage(
            mtv.full_clean,
            "parent",
            [
                "model to validate instance with id %r is not a valid choice."
                % mtv.parent_id
            ],
        )
        mtv = ModelToValidate(number=10, name="Some Name", ufm_id="Some Name")
        self.assertFieldFailsValidationWithMessage(
            mtv.full_clean,
            "ufm",
            [
                "unique fields model instance with unique_charfield %r is not "
                "a valid choice." % mtv.name
            ],
        )

    def test_correct_FK_value_validates(self):
        """
        Checks if a model instance with a valid foreign key value can successfully pass validation.

        The test creates a parent instance and then creates a new instance of the model, referencing the parent instance via its primary key. It then calls the full_clean method to validate the instance and asserts that no errors are raised, indicating that the foreign key value is valid.
        """
        parent = ModelToValidate.objects.create(number=10, name="Some Name")
        mtv = ModelToValidate(number=10, name="Some Name", parent_id=parent.pk)
        self.assertIsNone(mtv.full_clean())

    def test_limited_FK_raises_error(self):
        # The limit_choices_to on the parent field says that a parent object's
        # number attribute must be 10, so this should fail validation.
        """
        Tests that creating a ModelToValidate instance with a parent that exceeds the foreign key limit raises a validation error.

        The test verifies that when a ModelToValidate instance is created with a parent relationship, the instance is checked against the foreign key constraints. If the parent's identifier is not valid, the test asserts that the full clean validation method fails and an error message is raised indicating the invalid 'parent' field.
        """
        parent = ModelToValidate.objects.create(number=11, name="Other Name")
        mtv = ModelToValidate(number=10, name="Some Name", parent_id=parent.pk)
        self.assertFailsValidation(mtv.full_clean, ["parent"])

    def test_FK_validates_using_base_manager(self):
        # Archived articles are not available through the default manager, only
        # the base manager.
        author = Author.objects.create(name="Randy", archived=True)
        article = Article(title="My Article", author=author)
        self.assertIsNone(article.full_clean())

    def test_wrong_email_value_raises_error(self):
        """
        Tests that the model validation fails and raises an error when an invalid email address is provided, ensuring that the email field contains a correctly formatted email value.
        """
        mtv = ModelToValidate(number=10, name="Some Name", email="not-an-email")
        self.assertFailsValidation(mtv.full_clean, ["email"])

    def test_correct_email_value_passes(self):
        """
        Tests that a ModelToValidate instance with a valid email address does not raise any validation errors.

        Ensures that the full_clean method returns None when the email attribute contains a correct email value, 
        indicating successful validation and no errors encountered.
        """
        mtv = ModelToValidate(number=10, name="Some Name", email="valid@email.com")
        self.assertIsNone(mtv.full_clean())

    def test_wrong_url_value_raises_error(self):
        """
        Tests that providing an invalid URL value to the ModelToValidate instance raises a validation error.

        The test case checks that the full_clean method fails with a specific error message when the url field is assigned a string that does not represent a valid URL.

        Args:
            None

        Raises:
            AssertionError: If the validation error is not raised or the error message is not as expected.

        Notes:
            This test ensures that the url field of the ModelToValidate instance is correctly validated and that invalid URL values are rejected with a meaningful error message.
        """
        mtv = ModelToValidate(number=10, name="Some Name", url="not a url")
        self.assertFieldFailsValidationWithMessage(
            mtv.full_clean, "url", ["Enter a valid URL."]
        )

    def test_text_greater_that_charfields_max_length_raises_errors(self):
        """
        Tests that a text value greater than the maximum length allowed by a CharField raises a validation error.

        Verifies that when a model instance with a text field exceeds the defined maximum length,
        the full_clean method correctly identifies the error and raises a validation exception,
        indicating that the name field is too long.
        """
        mtv = ModelToValidate(number=10, name="Some Name" * 100)
        self.assertFailsValidation(mtv.full_clean, ["name"])

    def test_malformed_slug_raises_error(self):
        """
        Tests that a ModelToValidate instance with a malformed slug raises an error during validation.

        This test case checks that the model's full_clean method fails when the slug contains invalid characters, ensuring data integrity and adherence to slug formatting standards. It verifies that the validation error is correctly reported for the 'slug' field.
        """
        mtv = ModelToValidate(number=10, name="Some Name", slug="##invalid##")
        self.assertFailsValidation(mtv.full_clean, ["slug"])

    def test_full_clean_does_not_mutate_exclude(self):
        """
        Tests that full_clean does not modify the exclude list.

        This test case ensures that the full_clean method does not alter the original exclude list passed to it.
        It verifies that the full_clean method raises the expected validation error while keeping the exclude list unchanged.
        The test involves creating a model instance with a custom validator and validating it with a specific exclude list.
        It then asserts that the exclude list remains unchanged after the validation process, confirming that full_clean does not mutate the original list.
        """
        mtv = ModelToValidate(f_with_custom_validator=42)
        exclude = ["number"]
        self.assertFailsValidation(mtv.full_clean, ["name"], exclude=exclude)
        self.assertEqual(len(exclude), 1)
        self.assertEqual(exclude[0], "number")


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        exclude = ["author"]


class ModelFormsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(name="Joseph Kocherhans")

    def test_partial_validation(self):
        # Make sure the "commit=False and set field values later" idiom still
        # works with model validation.
        data = {
            "title": "The state of model validation",
            "pub_date": "2010-1-10 14:49:00",
        }
        form = ArticleForm(data)
        self.assertEqual(list(form.errors), [])
        article = form.save(commit=False)
        article.author = self.author
        article.save()

    def test_validation_with_empty_blank_field(self):
        # Since a value for pub_date wasn't provided and the field is
        # blank=True, model-validation should pass.
        # Also, Article.clean() should be run, so pub_date will be filled after
        # validation, so the form should save cleanly even though pub_date is
        # not allowed to be null.
        """

        Tests the validation of an ArticleForm with an empty blank field.

        Verifies that the form instance can be successfully validated and saved 
        when a field is left empty, but is defined as blank in the form. 
        The test checks for the absence of form errors and the automatic 
        assignment of a publication date.

        """
        data = {
            "title": "The state of model validation",
        }
        article = Article(author_id=self.author.id)
        form = ArticleForm(data, instance=article)
        self.assertEqual(list(form.errors), [])
        self.assertIsNotNone(form.instance.pub_date)
        article = form.save()

    def test_validation_with_invalid_blank_field(self):
        # Even though pub_date is set to blank=True, an invalid value was
        # provided, so it should fail validation.
        """
        Tests the validation of an ArticleForm with an invalid blank field.

        Verifies that when creating an ArticleForm instance with invalid data, specifically
        an empty or blank 'pub_date' field, the form's validation correctly identifies the error
        and reports it in the form's errors attribute. This ensures that the form will not
        save with invalid data and instead will prevent the creation of an article with
        incomplete or invalid information. 
        """
        data = {"title": "The state of model validation", "pub_date": "never"}
        article = Article(author_id=self.author.id)
        form = ArticleForm(data, instance=article)
        self.assertEqual(list(form.errors), ["pub_date"])


class GenericIPAddressFieldTests(ValidationAssertions, TestCase):
    def test_correct_generic_ip_passes(self):
        """
        Tests the GenericIPAddressTestModel's full_clean method with various correctly formatted IP addresses to ensure it passes validation without raising any errors, covering both IPv4 and IPv6 formats with varying whitespace characters.
        """
        giptm = GenericIPAddressTestModel(generic_ip="1.2.3.4")
        self.assertIsNone(giptm.full_clean())
        giptm = GenericIPAddressTestModel(generic_ip=" 1.2.3.4 ")
        self.assertIsNone(giptm.full_clean())
        giptm = GenericIPAddressTestModel(generic_ip="1.2.3.4\n")
        self.assertIsNone(giptm.full_clean())
        giptm = GenericIPAddressTestModel(generic_ip="2001::2")
        self.assertIsNone(giptm.full_clean())

    def test_invalid_generic_ip_raises_error(self):
        """
        Checks that invalid generic IP addresses raise an error.

        Tests various scenarios where the generic IP address is invalid, including:
            non-standard IP address formats, incomplete IP addresses, and non-string values.
        Verifies that each scenario triggers a validation error on the 'generic_ip' field.

        Validates the robustness of the GenericIPAddressTestModel's IP address validation
        by ensuring that it correctly identifies and reports invalid IP addresses.
        """
        giptm = GenericIPAddressTestModel(generic_ip="294.4.2.1")
        self.assertFailsValidation(giptm.full_clean, ["generic_ip"])
        giptm = GenericIPAddressTestModel(generic_ip="1:2")
        self.assertFailsValidation(giptm.full_clean, ["generic_ip"])
        giptm = GenericIPAddressTestModel(generic_ip=1)
        self.assertFailsValidation(giptm.full_clean, ["generic_ip"])
        giptm = GenericIPAddressTestModel(generic_ip=lazy(lambda: 1, int))
        self.assertFailsValidation(giptm.full_clean, ["generic_ip"])

    def test_correct_v4_ip_passes(self):
        """
        Tests that a valid IPv4 address passes validation without raising any errors.

        This test case checks that a GenericIPAddressTestModel instance with a correctly formatted IPv4 address can be cleaned without encountering any validation issues.

        :raises: AssertionError if the validation fails
        :return: None if the validation succeeds
        """
        giptm = GenericIPAddressTestModel(v4_ip="1.2.3.4")
        self.assertIsNone(giptm.full_clean())

    def test_invalid_v4_ip_raises_error(self):
        """
        Tests that providing an invalid IPv4 address to GenericIPAddressTestModel raises a validation error.

        This function covers two common cases of invalid IPv4 addresses: 
        an address with a value greater than 255 for one of its parts, 
        and an IPv6 address being passed where an IPv4 address is expected. 

        It verifies that the full_clean method of the model instance fails 
        validation and that the error is associated with the 'v4_ip' field.
        """
        giptm = GenericIPAddressTestModel(v4_ip="294.4.2.1")
        self.assertFailsValidation(giptm.full_clean, ["v4_ip"])
        giptm = GenericIPAddressTestModel(v4_ip="2001::2")
        self.assertFailsValidation(giptm.full_clean, ["v4_ip"])

    def test_correct_v6_ip_passes(self):
        giptm = GenericIPAddressTestModel(v6_ip="2001::2")
        self.assertIsNone(giptm.full_clean())

    def test_invalid_v6_ip_raises_error(self):
        """

        Tests that providing an invalid IPv6 address to the model raises a validation error.

        The function checks two common scenarios where the input is not a valid IPv6 address:
        an IPv4 address and an incomplete or malformed IPv6 address. It verifies that in both
        cases, the model validation fails with an error message indicating that the 'v6_ip'
        field is invalid.

        """
        giptm = GenericIPAddressTestModel(v6_ip="1.2.3.4")
        self.assertFailsValidation(giptm.full_clean, ["v6_ip"])
        giptm = GenericIPAddressTestModel(v6_ip="1:2")
        self.assertFailsValidation(giptm.full_clean, ["v6_ip"])

    def test_v6_uniqueness_detection(self):
        # These two addresses are the same with different syntax
        """
        Tests the uniqueness detection of IPv6 addresses for the GenericIPAddressTestModel.

        Verifies that attempting to save a model instance with a duplicate IPv6 address will fail validation, 
        ensuring that each address in the model is unique. This test case covers the scenario where two 
        different IPv6 addresses, although syntactically different due to condensed notation, are 
        semantically equivalent and thus considered duplicates.

        The test uses the GenericIPAddressTestModel with two different forms of the same IPv6 address 
        to validate this uniqueness constraint.
        """
        giptm = GenericIPAddressTestModel(generic_ip="2001::1:0:0:0:0:2")
        giptm.save()
        giptm = GenericIPAddressTestModel(generic_ip="2001:0:1:2")
        self.assertFailsValidation(giptm.full_clean, ["generic_ip"])

    def test_v4_unpack_uniqueness_detection(self):
        # These two are different, because we are not doing IPv4 unpacking
        """

        Tests that the GenericIPAddressField unpacks and detects uniqueness correctly when given IPv4 addresses in both IPv4 and IPv6 formats.

        This test checks that when an IPv4 address is supplied in IPv6 format (using the ::ffff: prefix), 
        it is unpacked and matched correctly with the same address supplied in IPv4 format, 
        ensuring that uniqueness checks work as expected.

        """
        giptm = GenericIPAddressTestModel(generic_ip="::ffff:10.10.10.10")
        giptm.save()
        giptm = GenericIPAddressTestModel(generic_ip="10.10.10.10")
        self.assertIsNone(giptm.full_clean())

        # These two are the same, because we are doing IPv4 unpacking
        giptm = GenericIPAddrUnpackUniqueTest(generic_v4unpack_ip="::ffff:18.52.18.52")
        giptm.save()
        giptm = GenericIPAddrUnpackUniqueTest(generic_v4unpack_ip="18.52.18.52")
        self.assertFailsValidation(giptm.full_clean, ["generic_v4unpack_ip"])

    def test_empty_generic_ip_passes(self):
        giptm = GenericIPAddressTestModel(generic_ip="")
        self.assertIsNone(giptm.full_clean())
        giptm = GenericIPAddressTestModel(generic_ip=None)
        self.assertIsNone(giptm.full_clean())

    def test_multiple_invalid_ip_raises_error(self):
        """
        Tests the validation behavior of GenericIPAddressTestModel when multiple invalid IP addresses are provided.
        It checks that attempting to validate the model with an invalid IPv6 address, an invalid IPv4 address,
        and an invalid generic IP address (which can be either IPv4 or IPv6) raises the expected validation errors,
        providing informative error messages for each field. The expected error messages are:
        - \"Enter a valid IPv6 address.\" for an invalid IPv6 address,
        - \"Enter a valid IPv4 address.\" for an invalid IPv4 address, and
        - \"Enter a valid IPv4 or IPv6 address.\" for an invalid generic IP address.
        """
        giptm = GenericIPAddressTestModel(
            v6_ip="1.2.3.4", v4_ip="::ffff:10.10.10.10", generic_ip="fsad"
        )
        self.assertFieldFailsValidationWithMessage(
            giptm.full_clean, "v6_ip", ["Enter a valid IPv6 address."]
        )
        self.assertFieldFailsValidationWithMessage(
            giptm.full_clean, "v4_ip", ["Enter a valid IPv4 address."]
        )
        self.assertFieldFailsValidationWithMessage(
            giptm.full_clean, "generic_ip", ["Enter a valid IPv4 or IPv6 address."]
        )
