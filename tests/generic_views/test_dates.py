import datetime
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings, skipUnlessDBFeature
from django.test.utils import requires_tz_support

from .models import Artist, Author, Book, BookSigning, Page


def _make_books(n, base_date):
    for i in range(n):
        Book.objects.create(
            name="Book %d" % i,
            slug="book-%d" % i,
            pages=100 + i,
            pubdate=base_date - datetime.timedelta(days=i),
        )


class TestDataMixin:
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the application, creating instances of Artists, Authors, Books, and Pages.

        This method is used to populate the database with a set of predefined objects, which can be used to test the functionality of the application.
        The created objects include two authors, two books (each with one author), an artist, and a page with sample content.
        The test data is created as class attributes, making it accessible to all tests within the class.

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


@override_settings(ROOT_URLCONF="generic_views.urls")
class ArchiveIndexViewTests(TestDataMixin, TestCase):
    def test_archive_view(self):
        """

        Tests the archive view for books.

        Verifies that the view returns a successful HTTP response (200 OK) and renders the correct template.
        Checks that the view context contains the expected list of dates and latest books, 
        which are retrieved from the database in descending order by publication year.

        """
        res = self.client.get("/dates/books/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(list(res.context["latest"]), list(Book.objects.all()))
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_archive_view_context_object_name(self):
        """

        Tests the archive view's context object name functionality.

        Verifies that the view returns a successful response (200 status code) and
        renders the expected template ('generic_views/book_archive.html'). Checks that
        the view's context contains the expected data, including a list of dates and
        a list of objects, and that it does not contain unnecessary data. 

        The test ensures the correct retrieval and ordering of date lists from the 'Book' objects,
        sorted in descending order by publication year, as well as the list of all 'Book' objects.

        """
        res = self.client.get("/dates/books/context_object_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(list(res.context["thingies"]), list(Book.objects.all()))
        self.assertNotIn("latest", res.context)
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_empty_archive_view(self):
        """
        Tests that the book archive view returns a 404 status code when the book database is empty.

        This test case simulates a scenario where there are no books in the database and verifies that the
        -archive view behaves as expected by returning a \"Not Found\" response. The test ensures that the 
        view handles empty data correctly and provides a proper error response to the client.
        """
        Book.objects.all().delete()
        res = self.client.get("/dates/books/")
        self.assertEqual(res.status_code, 404)

    def test_allow_empty_archive_view(self):
        """
        Tests the view that handles the display of books by date when the book archive is empty.

        Verifies that the view returns a successful status code, an empty list of dates, and renders the correct template.
        """
        Book.objects.all().delete()
        res = self.client.get("/dates/books/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [])
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_archive_view_template(self):
        """

        Tests the archive view template by simulating a GET request to the archive page.
        The test checks that the view returns a successful response (status code 200) and 
        renders the correct template ('generic_views/list.html'). It also verifies that 
        the view's context contains the expected data, including a list of dates of 
        published books in descending order and a list of all books.

        """
        res = self.client.get("/dates/books/template_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(list(res.context["latest"]), list(Book.objects.all()))
        self.assertTemplateUsed(res, "generic_views/list.html")

    def test_archive_view_template_suffix(self):
        """
        Tests the archive view template suffix URL pattern.

        Verifies that a GET request to the specified URL returns a successful response,
        renders the correct template, and populates the context with the expected data,
        including a list of book publication dates and a list of all books.

        The test case checks the status code of the response, the template used to render
        the response, and the contents of the response context to ensure they match the
        expected values. The test is designed to validate the correct functioning of the
        archive view template suffix URL pattern.

        """
        res = self.client.get("/dates/books/template_name_suffix/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(list(res.context["latest"]), list(Book.objects.all()))
        self.assertTemplateUsed(res, "generic_views/book_detail.html")

    def test_archive_view_invalid(self):
        """
        **:return:** None
        **:raises ImproperlyConfigured:** If BookArchive is improperly configured.

        Tests the BookArchive view with an invalid configuration, verifying that an ImproperlyConfigured exception is raised when the view is accessed.

        This test ensures that the view correctly handles the case where the BookArchive is missing a required QuerySet definition, either through the model attribute, queryset attribute, or get_queryset method. The test checks for a specific error message, confirming that the exception is raised with the expected detail.
        """
        msg = (
            "BookArchive is missing a QuerySet. Define BookArchive.model, "
            "BookArchive.queryset, or override BookArchive.get_queryset()."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/dates/books/invalid/")

    def test_archive_view_by_month(self):
        """
        Tests the archive view for books by month.

        Verifies that a GET request to the `/dates/books/by_month/` endpoint returns a successful response (200 status code) and that the list of dates returned in the response matches the list of publication dates for all books in the database, ordered in descending order by month.
        """
        res = self.client.get("/dates/books/by_month/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "month", "DESC")),
        )

    def test_paginated_archive_view(self):
        _make_books(20, base_date=datetime.date.today())
        res = self.client.get("/dates/books/paginated/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(list(res.context["latest"]), list(Book.objects.all()[0:10]))
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

        res = self.client.get("/dates/books/paginated/?page=2")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["page_obj"].number, 2)
        self.assertEqual(list(res.context["latest"]), list(Book.objects.all()[10:20]))

    def test_paginated_archive_view_does_not_load_entire_table(self):
        # Regression test for #18087
        _make_books(20, base_date=datetime.date.today())
        # 1 query for years list + 1 query for books
        with self.assertNumQueries(2):
            self.client.get("/dates/books/")
        # same as above + 1 query to test if books exist + 1 query to count them
        with self.assertNumQueries(4):
            self.client.get("/dates/books/paginated/")

    def test_no_duplicate_query(self):
        # Regression test for #18354
        """
        Tests that the view at '/dates/books/reverse/' does not execute duplicate database queries.

        This test case verifies that the number of database queries executed during the HTTP request is expected, 
        preventing potential performance issues due to unnecessary queries. 
        The expected number of queries is two, which includes any queries that may be executed by 
        the view or other middleware involved in processing the request.
        """
        with self.assertNumQueries(2):
            self.client.get("/dates/books/reverse/")

    def test_datetime_archive_view(self):
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        res = self.client.get("/dates/booksignings/")
        self.assertEqual(res.status_code, 200)

    @requires_tz_support
    @skipUnlessDBFeature("has_zoneinfo_database")
    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_archive_view(self):
        """
        Tests the archive view for book signings with aware datetime.

            This test case ensures that the archive view for book signings works correctly 
            when dealing with aware datetime objects, which include timezone information. 
            It creates a book signing event with a specific date and time in UTC, then 
            fetches the archive view for book signings and verifies that the response 
            status code is 200, indicating a successful request.

            The test requires timezone support and the presence of a zoneinfo database 
            in the database backend. It also overrides the USE_TZ and TIME_ZONE settings 
            to ensure that the test is run in a consistent environment.

        """
        BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 4, 2, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        res = self.client.get("/dates/booksignings/")
        self.assertEqual(res.status_code, 200)

    def test_date_list_order(self):
        """date_list should be sorted descending in index"""
        _make_books(5, base_date=datetime.date(2011, 12, 25))
        res = self.client.get("/dates/books/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            sorted(res.context["date_list"], reverse=True),
        )

    def test_archive_view_custom_sorting(self):
        """

        Tests the custom sorting functionality of the archive view.

        This test case verifies that the archive view can be sorted by a custom field ('name' in this case) and 
        that the sorted list is correctly displayed. It also checks that the view returns the correct status code 
        and uses the expected template. Additionally, it confirms that the view correctly retrieves the latest 
        objects and the list of dates, sorted in descending order by publication year.

        The test covers the following scenarios: 
        - The view returns a successful response (status code 200).
        - The sorted list of objects is correctly retrieved and displayed.
        - The correct template is used to render the view.
        - The list of dates is correctly retrieved and sorted.

        """
        Book.objects.create(
            name="Zebras for Dummies", pages=600, pubdate=datetime.date(2007, 5, 1)
        )
        res = self.client.get("/dates/books/sortedbyname/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(
            list(res.context["latest"]), list(Book.objects.order_by("name").all())
        )
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_archive_view_custom_sorting_dec(self):
        Book.objects.create(
            name="Zebras for Dummies", pages=600, pubdate=datetime.date(2007, 5, 1)
        )
        res = self.client.get("/dates/books/sortedbynamedec/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(
            list(res.context["latest"]), list(Book.objects.order_by("-name").all())
        )
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_archive_view_without_date_field(self):
        """
        Tests that a request to the BookArchiveWithoutDateField view raises an ImproperlyConfigured exception when no date field is defined.

        The view requires a date field to be specified in order to function correctly.
        This test ensures that the proper error message is raised when this field is missing,
        preventing the view from being used in an invalid state.

        :raises ImproperlyConfigured: When the date field is not defined
        """
        msg = "BookArchiveWithoutDateField.date_field is required."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/dates/books/without_date_field/")


@override_settings(ROOT_URLCONF="generic_views.urls")
class YearArchiveViewTests(TestDataMixin, TestCase):
    def test_year_view(self):
        """

        Test the year view functionality.

        Verifies that the year view returns a successful HTTP response, 
        correctly populates the date list, and renders the expected template.
        The test also checks that the year, previous year, and next year context variables are correctly set.


        """
        res = self.client.get("/dates/books/2008/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [datetime.date(2008, 10, 1)])
        self.assertEqual(res.context["year"], datetime.date(2008, 1, 1))
        self.assertTemplateUsed(res, "generic_views/book_archive_year.html")

        # Since allow_empty=False, next/prev years must be valid (#7164)
        self.assertIsNone(res.context["next_year"])
        self.assertEqual(res.context["previous_year"], datetime.date(2006, 1, 1))

    def test_year_view_make_object_list(self):
        res = self.client.get("/dates/books/2006/make_object_list/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [datetime.date(2006, 5, 1)])
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate__year=2006)),
        )
        self.assertEqual(
            list(res.context["object_list"]),
            list(Book.objects.filter(pubdate__year=2006)),
        )
        self.assertTemplateUsed(res, "generic_views/book_archive_year.html")

    def test_year_view_empty(self):
        res = self.client.get("/dates/books/1999/")
        self.assertEqual(res.status_code, 404)
        res = self.client.get("/dates/books/1999/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [])
        self.assertEqual(list(res.context["book_list"]), [])

        # Since allow_empty=True, next/prev are allowed to be empty years (#7164)
        self.assertEqual(res.context["next_year"], datetime.date(2000, 1, 1))
        self.assertEqual(res.context["previous_year"], datetime.date(1998, 1, 1))

    def test_year_view_allow_future(self):
        # Create a new book in the future
        """

        Test the year view functionality to handle future dates.

        This test case verifies the behavior of the year view when displaying books
        published in the future. It checks that:

        * A 404 status code is returned when trying to access the year view for a future year.
        * A 200 status code is returned and an empty book list is displayed when the 'allow_empty' parameter is used.
        * A 200 status code is returned and a list of future publication dates is displayed when the 'allow_future' parameter is used.

        The test creates a book with a future publication date and then tests the different scenarios.

        """
        year = datetime.date.today().year + 1
        Book.objects.create(
            name="The New New Testement", pages=600, pubdate=datetime.date(year, 1, 1)
        )
        res = self.client.get("/dates/books/%s/" % year)
        self.assertEqual(res.status_code, 404)

        res = self.client.get("/dates/books/%s/allow_empty/" % year)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["book_list"]), [])

        res = self.client.get("/dates/books/%s/allow_future/" % year)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [datetime.date(year, 1, 1)])

    def test_year_view_paginated(self):
        res = self.client.get("/dates/books/2006/paginated/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate__year=2006)),
        )
        self.assertEqual(
            list(res.context["object_list"]),
            list(Book.objects.filter(pubdate__year=2006)),
        )
        self.assertTemplateUsed(res, "generic_views/book_archive_year.html")

    def test_year_view_custom_sort_order(self):
        # Zebras comes after Dreaming by name, but before on '-pubdate' which
        # is the default sorting.
        """

        Tests the year view with a custom sort order, verifying the correct functionality 
        of the view when sorting books by name within a specific year.

        The test creates a new book and then retrieves the view, checking that the 
        response status code is 200. It also verifies that the context contains the 
        correct dates and books, sorted by name, and that the expected template is used.

        """
        Book.objects.create(
            name="Zebras for Dummies", pages=600, pubdate=datetime.date(2006, 9, 1)
        )
        res = self.client.get("/dates/books/2006/sortedbyname/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            [datetime.date(2006, 5, 1), datetime.date(2006, 9, 1)],
        )
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate__year=2006).order_by("name")),
        )
        self.assertEqual(
            list(res.context["object_list"]),
            list(Book.objects.filter(pubdate__year=2006).order_by("name")),
        )
        self.assertTemplateUsed(res, "generic_views/book_archive_year.html")

    def test_year_view_two_custom_sort_orders(self):
        Book.objects.create(
            name="Zebras for Dummies", pages=300, pubdate=datetime.date(2006, 9, 1)
        )
        Book.objects.create(
            name="Hunting Hippos", pages=400, pubdate=datetime.date(2006, 3, 1)
        )
        res = self.client.get("/dates/books/2006/sortedbypageandnamedec/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            [
                datetime.date(2006, 3, 1),
                datetime.date(2006, 5, 1),
                datetime.date(2006, 9, 1),
            ],
        )
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate__year=2006).order_by("pages", "-name")),
        )
        self.assertEqual(
            list(res.context["object_list"]),
            list(Book.objects.filter(pubdate__year=2006).order_by("pages", "-name")),
        )
        self.assertTemplateUsed(res, "generic_views/book_archive_year.html")

    def test_year_view_invalid_pattern(self):
        """

        Tests that a 404 status code is returned when attempting to access the year view with an invalid pattern.

        This test case verifies that the application correctly handles an invalid URL pattern by returning a \"Not Found\" HTTP response.

        """
        res = self.client.get("/dates/books/no_year/")
        self.assertEqual(res.status_code, 404)

    def test_no_duplicate_query(self):
        # Regression test for #18354
        """
        Tests that the view handling date-based book queries returns the correct results without executing duplicate database queries.

        This test case verifies that the view responds correctly to a GET request for books from a specific year (2008) in reverse order, while also ensuring that the underlying database queries are executed efficiently, with a expected total of 4 queries.
        """
        with self.assertNumQueries(4):
            self.client.get("/dates/books/2008/reverse/")

    def test_datetime_year_view(self):
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        res = self.client.get("/dates/booksignings/2008/")
        self.assertEqual(res.status_code, 200)

    @skipUnlessDBFeature("has_zoneinfo_database")
    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_year_view(self):
        BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 4, 2, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        res = self.client.get("/dates/booksignings/2008/")
        self.assertEqual(res.status_code, 200)

    def test_date_list_order(self):
        """date_list should be sorted ascending in year view"""
        _make_books(10, base_date=datetime.date(2011, 12, 25))
        res = self.client.get("/dates/books/2011/")
        self.assertEqual(
            list(res.context["date_list"]), sorted(res.context["date_list"])
        )

    @mock.patch("django.views.generic.list.MultipleObjectMixin.get_context_data")
    def test_get_context_data_receives_extra_context(self, mock):
        """
        MultipleObjectMixin.get_context_data() receives the context set by
        BaseYearArchiveView.get_dated_items(). This behavior is implemented in
        BaseDateListView.get().
        """
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        with self.assertRaisesMessage(
            TypeError, "context must be a dict rather than MagicMock."
        ):
            self.client.get("/dates/booksignings/2008/")
        args, kwargs = mock.call_args
        # These are context values from get_dated_items().
        self.assertEqual(kwargs["year"], datetime.date(2008, 1, 1))
        self.assertIsNone(kwargs["previous_year"])
        self.assertIsNone(kwargs["next_year"])

    def test_get_dated_items_not_implemented(self):
        """
        Tests that attempting to access a DateView without implementing the get_dated_items() method raises a NotImplementedError.

        This test ensures that the DateView correctly enforces the implementation of the get_dated_items() method, which is required for the view to function properly. The test verifies that accessing the view without this implementation results in the expected error message.

        :raises: NotImplementedError if the get_dated_items() method is not implemented.
        :raises: AssertionError if the error message does not match the expected message.

        """
        msg = "A DateView must provide an implementation of get_dated_items()"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.client.get("/BaseDateListViewTest/")


