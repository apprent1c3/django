from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse
from django.views.generic.base import View
from django.views.generic.edit import CreateView, FormMixin, ModelFormMixin

from . import views
from .forms import AuthorForm
from .models import Artist, Author


class FormMixinTests(SimpleTestCase):
    request_factory = RequestFactory()

    def test_initial_data(self):
        """Test instance independence of initial data dict (see #16138)"""
        initial_1 = FormMixin().get_initial()
        initial_1["foo"] = "bar"
        initial_2 = FormMixin().get_initial()
        self.assertNotEqual(initial_1, initial_2)

    def test_get_prefix(self):
        """Test prefix can be set (see #18872)"""
        test_string = "test"

        get_request = self.request_factory.get("/")

        class TestFormMixin(FormMixin):
            request = get_request

        default_kwargs = TestFormMixin().get_form_kwargs()
        self.assertIsNone(default_kwargs.get("prefix"))

        set_mixin = TestFormMixin()
        set_mixin.prefix = test_string
        set_kwargs = set_mixin.get_form_kwargs()
        self.assertEqual(test_string, set_kwargs.get("prefix"))

    def test_get_form(self):
        class TestFormMixin(FormMixin):
            request = self.request_factory.get("/")

        self.assertIsInstance(
            TestFormMixin().get_form(forms.Form),
            forms.Form,
            "get_form() should use provided form class.",
        )

        class FormClassTestFormMixin(TestFormMixin):
            form_class = forms.Form

        self.assertIsInstance(
            FormClassTestFormMixin().get_form(),
            forms.Form,
            "get_form() should fallback to get_form_class() if none is provided.",
        )

    def test_get_context_data(self):
        class FormContext(FormMixin):
            request = self.request_factory.get("/")
            form_class = forms.Form

        self.assertIsInstance(FormContext().get_context_data()["form"], forms.Form)


@override_settings(ROOT_URLCONF="generic_views.urls")
class BasicFormTests(TestCase):
    def test_post_data(self):
        res = self.client.post("/contact/", {"name": "Me", "message": "Hello"})
        self.assertRedirects(res, "/list/authors/")

    def test_late_form_validation(self):
        """
        A form can be marked invalid in the form_valid() method (#25548).
        """
        res = self.client.post("/late-validation/", {"name": "Me", "message": "Hello"})
        self.assertFalse(res.context["form"].is_valid())


class ModelFormMixinTests(SimpleTestCase):
    def test_get_form(self):
        """
        Tests that the get_form_class method of the AuthorGetQuerySetFormView returns a form class associated with the Author model. 

        This test case ensures correct form configuration for views handling Author instances, validating the expected model relationship.
        """
        form_class = views.AuthorGetQuerySetFormView().get_form_class()
        self.assertEqual(form_class._meta.model, Author)

    def test_get_form_checks_for_object(self):
        """
        Tests the get_form_kwargs method of the ModelFormMixin class to ensure it returns the expected keyword arguments for a form.

        The test case verifies that when no additional data is provided, the method returns an empty dictionary for initial data and None for the prefix, representing the default configuration for form keyword arguments.

        This test is significant to ensure the ModelFormMixin behaves as expected when creating forms, providing a robust foundation for views that require form handling.
        """
        mixin = ModelFormMixin()
        mixin.request = RequestFactory().get("/")
        self.assertEqual({"initial": {}, "prefix": None}, mixin.get_form_kwargs())


