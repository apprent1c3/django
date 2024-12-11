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
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/42/")
        self.assertEqual(res.status_code, 404)

    def test_paginated_invalid_page(self):
        self._make_authors(100)
        res = self.client.get("/list/authors/paginated/?page=frog")
        self.assertEqual(res.status_code, 404)

    def test_paginated_custom_paginator_class(self):
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
        self._make_authors(7)
        res = self.client.get("/list/authors/paginated/custom_constructor/")
        self.assertEqual(res.status_code, 200)
        # Custom pagination allows for 2 orphans on a page size of 5
        self.assertEqual(len(res.context["object_list"]), 7)

    def test_paginated_orphaned_queryset(self):
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
        Tests the list view for artists, ensuring a successful response and correct template usage.

        Verifies that the response status code is 200, the generic list template is used, and the object list 
        contains all artists. Additionally, checks that the artist list and object list are the same, 
        and pagination is not used in this view, resulting in 'paginator', 'page_obj' being None, 
        and 'is_paginated' being False. 
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
        """
        Tests that an ImproperlyConfigured exception is raised when a QuerySet is missing.

            Verifies that an error occurs when AuthorList does not have a defined model, queryset, 
            or a custom get_queryset method, by attempting to access an invalid author list URL.

            :raises: ImproperlyConfigured if AuthorList is not properly configured
        """
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
        """
        Creates a specified number of author instances in the database, replacing any existing authors.

        :param int n: The number of authors to create.
        :returns: None

        This method first removes all existing authors from the database. It then creates 'n' new authors, each with a name and slug in a specific format. The name of each author is 'Author xx' where 'xx' is a zero-padded two-digit number, and the slug is 'axx' where 'xx' is the same two-digit number. This method is typically used for testing or seeding the database with sample data.
        """
        Author.objects.all().delete()
        for i in range(n):
            Author.objects.create(name="Author %02i" % i, slug="a%s" % i)
