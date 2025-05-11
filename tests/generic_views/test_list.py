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
        Sets up test data for the class, creating instances of Artist, Author, Book, and Page models to be used in tests.
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
        Tests the HTTP GET request to the author list view, verifying a successful response, correct template usage, and expected context data.
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
        Tests the paginated queryset view for authors.

        Verifies a successful response with the correct template, 
        pagination, and author list contents.
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
        Tests that a paginated queryset is correctly rendered for a short dataset.

        Verifies that the paginated view returns a 200 status code, uses the correct template,
        and contains the expected context data, including the paginated object list and pagination metadata.
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
        Tests if paginated retrieval of authors by query string functions correctly.

        Verifies that the correct page of authors is returned with the expected status code, 
        template, and context data, ensuring proper pagination behavior.
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
        Tests that a paginated GET request to the authors endpoint returns the last page of results when 'page=last' is specified in the query string, verifying the correctness of the response status code, object list length, and pagination metadata.
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
        Tests a paginated view by retrieving a specific page via URL variable and verifies the response status, template used, number of objects returned, and page metadata.
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
        .Tests that the custom paginator class correctly paginates a list of authors when there are not enough items to span multiple pages.
        """
        self._make_authors(7)
        res = self.client.get("/list/authors/paginated/custom_class/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["paginator"].num_pages, 1)
        # Custom pagination allows for 2 orphans on a page size of 5
        self.assertEqual(len(res.context["object_list"]), 7)

    def test_paginated_custom_page_kwarg(self):
        """

        Tests the pagination view with a custom page keyword argument.

        Verifies the view returns the correct status code, uses the expected template,
        and paginates the results correctly.

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
        Tests the paginated orphaned queryset view by making GET requests to the corresponding endpoint with different page numbers, verifying that the correct page is returned and that a 404 error is raised for invalid page numbers.
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
        Tests that the artist list view returns a 200 status code, 
        renders the correct template, and populates the context with the correct data.
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
        Tests that a 404 status code is returned when the 'allow_empty' parameter is set to False and the queried data is empty.
        """
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 200)
        Author.objects.all().delete()
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 404)

    def test_template_name(self):
        """
        Tests the template name used for the authors list view, verifying a successful response and correct data rendering.
        """
        res = self.client.get("/list/authors/template_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/list.html")

    def test_template_name_suffix(self):
        """
        Tests that the template name suffix view returns the expected HTTP status code, 
        populates the template context correctly, and uses the correct template
        """
        res = self.client.get("/list/authors/template_name_suffix/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_objects.html")

    def test_context_object_name(self):
        """
        Tests the context object name used in the author list view, verifying that it returns the correct author list without an 'authors' context variable and uses the expected template.
        """
        res = self.client.get("/list/authors/context_object_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertNotIn("authors", res.context)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_list.html")

    def test_duplicate_context_object_name(self):
        """
        Tests the \"/list/authors/dupe_context_object_name/\" view, verifying it returns a successful response, 
         renders the correct template, and populates the expected context variables.
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
        Tests that the paginated list view fetches data in a paginated manner, 
        rather than loading the entire table at once, by verifying the number of database queries made.
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
        Tests that a list view of books is correctly ordered according to explicit sorting rules, 
        including sorting by name and by multiple fields (pages and name in descending order).
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
