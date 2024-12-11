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
        """

        Tests the get_form method of the FormMixin class.

        Checks that the method correctly instantiates and returns a form instance
        when a form class is explicitly provided, and that it falls back to using
        the form_class attribute if no form class is provided.

        Verifies that the returned object is an instance of the expected form class.

        """
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
        """
        Tests the functionality of posting data to the contact endpoint.

        This function sends a POST request to the contact endpoint with sample data, 
        including a name and a message, and verifies that the response redirects 
        to the authors list page, indicating a successful submission.
        """
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

        Tests that the form class returned by :meth:`views.AuthorGetQuerySetFormView.get_form_class` 
        is based on the Author model.

        This test ensures that the correct model is used when generating the form, 
        which is essential for proper form functionality and data validation.

        """
        form_class = views.AuthorGetQuerySetFormView().get_form_class()
        self.assertEqual(form_class._meta.model, Author)

    def test_get_form_checks_for_object(self):
        """
        @return: Dictionary containing keyword arguments to be passed to the form instance.
        @rtype: dict

        Checks that the ModelFormMixin's get_form_kwargs method returns the correct keyword arguments when no initial data or prefix is provided. 

        The expected keyword arguments include an empty dictionary for initial form data and None for the form prefix. 

        This test ensures that the form instance is initialized correctly with default values when no additional configuration is specified.
        """
        mixin = ModelFormMixin()
        mixin.request = RequestFactory().get("/")
        self.assertEqual({"initial": {}, "prefix": None}, mixin.get_form_kwargs())


@override_settings(ROOT_URLCONF="generic_views.urls")
class CreateViewTests(TestCase):
    def test_create(self):
        """
        Tests the creation of a new author.

        This test case covers the following scenarios:
        - A successful GET request to the author creation page, verifying the 
          response status code, form and view instances, and template usage.
        - A successful POST request to create a new author, verifying the 
          response status code, redirect to the author list page, and that 
          the new author is added to the database.

        This ensures that the author creation functionality works as expected 
        and that the new author is correctly added to the database upon 
        successful form submission.
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
        res = self.client.post(
            "/edit/authors/create/", {"name": "A" * 101, "slug": "randall-munroe"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_form.html")
        self.assertEqual(len(res.context["form"].errors), 1)
        self.assertEqual(Author.objects.count(), 0)

    def test_create_with_object_url(self):
        """
        Tests the creation of an artist via a POST request to the artist creation endpoint.

        This test verifies that the request is successful, resulting in a redirect to the newly created artist's detail page.
        The test also confirms that the artist object is correctly saved to the database, and that the redirect URL matches the expected format.
        """
        res = self.client.post("/edit/artists/create/", {"name": "Rene Magritte"})
        self.assertEqual(res.status_code, 302)
        artist = Artist.objects.get(name="Rene Magritte")
        self.assertRedirects(res, "/detail/artist/%d/" % artist.pk)
        self.assertQuerySetEqual(Artist.objects.all(), [artist])

    def test_create_with_redirect(self):
        """

        Test the creation of an author with a redirect.

        This test case verifies that when an author is created with a valid name and slug,
        the request is redirected to the authors create page and the author is successfully added to the database.
        The test checks for a successful HTTP redirect status code and confirms the author's presence in the database.

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

        Tests the creation of an author object with interpolated redirect URLs.

        This test checks that when a new author is created, the user is redirected to the author update page.
        It verifies that the redirect URL is correctly interpolated with the author's primary key.
        The test covers both ASCII and non-ASCII redirect URLs to ensure proper encoding.

        Upon successful creation, the test asserts that the author object is saved to the database and
        that the HTTP response status code is 302 (Found), indicating a redirect.

        The test also checks that the redirect URL is correctly formatted, including the author's primary key,
        and that the URL is properly encoded for non-ASCII characters.

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
        """

        Tests the creation of an author with special properties through the edit authors create view.

        Verifies that a GET request to the view returns a successful response (200 status code) with the correct form instance and template.
        Additionally, tests that a POST request to the view creates a new author object and redirects to the author's detail page.

        Ensures that the author object is properly created and stored in the database, with the correct attributes and relationships.

        """
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
        """

        Tests the creation of a restricted author.

        This test case checks if the creation of a restricted author is correctly redirected to the login page.
        It verifies that the HTTP request returns a 302 status code and redirects to the login URL with the
        expected next parameter.

        The test scenario involves attempting to create a restricted author without being logged in, and
        verifying that the application behaves as expected by redirecting to the login page.

        """
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
        Tests that the CreateView class correctly creates a form with all fields 
        when 'fields' attribute is set to '__all__'. This test case verifies that 
        the form generated by CreateView contains all fields of the specified model, 
        excluding any that are automatically managed by Django, and that the fields 
        are properly ordered and identified. The test checks that the form contains 
        the expected fields and that their names match the model's field names.
        """
        class MyCreateView(CreateView):
            model = Author
            fields = "__all__"

        self.assertEqual(
            list(MyCreateView().get_form_class().base_fields), ["name", "slug"]
        )

    def test_create_view_without_explicit_fields(self):
        """
        Tests that creating a view without specifying explicit fields raises an ImproperlyConfigured exception.

         This test case checks that using ModelFormMixin without defining the 'fields' attribute results in an error.

         :raises ImproperlyConfigured: If the 'fields' attribute is not specified in the view.

        """
        class MyCreateView(CreateView):
            model = Author

        message = (
            "Using ModelFormMixin (base class of MyCreateView) without the "
            "'fields' attribute is prohibited."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, message):
            MyCreateView().get_form_class()

    def test_define_both_fields_and_form_class(self):
        """
        Tests that defining both 'fields' and 'form_class' in a CreateView raises an ImproperlyConfigured exception. 
        This ensures that users are prevented from misconfiguring their view by specifying both a form class and a set of fields, which are mutually exclusive configuration options.
        """
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
        Tests the update post functionality for an author.

        This test case verifies that a GET request to the update author page returns
        a successful response with the correct form and author context. It also checks
        that the correct template is used to render the page.

        Additionally, it tests that a POST request to the update author page with valid
        data successfully updates the author's name and redirects to the author list
        page. The test also ensures that the updated author name is persisted in the
        database.

        The test covers the following scenarios:
        - Successful GET request to the update author page
        - Successful POST request to the update author page with valid data
        - Redirect to the author list page after a successful update
        - Persistence of the updated author name in the database
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

        Verifies that when an update request is made with invalid data (in this case, an author name exceeding the maximum allowed length), 
        the response status code is 200, the author form template is displayed, and a validation error is raised.
        Additionally, it checks that no changes are made to the author object in the database and that the view's get_form method is called once.
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
        """

        Tests the update functionality with interpolated redirects.

        This test case checks that updates to an author's name and slug are successfully applied and 
        that the system correctly redirects to the updated author's edit page after the changes have been made. 
        The test covers two scenarios: 
        - updating an author's details with a redirect to the author's edit page using the author's primary key in the URL path, 
        - updating an author's details with a redirect to the author's edit page using a non-ASCII character in the URL path.

        The tests verify that the redirects are correctly encoded and that the HTTP status code for the redirect response is 302.

        """
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
        Tests the update functionality for authors with special properties.

        This test case verifies that the update view for authors with special properties
        functions correctly, including rendering the form and handling form submissions.
        It checks the HTTP status codes, form instances, and context variables passed to
        the template. Additionally, it validates the update operation by checking the
        redirect URL and the updated author data in the database.

        The test covers the following scenarios:

        * GET request: Verifies that the view returns a 200 status code, renders the
          correct template, and passes the expected context variables.
        * POST request: Verifies that the view updates the author data correctly, returns
          a 302 status code, and redirects to the author detail page.

        The test ensures that the update functionality works as expected and the
        author data is updated correctly in the database.
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
        Tests that an update operation without a redirect URL raises an ImproperlyConfigured error.

        Verifies that when updating an object, an exception is raised if no URL to redirect to is provided, 
        either by supplying a URL or defining a get_absolute_url method on the Model. The error message 
        indicates that a URL or get_absolute_url method must be defined for the operation to proceed.

        Args:
            None

        Raises:
            ImproperlyConfigured: If no redirect URL is provided or get_absolute_url method is not defined.

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
        """

        Tests the update functionality of an author object through a GET and POST request.

        The test case covers the following scenarios:
        - A GET request to the update view returns a successful response (200 status code)
          with a rendered form and the correct author object.
        - A POST request to the update view with valid form data updates the author object
          and redirects to the authors list page.
        - The update is successfully persisted in the database.

        Verifies that the view uses the correct template, form, and view class.

        """
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
        .Tests the deletion of an author via a POST request.

        The test covers the following steps:
        - Retrieves the delete confirmation page for an author.
        - Verifies that the page is successfully loaded (status code 200) and the correct author object is passed to the template.
        - Submits the deletion form via a POST request.
        - Checks that the deletion is successful, resulting in a redirect (status code 302) to the authors list page.
        - Confirms that the author is removed from the database after deletion.
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
        """

        Test that deleting an author redirects to the create authors page and removes the author from the database.

        This test case verifies the successful deletion of an author by checking for a redirect
        to the author creation page and ensuring that the author is no longer present in the database.

        """
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
        """

        Tests the deletion of an author object through a special delete view.

        This test case checks the following scenarios:
        - A GET request to the delete view returns a 200 status code and the correct template, 
          along with the author object in the template context.
        - The template context does not contain an 'author' key.
        - A POST request to the delete view successfully deletes the author object and redirects 
          to the authors list page.
        - After deletion, the authors list is empty, verifying that the object was successfully removed.

        """
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
        """
        Tests that deleting an author without specifying a redirect URL raises an ImproperlyConfigured exception.

        The function sends a POST request to delete an author instance via a naive deletion endpoint and verifies that 
        the expected error message 'No URL to redirect to. Provide a success_url.' is returned when no redirect URL is provided.

        This test case ensures that the application correctly handles deletion actions when a success URL is not specified, 
        providing a safeguard against unexpected behavior or potential security vulnerabilities.
        """
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

        Tests the deletion of an author using a form submitted via POST request,
        verifying that a validation error is raised when the form is invalid.

        Checks that:
        - The form page is rendered correctly with a 200 status code.
        - The form is populated with the correct author object.
        - The correct template is used to render the form.
        - When the form is submitted without validation, a 200 status code is returned.
        - The form validation errors are correctly reported, including a global error
          requiring confirmation and a field-specific error for the confirm field.

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
