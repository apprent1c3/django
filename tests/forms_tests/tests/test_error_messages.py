from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    FileField,
    FloatField,
    Form,
    GenericIPAddressField,
    IntegerField,
    ModelChoiceField,
    ModelMultipleChoiceField,
    MultipleChoiceField,
    RegexField,
    SplitDateTimeField,
    TimeField,
    URLField,
    utils,
)
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, ignore_warnings
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.safestring import mark_safe

from ..models import ChoiceModel


class AssertFormErrorsMixin:
    def assertFormErrors(self, expected, the_callable, *args, **kwargs):
        with self.assertRaises(ValidationError) as cm:
            the_callable(*args, **kwargs)
        self.assertEqual(cm.exception.messages, expected)


class FormsErrorMessagesTestCase(SimpleTestCase, AssertFormErrorsMixin):
    def test_charfield(self):
        e = {
            "required": "REQUIRED",
            "min_length": "LENGTH %(show_value)s, MIN LENGTH %(limit_value)s",
            "max_length": "LENGTH %(show_value)s, MAX LENGTH %(limit_value)s",
        }
        f = CharField(min_length=5, max_length=10, error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["LENGTH 4, MIN LENGTH 5"], f.clean, "1234")
        self.assertFormErrors(["LENGTH 11, MAX LENGTH 10"], f.clean, "12345678901")

    def test_integerfield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
            "min_value": "MIN VALUE IS %(limit_value)s",
            "max_value": "MAX VALUE IS %(limit_value)s",
        }
        f = IntegerField(min_value=5, max_value=10, error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc")
        self.assertFormErrors(["MIN VALUE IS 5"], f.clean, "4")
        self.assertFormErrors(["MAX VALUE IS 10"], f.clean, "11")

    def test_floatfield(self):
        """
        Tests the functionality of a FloatField with custom error messages.

        This function checks the FloatField's behavior in various scenarios, including:
            when the field is left empty (required check)
            when the input is not a valid number (invalid check)
            when the input is below the minimum allowed value (min value check)
            when the input is above the maximum allowed value (max value check)

        Custom error messages are used to verify that the correct messages are returned for each scenario. The test ensures that the FloatField correctly validates user input and returns informative error messages when validation fails.
        """
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
            "min_value": "MIN VALUE IS %(limit_value)s",
            "max_value": "MAX VALUE IS %(limit_value)s",
        }
        f = FloatField(min_value=5, max_value=10, error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc")
        self.assertFormErrors(["MIN VALUE IS 5"], f.clean, "4")
        self.assertFormErrors(["MAX VALUE IS 10"], f.clean, "11")

    def test_decimalfield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
            "min_value": "MIN VALUE IS %(limit_value)s",
            "max_value": "MAX VALUE IS %(limit_value)s",
            "max_digits": "MAX DIGITS IS %(max)s",
            "max_decimal_places": "MAX DP IS %(max)s",
            "max_whole_digits": "MAX DIGITS BEFORE DP IS %(max)s",
        }
        f = DecimalField(min_value=5, max_value=10, error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc")
        self.assertFormErrors(["MIN VALUE IS 5"], f.clean, "4")
        self.assertFormErrors(["MAX VALUE IS 10"], f.clean, "11")

        f2 = DecimalField(max_digits=4, decimal_places=2, error_messages=e)
        self.assertFormErrors(["MAX DIGITS IS 4"], f2.clean, "123.45")
        self.assertFormErrors(["MAX DP IS 2"], f2.clean, "1.234")
        self.assertFormErrors(["MAX DIGITS BEFORE DP IS 2"], f2.clean, "123.4")

    def test_datefield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
        }
        f = DateField(error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc")

    def test_timefield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
        }
        f = TimeField(error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc")

    def test_datetimefield(self):
        """

        Tests the DateTimeField class to ensure it behaves as expected.

        The test checks that the field correctly handles required and invalid inputs,
        returning the appropriate error messages. The field is expected to return an
        error message when no input is provided or when the input is not a valid date/time.

        """
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
        }
        f = DateTimeField(error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc")

    def test_regexfield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
            "min_length": "LENGTH %(show_value)s, MIN LENGTH %(limit_value)s",
            "max_length": "LENGTH %(show_value)s, MAX LENGTH %(limit_value)s",
        }
        f = RegexField(r"^[0-9]+$", min_length=5, max_length=10, error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abcde")
        self.assertFormErrors(["LENGTH 4, MIN LENGTH 5"], f.clean, "1234")
        self.assertFormErrors(["LENGTH 11, MAX LENGTH 10"], f.clean, "12345678901")

    def test_emailfield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
            "min_length": "LENGTH %(show_value)s, MIN LENGTH %(limit_value)s",
            "max_length": "LENGTH %(show_value)s, MAX LENGTH %(limit_value)s",
        }
        f = EmailField(min_length=8, max_length=10, error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abcdefgh")
        self.assertFormErrors(["LENGTH 7, MIN LENGTH 8"], f.clean, "a@b.com")
        self.assertFormErrors(["LENGTH 11, MAX LENGTH 10"], f.clean, "aye@bee.com")

    def test_filefield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
            "missing": "MISSING",
            "empty": "EMPTY FILE",
        }
        f = FileField(error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc")
        self.assertFormErrors(["EMPTY FILE"], f.clean, SimpleUploadedFile("name", None))
        self.assertFormErrors(["EMPTY FILE"], f.clean, SimpleUploadedFile("name", ""))

    def test_urlfield(self):
        """

        Tests the functionality of a URLField with custom error messages.

        This test case verifies that the URLField correctly handles different error scenarios,
        including required fields, invalid URLs, and URLs exceeding the maximum allowed length.

        The test covers the following error cases:
            - Required: Tests that the field raises an error when no value is provided.
            - Invalid: Tests that the field raises an error when an invalid URL is provided.
            - Max length: Tests that the field raises an error when a URL exceeds the maximum allowed length.

        Custom error messages are used to provide more informative and user-friendly feedback.

        """
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID",
            "max_length": '"%(value)s" has more than %(limit_value)d characters.',
        }
        with ignore_warnings(category=RemovedInDjango60Warning):
            f = URLField(error_messages=e, max_length=17)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID"], f.clean, "abc.c")
        self.assertFormErrors(
            ['"http://djangoproject.com" has more than 17 characters.'],
            f.clean,
            "djangoproject.com",
        )

    def test_booleanfield(self):
        """
        Tests the BooleanField with custom error messages.

        Verifies that a BooleanField instance with a custom error message for the 'required' validation error correctly raises a 'REQUIRED' error when an empty value is passed to its clean method.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the BooleanField's clean method does not raise the expected error message.
        """
        e = {
            "required": "REQUIRED",
        }
        f = BooleanField(error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")

    def test_choicefield(self):
        e = {
            "required": "REQUIRED",
            "invalid_choice": "%(value)s IS INVALID CHOICE",
        }
        f = ChoiceField(choices=[("a", "aye")], error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["b IS INVALID CHOICE"], f.clean, "b")

    def test_multiplechoicefield(self):
        """

        Tests the validation of a MultipleChoiceField.

        This test ensures that the MultipleChoiceField correctly handles various scenarios, 
        including required fields, invalid choices, and non-list input values. 

        It verifies that the field raises the expected error messages for each case, 
        helping to ensure robust form validation.

        """
        e = {
            "required": "REQUIRED",
            "invalid_choice": "%(value)s IS INVALID CHOICE",
            "invalid_list": "NOT A LIST",
        }
        f = MultipleChoiceField(choices=[("a", "aye")], error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["NOT A LIST"], f.clean, "b")
        self.assertFormErrors(["b IS INVALID CHOICE"], f.clean, ["b"])

    def test_splitdatetimefield(self):
        e = {
            "required": "REQUIRED",
            "invalid_date": "INVALID DATE",
            "invalid_time": "INVALID TIME",
        }
        f = SplitDateTimeField(error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID DATE", "INVALID TIME"], f.clean, ["a", "b"])

    def test_generic_ipaddressfield(self):
        e = {
            "required": "REQUIRED",
            "invalid": "INVALID IP ADDRESS",
        }
        f = GenericIPAddressField(error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID IP ADDRESS"], f.clean, "127.0.0")

    def test_subclassing_errorlist(self):
        """

        Test that form field and non-field errors are correctly rendered when using the default error list class and a custom error list class.

        The test creates a form with fields for first name, last name, and birthday, and intentionally raises a validation error in the form's clean method.
        It then checks that the default error list class renders field and non-field errors as unordered lists, and that a custom error list class renders these errors as div elements.

        """
        class TestForm(Form):
            first_name = CharField()
            last_name = CharField()
            birthday = DateField()

            def clean(self):
                raise ValidationError("I like to be awkward.")

        class CustomErrorList(utils.ErrorList):
            def __str__(self):
                return self.as_divs()

            def as_divs(self):
                if not self:
                    return ""
                return mark_safe(
                    '<div class="error">%s</div>'
                    % "".join("<p>%s</p>" % e for e in self)
                )

        # This form should print errors the default way.
        form1 = TestForm({"first_name": "John"})
        self.assertHTMLEqual(
            str(form1["last_name"].errors),
            '<ul class="errorlist"><li>This field is required.</li></ul>',
        )
        self.assertHTMLEqual(
            str(form1.errors["__all__"]),
            '<ul class="errorlist nonfield"><li>I like to be awkward.</li></ul>',
        )

        # This one should wrap error groups in the customized way.
        form2 = TestForm({"first_name": "John"}, error_class=CustomErrorList)
        self.assertHTMLEqual(
            str(form2["last_name"].errors),
            '<div class="error"><p>This field is required.</p></div>',
        )
        self.assertHTMLEqual(
            str(form2.errors["__all__"]),
            '<div class="error"><p>I like to be awkward.</p></div>',
        )

    def test_error_messages_escaping(self):
        # The forms layer doesn't escape input values directly because error
        # messages might be presented in non-HTML contexts. Instead, the
        # message is marked for escaping by the template engine, so a template
        # is needed to trigger the escaping.
        t = Template("{{ form.errors }}")

        class SomeForm(Form):
            field = ChoiceField(choices=[("one", "One")])

        f = SomeForm({"field": "<script>"})
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            '<ul class="errorlist"><li>field<ul class="errorlist">'
            "<li>Select a valid choice. &lt;script&gt; is not one of the "
            "available choices.</li></ul></li></ul>",
        )

        class SomeForm(Form):
            field = MultipleChoiceField(choices=[("one", "One")])

        f = SomeForm({"field": ["<script>"]})
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            '<ul class="errorlist"><li>field<ul class="errorlist">'
            "<li>Select a valid choice. &lt;script&gt; is not one of the "
            "available choices.</li></ul></li></ul>",
        )

        class SomeForm(Form):
            field = ModelMultipleChoiceField(ChoiceModel.objects.all())

        f = SomeForm({"field": ["<script>"]})
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            '<ul class="errorlist"><li>field<ul class="errorlist">'
            "<li>“&lt;script&gt;” is not a valid value.</li>"
            "</ul></li></ul>",
        )