@override_settings(ROOT_URLCONF="generic_views.urls")
class CreateViewTests(TestCase):
    def test_create(self):
        """

        Tests the creation of a new author via the author creation view.

        This test case verifies that the creation view returns a successful response
        with the correct form and view instances when accessed via a GET request.
        It also checks that the view uses the expected template.

        Additionally, it tests the creation of a new author by submitting a POST request
        with valid form data and verifies that the response redirects to the author list
        view and that the new author is successfully created in the database.

        """
        res = self.client.get("/edit/authors/create/")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.context["form"], forms.ModelForm)
        self.assertIsInstance(res.context["view"], View)
        self.assertNotIn("object", res.context)
        self.assertNotIn("author", res.context)
        self.assertTemplateUsed(res, "generic_views/author_form.html")

        res = self.client.post(
            "/edit/authors/create/",
            {"name": "Randall Munroe", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/list/authors/")
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True), ["Randall Munroe"]
        )

    def test_create_invalid(self):
        """
        Test the creation of an invalid author.

        Checks that when attempting to create an author with a name that exceeds the maximum allowed length, 
        the following conditions are met:
        - The HTTP response status code is 200 (OK).
        - The 'author_form.html' template is used for rendering.
        - The form contains exactly one error.
        - No new author is created in the database.
        """
        res = self.client.post(
            "/edit/authors/create/", {"name": "A" * 101, "slug": "randall-munroe"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_form.html")
        self.assertEqual(len(res.context["form"].errors), 1)
        self.assertEqual(Author.objects.count(), 0)

    def test_create_with_object_url(self):
        res = self.client.post("/edit/artists/create/", {"name": "Rene Magritte"})
        self.assertEqual(res.status_code, 302)
        artist = Artist.objects.get(name="Rene Magritte")
        self.assertRedirects(res, "/detail/artist/%d/" % artist.pk)
        self.assertQuerySetEqual(Artist.objects.all(), [artist])

    def test_create_with_redirect(self):
        """
        Test creating an author with a redirect after successful creation.

        This test case verifies the functionality of creating a new author by sending a POST request to the specified endpoint.
        It checks that the request is redirected to the expected URL after a successful creation and that the newly created author is added to the database.
        The test ensures that the status code of the response is 302 (indicating a redirect) and that the redirect URL matches the expected path.
        Additionally, it confirms that the created author's name is correctly stored in the database.
        """
        res = self.client.post(
            "/edit/authors/create/redirect/",
            {"name": "Randall Munroe", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/edit/authors/create/")
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True), ["Randall Munroe"]
        )

    def test_create_with_interpolated_redirect(self):
        """

        Test creating an author with an interpolated redirect after successful creation.

        This test case checks the functionality of creating a new author and then redirecting
        to the author's update page. The redirect URL is interpolated based on the author's
        primary key. The test covers two scenarios: one with an ASCII redirect URL and
        another with a non-ASCII redirect URL. It verifies that the author is created
        successfully, the HTTP status code is 302 (Found), and the redirect URL is correct.

        """
        res = self.client.post(
            "/edit/authors/create/interpolate_redirect/",
            {"name": "Randall Munroe", "slug": "randall-munroe"},
        )
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True), ["Randall Munroe"]
        )
        self.assertEqual(res.status_code, 302)
        pk = Author.objects.first().pk
        self.assertRedirects(res, "/edit/author/%d/update/" % pk)
        # Also test with escaped chars in URL
        res = self.client.post(
            "/edit/authors/create/interpolate_redirect_nonascii/",
            {"name": "John Doe", "slug": "john-doe"},
        )
        self.assertEqual(res.status_code, 302)
        pk = Author.objects.get(name="John Doe").pk
        self.assertRedirects(res, "/%C3%A9dit/author/{}/update/".format(pk))

    def test_create_with_special_properties(self):
        res = self.client.get("/edit/authors/create/special/")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.context["form"], views.AuthorForm)
        self.assertNotIn("object", res.context)
        self.assertNotIn("author", res.context)
        self.assertTemplateUsed(res, "generic_views/form.html")

        res = self.client.post(
            "/edit/authors/create/special/",
            {"name": "Randall Munroe", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        obj = Author.objects.get(slug="randall-munroe")
        self.assertRedirects(res, reverse("author_detail", kwargs={"pk": obj.pk}))
        self.assertQuerySetEqual(Author.objects.all(), [obj])

    def test_create_without_redirect(self):
        msg = (
            "No URL to redirect to.  Either provide a url or define a "
            "get_absolute_url method on the Model."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.post(
                "/edit/authors/create/naive/",
                {"name": "Randall Munroe", "slug": "randall-munroe"},
            )

    def test_create_restricted(self):
        res = self.client.post(
            "/edit/authors/create/restricted/",
            {"name": "Randall Munroe", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(
            res, "/accounts/login/?next=/edit/authors/create/restricted/"
        )

    def test_create_view_with_restricted_fields(self):
        class MyCreateView(CreateView):
            model = Author
            fields = ["name"]

        self.assertEqual(list(MyCreateView().get_form_class().base_fields), ["name"])

    def test_create_view_all_fields(self):
        """
        Tests that a CreateView with fields set to '__all__' only includes the model's visible fields in its form.

         This test verifies that the CreateView correctly filters out hidden or internal fields from the model, 
         and only includes the fields that are intended to be user-editable. The test checks the base fields of 
         the form class generated by the CreateView, ensuring they match the expected list of visible fields.
        """
        class MyCreateView(CreateView):
            model = Author
            fields = "__all__"

        self.assertEqual(
            list(MyCreateView().get_form_class().base_fields), ["name", "slug"]
        )

    def test_create_view_without_explicit_fields(self):
        class MyCreateView(CreateView):
            model = Author

        message = (
            "Using ModelFormMixin (base class of MyCreateView) without the "
            "'fields' attribute is prohibited."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, message):
            MyCreateView().get_form_class()

    def test_define_both_fields_and_form_class(self):
        class MyCreateView(CreateView):
            model = Author
            form_class = AuthorForm
            fields = ["name"]

        message = "Specifying both 'fields' and 'form_class' is not permitted."
        with self.assertRaisesMessage(ImproperlyConfigured, message):
            MyCreateView().get_form_class()


@override_settings(ROOT_URLCONF="generic_views.urls")
class UpdateViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(
            pk=1,  # Required for OneAuthorUpdate.
            name="Randall Munroe",
            slug="randall-munroe",
        )

    def test_update_post(self):
        """

        Tests the update functionality of an author post.

        This test case verifies that the update view for an author post returns a successful response,
        renders the correct template with a model form, and correctly updates the author object upon form submission.
        The test covers the following scenarios:

        * Retrieval of the update page for an existing author
        * Verification of the rendered template and form
        * Successful submission of the update form with new author data
        * Redirect to the authors list page after successful update
        * Validation of the updated author data in the database

        """
        res = self.client.get("/edit/author/%d/update/" % self.author.pk)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.context["form"], forms.ModelForm)
        self.assertEqual(res.context["object"], self.author)
        self.assertEqual(res.context["author"], self.author)
        self.assertTemplateUsed(res, "generic_views/author_form.html")
        self.assertEqual(res.context["view"].get_form_called_count, 1)

        # Modification with both POST and PUT (browser compatible)
        res = self.client.post(
            "/edit/author/%d/update/" % self.author.pk,
            {"name": "Randall Munroe (xkcd)", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/list/authors/")
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True), ["Randall Munroe (xkcd)"]
        )

    def test_update_invalid(self):
        """

        Tests the update functionality of an author with invalid input data.

        Verifies that when attempting to update an author with a name exceeding the maximum allowed length,
        the request returns a successful status code, renders the author form template, and includes the expected form error.
        Additionally, confirms that the author object remains unchanged in the database and that the form's validation method was called.

        """
        res = self.client.post(
            "/edit/author/%d/update/" % self.author.pk,
            {"name": "A" * 101, "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_form.html")
        self.assertEqual(len(res.context["form"].errors), 1)
        self.assertQuerySetEqual(Author.objects.all(), [self.author])
        self.assertEqual(res.context["view"].get_form_called_count, 1)

    def test_update_with_object_url(self):
        """
        Tests that updating an artist using a POST request to the update URL redirects 
        to the artist detail page and does not alter the artist's name if the new name is 
        identical to the existing one. 

        Checks the HTTP status code of the response, ensures a successful redirect to the 
        artist detail page, and verifies that no changes have been made to the artist's 
        information in the database. 

        This test case covers the scenario where the update form is submitted with the 
        same data as the existing artist record, ensuring that the update operation has 
        the expected behavior of not modifying the data in this case.
        """
        a = Artist.objects.create(name="Rene Magritte")
        res = self.client.post(
            "/edit/artists/%d/update/" % a.pk, {"name": "Rene Magritte"}
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/detail/artist/%d/" % a.pk)
        self.assertQuerySetEqual(Artist.objects.all(), [a])

    def test_update_with_redirect(self):
        res = self.client.post(
            "/edit/author/%d/update/redirect/" % self.author.pk,
            {"name": "Randall Munroe (author of xkcd)", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/edit/authors/create/")
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True),
            ["Randall Munroe (author of xkcd)"],
        )

    def test_update_with_interpolated_redirect(self):
        res = self.client.post(
            "/edit/author/%d/update/interpolate_redirect/" % self.author.pk,
            {"name": "Randall Munroe (author of xkcd)", "slug": "randall-munroe"},
        )
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True),
            ["Randall Munroe (author of xkcd)"],
        )
        self.assertEqual(res.status_code, 302)
        pk = Author.objects.first().pk
        self.assertRedirects(res, "/edit/author/%d/update/" % pk)
        # Also test with escaped chars in URL
        res = self.client.post(
            "/edit/author/%d/update/interpolate_redirect_nonascii/" % self.author.pk,
            {"name": "John Doe", "slug": "john-doe"},
        )
        self.assertEqual(res.status_code, 302)
        pk = Author.objects.get(name="John Doe").pk
        self.assertRedirects(res, "/%C3%A9dit/author/{}/update/".format(pk))

    def test_update_with_special_properties(self):
        """
        Tests the update functionality with special properties for an author.

        Verifies that a GET request to the update page returns a successful response 
        with the correct template and form instance. Also checks that the context 
        variables are correctly set.

        Subsequently, tests a POST request to update the author's information, 
        checking that the update is successful, the user is redirected to the 
        author's detail page, and the author's name is updated correctly in the 
        database. 

        Ensures that the update process works as expected, handling both the 
        initial retrieval of the update form and the subsequent submission of the 
        updated data.
        """
        res = self.client.get("/edit/author/%d/update/special/" % self.author.pk)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.context["form"], views.AuthorForm)
        self.assertEqual(res.context["object"], self.author)
        self.assertEqual(res.context["thingy"], self.author)
        self.assertNotIn("author", res.context)
        self.assertTemplateUsed(res, "generic_views/form.html")

        res = self.client.post(
            "/edit/author/%d/update/special/" % self.author.pk,
            {"name": "Randall Munroe (author of xkcd)", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/detail/author/%d/" % self.author.pk)
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True),
            ["Randall Munroe (author of xkcd)"],
        )

    def test_update_without_redirect(self):
        """
        Tests that updating an object without a valid redirect URL raises an ImproperlyConfigured exception.

        This test case verifies that attempting to update an object without specifying a URL to redirect to, 
        either by providing a URL or defining a get_absolute_url method on the model, results in the expected error.

        The test checks for a specific error message, ensuring that the exception is raised with the correct information.

        """
        msg = (
            "No URL to redirect to.  Either provide a url or define a "
            "get_absolute_url method on the Model."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.post(
                "/edit/author/%d/update/naive/" % self.author.pk,
                {"name": "Randall Munroe (author of xkcd)", "slug": "randall-munroe"},
            )

    def test_update_get_object(self):
        res = self.client.get("/edit/author/update/")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.context["form"], forms.ModelForm)
        self.assertIsInstance(res.context["view"], View)
        self.assertEqual(res.context["object"], self.author)
        self.assertEqual(res.context["author"], self.author)
        self.assertTemplateUsed(res, "generic_views/author_form.html")

        # Modification with both POST and PUT (browser compatible)
        res = self.client.post(
            "/edit/author/update/",
            {"name": "Randall Munroe (xkcd)", "slug": "randall-munroe"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/list/authors/")
        self.assertQuerySetEqual(
            Author.objects.values_list("name", flat=True), ["Randall Munroe (xkcd)"]
        )


@override_settings(ROOT_URLCONF="generic_views.urls")
class DeleteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(
            name="Randall Munroe",
            slug="randall-munroe",
        )

    def test_delete_by_post(self):
        """
        Tests the functionality of deleting an author object through the web interface.

        This test case simulates a GET request to the delete author page, verifying that the page loads successfully and displays the correct author object.
        Then, it simulates a POST request to confirm the deletion, checking that the request is successful, and the user is redirected to the authors list page.
        Finally, it confirms that the author object has been successfully removed from the database.
        """
        res = self.client.get("/edit/author/%d/delete/" % self.author.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author)
        self.assertEqual(res.context["author"], self.author)
        self.assertTemplateUsed(res, "generic_views/author_confirm_delete.html")

        # Deletion with POST
        res = self.client.post("/edit/author/%d/delete/" % self.author.pk)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/list/authors/")
        self.assertQuerySetEqual(Author.objects.all(), [])

    def test_delete_by_delete(self):
        # Deletion with browser compatible DELETE method
        res = self.client.delete("/edit/author/%d/delete/" % self.author.pk)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/list/authors/")
        self.assertQuerySetEqual(Author.objects.all(), [])

    def test_delete_with_redirect(self):
        res = self.client.post("/edit/author/%d/delete/redirect/" % self.author.pk)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/edit/authors/create/")
        self.assertQuerySetEqual(Author.objects.all(), [])

    def test_delete_with_interpolated_redirect(self):
        res = self.client.post(
            "/edit/author/%d/delete/interpolate_redirect/" % self.author.pk
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/edit/authors/create/?deleted=%d" % self.author.pk)
        self.assertQuerySetEqual(Author.objects.all(), [])
        # Also test with escaped chars in URL
        a = Author.objects.create(
            **{"name": "Randall Munroe", "slug": "randall-munroe"}
        )
        res = self.client.post(
            "/edit/author/{}/delete/interpolate_redirect_nonascii/".format(a.pk)
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/%C3%A9dit/authors/create/?deleted={}".format(a.pk))

    def test_delete_with_special_properties(self):
        res = self.client.get("/edit/author/%d/delete/special/" % self.author.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author)
        self.assertEqual(res.context["thingy"], self.author)
        self.assertNotIn("author", res.context)
        self.assertTemplateUsed(res, "generic_views/confirm_delete.html")

        res = self.client.post("/edit/author/%d/delete/special/" % self.author.pk)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/list/authors/")
        self.assertQuerySetEqual(Author.objects.all(), [])

    def test_delete_without_redirect(self):
        msg = "No URL to redirect to. Provide a success_url."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.post("/edit/author/%d/delete/naive/" % self.author.pk)

    def test_delete_with_form_as_post(self):
        res = self.client.get("/edit/author/%d/delete/form/" % self.author.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author)
        self.assertEqual(res.context["author"], self.author)
        self.assertTemplateUsed(res, "generic_views/author_confirm_delete.html")
        res = self.client.post(
            "/edit/author/%d/delete/form/" % self.author.pk, data={"confirm": True}
        )
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, "/list/authors/")
        self.assertSequenceEqual(Author.objects.all(), [])

    def test_delete_with_form_as_post_with_validation_error(self):
        """
        Tests the delete functionality of an author object using a POST request with a form.

        This test case verifies that the delete form is rendered correctly when a GET request is made.
        It then tests that a POST request with an invalid form (i.e., without confirmation) returns a 200 status code,
        triggers the correct template, and displays the expected validation errors.

        The test checks for the presence of errors in the form, specifically the '__all__' and 'confirm' fields,
        to ensure that the user is properly prompted to confirm the deletion of the author object.
        """
        res = self.client.get("/edit/author/%d/delete/form/" % self.author.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author)
        self.assertEqual(res.context["author"], self.author)
        self.assertTemplateUsed(res, "generic_views/author_confirm_delete.html")

        res = self.client.post("/edit/author/%d/delete/form/" % self.author.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context_data["form"].errors), 2)
        self.assertEqual(
            res.context_data["form"].errors["__all__"],
            ["You must confirm the delete."],
        )
        self.assertEqual(
            res.context_data["form"].errors["confirm"],
            ["This field is required."],
        )
