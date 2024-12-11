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

        Setup test data for unit tests.

        This method creates a set of test data instances, including artists, authors, books, and pages, 
        which are used to populate the database for testing purposes. The created instances are 
        class attributes, making them accessible to all test methods in the class.

        The test data includes:
        - Two authors with their respective slugs
        - Two books with their titles, slugs, page counts, and publication dates
        - One page with content and a template
        - Associations between books and their authors

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
        """

        Tests the retrieval of a paginated page based on a query string.

        This function verifies that a GET request with a page number specified in the query string
        returns the correct page of results, along with the expected template and context variables.
        The test checks the status code, template used, and contents of the page object to ensure
        correct pagination and display of the author list.

        The test assumes a dataset with a large number of authors has been pre-populated, and
        verifies that the correct page of authors is returned, along with the expected page number
        and other context variables.

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
        Tests that a paginated GET request with 'last' as the page query string 
        successfully retrieves the last page of authors.

        Verifies that the response status code is 200, the number of authors returned 
        is 10, and the correct authors are displayed on the last page. Specifically, 
        it checks that the first author on the last page is 'Author 90' and that the 
        page number is correctly set to 4, demonstrating proper pagination.

        """
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
        Tests that a paginated page request with an out-of-range page number returns a 404 status code.

        This test case verifies the handling of invalid pagination requests by attempting to access a page that exceeds the total number of pages in the paginated list of authors. The test expects the server to respond with a 404 Not Found status code, indicating that the requested page does not exist.
        """
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/42/")
        self.assertEqual(res.status_code, 404)

    def test_paginated_invalid_page(self):
        """
        Tests the paginated authors endpoint with an invalid page parameter.

        Verifies that a 404 status code is returned when a non-numeric page value is provided.
        This test case ensures the endpoint correctly handles invalid pagination requests.

        """
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/?page=frog")
        self.assertEqual(res.status_code, 404)

    def test_paginated_custom_paginator_class(self):
        """

        Tests the usage of a custom paginator class with paginated views.

        Verifies that a GET request to a paginated view that utilizes a custom paginator class returns a successful response (200 status code) and contains the correct pagination information.

        Specifically, this test case checks that the paginator correctly handles a small number of objects, resulting in a single page, and ensures that all objects are included in the page's object list.

        """
        self._make_authors(7)
        res = self.client.get("/list/authors/paginated/custom_class/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["paginator"].num_pages, 1)
        # Custom pagination allows for 2 orphans on a page size of 5
        self.assertEqual(len(res.context["object_list"]), 7)

    def test_paginated_custom_page_kwarg(self):
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
        """
        Tests the custom paginator constructor in the paginated authors view.

        This test case checks that the paginated view returns a successful response (200 OK) 
        and that the number of authors returned in the response matches the expected number 
        (7 authors). The test covers the scenario where the custom paginator constructor is 
        used to paginate the authors list.

        The test provides assurance that the custom paginator is correctly instantiated and 
        that it properly paginates the authors data, returning the correct number of items 
        in the response context.
        """
        self._make_authors(7)
        res = self.client.get("/list/authors/paginated/custom_constructor/")
        self.assertEqual(res.status_code, 200)
        # Custom pagination allows for 2 orphans on a page size of 5
        self.assertEqual(len(res.context["object_list"]), 7)

    def test_paginated_orphaned_queryset(self):
        """

        Testing paginated orphaned querysets in author listings.

        Checks that paginated responses for orphaned authors are correctly paginated and 
        handled for different page requests, including first page, last page, valid page number, 
        and an invalid page number.

        Verifies status code 200 for valid page requests and status code 404 for an invalid page.

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
        """

        Tests the paginated non-queryset view by making a GET request to the '/list/dict/paginated/' endpoint.

        Checks if the response status code is 200 (OK) and if the object list in the response context contains exactly one item.

        """
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
        """
        Tests the behavior of the author list view when the `allow_empty` parameter is set to False.

        This test case verifies that the view returns a 200 status code when the author list is not empty, 
        and a 404 status code when the author list is empty, confirming the expected behavior when `allow_empty` is False.
        """
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 200)
        Author.objects.all().delete()
        res = self.client.get("/list/authors/notempty/")
        self.assertEqual(res.status_code, 404)

    def test_template_name(self):
        """

        Tests the list view for authors using a template name.

        Verifies that the view returns a successful response, contains all authors in the database,
        and that the author list and object list are equivalent. Additionally, confirms that the correct
        template, 'generic_views/list.html', is used to render the response.

        """
        res = self.client.get("/list/authors/template_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/list.html")

    def test_template_name_suffix(self):
        """
        Tests the template name suffix for the author list view.

        Verifies that the view returns a successful HTTP response, contains the expected list of authors,
        and uses the correct template. It also checks that the 'author_list' and 'object_list' context
        variables are equivalent, ensuring consistency in the template naming convention.

        The test case covers the functionality of rendering the author list template with the correct
        data and verifies that the template name suffix is correctly applied to use the 'author_objects.html'
        template from the 'generic_views' directory.
        """
        res = self.client.get("/list/authors/template_name_suffix/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_objects.html")

    def test_context_object_name(self):
        res = self.client.get("/list/authors/context_object_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["object_list"]), list(Author.objects.all()))
        self.assertNotIn("authors", res.context)
        self.assertIs(res.context["author_list"], res.context["object_list"])
        self.assertTemplateUsed(res, "generic_views/author_list.html")

    def test_duplicate_context_object_name(self):
        """

        Tests the case where a view's context object name is duplicated.

        Verifies that the view returns a successful HTTP response, 
        renders the expected template with the correct object list, 
        and ensures that duplicate context object names are not present in the response context.

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
        """
        Tests that AuthorListGetQuerysetReturnsNone is properly configured.

        Verifies that either a template name attribute or a get_queryset method returning a QuerySet is defined.
        If neither condition is met, it checks that an ImproperlyConfigured exception is raised with a specific error message.

        Raises:
            ImproperlyConfigured: If the view is not properly configured.

        """
        msg = (
            "AuthorListGetQuerysetReturnsNone requires either a 'template_name' "
            "attribute or a get_queryset() method that returns a QuerySet."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/list/authors/get_queryset/")

    def test_paginated_list_view_does_not_load_entire_table(self):
        # Regression test for #17535
        """

        Checks the paginated list view to ensure it does not load the entire table.

        This test verifies that the paginated list view fetches data in a way that minimizes database queries,
        improving performance by avoiding the retrieval of unnecessary data.

        It first sets up a scenario with a small number of authors, then checks the number of database queries 
        made when retrieving the list of authors in both non-paginated and paginated modes.

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
        """
        Tests that a paginated list view returns a useful message when an invalid page is requested.

            The function verifies that when a GET request is made to a paginated list view with an invalid page number,
            the view correctly returns a 404 status code and includes a descriptive error message in the response context.
            The error message indicates that the requested page is invalid because it does not contain any results.
        """
        self._make_authors(1)
        res = self.client.get("/list/authors/paginated/2/")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(
            res.context.get("reason"), "Invalid page (2): That page contains no results"
        )

    def _make_authors(self, n):
        """
        Create a specified number of authors and remove all existing authors.

        This method purges the database of all current authors and generates a new set of authors.
        The number of authors to be created is defined by the input parameter.
        Each author is assigned a name and slug in the format 'Author XX' and 'aXX' respectively, where XX represents a zero-padded author index.

        :param int n: The number of authors to create.

        """
        Author.objects.all().delete()
        for i in range(n):
            Author.objects.create(name="Author %02i" % i, slug="a%s" % i)