class ModelChoiceFieldErrorMessagesTestCase(TestCase, AssertFormErrorsMixin):
    def test_modelchoicefield(self):
        # Create choices for the model choice field tests below.
        ChoiceModel.objects.create(pk=1, name="a")
        ChoiceModel.objects.create(pk=2, name="b")
        ChoiceModel.objects.create(pk=3, name="c")

        # ModelChoiceField
        e = {
            "required": "REQUIRED",
            "invalid_choice": "INVALID CHOICE",
        }
        f = ModelChoiceField(queryset=ChoiceModel.objects.all(), error_messages=e)
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["INVALID CHOICE"], f.clean, "4")

        # ModelMultipleChoiceField
        e = {
            "required": "REQUIRED",
            "invalid_choice": "%(value)s IS INVALID CHOICE",
            "invalid_list": "NOT A LIST OF VALUES",
        }
        f = ModelMultipleChoiceField(
            queryset=ChoiceModel.objects.all(), error_messages=e
        )
        self.assertFormErrors(["REQUIRED"], f.clean, "")
        self.assertFormErrors(["NOT A LIST OF VALUES"], f.clean, "3")
        self.assertFormErrors(["4 IS INVALID CHOICE"], f.clean, ["4"])

    def test_modelchoicefield_value_placeholder(self):
        f = ModelChoiceField(
            queryset=ChoiceModel.objects.all(),
            error_messages={
                "invalid_choice": '"%(value)s" is not one of the available choices.',
            },
        )
        self.assertFormErrors(
            ['"invalid" is not one of the available choices.'],
            f.clean,
            "invalid",
        )
