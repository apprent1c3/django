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

        Verifies that the view returns a successful HTTP response, and that the
        context contains the correct list of dates and the latest books. Also checks
        that the correct template is used to render the response.

        The test covers the following scenarios:
        - A successful HTTP GET request to the archive view
        - The presence of a date list in the response context
        - The presence of the latest books in the response context
        - The use of the correct template to render the response

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
        Book.objects.all().delete()
        res = self.client.get("/dates/books/")
        self.assertEqual(res.status_code, 404)

    def test_allow_empty_archive_view(self):
        Book.objects.all().delete()
        res = self.client.get("/dates/books/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [])
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_archive_view_template(self):
        res = self.client.get("/dates/books/template_name/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(list(res.context["latest"]), list(Book.objects.all()))
        self.assertTemplateUsed(res, "generic_views/list.html")

    def test_archive_view_template_suffix(self):
        res = self.client.get("/dates/books/template_name_suffix/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "year", "DESC")),
        )
        self.assertEqual(list(res.context["latest"]), list(Book.objects.all()))
        self.assertTemplateUsed(res, "generic_views/book_detail.html")

    def test_archive_view_invalid(self):
        msg = (
            "BookArchive is missing a QuerySet. Define BookArchive.model, "
            "BookArchive.queryset, or override BookArchive.get_queryset()."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/dates/books/invalid/")

    def test_archive_view_by_month(self):
        """

        Tests the archive view functionality for retrieving a list of book publication dates grouped by month.

        This view is expected to return a successful HTTP response (200 OK) and a list of dates in descending order, 
        corresponding to the publication dates of all books in the database.

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
        ).. 
                Tests that the view for reverse ordering of book dates by publication 
                date does not execute more than the expected number of database queries. 
                The expected number of queries is 2. This test case ensures that the 
                database operations are optimized and no unnecessary queries are made.
        """
        with self.assertNumQueries(2):
            self.client.get("/dates/books/reverse/")

    def test_datetime_archive_view(self):
        """

        Tests the datetime archive view by creating a BookSigning object with a specific event date 
        and verifying that a GET request to the '/dates/booksignings/' endpoint returns a successful response.

        The purpose of this test is to ensure that the datetime archive view is functioning correctly 
        and returning the expected HTTP status code (200) when a valid request is made.

        """
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        res = self.client.get("/dates/booksignings/")
        self.assertEqual(res.status_code, 200)

    @requires_tz_support
    @skipUnlessDBFeature("has_zoneinfo_database")
    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_archive_view(self):
        """

        Tests the aware datetime archive view for book signings.

        This test case ensures that the archive view correctly handles datetime objects 
        with time zone information. It creates a book signing event with a datetime in 
        UTC and then makes a GET request to the archive view. The test asserts that the 
        view returns a successful response (200 status code).

        The test is skipped if the database does not support time zones and requires 
        time zone support to be enabled.

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
        Tests that attempting to access the book archive view without a date field raises an ImproperlyConfigured exception.

        The test verifies that a specific error message is displayed when the date_field attribute is missing, ensuring that the view is properly configured to handle date-based queries.

        :raises: ImproperlyConfigured
        :note: This test case covers a specific edge case where the date field is not provided, ensuring the robustness of the archive view functionality.
        """
        msg = "BookArchiveWithoutDateField.date_field is required."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/dates/books/without_date_field/")


@override_settings(ROOT_URLCONF="generic_views.urls")
class YearArchiveViewTests(TestDataMixin, TestCase):
    def test_year_view(self):
        """
        Tests the year view functionality for book archives.

        Verifies that a GET request to the year view endpoint returns a successful response,
        renders the correct template, and includes the expected context variables, including
        a list of dates, the current year, and navigation links to previous and next years.

        Specifically, it checks that the response status code is 200, the date list contains
        the expected dates, the year is correctly set, and the previous and next year links
        are correctly determined. The test also ensures that the correct template is used to
        render the year view page.
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
        Tests the year view endpoint when an invalid pattern is used.

        The function sends a GET request to the '/dates/books/no_year/' endpoint and checks if the server returns a 404 status code, indicating that the requested resource cannot be found due to an invalid year pattern. This test ensures that the application handles invalid year patterns correctly and returns an appropriate error response.
        """
        res = self.client.get("/dates/books/no_year/")
        self.assertEqual(res.status_code, 404)

    def test_no_duplicate_query(self):
        # Regression test for #18354
        """

        Tests that the 'reverse' view for books by date does not execute duplicate database queries.

        The test simulates a GET request to the '/dates/books/2008/reverse/' endpoint and verifies that the database is queried exactly 4 times.

        It ensures that the view is optimized to minimize database queries, preventing potential performance issues.

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

        Tests the month view functionality when allowing empty results.

        This test checks that the month view returns a 404 status code when no 'allow_empty' parameter is provided and the view would otherwise be empty.
        It then tests that when the 'allow_empty' parameter is provided, the view returns a 200 status code and an empty list of dates and books.
        Additionally, it verifies that the correct month, next month, and previous month are displayed in the view context.
        The test also checks that when the current month is requested with the 'allow_empty' parameter, the view returns a 200 status code and the next month is None.

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

        Tests the month view functionality when allowing future dates.

        This test case ensures that the month view returns a 404 status code when
        trying to access a future month without allowing future dates. It also
        verifies that when allowing future dates, the view returns a 200 status
        code and correctly populates the context with the expected data, including
        the list of dates, books, and navigation links to next and previous months.

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
        Tests the API endpoint for retrieving book data by custom month format.

        Verifies that a GET request to the '/dates/books/year/month/' endpoint returns a successful response (200 status code) when given a valid year and month.

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
        """

        Tests the date view functionality for retrieving book signings by month.

        Verifies that a successful HTTP request (200 status code) is returned when
        retrieving book signings for a specific month (e.g., April 2008), even if
        there are book signings in other months.

        """
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

        Tests the week view of the book archive.

        This test case retrieves the week view for the year 2008, specifically week 39, 
        and verifies that the HTTP response status code is 200. It also checks that 
        the correct template is used to render the page and that the book list, week 
        and navigation links (previous and next week) are correctly populated in the 
        response context.

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

        Tests the week view functionality when allowing future dates.

        This test case ensures that the week view returns a 404 status code when future dates are not allowed.
        It also verifies that when future dates are allowed, the view returns a 200 status code and the expected book list.
        Additionally, it checks the context variables 'book_list', 'week', 'next_week', and 'previous_week' for correctness.

        The test creates a book with a future publication date and then makes GET requests to the week view URL with and without the 'allow_future' parameter.
        It asserts that the response status codes and context variables match the expected values.

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
        Tests the week view with pagination for books.

        This test case verifies that the week view page for books is correctly rendered
        and that the book list is properly filtered based on the specified week.

        It checks the following:
            * The HTTP response status code is 200 (OK)
            * The book list in the response context matches the expected list of books
              published during the specified week
            * The object list in the response context matches the book list
            * The correct template (book_archive_week.html) is used to render the page
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
        res = self.client.get("/dates/books/2007/week/no_week/")
        self.assertEqual(res.status_code, 404)

    def test_week_start_Monday(self):
        # Regression for #14752
        """
        Tests that the week start date is correctly determined as Monday for the given year and week number.

            Checks the HTTP response status code and the week start date in the response context for two scenarios:
            - when the week number is provided without specifying the day of the week
            - when 'monday' is explicitly specified as the day of the week

            Verifies that the response status code is 200 (OK) and the week start date is correctly set to a Monday in both cases.
        """
        res = self.client.get("/dates/books/2008/week/39/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 28))

        res = self.client.get("/dates/books/2008/week/39/monday/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 29))

    def test_week_iso_format(self):
        """
        Tests the week ISO format view for books.

        Verifies that the view returns a successful response, uses the correct template,
        and includes the expected book and week information in the response context.

        The view is expected to filter books by a specific week of the year in ISO format,
        and return a list of books published during that week, along with the start date of the week.
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
        Tests the handling of incompatible ISO week format in the view.

        Verifies that attempting to access a date with an ISO week format that includes 
        the year directive '%Y' raises a ValueError, as this is incompatible with the 
        ISO week directive '%V'. The correct usage should involve the ISO year '%G' 
        instead, to avoid ambiguity and ensure proper date interpretation.

        Args: 
            None

        Returns: 
            None

        Raises: 
            ValueError: With a message indicating the incompatibility of the ISO week 
            directive with the year directive, suggesting the use of the ISO year 
            directive instead.
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
        """

        Tests the day view functionality, specifically the behavior when allowing empty results.

        The test case covers two scenarios:
        - When the day view is accessed without allowing empty results, it should return a 404 status code.
        - When the day view is accessed with the 'allow_empty' parameter, it should return a 200 status code and an empty book list.

        Additionally, the test verifies that the response context contains the correct day, next day, and previous day information.
        The test also checks the behavior when accessing the day view for the current date, ensuring that the 'next_day' parameter is None.

        """
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
        """

        Checks the day view page with pagination for correctness.

        Verifies that a GET request to the day view page returns a successful status code (200),
        and that the correct book objects are displayed based on the date specified in the URL.
        The view's context is inspected to ensure it contains the expected list of books,
        and that the correct template ('book_archive_day.html') is used to render the page.

        """
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
        Tests the next and previous context functionality for archive dates.

        This test case asserts that when retrieving an archive date, the correct
        previous day is returned. The test uses a specific date (October 1, 2008)
        and verifies that the previous day is correctly identified as May 1, 2006.

        The test checks the HTTP response content from the client to ensure it
        matches the expected output, indicating that the next and previous context
        functionality is working as expected.

        :param None
        :returns: None
        :raises: AssertionError if the response content does not match the expected output
        """
        res = self.client.get("/dates/books/2008/oct/01/")
        self.assertEqual(
            res.content, b"Archive for Oct. 1, 2008. Previous day is May 1, 2006\n"
        )

    def test_custom_month_format(self):
        """

        Tests the custom month format functionality by sending a GET request to the '/dates/books/yyyy/mm/dd/' endpoint.
        The request includes a specific date, and the function checks if the server returns a successful response (status code 200).
        This test case ensures that the custom month format is properly handled and the application behaves as expected when receiving requests with date parameters in the specified format.

        """
        res = self.client.get("/dates/books/2008/10/01/")
        self.assertEqual(res.status_code, 200)

    def test_day_view_invalid_pattern(self):
        res = self.client.get("/dates/books/2007/oct/no_day/")
        self.assertEqual(res.status_code, 404)

    def test_today_view(self):
        res = self.client.get("/dates/books/today/")
        self.assertEqual(res.status_code, 404)
        res = self.client.get("/dates/books/today/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["day"], datetime.date.today())

    def test_datetime_day_view(self):
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

        Tests that the date detail view by primary key returns a successful response 
        and renders the correct template with the expected book object.

        Checks that the view returns a 200 status code, and that the book object 
        retrieved from the database matches the expected book object. 
        Also verifies that the correct template is used to render the response.

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
        """
        Tests that a date detail view for a custom month format returns a successful response and includes the expected book object in the context. 

        The view is tested for a specific date (October 1, 2008) and verifies that the HTTP status code is 200 (OK) and that the book object retrieved from the database matches the one used in the test.
        """
        res = self.client.get("/dates/books/2008/10/01/%s/" % self.book1.pk)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["book"], self.book1)

    def test_date_detail_allow_future(self):
        """
        Tests the date detail view for books, specifically when a future publication date is allowed.

        Verifies that when a book has a future publication date, its detail page is not accessible by default, 
        returning a 404 status code. However, when the 'allow_future' parameter is included in the URL, 
        the detail page becomes accessible, returning a 200 status code, and rendering the expected template with the book object.
        """
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
        """

        Tests the number of database queries made when retrieving an object using a custom queryset.

        Verifies that a single GET request to the specified URL results in only one database query.
        The test case ensures that the queryset is optimized to minimize database interactions.

        """
        with self.assertNumQueries(1):
            self.client.get("/dates/books/get_object_custom_queryset/2006/may/01/2/")

    def test_datetime_date_detail(self):
        """
        Tests the retrieval of a book signing event's date details.

        This test case verifies that a GET request to the book signing event date detail
        page returns a successful response (200 status code). The test creates a sample
        book signing event with a specific date and time, and then checks if the event's
        date details can be accessed through the API endpoint.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the response status code is not 200
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
