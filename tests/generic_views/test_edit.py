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
        """
        Verifies that the initial data dictionary is instance-independent, ensuring each instance of FormMixin generates a unique initial data set.
        """
        initial_1 = FormMixin().get_initial()
        initial_1["foo"] = "bar"
        initial_2 = FormMixin().get_initial()
        self.assertNotEqual(initial_1, initial_2)

    def test_get_prefix(self):
        """
        Tests the functionality of setting and retrieving the prefix in a FormMixin instance.
        """
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
        Tests the get_form method to ensure it returns an instance of the provided form class, or falls back to the form_class attribute if none is provided.
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
        form_class = views.AuthorGetQuerySetFormView().get_form_class()
        self.assertEqual(form_class._meta.model, Author)

    def test_get_form_checks_for_object(self):
        mixin = ModelFormMixin()
        mixin.request = RequestFactory().get("/")
        self.assertEqual({"initial": {}, "prefix": None}, mixin.get_form_kwargs())


@override_settings(ROOT_URLCONF="generic_views.urls")
class CreateViewTests(TestCase):
    def test_create(self):
        """
        Tests the creation of a new author, ensuring the creation page is accessible, displays the correct form and template, and successfully redirects to the author list after submission.
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
        Tests that creating an author with an invalid name (exceeding the maximum character limit) results in a form error and prevents the author from being saved.
        """
        res = self.client.post(
            "/edit/authors/create/", {"name": "A" * 101, "slug": "randall-munroe"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_form.html")
        self.assertEqual(len(res.context["form"].errors), 1)
        self.assertEqual(Author.objects.count(), 0)

    def test_create_with_object_url(self):
        """
        Tests the creation of a new artist via POST request to the '/edit/artists/create/' endpoint, verifying a successful redirect to the artist's detail page and the correct addition of the artist to the database.
        """
        res = self.client.post("/edit/artists/create/", {"name": "Rene Magritte"})
        self.assertEqual(res.status_code, 302)
        artist = Artist.objects.get(name="Rene Magritte")
        self.assertRedirects(res, "/detail/artist/%d/" % artist.pk)
        self.assertQuerySetEqual(Artist.objects.all(), [artist])

    def test_create_with_redirect(self):
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
        Tests the creation of an author with an interpolated redirect after a successful POST request, verifying that the author is created, a redirect to the author's update page occurs, and non-ASCII characters are correctly handled in the redirect URL.
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
        Tests the creation of a new author with special properties, verifying that the form is correctly rendered and that the author is successfully created and redirected to the author detail page.
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
        class MyCreateView(CreateView):
            model = Author
            fields = "__all__"

        self.assertEqual(
            list(MyCreateView().get_form_class().base_fields), ["name", "slug"]
        )

    def test_create_view_without_explicit_fields(self):
        """
        Tests that creating a view without explicitly defining fields raises an ImproperlyConfigured exception.
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
        Tests that defining both 'fields' and 'form_class' in a CreateView raises an ImproperlyConfigured error, as this configuration is not permitted.
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
        Tests the update post functionality for an author, verifying that the update form is successfully rendered and that the update operation redirects to the author list page after successfully updating the author's information.
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
        Tests the updating of an author with invalid input, verifying that the update fails and the original author data remains unchanged, with an error message displayed to the user.
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
        ..: Tests the update functionality for an artist object using a URL. 

            This checks that the update request is successful, with a 302 status code, 
            and that the response redirects to the artist's detail page. It also 
            verifies that the artist object remains unchanged in the database.
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
        """
        Tests that the update view correctly handles redirects after updating an author,
        including cases where the redirect URL contains non-ASCII characters, ensuring
        the user is sent to the correct edit page following a successful update.
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
        Tests the special update view for authors, ensuring it renders the correct form and template, and correctly handles GET and POST requests to update an author's properties.
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
        \".. 
            Tests the update functionality of the author object, verifying that a GET request 
            returns a 200 status code with the correct form and context, and that a POST request 
            successfully updates the author object and redirects to the authors list page. 
        \"
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

        Tests the deletion of an author object via a POST request.

        Verifies that the deletion page is correctly rendered, the object is properly removed,
        and the user is redirected to the authors list page after deletion.

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
        """
        Tests deletion of an author object with interpolated redirect.

        Checks that deleting an author redirects to the create author page with a 
        deleted parameter, and that the author is successfully removed from the database.
        Also tests non-ASCII character handling in the redirect URL.
        """
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
        Tests deletion of an author object using a special delete view, 
        verifying the response and template used in the GET request, as well as 
        the redirect and deletion of the object after a POST request.
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
        msg = "No URL to redirect to. Provide a success_url."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.post("/edit/author/%d/delete/naive/" % self.author.pk)

    def test_delete_with_form_as_post(self):
        """
        Tests the deletion of an author via a POST form submission, verifying that the deletion form is correctly rendered and that the author is successfully removed after confirmation.
        """
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
        Tests the author deletion form handles POST requests with validation errors, ensuring the form is rendered correctly and error messages are displayed when required fields are not provided.
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
