import datetime

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.views.generic.base import View

from .models import Artist, Author, Book, Page


@override_settings(ROOT_URLCONF="generic_views.urls")
class ListViewTests(TestCase):
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

    def test_items(self):
        """

        Tests the retrieval of items from the '/list/dict/' endpoint.

        Verifies that the HTTP request returns a successful status code (200),
        that the 'generic_views/list.html' template is used for rendering, and
        that the first item in the result list has the expected 'first' attribute value.

        """
        res = self.client.get("/list/dict/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/list.html")
        self.assertEqual(res.context["object_list"][0]["first"], "John")

    def test_queryset(self):
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
        res = self.client.get("/list/authors/paginated/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["page_obj"].number, 1)
        self.assertEqual(res.context["paginator"].num_pages, 1)
        self.assertFalse(res.context["is_paginated"])

    def test_paginated_get_page_by_query_string(self):
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/", {"page": "2"})
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(len(res.context["object_list"]), 30)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["author_list"][0].name, "Author 30")
        self.assertEqual(res.context["page_obj"].number, 2)

    def test_paginated_get_last_page_by_query_string(self):
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/", {"page": "last"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context["object_list"]), 10)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["author_list"][0].name, "Author 90")
        self.assertEqual(res.context["page_obj"].number, 4)

    def test_paginated_get_page_by_urlvar(self):
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/3/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/author_list.html")
        self.assertEqual(len(res.context["object_list"]), 30)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertEqual(res.context["author_list"][0].name, "Author 60")
        self.assertEqual(res.context["page_obj"].number, 3)

    def test_paginated_page_out_of_range(self):
        """
        Tests that a paginated page with an out-of-range page number returns a 404 status code.

        This test case verifies the behavior of the paginated author list endpoint when
        attempting to access a page that exceeds the total number of available pages.
        It ensures that the API correctly handles such requests and returns a \"Not Found\"
        response instead of attempting to process the invalid page number.
        """
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/42/")
        self.assertEqual(res.status_code, 404)

    def test_paginated_invalid_page(self):
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/?page=frog")
        self.assertEqual(res.status_code, 404)

    def test_paginated_custom_paginator_class(self):
        """
        Tests the paginated view with a custom paginator class.

        This test case creates a set of authors and then sends a GET request to the 
        paginated authors endpoint. It verifies that the response status code is 200, 
        indicating a successful request. Additionally, it checks that the paginator 
        instance in the response context has the correct number of pages and that the 
        number of authors in the object list matches the expected count.
        """
        self._make_authors(7)
        res = self.client.get("/list/authors/paginated/custom_class/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["paginator"].num_pages, 1)
        # Custom pagination allows for 2 orphans on a page size of 5
        self.assertEqual(len(res.context["object_list"]), 7)

    def test_paginated_custom_page_kwarg(self):
        """
        Tests the paginated view for authors with a custom page keyword.

        This test ensures that the paginated view functions correctly when using a custom page keyword ('pagina') instead of the default 'page' parameter.
        It verifies that the view returns a successful response, uses the correct template, and correctly paginates the author list.
        The test also checks that the paginated list is correctly populated with authors and that the page object is correctly set to the requested page number.
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
        ::

            Tests the paginated orphaned queryset view by making a series of requests and 
            verifying the correctness of the pagination. 

            The test creates a set of authors, then checks the response status code and 
            pagination context for the first page, the last page, a specific page, and 
            an invalid page number, ensuring proper handling of pagination and 
            edge cases.
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
        res = self.client.get("/list/artists/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/list.html")
        self.assertEqual(list(res.context["object_list"]), list(Artist.objects.all()))
        self.assertIs(res.context["artist_list"], res.context["object_list"])
        self.assertIsNone(res.context["paginator"])
        self.assertIsNone(res.context["page_obj"])
        self.assertFalse(res.context["is_paginated"])

    def test_allow_empty_false(self):
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 200)
        Author.objects.all().delete()
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 404)

    def test_template_name(self):
        res = self.client.get("/list/authors/template_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/list.html")

    def test_template_name_suffix(self):
        res = self.client.get("/list/authors/template_name_suffix/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_objects.html")

    def test_context_object_name(self):
        """

         Tests the context object name in the author list view.

         Verifies that the view returns a successful response (200 status code) and 
         renders the correct template. Additionally, checks that the context contains 
         the expected 'object_list' and 'author_list' variables, which should be 
         equivalent, and does not contain an 'authors' variable. This ensures that the 
         view is correctly populating the context with the list of authors.

        """
        res = self.client.get("/list/authors/context_object_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertNotIn("authors", res.context)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_list.html")

    def test_duplicate_context_object_name(self):
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
        Checks that the paginated list view for authors does not load the entire table in a single query.

        It tests that a request to the paginated list view results in an expected number of database queries, 
        assuring efficient data retrieval by only fetching the data for the current page.
        """
        self._make_authors(3)
        # 1 query for authors
        with self.assertNumQueries(1):
            self.client.get("/list/authors/notempty/")
        # same as above + 1 query to test if authors exist + 1 query for pagination
        with self.assertNumQueries(3):
            self.client.get("/list/authors/notempty/paginated/")

    def test_explicitly_ordered_list_view(self):
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
