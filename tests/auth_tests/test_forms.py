import datetime
import re
import urllib.parse
from unittest import mock

from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordChangeForm,
    PasswordResetForm,
    ReadOnlyPasswordHashField,
    ReadOnlyPasswordHashWidget,
    SetPasswordForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_login_failed
from django.contrib.sites.models import Site
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.forms import forms
from django.forms.fields import CharField, Field, IntegerField
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from .models.custom_user import (
    CustomUser,
    CustomUserWithoutIsActiveField,
    ExtensionUser,
)
from .models.with_custom_email_field import CustomEmailField
from .models.with_integer_username import IntegerUsernameUser
from .models.with_many_to_many import CustomUserWithM2M, Organization
from .settings import AUTH_TEMPLATES


class TestDataMixin:
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for user authentication scenarios.

        Creates a set of predefined users with varying properties, such as active/inactive status and different password formats, to support testing of user-related functionality.
        """
        cls.u1 = User.objects.create_user(
            username="testclient", password="password", email="testclient@example.com"
        )
        cls.u2 = User.objects.create_user(
            username="inactive", password="password", is_active=False
        )
        cls.u3 = User.objects.create_user(username="staff", password="password")
        cls.u4 = User.objects.create(username="empty_password", password="")
        cls.u5 = User.objects.create(username="unmanageable_password", password="$")
        cls.u6 = User.objects.create(username="unknown_password", password="foo$bar")
        cls.u7 = User.objects.create(
            username="unusable_password", password=make_password(None)
        )


class ExtraValidationFormMixin:
    def __init__(self, *args, failing_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.failing_fields = failing_fields or {}

    def failing_helper(self, field_name):
        if field_name in self.failing_fields:
            errors = [
                ValidationError(error, code="invalid")
                for error in self.failing_fields[field_name]
            ]
            raise ValidationError(errors)
        return self.cleaned_data[field_name]


class BaseUserCreationFormTest(TestDataMixin, TestCase):
    def test_user_already_exists(self):
        data = {
            "username": "testclient",
            "password1": "test123",
            "password2": "test123",
        }
        form = BaseUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form["username"].errors,
            [str(User._meta.get_field("username").error_messages["unique"])],
        )

    def test_invalid_data(self):
        """
        Tests that the BaseUserCreationForm correctly invalidates a username with invalid characters.\"\"\"

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        Verifies that the form's validation process correctly identifies and reports an error when a username contains disallowed characters, 
        ensuring that only valid usernames are accepted during user creation.
        """
        data = {
            "username": "jsmith!",
            "password1": "test123",
            "password2": "test123",
        }
        form = BaseUserCreationForm(data)
        self.assertFalse(form.is_valid())
        validator = next(
            v
            for v in User._meta.get_field("username").validators
            if v.code == "invalid"
        )
        self.assertEqual(form["username"].errors, [str(validator.message)])

    def test_password_verification(self):
        # The verification password is incorrect.
        data = {
            "username": "jsmith",
            "password1": "test123",
            "password2": "test",
        }
        form = BaseUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form["password2"].errors, [str(form.error_messages["password_mismatch"])]
        )

    def test_both_passwords(self):
        # One (or both) passwords weren't given
        """

        Tests that both password fields are required in the user creation form.
        Verifies that an error is raised when either password field is left blank.

        """
        data = {"username": "jsmith"}
        form = BaseUserCreationForm(data)
        required_error = [str(Field.default_error_messages["required"])]
        self.assertFalse(form.is_valid())
        self.assertEqual(form["password1"].errors, required_error)
        self.assertEqual(form["password2"].errors, required_error)

        data["password2"] = "test123"
        form = UserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form["password1"].errors, required_error)
        self.assertEqual(form["password2"].errors, [])

    @mock.patch("django.contrib.auth.password_validation.password_changed")
    def test_success(self, password_changed):
        # The success case.
        """
        Tests the successful creation of a new user using the BaseUserCreationForm, verifying that the form validates correctly and that the password_changed signal is sent once when the user is saved.
        """
        data = {
            "username": "jsmith@example.com",
            "password1": "test123",
            "password2": "test123",
        }
        form = BaseUserCreationForm(data)
        self.assertTrue(form.is_valid())
        form.save(commit=False)
        self.assertEqual(password_changed.call_count, 0)
        u = form.save()
        self.assertEqual(password_changed.call_count, 1)
        self.assertEqual(repr(u), "<User: jsmith@example.com>")

    def test_unicode_username(self):
        """
        Tests that a user can be created with a Unicode username.
        """
        data = {
            "username": "宝",
            "password1": "test123",
            "password2": "test123",
        }
        form = BaseUserCreationForm(data)
        self.assertTrue(form.is_valid())
        u = form.save()
        self.assertEqual(u.username, "宝")

    def test_normalize_username(self):
        # The normalization happens in AbstractBaseUser.clean() and ModelForm
        # validation calls Model.clean().
        """

        Verifies that usernames are normalized during the user creation process, 
        replacing non-ASCII characters with their closest ASCII equivalent to ensure compatibility.

        """
        ohm_username = "testΩ"  # U+2126 OHM SIGN
        data = {
            "username": ohm_username,
            "password1": "pwd2",
            "password2": "pwd2",
        }
        form = BaseUserCreationForm(data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertNotEqual(user.username, ohm_username)
        self.assertEqual(user.username, "testΩ")  # U+03A9 GREEK CAPITAL LETTER OMEGA

    def test_invalid_username_no_normalize(self):
        field = UsernameField(max_length=254)
        # Usernames are not normalized if they are too long.
        self.assertEqual(field.to_python("½" * 255), "½" * 255)
        self.assertEqual(field.to_python("ﬀ" * 254), "ff" * 254)

    def test_duplicate_normalized_unicode(self):
        """
        Tests that Django properly handles Unicode NFKC normalization when creating new usernames, 
        preventing almost identical usernames that differ only by their Unicode code points.
        """
        omega_username = "iamtheΩ"  # U+03A9 GREEK CAPITAL LETTER OMEGA
        ohm_username = "iamtheΩ"  # U+2126 OHM SIGN
        self.assertNotEqual(omega_username, ohm_username)
        User.objects.create_user(username=omega_username, password="pwd")
        data = {
            "username": ohm_username,
            "password1": "pwd2",
            "password2": "pwd2",
        }
        form = BaseUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["username"], ["A user with that username already exists."]
        )

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": (
                    "django.contrib.auth.password_validation."
                    "UserAttributeSimilarityValidator"
                )
            },
            {
                "NAME": (
                    "django.contrib.auth.password_validation.MinimumLengthValidator"
                ),
                "OPTIONS": {
                    "min_length": 12,
                },
            },
        ]
    )
    def test_validates_password(self):
        """

        Tests that the password validation for user creation forms is working as expected.

        The function checks that the form validation rules are enforced correctly,
        specifically that passwords that are too similar to the username or too short
        are rejected and that errors are reported correctly.

        """
        data = {
            "username": "testclient",
            "password1": "testclient",
            "password2": "testclient",
        }
        form = BaseUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form["password2"].errors), 2)
        self.assertIn(
            "The password is too similar to the username.", form["password2"].errors
        )
        self.assertIn(
            "This password is too short. It must contain at least 12 characters.",
            form["password2"].errors,
        )

        # passwords are not validated if `usable_password` is unset
        data = {
            "username": "othertestclient",
            "password1": "othertestclient",
            "password2": "othertestclient",
            "usable_password": "false",
        }
        form = BaseUserCreationForm(data)
        self.assertIs(form.is_valid(), True, form.errors)

    def test_custom_form(self):
        """
        Tests the creation of a custom user using the CustomUserCreationForm, ensuring the form validation succeeds with the provided data, including the additional 'date_of_birth' field.
        """
        class CustomUserCreationForm(BaseUserCreationForm):
            class Meta(BaseUserCreationForm.Meta):
                model = ExtensionUser
                fields = UserCreationForm.Meta.fields + ("date_of_birth",)

        data = {
            "username": "testclient",
            "password1": "testclient",
            "password2": "testclient",
            "date_of_birth": "1988-02-24",
        }
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())

    def test_custom_form_with_different_username_field(self):
        """
        Tests a custom user creation form with a non-default username field, ensuring it successfully validates user data when the username is represented by an email address.
        """
        class CustomUserCreationForm(BaseUserCreationForm):
            class Meta(BaseUserCreationForm.Meta):
                model = CustomUser
                fields = ("email", "date_of_birth")

        data = {
            "email": "test@client222.com",
            "password1": "testclient",
            "password2": "testclient",
            "date_of_birth": "1988-02-24",
        }
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())

    def test_custom_form_hidden_username_field(self):
        """
        Tests the validation of a custom user creation form where the username field is not visible, ensuring that a user can be created with only an email address.
        """
        class CustomUserCreationForm(BaseUserCreationForm):
            class Meta(BaseUserCreationForm.Meta):
                model = CustomUserWithoutIsActiveField
                fields = ("email",)  # without USERNAME_FIELD

        data = {
            "email": "testclient@example.com",
            "password1": "testclient",
            "password2": "testclient",
        }
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())

    def test_custom_form_saves_many_to_many_field(self):
        """
        Tests that a custom user creation form correctly saves a many-to-many field (orgs) when creating a new user.
        """
        class CustomUserCreationForm(BaseUserCreationForm):
            class Meta(BaseUserCreationForm.Meta):
                model = CustomUserWithM2M
                fields = UserCreationForm.Meta.fields + ("orgs",)

        organization = Organization.objects.create(name="organization 1")

        data = {
            "username": "testclient@example.com",
            "password1": "testclient",
            "password2": "testclient",
            "orgs": [str(organization.pk)],
        }
        form = CustomUserCreationForm(data)
        self.assertIs(form.is_valid(), True)
        user = form.save(commit=True)
        self.assertSequenceEqual(user.orgs.all(), [organization])

    def test_password_whitespace_not_stripped(self):
        """
        Checks if the BaseUserCreationForm correctly handles passwords containing whitespace, ensuring that leading and trailing spaces are preserved during validation.
        """
        data = {
            "username": "testuser",
            "password1": "   testpassword   ",
            "password2": "   testpassword   ",
        }
        form = BaseUserCreationForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["password1"], data["password1"])
        self.assertEqual(form.cleaned_data["password2"], data["password2"])

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": (
                    "django.contrib.auth.password_validation."
                    "UserAttributeSimilarityValidator"
                )
            },
        ]
    )
    def test_password_help_text(self):
        form = BaseUserCreationForm()
        self.assertEqual(
            form.fields["password1"].help_text,
            "<ul><li>"
            "Your password can’t be too similar to your other personal information."
            "</li></ul>",
        )

    def test_password_extra_validations(self):
        """
        Tests the extra password validation functionality in the user creation form.

        Checks that the form validation fails when extra validation errors are introduced 
        on either the password1 or password2 fields, or both, and that the correct error 
        messages are returned.
        """
        class ExtraValidationForm(ExtraValidationFormMixin, BaseUserCreationForm):
            def clean_password1(self):
                return self.failing_helper("password1")

            def clean_password2(self):
                return self.failing_helper("password2")

        data = {"username": "extra", "password1": "abc", "password2": "abc"}
        for fields in (["password1"], ["password2"], ["password1", "password2"]):
            with self.subTest(fields=fields):
                errors = {field: [f"Extra validation for {field}."] for field in fields}
                form = ExtraValidationForm(data, failing_fields=errors)
                self.assertIs(form.is_valid(), False)
                self.assertDictEqual(form.errors, errors)

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": (
                    "django.contrib.auth.password_validation."
                    "UserAttributeSimilarityValidator"
                )
            },
        ]
    )
    def test_user_create_form_validates_password_with_all_data(self):
        """
        Tests that the password validation in BaseUserCreationForm checks all form data to prevent similar passwords and values.
        """

        class CustomUserCreationForm(BaseUserCreationForm):
            class Meta(BaseUserCreationForm.Meta):
                model = User
                fields = ("username", "email", "first_name", "last_name")

        form = CustomUserCreationForm(
            {
                "username": "testuser",
                "password1": "testpassword",
                "password2": "testpassword",
                "first_name": "testpassword",
                "last_name": "lastname",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["password2"],
            ["The password is too similar to the first name."],
        )

        # passwords are not validated if `usable_password` is unset
        form = CustomUserCreationForm(
            {
                "username": "testuser",
                "password1": "testpassword",
                "password2": "testpassword",
                "first_name": "testpassword",
                "last_name": "lastname",
                "usable_password": "false",
            }
        )
        self.assertIs(form.is_valid(), True, form.errors)

    def test_username_field_autocapitalize_none(self):
        form = BaseUserCreationForm()
        self.assertEqual(
            form.fields["username"].widget.attrs.get("autocapitalize"), "none"
        )

    def test_html_autocomplete_attributes(self):
        """
        Tests that HTML autocomplete attributes are correctly set on user creation form fields.
        """
        form = BaseUserCreationForm()
        tests = (
            ("username", "username"),
            ("password1", "new-password"),
            ("password2", "new-password"),
        )
        for field_name, autocomplete in tests:
            with self.subTest(field_name=field_name, autocomplete=autocomplete):
                self.assertEqual(
                    form.fields[field_name].widget.attrs["autocomplete"], autocomplete
                )

    def test_unusable_password(self):
        """

        Verifies that a user can be created with an unusable password.

        Tests that the user creation form accepts a user with an unusable password, 
        and that the saved user object has the expected username and no usable password.

        """
        data = {
            "username": "new-user-which-does-not-exist",
            "usable_password": "false",
        }
        form = BaseUserCreationForm(data)
        self.assertIs(form.is_valid(), True, form.errors)
        u = form.save()
        self.assertEqual(u.username, data["username"])
        self.assertFalse(u.has_usable_password())


class UserCreationFormTest(TestDataMixin, TestCase):
    def test_case_insensitive_username(self):
        data = {
            "username": "TeStClIeNt",
            "password1": "test123",
            "password2": "test123",
        }
        form = UserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form["username"].errors,
            ["A user with that username already exists."],
        )

    @override_settings(AUTH_USER_MODEL="auth_tests.ExtensionUser")
    def test_case_insensitive_username_custom_user_and_error_message(self):
        """

        Tests that a custom UserCreationForm with case-insensitive username validation
        correctly displays an error message when attempting to create a user with an
        existing username, ignoring case differences.

        Verifies that the form validation is case-insensitive and returns the
        configured error message for duplicate usernames.

        """
        class CustomUserCreationForm(UserCreationForm):
            class Meta(UserCreationForm.Meta):
                model = ExtensionUser
                fields = UserCreationForm.Meta.fields + ("date_of_birth",)
                error_messages = {
                    "username": {"unique": "This username has already been taken."}
                }

        ExtensionUser.objects.create_user(
            username="testclient",
            password="password",
            email="testclient@example.com",
            date_of_birth=datetime.date(1984, 3, 5),
        )
        data = {
            "username": "TeStClIeNt",
            "password1": "test123",
            "password2": "test123",
            "date_of_birth": "1980-01-01",
        }
        form = CustomUserCreationForm(data)
        self.assertIs(form.is_valid(), False)
        self.assertEqual(
            form["username"].errors,
            ["This username has already been taken."],
        )


# To verify that the login form rejects inactive users, use an authentication
# backend that allows them.
@override_settings(
    AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.AllowAllUsersModelBackend"]
)
class AuthenticationFormTest(TestDataMixin, TestCase):
    def test_invalid_username(self):
        # The user submits an invalid username.

        data = {
            "username": "jsmith_does_not_exist",
            "password": "test123",
        }
        form = AuthenticationForm(None, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.non_field_errors(),
            [
                form.error_messages["invalid_login"]
                % {"username": User._meta.get_field("username").verbose_name}
            ],
        )

    def test_inactive_user(self):
        # The user is inactive.
        data = {
            "username": "inactive",
            "password": "password",
        }
        form = AuthenticationForm(None, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.non_field_errors(), [str(form.error_messages["inactive"])]
        )

    # Use an authentication backend that rejects inactive users.
    @override_settings(
        AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.ModelBackend"]
    )
    def test_inactive_user_incorrect_password(self):
        """
        Tests that an invalid login attempt with an inactive user does not reveal the user's inactive status, instead displaying a standard invalid login error message.
        """
        data = {
            "username": "inactive",
            "password": "incorrect",
        }
        form = AuthenticationForm(None, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.non_field_errors(),
            [
                form.error_messages["invalid_login"]
                % {"username": User._meta.get_field("username").verbose_name}
            ],
        )

    def test_login_failed(self):
        """

        Tests that the user_login_failed signal is sent when the authentication form is invalid.

        Verifies that the signal is dispatched with the correct request object when a login attempt fails.

        """
        signal_calls = []

        def signal_handler(**kwargs):
            signal_calls.append(kwargs)

        user_login_failed.connect(signal_handler)
        fake_request = object()
        try:
            form = AuthenticationForm(
                fake_request,
                {
                    "username": "testclient",
                    "password": "incorrect",
                },
            )
            self.assertFalse(form.is_valid())
            self.assertIs(signal_calls[0]["request"], fake_request)
        finally:
            user_login_failed.disconnect(signal_handler)

    def test_inactive_user_i18n(self):
        """
        Tests that the AuthenticationForm correctly handles an inactive user when internationalization is enabled, specifically checking for the proper error message in the 'pt-br' locale.
        """
        with (
            self.settings(USE_I18N=True),
            translation.override("pt-br", deactivate=True),
        ):
            # The user is inactive.
            data = {
                "username": "inactive",
                "password": "password",
            }
            form = AuthenticationForm(None, data)
            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.non_field_errors(), [str(form.error_messages["inactive"])]
            )

    # Use an authentication backend that allows inactive users.
    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "django.contrib.auth.backends.AllowAllUsersModelBackend"
        ]
    )
    def test_custom_login_allowed_policy(self):
        # The user is inactive, but our custom form policy allows them to log in.
        """
        Tests the login allowed policy functionality of a custom authentication form, 
        covering scenarios where inactive users are allowed or disallowed to log in by 
        the form's confirm_login_allowed method.
        """
        data = {
            "username": "inactive",
            "password": "password",
        }

        class AuthenticationFormWithInactiveUsersOkay(AuthenticationForm):
            def confirm_login_allowed(self, user):
                pass

        form = AuthenticationFormWithInactiveUsersOkay(None, data)
        self.assertTrue(form.is_valid())

        # Raise a ValidationError in the form to disallow some logins according
        # to custom logic.
        class PickyAuthenticationForm(AuthenticationForm):
            def confirm_login_allowed(self, user):
                if user.username == "inactive":
                    raise ValidationError("This user is disallowed.")
                raise ValidationError("Sorry, nobody's allowed in.")

        form = PickyAuthenticationForm(None, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.non_field_errors(), ["This user is disallowed."])

        data = {
            "username": "testclient",
            "password": "password",
        }
        form = PickyAuthenticationForm(None, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.non_field_errors(), ["Sorry, nobody's allowed in."])

    def test_success(self):
        # The success case
        data = {
            "username": "testclient",
            "password": "password",
        }
        form = AuthenticationForm(None, data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.non_field_errors(), [])

    def test_unicode_username(self):
        """
        Tests that an AuthenticationForm can validate a Unicode username successfully.
        """
        User.objects.create_user(username="Σαρα", password="pwd")
        data = {
            "username": "Σαρα",
            "password": "pwd",
        }
        form = AuthenticationForm(None, data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.non_field_errors(), [])

    @override_settings(AUTH_USER_MODEL="auth_tests.CustomEmailField")
    def test_username_field_max_length_matches_user_model(self):
        """

        Verifies that the username field's maximum length in the authentication form 
        matches the max length defined in the custom user model.

        """
        self.assertEqual(CustomEmailField._meta.get_field("username").max_length, 255)
        data = {
            "username": "u" * 255,
            "password": "pwd",
            "email": "test@example.com",
        }
        CustomEmailField.objects.create_user(**data)
        form = AuthenticationForm(None, data)
        self.assertEqual(form.fields["username"].max_length, 255)
        self.assertEqual(form.fields["username"].widget.attrs.get("maxlength"), 255)
        self.assertEqual(form.errors, {})

    @override_settings(AUTH_USER_MODEL="auth_tests.IntegerUsernameUser")
    def test_username_field_max_length_defaults_to_254(self):
        """
        Checks that the username field's maximum length defaults to 254 when not explicitly set, ensuring consistent validation across models and forms.
        """
        self.assertIsNone(IntegerUsernameUser._meta.get_field("username").max_length)
        data = {
            "username": "0123456",
            "password": "password",
        }
        IntegerUsernameUser.objects.create_user(**data)
        form = AuthenticationForm(None, data)
        self.assertEqual(form.fields["username"].max_length, 254)
        self.assertEqual(form.fields["username"].widget.attrs.get("maxlength"), 254)
        self.assertEqual(form.errors, {})

    def test_username_field_label(self):
        class CustomAuthenticationForm(AuthenticationForm):
            username = CharField(label="Name", max_length=75)

        form = CustomAuthenticationForm()
        self.assertEqual(form["username"].label, "Name")

    def test_username_field_label_not_set(self):
        """
        Verifies that the label for the username field in a form is set to the 
        verbose name of the username field, capitalized, when the label is not explicitly set.
        """
        class CustomAuthenticationForm(AuthenticationForm):
            username = CharField()

        form = CustomAuthenticationForm()
        username_field = User._meta.get_field(User.USERNAME_FIELD)
        self.assertEqual(
            form.fields["username"].label, capfirst(username_field.verbose_name)
        )

    def test_username_field_autocapitalize_none(self):
        form = AuthenticationForm()
        self.assertEqual(
            form.fields["username"].widget.attrs.get("autocapitalize"), "none"
        )

    def test_username_field_label_empty_string(self):
        class CustomAuthenticationForm(AuthenticationForm):
            username = CharField(label="")

        form = CustomAuthenticationForm()
        self.assertEqual(form.fields["username"].label, "")

    def test_password_whitespace_not_stripped(self):
        data = {
            "username": "testuser",
            "password": " pass ",
        }
        form = AuthenticationForm(None, data)
        form.is_valid()  # Not necessary to have valid credentails for the test.
        self.assertEqual(form.cleaned_data["password"], data["password"])

    @override_settings(AUTH_USER_MODEL="auth_tests.IntegerUsernameUser")
    def test_integer_username(self):
        """
        Tests that the AuthenticationForm can handle integer usernames by creating a custom form with an IntegerField for the username, and verifying that the form validation and user caching work as expected.
        """
        class CustomAuthenticationForm(AuthenticationForm):
            username = IntegerField()

        user = IntegerUsernameUser.objects.create_user(username=0, password="pwd")
        data = {
            "username": 0,
            "password": "pwd",
        }
        form = CustomAuthenticationForm(None, data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["username"], data["username"])
        self.assertEqual(form.cleaned_data["password"], data["password"])
        self.assertEqual(form.errors, {})
        self.assertEqual(form.user_cache, user)

    def test_get_invalid_login_error(self):
        """
        Tests the get_invalid_login_error method of the AuthenticationForm class, verifying it returns a ValidationError with the expected message, code, and parameters.
        """
        error = AuthenticationForm().get_invalid_login_error()
        self.assertIsInstance(error, ValidationError)
        self.assertEqual(
            error.message,
            "Please enter a correct %(username)s and password. Note that both "
            "fields may be case-sensitive.",
        )
        self.assertEqual(error.code, "invalid_login")
        self.assertEqual(error.params, {"username": "username"})

    def test_html_autocomplete_attributes(self):
        """
        Verifies that the autocomplete attribute is correctly set for form fields, specifically testing that the 'username' field has an autocomplete value of 'username' and the 'password' field has an autocomplete value of 'current-password'.
        """
        form = AuthenticationForm()
        tests = (
            ("username", "username"),
            ("password", "current-password"),
        )
        for field_name, autocomplete in tests:
            with self.subTest(field_name=field_name, autocomplete=autocomplete):
                self.assertEqual(
                    form.fields[field_name].widget.attrs["autocomplete"], autocomplete
                )

    def test_no_password(self):
        data = {"username": "username"}
        form = AuthenticationForm(None, data)
        self.assertIs(form.is_valid(), False)
        self.assertEqual(
            form["password"].errors, [Field.default_error_messages["required"]]
        )


class SetPasswordFormTest(TestDataMixin, TestCase):
    def test_password_verification(self):
        # The two new passwords do not match.
        """
        Tests that password verification fails when new passwords do not match.\"\"\"
        ```
        """
        user = User.objects.get(username="testclient")
        data = {
            "new_password1": "abc123",
            "new_password2": "abc",
        }
        form = SetPasswordForm(user, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form["new_password2"].errors,
            [str(form.error_messages["password_mismatch"])],
        )

    @mock.patch("django.contrib.auth.password_validation.password_changed")
    def test_success(self, password_changed):
        """
        Tests the successful password change functionality of the SetPasswordForm.

        Verifies that the form validates correctly, and that the password_changed signal
        is sent only after the form data has been saved.
        """
        user = User.objects.get(username="testclient")
        data = {
            "new_password1": "abc123",
            "new_password2": "abc123",
        }
        form = SetPasswordForm(user, data)
        self.assertTrue(form.is_valid())
        form.save(commit=False)
        self.assertEqual(password_changed.call_count, 0)
        form.save()
        self.assertEqual(password_changed.call_count, 1)

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": (
                    "django.contrib.auth.password_validation."
                    "UserAttributeSimilarityValidator"
                )
            },
            {
                "NAME": (
                    "django.contrib.auth.password_validation.MinimumLengthValidator"
                ),
                "OPTIONS": {
                    "min_length": 12,
                },
            },
        ]
    )
    def test_validates_password(self):
        """
        Tests that the SetPasswordForm correctly validates user passwords based on the defined authentication password validators, checking for password similarity to the username and minimum length.
        """
        user = User.objects.get(username="testclient")
        data = {
            "new_password1": "testclient",
            "new_password2": "testclient",
        }
        form = SetPasswordForm(user, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form["new_password2"].errors), 2)
        self.assertIn(
            "The password is too similar to the username.", form["new_password2"].errors
        )
        self.assertIn(
            "This password is too short. It must contain at least 12 characters.",
            form["new_password2"].errors,
        )

        # SetPasswordForm does not consider usable_password for form validation
        data = {
            "new_password1": "testclient",
            "new_password2": "testclient",
            "usable_password": "false",
        }
        form = SetPasswordForm(user, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form["new_password2"].errors), 2)
        self.assertIn(
            "The password is too similar to the username.", form["new_password2"].errors
        )
        self.assertIn(
            "This password is too short. It must contain at least 12 characters.",
            form["new_password2"].errors,
        )

    def test_no_password(self):
        """
        Tests that the SetPasswordForm is invalid when the new password or its confirmation is missing, ensuring the form requires both fields to be filled.
        """
        user = User.objects.get(username="testclient")
        data = {"new_password1": "new-password"}
        form = SetPasswordForm(user, data)
        self.assertIs(form.is_valid(), False)
        self.assertEqual(
            form["new_password2"].errors, [Field.default_error_messages["required"]]
        )
        form = SetPasswordForm(user, {})
        self.assertIs(form.is_valid(), False)
        self.assertEqual(
            form["new_password1"].errors, [Field.default_error_messages["required"]]
        )
        self.assertEqual(
            form["new_password2"].errors, [Field.default_error_messages["required"]]
        )

    def test_password_whitespace_not_stripped(self):
        """
        Test that whitespace in password fields is not stripped during password setting.\"\"\"

         \"\"\" 
            Verifies that the SetPasswordForm preserves leading and trailing whitespace in 
            password input, ensuring that validation and processing treat the input as entered.

        """
        user = User.objects.get(username="testclient")
        data = {
            "new_password1": "   password   ",
            "new_password2": "   password   ",
        }
        form = SetPasswordForm(user, data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["new_password1"], data["new_password1"])
        self.assertEqual(form.cleaned_data["new_password2"], data["new_password2"])

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": (
                    "django.contrib.auth.password_validation."
                    "UserAttributeSimilarityValidator"
                )
            },
            {
                "NAME": (
                    "django.contrib.auth.password_validation.MinimumLengthValidator"
                ),
                "OPTIONS": {
                    "min_length": 12,
                },
            },
        ]
    )
    def test_help_text_translation(self):
        """
        Tests that password help text is correctly translated to French when the locale is set to French. Verifies that the help text matches the expected translations for the UserAttributeSimilarityValidator and MinimumLengthValidator password validators.
        """
        french_help_texts = [
            "Votre mot de passe ne peut pas trop ressembler à vos autres informations "
            "personnelles.",
            "Votre mot de passe doit contenir au minimum 12 caractères.",
        ]
        form = SetPasswordForm(self.u1)
        with translation.override("fr"):
            html = form.as_p()
            for french_text in french_help_texts:
                self.assertIn(french_text, html)

    def test_html_autocomplete_attributes(self):
        """
        Tests whether the autocomplete attribute for password fields in the SetPasswordForm is set correctly, ensuring it matches the expected HTML autocomplete values for form fields.
        """
        form = SetPasswordForm(self.u1)
        tests = (
            ("new_password1", "new-password"),
            ("new_password2", "new-password"),
        )
        for field_name, autocomplete in tests:
            with self.subTest(field_name=field_name, autocomplete=autocomplete):
                self.assertEqual(
                    form.fields[field_name].widget.attrs["autocomplete"], autocomplete
                )

    def test_password_extra_validations(self):
        """
        Tests that the SetPasswordForm with extra validation mixin correctly handles 
        validation errors when setting a new password, ensuring that the form is invalid 
        and that error messages are correctly assigned to the failing fields.
        """
        class ExtraValidationForm(ExtraValidationFormMixin, SetPasswordForm):
            def clean_new_password1(self):
                return self.failing_helper("new_password1")

            def clean_new_password2(self):
                return self.failing_helper("new_password2")

        user = User.objects.get(username="testclient")
        data = {"new_password1": "abc", "new_password2": "abc"}
        for fields in (
            ["new_password1"],
            ["new_password2"],
            ["new_password1", "new_password2"],
        ):
            with self.subTest(fields=fields):
                errors = {field: [f"Extra validation for {field}."] for field in fields}
                form = ExtraValidationForm(user, data, failing_fields=errors)
                self.assertIs(form.is_valid(), False)
                self.assertDictEqual(form.errors, errors)


class PasswordChangeFormTest(TestDataMixin, TestCase):
    def test_incorrect_password(self):
        """
        Tests that the password change form returns an error when the old password is incorrect.
        """
        user = User.objects.get(username="testclient")
        data = {
            "old_password": "test",
            "new_password1": "abc123",
            "new_password2": "abc123",
        }
        form = PasswordChangeForm(user, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form["old_password"].errors,
            [str(form.error_messages["password_incorrect"])],
        )

    def test_password_verification(self):
        # The two new passwords do not match.
        """
        Tests the password verification functionality in the password change form, ensuring that it correctly handles mismatched new passwords.
        """
        user = User.objects.get(username="testclient")
        data = {
            "old_password": "password",
            "new_password1": "abc123",
            "new_password2": "abc",
        }
        form = PasswordChangeForm(user, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form["new_password2"].errors,
            [str(form.error_messages["password_mismatch"])],
        )

    @mock.patch("django.contrib.auth.password_validation.password_changed")
    def test_success(self, password_changed):
        # The success case.
        """
        Tests the successful change of a user's password using the PasswordChangeForm, verifying that the password_changed signal is emitted only after the form data is saved.
        """
        user = User.objects.get(username="testclient")
        data = {
            "old_password": "password",
            "new_password1": "abc123",
            "new_password2": "abc123",
        }
        form = PasswordChangeForm(user, data)
        self.assertTrue(form.is_valid())
        form.save(commit=False)
        self.assertEqual(password_changed.call_count, 0)
        form.save()
        self.assertEqual(password_changed.call_count, 1)

    def test_field_order(self):
        # Regression test - check the order of fields:
        user = User.objects.get(username="testclient")
        self.assertEqual(
            list(PasswordChangeForm(user, {}).fields),
            ["old_password", "new_password1", "new_password2"],
        )

    def test_password_whitespace_not_stripped(self):
        """
        Tests the PasswordChangeForm to ensure that whitespace in password fields is not stripped, allowing passwords with leading or trailing spaces to be validated correctly.
        """
        user = User.objects.get(username="testclient")
        user.set_password("   oldpassword   ")
        data = {
            "old_password": "   oldpassword   ",
            "new_password1": " pass ",
            "new_password2": " pass ",
        }
        form = PasswordChangeForm(user, data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["old_password"], data["old_password"])
        self.assertEqual(form.cleaned_data["new_password1"], data["new_password1"])
        self.assertEqual(form.cleaned_data["new_password2"], data["new_password2"])

    def test_html_autocomplete_attributes(self):
        user = User.objects.get(username="testclient")
        form = PasswordChangeForm(user)
        self.assertEqual(
            form.fields["old_password"].widget.attrs["autocomplete"], "current-password"
        )


class UserChangeFormTest(TestDataMixin, TestCase):
    def test_username_validity(self):
        """
        Checks the validity of a given username by testing an invalid username against the User model's username field validators.
        """
        user = User.objects.get(username="testclient")
        data = {"username": "not valid"}
        form = UserChangeForm(data, instance=user)
        self.assertFalse(form.is_valid())
        validator = next(
            v
            for v in User._meta.get_field("username").validators
            if v.code == "invalid"
        )
        self.assertEqual(form["username"].errors, [str(validator.message)])

    def test_bug_14242(self):
        # A regression test, introduce by adding an optimization for the
        # UserChangeForm.

        """
        Tests the bug #14242 by defining a custom user form with a modified help text for the 'groups' field and instantiating it with an empty dictionary.
        """
        class MyUserForm(UserChangeForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["groups"].help_text = (
                    "These groups give users different permissions"
                )

            class Meta(UserChangeForm.Meta):
                fields = ("groups",)

        # Just check we can create it
        MyUserForm({})

    def test_unusable_password(self):
        user = User.objects.get(username="unusable_password")
        form = UserChangeForm(instance=user)
        self.assertIn(_("No password set."), form.as_table())

    def test_bug_17944_empty_password(self):
        user = User.objects.get(username="empty_password")
        form = UserChangeForm(instance=user)
        self.assertIn(_("No password set."), form.as_table())

    def test_bug_17944_unmanageable_password(self):
        user = User.objects.get(username="unmanageable_password")
        form = UserChangeForm(instance=user)
        self.assertIn(
            _("Invalid password format or unknown hashing algorithm."), form.as_table()
        )

    def test_bug_17944_unknown_password_algorithm(self):
        user = User.objects.get(username="unknown_password")
        form = UserChangeForm(instance=user)
        self.assertIn(
            _("Invalid password format or unknown hashing algorithm."), form.as_table()
        )

    def test_bug_19133(self):
        """
        Tests that changing a user's password through the change form does not return the new password value in plain text, but rather a hashed password value.
        """
        # Use the form to construct the POST data
        user = User.objects.get(username="testclient")
        form_for_data = UserChangeForm(instance=user)
        post_data = form_for_data.initial

        # The password field should be readonly, so anything
        # posted here should be ignored; the form will be
        # valid, and give back the 'initial' value for the
        # password field.
        post_data["password"] = "new password"
        form = UserChangeForm(instance=user, data=post_data)

        self.assertTrue(form.is_valid())
        # original hashed password contains $
        self.assertIn("$", form.cleaned_data["password"])

    def test_bug_19349_bound_password_field(self):
        user = User.objects.get(username="testclient")
        form = UserChangeForm(data={}, instance=user)
        # When rendering the bound password field,
        # ReadOnlyPasswordHashWidget needs the initial
        # value to render correctly
        self.assertEqual(form.initial["password"], form["password"].value())

    @override_settings(ROOT_URLCONF="auth_tests.urls_admin")
    def test_link_to_password_reset_in_user_change_form(self):
        """
        Checks the user change form for a password reset link, verifying its presence, URL, and label for different user cases.
        """
        cases = [
            (
                "testclient",
                "Raw passwords are not stored, so there is no way to see "
                "the user’s password.",
                "Reset password",
            ),
            (
                "unusable_password",
                "Enable password-based authentication for this user by setting a "
                "password.",
                "Set password",
            ),
        ]
        password_reset_link = r'<a class="button" href="([^"]*)">([^<]*)</a>'
        for username, expected_help_text, expected_button_label in cases:
            with self.subTest(username=username):
                user = User.objects.get(username=username)
                form = UserChangeForm(data={}, instance=user)
                password_help_text = form.fields["password"].help_text
                self.assertEqual(password_help_text, expected_help_text)

                matches = re.search(password_reset_link, form.as_p())
                self.assertIsNotNone(matches)
                self.assertEqual(len(matches.groups()), 2)
                url_prefix = f"admin:{user._meta.app_label}_{user._meta.model_name}"
                # URL to UserChangeForm in admin via to_field (instead of pk).
                user_change_url = reverse(f"{url_prefix}_change", args=(user.pk,))
                joined_url = urllib.parse.urljoin(user_change_url, matches.group(1))

                pw_change_url = reverse(
                    f"{url_prefix}_password_change", args=(user.pk,)
                )
                self.assertEqual(joined_url, pw_change_url)
                self.assertEqual(matches.group(2), expected_button_label)

    def test_custom_form(self):
        """

        Tests the validity of a custom user change form.

        Verifies that the form can successfully validate and save user data.

        """
        class CustomUserChangeForm(UserChangeForm):
            class Meta(UserChangeForm.Meta):
                model = ExtensionUser
                fields = (
                    "username",
                    "password",
                    "date_of_birth",
                )

        user = User.objects.get(username="testclient")
        data = {
            "username": "testclient",
            "password": "testclient",
            "date_of_birth": "1998-02-24",
        }
        form = CustomUserChangeForm(data, instance=user)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(form.cleaned_data["username"], "testclient")
        self.assertEqual(form.cleaned_data["date_of_birth"], datetime.date(1998, 2, 24))

    def test_password_excluded(self):
        """
        Checks that the password field is excluded from the user change form.
        """
        class UserChangeFormWithoutPassword(UserChangeForm):
            password = None

            class Meta:
                model = User
                exclude = ["password"]

        form = UserChangeFormWithoutPassword()
        self.assertNotIn("password", form.fields)

    def test_username_field_autocapitalize_none(self):
        form = UserChangeForm()
        self.assertEqual(
            form.fields["username"].widget.attrs.get("autocapitalize"), "none"
        )


@override_settings(TEMPLATES=AUTH_TEMPLATES)
class PasswordResetFormTest(TestDataMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # This cleanup is necessary because contrib.sites cache
        # makes tests interfere with each other, see #11505
        Site.objects.clear_cache()

    def create_dummy_user(self):
        """
        Create a dummy user for testing purposes, returning the created user object along with its generated username and email address.
        """
        username = "jsmith"
        email = "jsmith@example.com"
        user = User.objects.create_user(username, email, "test123")
        return (user, username, email)

    def test_invalid_email(self):
        data = {"email": "not valid"}
        form = PasswordResetForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form["email"].errors, [_("Enter a valid email address.")])

    def test_user_email_unicode_collision(self):
        """
        Tests password reset functionality when two users have similar email addresses, one of which contains a Unicode character, to ensure that the password reset email is sent to the correct user.
        """
        User.objects.create_user("mike123", "mike@example.org", "test123")
        User.objects.create_user("mike456", "mıke@example.org", "test123")
        data = {"email": "mıke@example.org"}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mıke@example.org"])

    def test_user_email_domain_unicode_collision(self):
        """

        Checks that a password reset form can handle email addresses with Unicode domain names without colliding with similar ASCII domain names.

        Tests whether the form saves correctly and sends a password reset email to the specified address.

        """
        User.objects.create_user("mike123", "mike@ixample.org", "test123")
        User.objects.create_user("mike456", "mike@ıxample.org", "test123")
        data = {"email": "mike@ıxample.org"}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mike@ıxample.org"])

    def test_user_email_unicode_collision_nonexistent(self):
        """
        Checks that a password reset form with a Unicode email that collides with an existing ASCII email does not send a password reset email when the colliding ASCII email is not a registered user.
        """
        User.objects.create_user("mike123", "mike@example.org", "test123")
        data = {"email": "mıke@example.org"}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_user_email_domain_unicode_collision_nonexistent(self):
        """
        Tests that a password reset form handles Unicode domain name collisions correctly when the colliding domain has no existing user account. Verifies that the form validates the provided email address but does not send an email since no matching user exists.
        """
        User.objects.create_user("mike123", "mike@ixample.org", "test123")
        data = {"email": "mike@ıxample.org"}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_nonexistent_email(self):
        """
        Verify that password reset functionality properly handles a non-existent email address, ensuring it does not reveal information about registered users.
        """
        data = {"email": "foo@bar.com"}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(len(mail.outbox), 0)

    def test_cleaned_data(self):
        """
        Tests the password reset functionality by creating a dummy user, filling out a password reset form with the user's email, verifying the form's validity, saving the form, and confirming that a password reset email is sent.
        """
        (user, username, email) = self.create_dummy_user()
        data = {"email": email}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        form.save(domain_override="example.com")
        self.assertEqual(form.cleaned_data["email"], email)
        self.assertEqual(len(mail.outbox), 1)

    def test_custom_email_subject(self):
        """
        Tests that the password reset form sends a custom email with the correct subject line when the domain override is specified.
        """
        data = {"email": "testclient@example.com"}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        # Since we're not providing a request object, we must provide a
        # domain_override to prevent the save operation from failing in the
        # potential case where contrib.sites is not installed. Refs #16412.
        form.save(domain_override="example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Custom password reset on example.com")

    def test_custom_email_constructor(self):
        """
        Tests the custom email password reset form and its ability to construct and send emails, verifying that it works correctly and sends an email with the expected subject, body, and recipient configuration.
        """
        data = {"email": "testclient@example.com"}

        class CustomEmailPasswordResetForm(PasswordResetForm):
            def send_mail(
                self,
                subject_template_name,
                email_template_name,
                context,
                from_email,
                to_email,
                html_email_template_name=None,
            ):
                EmailMultiAlternatives(
                    "Forgot your password?",
                    "Sorry to hear you forgot your password.",
                    None,
                    [to_email],
                    ["site_monitor@example.com"],
                    headers={"Reply-To": "webmaster@example.com"},
                    alternatives=[
                        ("Really sorry to hear you forgot your password.", "text/html")
                    ],
                ).send()

        form = CustomEmailPasswordResetForm(data)
        self.assertTrue(form.is_valid())
        # Since we're not providing a request object, we must provide a
        # domain_override to prevent the save operation from failing in the
        # potential case where contrib.sites is not installed. Refs #16412.
        form.save(domain_override="example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Forgot your password?")
        self.assertEqual(mail.outbox[0].bcc, ["site_monitor@example.com"])
        self.assertEqual(mail.outbox[0].content_subtype, "plain")

    def test_preserve_username_case(self):
        """
        Verify that the case of the username in an email address is preserved when creating a new user, ensuring consistency in user identification.
        """
        user = User.objects.create_user("forms_test2", "tesT@EXAMple.com", "test")
        self.assertEqual(user.email, "tesT@example.com")
        user = User.objects.create_user("forms_test3", "tesT", "test")
        self.assertEqual(user.email, "tesT")

    def test_inactive_user(self):
        """
        Tests that an inactive user does not receive a password reset email.
        """
        (user, username, email) = self.create_dummy_user()
        user.is_active = False
        user.save()
        form = PasswordResetForm({"email": email})
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_unusable_password(self):
        """
        Tests that a password reset form remains valid and doesn't send a password reset email when the user's password is set to unusable. Verifies that the form behaves correctly in this edge case.
        """
        user = User.objects.create_user("testuser", "test@example.com", "test")
        data = {"email": "test@example.com"}
        form = PasswordResetForm(data)
        self.assertTrue(form.is_valid())
        user.set_unusable_password()
        user.save()
        form = PasswordResetForm(data)
        # The form itself is valid, but no email is sent
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_save_plaintext_email(self):
        """

            Test the PasswordResetForm's save method functionality with plaintext email.
            Verifies that the original behavior remains unchanged and the method sends a
            single plaintext email with a password reset link to the provided email address.

        """
        (user, username, email) = self.create_dummy_user()
        form = PasswordResetForm({"email": email})
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0].message()
        self.assertFalse(message.is_multipart())
        self.assertEqual(message.get_content_type(), "text/plain")
        self.assertEqual(message.get("subject"), "Custom password reset on example.com")
        self.assertEqual(len(mail.outbox[0].alternatives), 0)
        self.assertEqual(message.get_all("to"), [email])
        self.assertTrue(
            re.match(r"^http://example.com/reset/[\w+/-]", message.get_payload())
        )

    def test_save_html_email_template_name(self):
        """
        Tests the PasswordResetForm's save method with a specified HTML email template, ensuring a multipart email is sent with both text and HTML parts.
        """
        (user, username, email) = self.create_dummy_user()
        form = PasswordResetForm({"email": email})
        self.assertTrue(form.is_valid())
        form.save(
            html_email_template_name="registration/html_password_reset_email.html"
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        message = mail.outbox[0].message()
        self.assertEqual(message.get("subject"), "Custom password reset on example.com")
        self.assertEqual(len(message.get_payload()), 2)
        self.assertTrue(message.is_multipart())
        self.assertEqual(message.get_payload(0).get_content_type(), "text/plain")
        self.assertEqual(message.get_payload(1).get_content_type(), "text/html")
        self.assertEqual(message.get_all("to"), [email])
        self.assertTrue(
            re.match(
                r"^http://example.com/reset/[\w/-]+",
                message.get_payload(0).get_payload(),
            )
        )
        self.assertTrue(
            re.match(
                r'^<html><a href="http://example.com/reset/[\w/-]+/">Link</a></html>$',
                message.get_payload(1).get_payload(),
            )
        )

    @override_settings(AUTH_USER_MODEL="auth_tests.CustomEmailField")
    def test_custom_email_field(self):
        """
        Tests password reset functionality with a custom email field, verifying form validation and email delivery.
        """
        email = "test@mail.com"
        CustomEmailField.objects.create_user("test name", "test password", email)
        form = PasswordResetForm({"email": email})
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(form.cleaned_data["email"], email)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [email])

    def test_html_autocomplete_attributes(self):
        form = PasswordResetForm()
        self.assertEqual(form.fields["email"].widget.attrs["autocomplete"], "email")


class ReadOnlyPasswordHashTest(SimpleTestCase):
    def test_bug_19349_render_with_none_value(self):
        # Rendering the widget with value set to None
        # mustn't raise an exception.
        widget = ReadOnlyPasswordHashWidget()
        html = widget.render(name="password", value=None, attrs={})
        self.assertIn(_("No password set."), html)

    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
    )
    def test_render(self):
        widget = ReadOnlyPasswordHashWidget()
        value = (
            "pbkdf2_sha256$100000$a6Pucb1qSFcD$WmCkn9Hqidj48NVe5x0FEM6A9YiOqQcl/83m2Z5u"
            "dm0="
        )
        self.assertHTMLEqual(
            widget.render("name", value, {"id": "id_password"}),
            '<div id="id_password">'
            "  <p>"
            "    <strong>algorithm</strong>: <bdi>pbkdf2_sha256</bdi>"
            "    <strong>iterations</strong>: <bdi>100000</bdi>"
            "    <strong>salt</strong>: <bdi>a6Pucb******</bdi>"
            "    <strong>hash</strong>: "
            "       <bdi>WmCkn9**************************************</bdi>"
            "  </p>"
            '  <p><a class="button" href="../password/">Reset password</a></p>'
            "</div>",
        )

    def test_readonly_field_has_changed(self):
        field = ReadOnlyPasswordHashField()
        self.assertIs(field.disabled, True)
        self.assertFalse(field.has_changed("aaa", "bbb"))

    def test_label(self):
        """
        Verify that the ReadOnlyPasswordHashWidget correctly handles label generation, 
        as it does not contain a labelable element and should return None for id_for_label.
        """

        class TestForm(forms.Form):
            hash_field = ReadOnlyPasswordHashField()

        bound_field = TestForm()["hash_field"]
        self.assertIsNone(bound_field.field.widget.id_for_label("id"))
        self.assertEqual(bound_field.label_tag(), "<label>Hash field:</label>")


class AdminPasswordChangeFormTest(TestDataMixin, TestCase):
    @mock.patch("django.contrib.auth.password_validation.password_changed")
    def test_success(self, password_changed):
        """
        Tests the successful changing of a user's password using the AdminPasswordChangeForm. 

        Verifies that the password_changed signal is sent when the form is saved, 
        and that the changed_data attribute of the form is correctly updated.
        """
        user = User.objects.get(username="testclient")
        data = {
            "password1": "test123",
            "password2": "test123",
        }
        form = AdminPasswordChangeForm(user, data)
        self.assertTrue(form.is_valid())
        form.save(commit=False)
        self.assertEqual(password_changed.call_count, 0)
        form.save()
        self.assertEqual(password_changed.call_count, 1)
        self.assertEqual(form.changed_data, ["password"])

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": (
                    "django.contrib.auth.password_validation."
                    "UserAttributeSimilarityValidator"
                )
            },
            {
                "NAME": (
                    "django.contrib.auth.password_validation.MinimumLengthValidator"
                ),
                "OPTIONS": {
                    "min_length": 12,
                },
            },
        ]
    )
    def test_validates_password(self):
        """
        Checks the validation of passwords during the administration password change process, ensuring that the password is not similar to the username and meets the minimum length requirement.
        """
        user = User.objects.get(username="testclient")
        data = {
            "password1": "testclient",
            "password2": "testclient",
        }
        form = AdminPasswordChangeForm(user, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form["password2"].errors), 2)
        self.assertIn(
            "The password is too similar to the username.",
            form["password2"].errors,
        )
        self.assertIn(
            "This password is too short. It must contain at least 12 characters.",
            form["password2"].errors,
        )

        # passwords are not validated if `usable_password` is unset
        data = {
            "password1": "testclient",
            "password2": "testclient",
            "usable_password": "false",
        }
        form = AdminPasswordChangeForm(user, data)
        self.assertIs(form.is_valid(), True, form.errors)

    def test_password_whitespace_not_stripped(self):
        """
        Tests that leading and trailing whitespace in passwords is preserved and not stripped by the AdminPasswordChangeForm
        """
        user = User.objects.get(username="testclient")
        data = {
            "password1": " pass ",
            "password2": " pass ",
        }
        form = AdminPasswordChangeForm(user, data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["password1"], data["password1"])
        self.assertEqual(form.cleaned_data["password2"], data["password2"])
        self.assertEqual(form.changed_data, ["password"])

    def test_password_extra_validations(self):
        """
        Tests that the password change form correctly handles extra validation errors for the password fields, ensuring that the form is invalid and the expected error messages are displayed when validation fails for one or both password fields.
        """
        class ExtraValidationForm(ExtraValidationFormMixin, AdminPasswordChangeForm):
            def clean_password1(self):
                return self.failing_helper("password1")

            def clean_password2(self):
                return self.failing_helper("password2")

        user = User.objects.get(username="testclient")
        data = {"username": "extra", "password1": "abc", "password2": "abc"}
        for fields in (["password1"], ["password2"], ["password1", "password2"]):
            with self.subTest(fields=fields):
                errors = {field: [f"Extra validation for {field}."] for field in fields}
                form = ExtraValidationForm(user, data, failing_fields=errors)
                self.assertIs(form.is_valid(), False)
                self.assertDictEqual(form.errors, errors)

    def test_non_matching_passwords(self):
        """
        Tests that the AdminPasswordChangeForm correctly handles non-matching password inputs, verifying that a password mismatch error is raised and no password change is applied.
        """
        user = User.objects.get(username="testclient")
        data = {"password1": "password1", "password2": "password2"}
        form = AdminPasswordChangeForm(user, data)
        self.assertEqual(
            form.errors["password2"], [form.error_messages["password_mismatch"]]
        )
        self.assertEqual(form.changed_data, ["password"])

    def test_missing_passwords(self):
        """
        Tests that a password change form correctly reports errors when both password fields are left empty.
        """
        user = User.objects.get(username="testclient")
        data = {"password1": "", "password2": ""}
        form = AdminPasswordChangeForm(user, data)
        required_error = [Field.default_error_messages["required"]]
        self.assertEqual(form.errors["password1"], required_error)
        self.assertEqual(form.errors["password2"], required_error)
        self.assertEqual(form.changed_data, [])

    def test_one_password(self):
        """
        Tests that AdminPasswordChangeForm correctly validates password fields.

        Ensures that both password fields are required and that errors are raised accordingly when either field is empty.

        """
        user = User.objects.get(username="testclient")
        form1 = AdminPasswordChangeForm(user, {"password1": "", "password2": "test"})
        required_error = [Field.default_error_messages["required"]]
        self.assertEqual(form1.errors["password1"], required_error)
        self.assertNotIn("password2", form1.errors)
        self.assertEqual(form1.changed_data, [])
        form2 = AdminPasswordChangeForm(user, {"password1": "test", "password2": ""})
        self.assertEqual(form2.errors["password2"], required_error)
        self.assertNotIn("password1", form2.errors)
        self.assertEqual(form2.changed_data, [])

    def test_html_autocomplete_attributes(self):
        """

        Tests that the autocomplete attributes for password fields in the AdminPasswordChangeForm are correctly set.
        Verifies that the 'password1' and 'password2' fields have their autocomplete attributes set to 'new-password'.

        """
        user = User.objects.get(username="testclient")
        form = AdminPasswordChangeForm(user)
        tests = (
            ("password1", "new-password"),
            ("password2", "new-password"),
        )
        for field_name, autocomplete in tests:
            with self.subTest(field_name=field_name, autocomplete=autocomplete):
                self.assertEqual(
                    form.fields[field_name].widget.attrs["autocomplete"], autocomplete
                )

    def test_enable_password_authentication(self):
        """
        Tests enabling password authentication for a user with an unusable password by changing their password through the admin interface.
        """
        user = User.objects.get(username="unusable_password")
        form = AdminPasswordChangeForm(
            user,
            {"password1": "complexpassword", "password2": "complexpassword"},
        )
        self.assertNotIn("usable_password", form.fields)
        self.assertIs(form.is_valid(), True)
        user = form.save(commit=True)
        self.assertIs(user.has_usable_password(), True)

    def test_disable_password_authentication(self):
        """

        Tests the disabling of password authentication for a user.

        Verifies that the password can be disabled through the AdminPasswordChangeForm,
        and that the user's current password is lost after disabling.

        """
        user = User.objects.get(username="testclient")
        form = AdminPasswordChangeForm(
            user,
            {"usable_password": "false", "password1": "", "password2": "test"},
        )
        self.assertIn("usable_password", form.fields)
        self.assertIn(
            "If disabled, the current password for this user will be lost.",
            form.fields["usable_password"].help_text,
        )
        self.assertIs(form.is_valid(), True)  # Valid despite password empty/mismatch.
        user = form.save(commit=True)
        self.assertIs(user.has_usable_password(), False)
