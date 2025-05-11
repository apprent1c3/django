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
        """

        Sets up test data for the application, creating instances of Artist, Author, Book, and Page models
        with predefined attributes to facilitate testing.

        """
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
        """
        Tests that a simple object is correctly retrieved and rendered via a GET request to the detail view, verifying the status code, response data, view instance, and template usage.
        """
        res = self.client.get("/detail/obj/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], {"foo": "bar"})
        self.assertIsInstance(res.context["view"], View)
        self.assertTemplateUsed(res, "generic_views/detail.html")

    def test_detail_by_pk(self):
        """
        Verifies that an author's detail page can be successfully retrieved by primary key.

        Tests that the HTTP request returns a 200 status code, the correct author object is passed to the template context, 
        and the expected template is used to render the page.
        """
        res = self.client.get("/detail/author/%s/" % self.author1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_missing_object(self):
        res = self.client.get("/detail/author/500/")
        self.assertEqual(res.status_code, 404)

    def test_detail_object_does_not_exist(self):
        with self.assertRaises(ObjectDoesNotExist):
            self.client.get("/detail/doesnotexist/1/")

    def test_detail_by_custom_pk(self):
        """
        Tests that an author detail page can be retrieved successfully by a custom primary key.

        Verifies the page returns a 200 status code, contains the correct author object, and uses the expected template.
        """
        res = self.client.get("/detail/author/bycustompk/%s/" % self.author1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_slug(self):
        """

        Tests that an author's detail view is correctly rendered by slug.

        Verifies that the view returns a 200 status code, the correct author object,
        and the expected template.

        """
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
        Tests that the author detail view can be accessed by a custom slug and renders the correct template with the expected data.
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
        """
        Tests that an author detail page can be retrieved by primary key, 
        regardless of the slug provided in the URL.
        """
        res = self.client.get(
            "/detail/author/bypkignoreslug/%s-roberto-bolano/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_detail.html")

    def test_detail_by_pk_ignore_slug_mismatch(self):
        """
        Checks that the author detail view can be accessed by ID, ignoring any slug mismatches, and returns the correct author object with a 200 status code.
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
        Tests the detail view of an author by their primary key and slug, verifying a successful response and correct template rendering with the expected author object.
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
        """
        Tests the verbose name of the artist detail view, verifying that the correct template is rendered and the expected object is displayed.
        """
        res = self.client.get("/detail/artist/%s/" % self.artist1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.artist1)
        self.assertEqual(res.context["artist"], self.artist1)
        self.assertTemplateUsed(res, "generic_views/artist_detail.html")

    def test_template_name(self):
        """
        Tests the template used to display an author's details, verifying that the correct template is rendered and the expected data is passed to it.
        """
        res = self.client.get("/detail/author/%s/template_name/" % self.author1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/about.html")

    def test_template_name_suffix(self):
        """
        Tests the template name suffix for the author detail view, verifying a successful response, correct object context, and the use of the expected template.
        """
        res = self.client.get(
            "/detail/author/%s/template_name_suffix/" % self.author1.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.author1)
        self.assertEqual(res.context["author"], self.author1)
        self.assertTemplateUsed(res, "generic_views/author_view.html")

    def test_template_name_field(self):
        """
        Tests a generic view for a page detail template, verifying a successful response and correct template and object usage.
        """
        res = self.client.get("/detail/page/%s/field/" % self.page1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.page1)
        self.assertEqual(res.context["page"], self.page1)
        self.assertTemplateUsed(res, "generic_views/page_template.html")

    def test_context_object_name(self):
        """
        Checks the context object name in the author detail view, verifying that the response is successful, the correct author object is passed, and the expected template is used.
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
        """
        Tests that a duplicated context object name does not interfere with template rendering and context data, 
        ensuring the correct object and template are used in the author detail view.
        """
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
        """
        Tests if a deferred queryset correctly resolves template name for a generic view.\"\"\"

         Args:
            None

         Returns:
            None

         Notes:
            Verifies the `get_template_names` method of `SingleObjectTemplateResponseMixin` when the object is fetched using a deferred queryset.
        """
        class FormContext(SingleObjectTemplateResponseMixin):
            request = RequestFactory().get("/")
            model = Author
            object = Author.objects.defer("name").get(pk=self.author1.pk)

        self.assertEqual(
            FormContext().get_template_names()[0], "generic_views/author_detail.html"
        )

    def test_deferred_queryset_context_object_name(self):
        """
        Tests that the context object name is correctly used when a deferred queryset is used in a ModelFormMixin.
        """
        class FormContext(ModelFormMixin):
            request = RequestFactory().get("/")
            model = Author
            object = Author.objects.defer("name").get(pk=self.author1.pk)
            fields = ("name",)

        form_context_data = FormContext().get_context_data()
        self.assertEqual(form_context_data["object"], self.author1)
        self.assertEqual(form_context_data["author"], self.author1)

    def test_invalid_url(self):
        with self.assertRaises(AttributeError):
            self.client.get("/detail/author/invalid/url/")

    def test_invalid_queryset(self):
        msg = (
            "AuthorDetail is missing a QuerySet. Define AuthorDetail.model, "
            "AuthorDetail.queryset, or override AuthorDetail.get_queryset()."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/detail/author/invalid/qs/")

    def test_non_model_object_with_meta(self):
        res = self.client.get("/detail/nonmodel/1/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"].id, "non_model_1")
