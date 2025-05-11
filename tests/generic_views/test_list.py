import datetime

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.views.generic.base import View

from .models import Artist, Author, Book, Page


@override_settings(ROOT_URLCONF="generic_views.urls")
class ListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for use in tests, creating instances of Artist, Author, Book, and Page models with predefined attributes.
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

    def test_items(self):
        res = self.client.get("/list/dict/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/list.html")
        self.assertEqual(res.context["object_list"][0]["first"], "John")

    def test_queryset(self):
        """
        Tests the queryset returned by the author list view, verifying that it returns a successful response, uses the correct template, and contains the expected data from the Author model. Additionally, it checks that various pagination-related context variables are properly set.
        """
        res = self.client.get("/list/authors/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIsInstance(res.context["view"], View)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertIsNone(res.context["paginator"])
        self.assertIsNone(res.context["page_obj"])
        self.assertFalse(res.context["is_paginated"])

    def test_paginated_queryset(self):
        """
        Tests the paginated queryset view for authors, verifying that it returns the correct page of authors, uses the correct template, and properly paginates the results.
        """
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(len(res.context["object_list"]), 30)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTrue(res.context["is_paginated"])
        self.assertEqual(res.context["page_obj"].number, 1)
        self.assertEqual(res.context["paginator"].num_pages, 4)
        self.assertEqual(res.context["author_list"][0].name, "Author 00")
        self.assertEqual(list(res.context["author_list"])[-1].name, "Author 29")

    def test_paginated_queryset_shortdata(self):
        # Short datasets also result in a paginated view.
        """

        Tests the paginated queryset for the author list view, verifying that the
        correct template is used, all authors are displayed, and pagination metadata is correct.

        """
        res = self.client.get("/list/authors/paginated/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["page_obj"].number, 1)
        self.assertEqual(res.context["paginator"].num_pages, 1)
        self.assertFalse(res.context["is_paginated"])

    def test_paginated_get_page_by_query_string(self):
        """
        Tests that the paginated author list view returns the correct page of results based on the query string 'page' parameter.
        """
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/", {"page": "2"})
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(len(res.context["object_list"]), 30)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["author_list"][0].name, "Author 30")
        self.assertEqual(res.context["page_obj"].number, 2)

    def test_paginated_get_last_page_by_query_string(self):
        """
        Tests retrieving the last page of paginated authors by query string.

        Verifies that the last page of authors can be retrieved successfully by passing 'last' as the page query string,
        and that the correct authors and pagination information are returned.
        """
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/", {"page": "last"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context["object_list"]), 10)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["author_list"][0].name, "Author 90")
        self.assertEqual(res.context["page_obj"].number, 4)

    def test_paginated_get_page_by_urlvar(self):
        """

         Tests a paginated GET request to the author list view, 
         verifying the correct page is retrieved and rendered with the expected data.

        """
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/3/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(len(res.context["object_list"]), 30)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["author_list"][0].name, "Author 60")
        self.assertEqual(res.context["page_obj"].number, 3)

    def test_paginated_page_out_of_range(self):
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/42/")
        self.assertEqual(res.status_code, 404)

    def test_paginated_invalid_page(self):
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/?page=frog")
        self.assertEqual(res.status_code, 404)

    def test_paginated_custom_paginator_class(self):
        """
        Tests the paginated view with a custom paginator class, verifying that the response is successful and the pagination is correctly applied to the list of authors.
        """
        self._make_authors(7)
        res = self.client.get("/list/authors/paginated/custom_class/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["paginator"].num_pages, 1)
        # Custom pagination allows for 2 orphans on a page size of 5
        self.assertEqual(len(res.context["object_list"]), 7)

    def test_paginated_custom_page_kwarg(self):
        """
        Tests the paginated view for authors with a custom page keyword argument, verifying successful page retrieval, template usage, and expected data in the response context.
        """
        self._make_authors(100)
        res = self.client.get(
            "/list/authors/paginated/custom_page_kwarg/", {"pagina": "2"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(len(res.context["object_list"]), 30)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["author_list"][0].name, "Author 30")
        self.assertEqual(res.context["page_obj"].number, 2)

    def test_paginated_custom_paginator_constructor(self):
        self._make_authors(7)
        res = self.client.get("/list/authors/paginated/custom_constructor/")
        self.assertEqual(res.status_code, 200)
        # Custom pagination allows for 2 orphans on a page size of 5
        self.assertEqual(len(res.context["object_list"]), 7)

    def test_paginated_orphaned_queryset(self):
        """

        Tests the paginated orphaned queryset view to ensure it correctly paginates results and handles invalid page requests.

        The test creates a large number of authors, then checks that the view returns the correct page of results when no page is specified, 
        when the 'last' page is requested, when a valid page number is specified, and that it returns a 404 when an invalid page number is requested.

        """
        self._make_authors(92)
        res = self.client.get("/list/authors/paginated-orphaned/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["page_obj"].number, 1)
        res = self.client.get("/list/authors/paginated-orphaned/", {"page": "last"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["page_obj"].number, 3)
        res = self.client.get("/list/authors/paginated-orphaned/", {"page": "3"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["page_obj"].number, 3)
        res = self.client.get("/list/authors/paginated-orphaned/", {"page": "4"})
        self.assertEqual(res.status_code, 404)

    def test_paginated_non_queryset(self):
        res = self.client.get("/list/dict/paginated/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context["object_list"]), 1)

    def test_verbose_name(self):
        """
        Tests the list view for artists, ensuring it returns a 200 status code, 
        uses the correct template, and provides the expected context variables, 
        including the list of artists and pagination settings.
        """
        res = self.client.get("/list/artists/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/list.html")
        self.assertEqual(list(res.context["object_list"]), list(Artist.objects.all()))
        self.assertIs(res.context["artist_list"], res.context["object_list"])
        self.assertIsNone(res.context["paginator"])
        self.assertIsNone(res.context["page_obj"])
        self.assertFalse(res.context["is_paginated"])

    def test_allow_empty_false(self):
        """
        Tests the behavior of the authors list view when the allow_empty parameter is set to False, verifying a 404 status code is returned when no authors exist.
        """
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 200)
        Author.objects.all().delete()
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 404)

    def test_template_name(self):
        """
        Tests that the template name for the author list view is correctly rendered.

        Verifies that the view returns a successful response, contains all authors, 
        and uses the expected template.
        """
        res = self.client.get("/list/authors/template_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/list.html")

    def test_template_name_suffix(self):
        """

        Tests that a view using a template with a suffix correctly renders and returns the expected data.

        """
        res = self.client.get("/list/authors/template_name_suffix/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_objects.html")

    def test_context_object_name(self):
        """

        Tests the correct rendering of the context object name in the authors list view.

        Verifies that the view returns a successful response, contains the expected list of authors,
        and uses the correct template, while ensuring that the context object name is properly set.

        """
        res = self.client.get("/list/authors/context_object_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertNotIn("authors", res.context)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_list.html")

    def test_duplicate_context_object_name(self):
        """
        Tests that a view with a duplicate context object name behaves correctly.

        Verifies that the view returns a successful response, populates the object list
        correctly, and does not include incorrect keys in the context. Also checks that
        the correct template is used for rendering the response.
        """
        res = self.client.get("/list/authors/dupe_context_object_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertNotIn("authors", res.context)
        self.assertNotIn("author_list", res.context)
        self.assertTemplateUsed(res, "generic_views/author_list.html")

    def test_missing_items(self):
        msg = (
            "AuthorList is missing a QuerySet. Define AuthorList.model, "
            "AuthorList.queryset, or override AuthorList.get_queryset()."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/list/authors/invalid/")

    def test_invalid_get_queryset(self):
        msg = (
            "AuthorListGetQuerysetReturnsNone requires either a 'template_name' "
            "attribute or a get_queryset() method that returns a QuerySet."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/list/authors/get_queryset/")

    def test_paginated_list_view_does_not_load_entire_table(self):
        # Regression test for #17535
        """
        Tests that the paginated list view only loads the necessary data, rather than the entire table, by verifying the number of database queries executed when accessing the paginated and non-paginated views.
        """
        self._make_authors(3)
        # 1 query for authors
        with self.assertNumQueries(1):
            self.client.get("/list/authors/notempty/")
        # same as above + 1 query to test if authors exist + 1 query for pagination
        with self.assertNumQueries(3):
            self.client.get("/list/authors/notempty/paginated/")

    def test_explicitly_ordered_list_view(self):
        """

        Tests the explicitly ordered list view functionality.

        This test case verifies that the list view returns objects in the correct order,
        as specified by the URL path. It checks the ordering by name and by a combination
        of pages and name.

        """
        Book.objects.create(
            name="Zebras for Dummies", pages=800, pubdate=datetime.date(2006, 9, 1)
        )
        res = self.client.get("/list/books/sorted/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object_list"][0].name, "2066")
        self.assertEqual(res.context["object_list"][1].name, "Dreaming in Code")
        self.assertEqual(res.context["object_list"][2].name, "Zebras for Dummies")

        res = self.client.get("/list/books/sortedbypagesandnamedec/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object_list"][0].name, "Dreaming in Code")
        self.assertEqual(res.context["object_list"][1].name, "Zebras for Dummies")
        self.assertEqual(res.context["object_list"][2].name, "2066")

    @override_settings(DEBUG=True)
    def test_paginated_list_view_returns_useful_message_on_invalid_page(self):
        # test for #19240
        # tests that source exception's message is included in page
        self._make_authors(1)
        res = self.client.get("/list/authors/paginated/2/")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(
            res.context.get("reason"), "Invalid page (2): That page contains no results"
        )

    def _make_authors(self, n):
        Author.objects.all().delete()
        for i in range(n):
            Author.objects.create(name="Author %02i" % i, slug="a%s" % i)