@override_settings(ROOT_URLCONF="generic_views.urls")
class MonthArchiveViewTests(TestDataMixin, TestCase):
    def test_month_view(self):
        res = self.client.get("/dates/books/2008/oct/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/book_archive_month.html")
        self.assertEqual(list(res.context["date_list"]), [datetime.date(2008, 10, 1)])
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate=datetime.date(2008, 10, 1))),
        )
        self.assertEqual(res.context["month"], datetime.date(2008, 10, 1))

        # Since allow_empty=False, next/prev months must be valid (#7164)
        self.assertIsNone(res.context["next_month"])
        self.assertEqual(res.context["previous_month"], datetime.date(2006, 5, 1))

    def test_month_view_allow_empty(self):
        # allow_empty = False, empty month
        """

        Tests the month view functionality in two scenarios: 
        when empty dates are not allowed and when they are allowed.

        This test case checks the status code of the HTTP response, 
        the data returned in the context and the navigation to the next and previous months.
        It also tests the functionality with the current date.

        """
        res = self.client.get("/dates/books/2000/jan/")
        self.assertEqual(res.status_code, 404)

        # allow_empty = True, empty month
        res = self.client.get("/dates/books/2000/jan/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [])
        self.assertEqual(list(res.context["book_list"]), [])
        self.assertEqual(res.context["month"], datetime.date(2000, 1, 1))

        # Since allow_empty=True, next/prev are allowed to be empty months (#7164)
        self.assertEqual(res.context["next_month"], datetime.date(2000, 2, 1))
        self.assertEqual(res.context["previous_month"], datetime.date(1999, 12, 1))

        # allow_empty but not allow_future: next_month should be empty (#7164)
        url = datetime.date.today().strftime("/dates/books/%Y/%b/allow_empty/").lower()
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.context["next_month"])

    def test_month_view_allow_future(self):
        """

        Tests the month view for the books application, ensuring that future dates are handled correctly.

        The test case checks the following scenarios:
        - When future dates are not allowed, a 404 status code is returned.
        - When future dates are allowed, a 200 status code is returned and the correct book information is displayed.
        - The test also verifies that the next and previous month navigation is working correctly, even when future dates are allowed.

        By validating these different scenarios, this test provides assurance that the month view functionality is working as expected.

        """
        future = (datetime.date.today() + datetime.timedelta(days=60)).replace(day=1)
        urlbit = future.strftime("%Y/%b").lower()
        b = Book.objects.create(name="The New New Testement", pages=600, pubdate=future)

        # allow_future = False, future month
        res = self.client.get("/dates/books/%s/" % urlbit)
        self.assertEqual(res.status_code, 404)

        # allow_future = True, valid future month
        res = self.client.get("/dates/books/%s/allow_future/" % urlbit)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["date_list"][0], b.pubdate)
        self.assertEqual(list(res.context["book_list"]), [b])
        self.assertEqual(res.context["month"], future)

        # Since allow_future = True but not allow_empty, next/prev are not
        # allowed to be empty months (#7164)
        self.assertIsNone(res.context["next_month"])
        self.assertEqual(res.context["previous_month"], datetime.date(2008, 10, 1))

        # allow_future, but not allow_empty, with a current month. So next
        # should be in the future (yup, #7164, again)
        res = self.client.get("/dates/books/2008/oct/allow_future/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["next_month"], future)
        self.assertEqual(res.context["previous_month"], datetime.date(2006, 5, 1))

    def test_month_view_paginated(self):
        """
        Tests the month view with pagination.

        This test case verifies that the month view returns a successful response, with the correct list of books published in the specified month and year. It also checks that the expected template is used to render the response.

        The test checks the following:

        * The HTTP status code of the response is 200 (OK)
        * The list of books in the response context matches the expected list of books published in the specified month and year
        * The template used to render the response is the correct one for a month archive view
        """
        res = self.client.get("/dates/books/2008/oct/paginated/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate__year=2008, pubdate__month=10)),
        )
        self.assertEqual(
            list(res.context["object_list"]),
            list(Book.objects.filter(pubdate__year=2008, pubdate__month=10)),
        )
        self.assertTemplateUsed(res, "generic_views/book_archive_month.html")

    def test_custom_month_format(self):
        """
        .\"\"\"
        Test that the custom month format API endpoint returns a successful response.

        This test case checks if the API endpoint for retrieving books by month
        returns a HTTP status code of 200, indicating a successful request.
        The endpoint is tested with a specific date range (October 2008).

        """
        res = self.client.get("/dates/books/2008/10/")
        self.assertEqual(res.status_code, 200)

    def test_month_view_invalid_pattern(self):
        res = self.client.get("/dates/books/2007/no_month/")
        self.assertEqual(res.status_code, 404)

    def test_previous_month_without_content(self):
        "Content can exist on any day of the previous month. Refs #14711"
        self.pubdate_list = [
            datetime.date(2010, month, day) for month, day in ((9, 1), (10, 2), (11, 3))
        ]
        for pubdate in self.pubdate_list:
            name = str(pubdate)
            Book.objects.create(name=name, slug=name, pages=100, pubdate=pubdate)

        res = self.client.get("/dates/books/2010/nov/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["previous_month"], datetime.date(2010, 10, 1))
        # The following test demonstrates the bug
        res = self.client.get("/dates/books/2010/nov/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["previous_month"], datetime.date(2010, 10, 1))
        # The bug does not occur here because a Book with pubdate of Sep 1 exists
        res = self.client.get("/dates/books/2010/oct/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["previous_month"], datetime.date(2010, 9, 1))

    def test_datetime_month_view(self):
        BookSigning.objects.create(event_date=datetime.datetime(2008, 2, 1, 12, 0))
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        BookSigning.objects.create(event_date=datetime.datetime(2008, 6, 3, 12, 0))
        res = self.client.get("/dates/booksignings/2008/apr/")
        self.assertEqual(res.status_code, 200)

    def test_month_view_get_month_from_request(self):
        oct1 = datetime.date(2008, 10, 1)
        res = self.client.get("/dates/books/without_month/2008/?month=oct")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/book_archive_month.html")
        self.assertEqual(list(res.context["date_list"]), [oct1])
        self.assertEqual(
            list(res.context["book_list"]), list(Book.objects.filter(pubdate=oct1))
        )
        self.assertEqual(res.context["month"], oct1)

    def test_month_view_without_month_in_url(self):
        """

        Tests the month view when no month is specified in the URL.

        This test case simulates a GET request to a URL that does not contain a month value.
        It verifies that the server returns a 404 status code and that the response context
        contains an 'exception' key with the message 'No month specified', indicating that
        the request was invalid due to the missing month parameter.

        """
        res = self.client.get("/dates/books/without_month/2008/")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.context["exception"], "No month specified")

    @skipUnlessDBFeature("has_zoneinfo_database")
    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_month_view(self):
        BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 2, 1, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 4, 2, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 6, 3, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        res = self.client.get("/dates/booksignings/2008/apr/")
        self.assertEqual(res.status_code, 200)

    def test_date_list_order(self):
        """date_list should be sorted ascending in month view"""
        _make_books(10, base_date=datetime.date(2011, 12, 25))
        res = self.client.get("/dates/books/2011/dec/")
        self.assertEqual(
            list(res.context["date_list"]), sorted(res.context["date_list"])
        )


@override_settings(ROOT_URLCONF="generic_views.urls")
class WeekArchiveViewTests(TestDataMixin, TestCase):
    def test_week_view(self):
        """

        Tests the week view functionality of the application.

        This test case verifies that the week view page returns a successful response,
        renders the correct template, and populates the context with the correct data.
        The test checks the status code of the response, the template used, and the
        contents of the context, including the list of books and week navigation links.

        """
        res = self.client.get("/dates/books/2008/week/39/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/book_archive_week.html")
        self.assertEqual(
            res.context["book_list"][0],
            Book.objects.get(pubdate=datetime.date(2008, 10, 1)),
        )
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 28))

        # Since allow_empty=False, next/prev weeks must be valid
        self.assertIsNone(res.context["next_week"])
        self.assertEqual(res.context["previous_week"], datetime.date(2006, 4, 30))

    def test_week_view_allow_empty(self):
        # allow_empty = False, empty week
        res = self.client.get("/dates/books/2008/week/12/")
        self.assertEqual(res.status_code, 404)

        # allow_empty = True, empty month
        res = self.client.get("/dates/books/2008/week/12/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["book_list"]), [])
        self.assertEqual(res.context["week"], datetime.date(2008, 3, 23))

        # Since allow_empty=True, next/prev are allowed to be empty weeks
        self.assertEqual(res.context["next_week"], datetime.date(2008, 3, 30))
        self.assertEqual(res.context["previous_week"], datetime.date(2008, 3, 16))

        # allow_empty but not allow_future: next_week should be empty
        url = (
            datetime.date.today()
            .strftime("/dates/books/%Y/week/%U/allow_empty/")
            .lower()
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.context["next_week"])

    def test_week_view_allow_future(self):
        # January 7th always falls in week 1, given Python's definition of week numbers
        """
        Tests the week view for a book when the publication date is in the future.

        Verifies that when the `allow_future` parameter is not provided, the view returns a 404 status code.
        When `allow_future` is provided, the view returns a 200 status code, including the book in the context's book list.
        Additionally, checks that the context's week is set to the first Sunday of the year the book will be published,
        and that the next and previous week URLs are correctly set based on the publication date and `allow_future` parameter.

        The test case ensures the correct functionality of the week view when dealing with future publication dates.
        """
        future = datetime.date(datetime.date.today().year + 1, 1, 7)
        future_sunday = future - datetime.timedelta(days=(future.weekday() + 1) % 7)
        b = Book.objects.create(name="The New New Testement", pages=600, pubdate=future)

        res = self.client.get("/dates/books/%s/week/1/" % future.year)
        self.assertEqual(res.status_code, 404)

        res = self.client.get("/dates/books/%s/week/1/allow_future/" % future.year)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["book_list"]), [b])
        self.assertEqual(res.context["week"], future_sunday)

        # Since allow_future = True but not allow_empty, next/prev are not
        # allowed to be empty weeks
        self.assertIsNone(res.context["next_week"])
        self.assertEqual(res.context["previous_week"], datetime.date(2008, 9, 28))

        # allow_future, but not allow_empty, with a current week. So next
        # should be in the future
        res = self.client.get("/dates/books/2008/week/39/allow_future/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["next_week"], future_sunday)
        self.assertEqual(res.context["previous_week"], datetime.date(2006, 4, 30))

    def test_week_view_paginated(self):
        """

        Tests the week view of the book archive, ensuring it returns a paginated list of books 
        published within the specified week.

        Verifies that the view returns a successful HTTP response, contains the correct list 
        of books published during the week, and uses the expected template.

        """
        week_start = datetime.date(2008, 9, 28)
        week_end = week_start + datetime.timedelta(days=7)
        res = self.client.get("/dates/books/2008/week/39/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate__gte=week_start, pubdate__lt=week_end)),
        )
        self.assertEqual(
            list(res.context["object_list"]),
            list(Book.objects.filter(pubdate__gte=week_start, pubdate__lt=week_end)),
        )
        self.assertTemplateUsed(res, "generic_views/book_archive_week.html")

    def test_week_view_invalid_pattern(self):
        """
        Tests the week view endpoint with an invalid week pattern.

        Verifies that a 404 status code is returned when attempting to access a week view
        with an invalid pattern, ensuring the endpoint handles malformed requests correctly.

         Args:
            None

         Returns:
            None

         Notes:
            This test is used to validate the robustness of the week view endpoint against
            incorrect or malformed input, helping to prevent potential errors or security
            vulnerabilities in the application.

        """
        res = self.client.get("/dates/books/2007/week/no_week/")
        self.assertEqual(res.status_code, 404)

    def test_week_start_Monday(self):
        # Regression for #14752
        res = self.client.get("/dates/books/2008/week/39/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 28))

        res = self.client.get("/dates/books/2008/week/39/monday/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 29))

    def test_week_iso_format(self):
        """
        Tests the view for retrieving books by week in ISO format, verifying a successful response, correct template usage, and expected book listing for a given week.
        """
        res = self.client.get("/dates/books/2008/week/40/iso_format/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/book_archive_week.html")
        self.assertEqual(
            list(res.context["book_list"]),
            [Book.objects.get(pubdate=datetime.date(2008, 10, 1))],
        )
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 29))

    def test_unknown_week_format(self):
        msg = "Unknown week format '%T'. Choices are: %U, %V, %W"
        with self.assertRaisesMessage(ValueError, msg):
            self.client.get("/dates/books/2008/week/39/unknown_week_format/")

    def test_incompatible_iso_week_format_view(self):
        """
        Tests that the API endpoint correctly raises an error when the ISO week format is used with the year directive '%Y' instead of the ISO year directive '%G'. The function verifies that a ValueError is raised with a specific message indicating the incompatibility and suggesting the correct usage.
        """
        msg = (
            "ISO week directive '%V' is incompatible with the year directive "
            "'%Y'. Use the ISO year '%G' instead."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.client.get("/dates/books/2008/week/40/invalid_iso_week_year_format/")

    def test_datetime_week_view(self):
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        res = self.client.get("/dates/booksignings/2008/week/13/")
        self.assertEqual(res.status_code, 200)

    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_week_view(self):
        """

        Tests the week view for book signings using aware datetime objects.

        This test case verifies that the week view for book signings returns a successful response (200 OK)
        when the event date is specified in a specific time zone. The test creates a book signing event with
        an aware datetime object and then makes a GET request to the week view URL for that event.

        """
        BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 4, 2, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        res = self.client.get("/dates/booksignings/2008/week/13/")
        self.assertEqual(res.status_code, 200)


@override_settings(ROOT_URLCONF="generic_views.urls")
class DayArchiveViewTests(TestDataMixin, TestCase):
    def test_day_view(self):
        """

        Tests the day view functionality by simulating a GET request to the day view URL.

        Verifies that the request returns a successful response (200 status code), uses the correct template, 
        and populates the response context with the correct data, including a list of books published on the specified day, 
        the day itself, and navigation links to previous and next days.

        Checks the accuracy of the book list, day, and navigation links to ensure they match the expected values.

        """
        res = self.client.get("/dates/books/2008/oct/01/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "generic_views/book_archive_day.html")
        self.assertEqual(
            list(res.context["book_list"]),
            list(Book.objects.filter(pubdate=datetime.date(2008, 10, 1))),
        )
        self.assertEqual(res.context["day"], datetime.date(2008, 10, 1))

        # Since allow_empty=False, next/prev days must be valid.
        self.assertIsNone(res.context["next_day"])
        self.assertEqual(res.context["previous_day"], datetime.date(2006, 5, 1))

    def test_day_view_allow_empty(self):
        # allow_empty = False, empty month
        res = self.client.get("/dates/books/2000/jan/1/")
        self.assertEqual(res.status_code, 404)

        # allow_empty = True, empty month
        res = self.client.get("/dates/books/2000/jan/1/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["book_list"]), [])
        self.assertEqual(res.context["day"], datetime.date(2000, 1, 1))

        # Since it's allow empty, next/prev are allowed to be empty months (#7164)
        self.assertEqual(res.context["next_day"], datetime.date(2000, 1, 2))
        self.assertEqual(res.context["previous_day"], datetime.date(1999, 12, 31))

        # allow_empty but not allow_future: next_month should be empty (#7164)
        url = (
            datetime.date.today().strftime("/dates/books/%Y/%b/%d/allow_empty/").lower()
        )
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.context["next_day"])

    def test_day_view_allow_future(self):
        future = datetime.date.today() + datetime.timedelta(days=60)
        urlbit = future.strftime("%Y/%b/%d").lower()
        b = Book.objects.create(name="The New New Testement", pages=600, pubdate=future)

        # allow_future = False, future month
        res = self.client.get("/dates/books/%s/" % urlbit)
        self.assertEqual(res.status_code, 404)

        # allow_future = True, valid future month
        res = self.client.get("/dates/books/%s/allow_future/" % urlbit)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["book_list"]), [b])
        self.assertEqual(res.context["day"], future)

        # allow_future but not allow_empty, next/prev must be valid
        self.assertIsNone(res.context["next_day"])
        self.assertEqual(res.context["previous_day"], datetime.date(2008, 10, 1))

        # allow_future, but not allow_empty, with a current month.
        res = self.client.get("/dates/books/2008/oct/01/allow_future/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["next_day"], future)
        self.assertEqual(res.context["previous_day"], datetime.date(2006, 5, 1))

        # allow_future for yesterday, next_day is today (#17192)
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        res = self.client.get(
            "/dates/books/%s/allow_empty_and_future/"
            % yesterday.strftime("%Y/%b/%d").lower()
        )
        self.assertEqual(res.context["next_day"], today)

    def test_day_view_paginated(self):
        res = self.client.get("/dates/books/2008/oct/1/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["book_list"]),
            list(
                Book.objects.filter(
                    pubdate__year=2008, pubdate__month=10, pubdate__day=1
                )
            ),
        )
        self.assertEqual(
            list(res.context["object_list"]),
            list(
                Book.objects.filter(
                    pubdate__year=2008, pubdate__month=10, pubdate__day=1
                )
            ),
        )
        self.assertTemplateUsed(res, "generic_views/book_archive_day.html")

    def test_next_prev_context(self):
        """

        Tests the next and previous context links in the date archive view.

        Verifies that the correct previous day is displayed when viewing a specific date archive page.

        """
        res = self.client.get("/dates/books/2008/oct/01/")
        self.assertEqual(
            res.content, b"Archive for Oct. 1, 2008. Previous day is May 1, 2006\n"
        )

    def test_custom_month_format(self):
        res = self.client.get("/dates/books/2008/10/01/")
        self.assertEqual(res.status_code, 200)

    def test_day_view_invalid_pattern(self):
        res = self.client.get("/dates/books/2007/oct/no_day/")
        self.assertEqual(res.status_code, 404)

    def test_today_view(self):
        """

        Tests the 'today' view for retrieving books.

        This test suite verifies two scenarios:
        - That the view returns a 404 status code when empty results are not allowed.
        - That the view returns a 200 status code and the correct current date when empty results are allowed.

        """
        res = self.client.get("/dates/books/today/")
        self.assertEqual(res.status_code, 404)
        res = self.client.get("/dates/books/today/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["day"], datetime.date.today())

    def test_datetime_day_view(self):
        """
        Tests the datetime day view for book signings, ensuring a successful HTTP response when retrieving a specific date. 

        This test case covers the scenario where a book signing event is scheduled on a particular day and verifies that the corresponding day view page returns a status code of 200, indicating a successful request. The test creates a book signing event on a specific date and time, then simulates a GET request to the day view page for that date, asserting that the response status code is 200 (OK).
        """
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        res = self.client.get("/dates/booksignings/2008/apr/2/")
        self.assertEqual(res.status_code, 200)

    @requires_tz_support
    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_day_view(self):
        bs = BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 4, 2, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        res = self.client.get("/dates/booksignings/2008/apr/2/")
        self.assertEqual(res.status_code, 200)
        # 2008-04-02T00:00:00+03:00 (beginning of day) >
        # 2008-04-01T22:00:00+00:00 (book signing event date).
        bs.event_date = datetime.datetime(
            2008, 4, 1, 22, 0, tzinfo=datetime.timezone.utc
        )
        bs.save()
        res = self.client.get("/dates/booksignings/2008/apr/2/")
        self.assertEqual(res.status_code, 200)
        # 2008-04-03T00:00:00+03:00 (end of day) > 2008-04-02T22:00:00+00:00
        # (book signing event date).
        bs.event_date = datetime.datetime(
            2008, 4, 2, 22, 0, tzinfo=datetime.timezone.utc
        )
        bs.save()
        res = self.client.get("/dates/booksignings/2008/apr/2/")
        self.assertEqual(res.status_code, 404)


@override_settings(ROOT_URLCONF="generic_views.urls")
class DateDetailViewTests(TestDataMixin, TestCase):
    def test_date_detail_by_pk(self):
        """

         Tests the date detail view by primary key, ensuring a successful HTTP response.

         Verifies that the view correctly retrieves a specific book object by its primary key,
         and that the response contains the expected context and template.

         The test checks for the following conditions:
          - A successful HTTP GET request (200 status code)
          - The retrieved object matches the expected book object
          - The response context contains the correct book object
          - The correct template is used for rendering the response

        """
        res = self.client.get("/dates/books/2008/oct/01/%s/" % self.book1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.book1)
        self.assertEqual(res.context["book"], self.book1)
        self.assertTemplateUsed(res, "generic_views/book_detail.html")

    def test_date_detail_by_slug(self):
        res = self.client.get("/dates/books/2006/may/01/byslug/dreaming-in-code/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["book"], Book.objects.get(slug="dreaming-in-code"))

    def test_date_detail_custom_month_format(self):
        res = self.client.get("/dates/books/2008/10/01/%s/" % self.book1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["book"], self.book1)

    def test_date_detail_allow_future(self):
        future = datetime.date.today() + datetime.timedelta(days=60)
        urlbit = future.strftime("%Y/%b/%d").lower()
        b = Book.objects.create(
            name="The New New Testement", slug="new-new", pages=600, pubdate=future
        )

        res = self.client.get("/dates/books/%s/new-new/" % urlbit)
        self.assertEqual(res.status_code, 404)

        res = self.client.get("/dates/books/%s/%s/allow_future/" % (urlbit, b.id))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["book"], b)
        self.assertTemplateUsed(res, "generic_views/book_detail.html")

    def test_year_out_of_range(self):
        urls = [
            "/dates/books/9999/",
            "/dates/books/9999/12/",
            "/dates/books/9999/week/52/",
        ]
        for url in urls:
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 404)
                self.assertEqual(res.context["exception"], "Date out of range")

    def test_invalid_url(self):
        """
        Test that a 404 or an AttributeError is raised when an invalid URL is used to access the BookDetail view.

            The test checks the view's behavior when the URL does not contain a valid primary key (pk) or slug, 
            ensuring it correctly handles this edge case by raising the expected error with a suitable error message.
        """
        msg = (
            "Generic detail view BookDetail must be called with either an "
            "object pk or a slug in the URLconf."
        )
        with self.assertRaisesMessage(AttributeError, msg):
            self.client.get("/dates/books/2008/oct/01/nopk/")

    def test_get_object_custom_queryset(self):
        """
        Custom querysets are used when provided to
        BaseDateDetailView.get_object().
        """
        res = self.client.get(
            "/dates/books/get_object_custom_queryset/2006/may/01/%s/" % self.book2.pk
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["object"], self.book2)
        self.assertEqual(res.context["book"], self.book2)
        self.assertTemplateUsed(res, "generic_views/book_detail.html")

        res = self.client.get(
            "/dates/books/get_object_custom_queryset/2008/oct/01/9999999/"
        )
        self.assertEqual(res.status_code, 404)

    def test_get_object_custom_queryset_numqueries(self):
        with self.assertNumQueries(1):
            self.client.get("/dates/books/get_object_custom_queryset/2006/may/01/2/")

    def test_datetime_date_detail(self):
        """
        Tests the retrieval of a specific BookSigning event's date details.

        This test case checks that when the date URL for a BookSigning event is accessed, the server responds with a successful HTTP status code (200 OK). The test creates a BookSigning event with a specific date and time, then attempts to retrieve the event's details using the client. The expected result is a successful response, indicating that the event's date details can be accessed correctly.
        """
        bs = BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        res = self.client.get("/dates/booksignings/2008/apr/2/%d/" % bs.pk)
        self.assertEqual(res.status_code, 200)

    @requires_tz_support
    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_date_detail(self):
        bs = BookSigning.objects.create(
            event_date=datetime.datetime(
                2008, 4, 2, 12, 0, tzinfo=datetime.timezone.utc
            )
        )
        res = self.client.get("/dates/booksignings/2008/apr/2/%d/" % bs.pk)
        self.assertEqual(res.status_code, 200)
        # 2008-04-02T00:00:00+03:00 (beginning of day) >
        # 2008-04-01T22:00:00+00:00 (book signing event date).
        bs.event_date = datetime.datetime(
            2008, 4, 1, 22, 0, tzinfo=datetime.timezone.utc
        )
        bs.save()
        res = self.client.get("/dates/booksignings/2008/apr/2/%d/" % bs.pk)
        self.assertEqual(res.status_code, 200)
        # 2008-04-03T00:00:00+03:00 (end of day) > 2008-04-02T22:00:00+00:00
        # (book signing event date).
        bs.event_date = datetime.datetime(
            2008, 4, 2, 22, 0, tzinfo=datetime.timezone.utc
        )
        bs.save()
        res = self.client.get("/dates/booksignings/2008/apr/2/%d/" % bs.pk)
        self.assertEqual(res.status_code, 404)
