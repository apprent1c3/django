import datetime

from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.test import TestCase, override_settings
from django.test.client import RequestFactory
from django.views.generic.base import View
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin

from .models import Artist, Author, Book, Page


@override_settings(ROOT_URLCONF="generic_views.urls")
class DetailViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.artist1 = Artist.objects.create(name="Rene Magritte")
        cls.author1 = Author.objects.create(
            name="Roberto Bolaño", slug="roberto-bolano"
        )
        cls.author2 = Author.objects.create(
            name="Scott Rosenberg", slug="scott-rosenberg"
        )
        cls.book1 = Book.objects.create(
            name="2066", slug="2066", pages=800, pubdate=datetime.date(2008, 10, 1)
        )
        cls.book1.authors.add(cls.author1)
        cls.book2 = Book.objects.create(
            name="Dreaming in Code",
            slug="dreaming-in-code",
            pages=300,
            pubdate=datetime.date(2006, 5, 1),
        )
        cls.page1 = Page.objects.create(
            content="I was once bitten by a moose.",
            template="generic_views/page_template.html",
        )

    def test_simple_object(self):
        res = self.client.get("/detail/obj/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], {"foo": "bar"})
        self.assertIsInstance(res.context["view"], View)
        self.assertTemplateUsed(res, "generic_views/detail.html")

    def test_detail_by_pk(self):
        res = self.client.get("/detail/author/%s/" % self.author1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_missing_object(self):
        res = self.client.get("/detail/author/500/")
        self.assertEqual(res.status_code, 404)

    def test_detail_object_does_not_exist(self):
        """
        \Tests that a 404 error is raised when attempting to retrieve a detail object that does not exist.

        This test case verifies the application's behavior when a user tries to access a non-existent detail object via the '/detail/<object_name>/<id>/' endpoint. The expected outcome is that the application raises an ObjectDoesNotExist exception, indicating that the requested object does not exist in the system.
        """
        with self.assertRaises(ObjectDoesNotExist):
            self.client.get("/detail/doesnotexist/1/")

    def test_detail_by_custom_pk(self):
        """

        Tests the detail view of an author by custom primary key.

        Verifies that the view returns a successful response, contains the expected author
        object, and uses the correct template.

        Checks the following conditions:
            - A GET request to the detail view URL with a custom primary key returns a 200 status code.
            - The response context contains the expected author object.
            - The response context contains the author object under the 'author' key.
            - The response uses the 'generic_views/author_detail.html' template.

        """
        res = self.client.get("/detail/author/bycustompk/%s/" % self.author1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_slug(self):
        res = self.client.get("/detail/author/byslug/scott-rosenberg/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.context["object"], Author.objects.get(slug="scott-rosenberg")
        )
        self.assertEqual(
            res.context["author"], Author.objects.get(slug="scott-rosenberg")
        )
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_custom_slug(self):
        """

        Tests the detail view for an author object retrieved by a custom slug.

        This test case ensures that the detail view returns a successful HTTP response
        (200 status code) when an author object is accessed via a custom slug.
        It verifies that the correct author object is retrieved from the database
        and passed to the template context, and that the expected template is rendered.

        """
        res = self.client.get("/detail/author/bycustomslug/scott-rosenberg/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.context["object"], Author.objects.get(slug="scott-rosenberg")
        )
        self.assertEqual(
            res.context["author"], Author.objects.get(slug="scott-rosenberg")
        )
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_pk_ignore_slug(self):
        res = self.client.get(
            "/detail/author/bypkignoreslug/%s-roberto-bolano/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_pk_ignore_slug_mismatch(self):
        """

        Tests that the author detail view correctly retrieves an author by primary key, 
        ignoring any mismatch in the slug.

        Verifies that the HTTP request is successful, the correct author object is 
        retrieved, and the expected template is used to render the response.

        """
        res = self.client.get(
            "/detail/author/bypkignoreslug/%s-scott-rosenberg/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_pk_and_slug(self):
        """
        Tests the retrieval of an author's detail page using both the primary key and slug.

            This test case verifies that the author detail page can be accessed using a URL that combines 
            the primary key and slug of the author. It checks that the HTTP request is successful (200 status code), 
            that the correct author object is retrieved, and that the correct template is used to render the page.
        """
        res = self.client.get(
            "/detail/author/bypkandslug/%s-roberto-bolano/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_pk_and_slug_mismatch_404(self):
        res = self.client.get(
            "/detail/author/bypkandslug/%s-scott-rosenberg/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 404)

    def test_verbose_name(self):
        res = self.client.get("/detail/artist/%s/" % self.artist1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.artist1)
        self.assertEqual(res.context["artist"], self.artist1)
        self.assertTemplateUsed(res, "generic_views/artist_detail.html")

    def test_template_name(self):
        """
        Tests that the template name view for an author returns the correct status code, 
        context and template.

        The view is expected to respond with a 200 status code and the context should 
        contain the author object under both 'object' and 'author' keys. Additionally, 
        the view should render the 'generic_views/about.html' template.

        This test case ensures that the author's detail page with the template name 
        is correctly displayed and the required data is passed to the template.
        """
        res = self.client.get("/detail/author/%s/template_name/" % self.author1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/about.html")

    def test_template_name_suffix(self):
        """
        Tests the template name suffix in the author detail view.

            Verifies that the view returns a successful response, renders the correct
            template, and passes the expected context variables. The test checks the
            HTTP status code, the object and author context variables, and the
            template used to render the view.

            This test case ensures that the author detail view functions as expected
            when the template name suffix is used, providing a solid foundation for
            further testing and development of the view.

        """
        res = self.client.get(
            "/detail/author/%s/template_name_suffix/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_view.html")

    def test_template_name_field(self):
        res = self.client.get("/detail/page/%s/field/" % self.page1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.page1)
        self.assertEqual(res.context["page"], self.page1)
        self.assertTemplateUsed(res, "generic_views/page_template.html")

    def test_context_object_name(self):
        """

        Tests the context object name for an author detail view.

        Verifies that the view returns a successful response, and that the context
        contains the expected author object and variables, while ensuring that
        unnecessary context variables are not present. Also checks that the correct
        template is used for rendering the response.

        """
        res = self.client.get(
            "/detail/author/%s/context_object_name/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["thingy"], self.author1)
        self.assertNotIn("author", res.context)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_duplicated_context_object_name(self):
        res = self.client.get(
            "/detail/author/%s/dupe_context_object_name/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertNotIn("author", res.context)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_custom_detail(self):
        """
        AuthorCustomDetail overrides get() and ensures that
        SingleObjectMixin.get_context_object_name() always uses the obj
        parameter instead of self.object.
        """
        res = self.client.get("/detail/author/%s/custom_detail/" % self.author1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["custom_author"], self.author1)
        self.assertNotIn("author", res.context)
        self.assertNotIn("object", res.context)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_deferred_queryset_template_name(self):
        class FormContext(SingleObjectTemplateResponseMixin):
            request = RequestFactory().get("/")
            model = Author
            object = Author.objects.defer("name").get(pk=self.author1.pk)

        self.assertEqual(
            FormContext().get_template_names()[0], "generic_views/author_detail.html"
        )

    def test_deferred_queryset_context_object_name(self):
        class FormContext(ModelFormMixin):
            request = RequestFactory().get("/")
            model = Author
            object = Author.objects.defer("name").get(pk=self.author1.pk)
            fields = ("name",)

        form_context_data = FormContext().get_context_data()
        self.assertEqual(form_context_data["object"], self.author1)
        self.assertEqual(form_context_data["author"], self.author1)

    def test_invalid_url(self):
        """
        Tests that an AttributeError is raised when attempting to retrieve an author's detail page with an invalid URL.

        This test case verifies that the client correctly handles invalid URLs and raises the expected exception, ensuring the system's robustness and error handling capabilities.

        Args: None

        Returns: None

        Raises: 
            AttributeError: When an invalid URL is provided to the client's get method.
        """
        with self.assertRaises(AttributeError):
            self.client.get("/detail/author/invalid/url/")

    def test_invalid_queryset(self):
        """
        Tests that a proper error is raised when an invalid queryset is used in the AuthorDetail view.

        Checks that an ImproperlyConfigured exception is raised with a specific error message when the view is missing a QuerySet.
        The error message instructs the developer to define AuthorDetail.model, AuthorDetail.queryset, or override AuthorDetail.get_queryset().

        This test case ensures that the application provides clear guidance to users when a common configuration mistake is made, helping to prevent and diagnose issues with the view.
        """
        msg = (
            "AuthorDetail is missing a QuerySet. Define AuthorDetail.model, "
            "AuthorDetail.queryset, or override AuthorDetail.get_queryset()."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/detail/author/invalid/qs/")

    def test_non_model_object_with_meta(self):
        """
        Tests the response of a non-model object view with metadata.

        This test checks that a GET request to the detail view of a non-model object
        results in a successful response (200 status code) and verifies that the 
        object retrieved in the response context has the expected identifier. 
        """
        res = self.client.get("/detail/nonmodel/1/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"].id, "non_model_1")
