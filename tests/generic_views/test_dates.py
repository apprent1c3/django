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

        Sets up test data used across the class, creating instances of Artist, Author, Book, and Page.
        These pre-defined objects are used to test the functionality of the class in various scenarios.

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
        Tests the book archive view, verifying that it returns a successful response, 
        correctly retrieves a list of years for published books in descending order, 
        includes all books in the 'latest' context, and uses the expected template.
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
        Tests the archive view to ensure the correct context object name and template are used, verifying that the view returns a successful response with the expected date list and book objects.\"\"\"

        :param self: instance of the test class
        :returns: None, raises assertion error if the test fails
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
        Book.objects.all().delete()
        res = self.client.get("/dates/books/")
        self.assertEqual(res.status_code, 404)

    def test_allow_empty_archive_view(self):
        """

        Tests that the archive view for books correctly handles an empty list of dates.

        Verifies that the view returns a 200 status code, an empty date list, and uses the correct template.

        """
        Book.objects.all().delete()
        res = self.client.get("/dates/books/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [])
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_archive_view_template(self):
        """
        Tests the archive view template by verifying its HTTP status code, date list and latest book objects, and ensures the correct template is used for rendering.
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
        Tests the archive view with a custom template suffix, verifying the HTTP status code, 
        date list context, latest context, and the template used for rendering the page.
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
        msg = (
            "BookArchive is missing a QuerySet. Define BookArchive.model, "
            "BookArchive.queryset, or override BookArchive.get_queryset()."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/dates/books/invalid/")

    def test_archive_view_by_month(self):
        res = self.client.get("/dates/books/by_month/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            list(Book.objects.dates("pubdate", "month", "DESC")),
        )

    def test_paginated_archive_view(self):
        """

        Tests the paginated archive view, ensuring it returns the correct list of dates, latest items, and handles pagination correctly.

        Checks the view returns a 200 status code, uses the correct template, and presents the latest items and date lists as expected on the first and second pages.

        """
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
        """
        Tests that the paginated archive view for books retrieves data in a limited number of database queries, preventing the entire table from being loaded at once.
        """
        _make_books(20, base_date=datetime.date.today())
        # 1 query for years list + 1 query for books
        with self.assertNumQueries(2):
            self.client.get("/dates/books/")
        # same as above + 1 query to test if books exist + 1 query to count them
        with self.assertNumQueries(4):
            self.client.get("/dates/books/paginated/")

    def test_no_duplicate_query(self):
        # Regression test for #18354
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
        Tests the custom sorting functionality of the book archive view, verifying that books are sorted by name and dates are correctly retrieved and rendered in the template.
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
        """
        Tests the custom sorting functionality of the archive view.

        Verifies that the view returns a 200 status code, sorts books by date in descending order,
        and displays the latest books sorted by name in descending order, using the correct template.
        """
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
        msg = "BookArchiveWithoutDateField.date_field is required."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/dates/books/without_date_field/")


@override_settings(ROOT_URLCONF="generic_views.urls")
class YearArchiveViewTests(TestDataMixin, TestCase):
    def test_year_view(self):
        """
        Test that the year view for book dates returns the correct context and uses the expected template. The test checks the status code, date list, year, next year, and previous year in the response context, as well as the template used to render the view.
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
        """
        Tests the year view 'make_object_list' functionality by verifying the status code, context data and template used in the response.
        """
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
        """
        Tests the view for retrieving books by year, checking that it correctly handles cases where no books exist for the given year, with and without allowing empty results.
        """
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
        Checks that the year view behaves correctly when future dates are involved, verifying that it returns a 404 by default, an empty list when allowing empty results, and includes future dates when explicitly allowed.
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
        """
        Tests the paginated year view by verifying that it returns a 200 status code, 
        contains the correct list of books published in the specified year, 
        and uses the expected template.
        """
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

        Tests that the year view uses a custom sort order when the 'sortedbyname' URL keyword is used.

        Verifies the view returns a 200 status code, and the correct lists of dates, books, and objects, 
        all sorted by book name, are passed to the template.

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
        """
        Tests the year view with two custom sort orders, verifying that the 
        response status code is 200, the date list and book list are sorted 
        correctly by page and name, and the correct template is used.
        """
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
        res = self.client.get("/dates/books/no_year/")
        self.assertEqual(res.status_code, 404)

    def test_no_duplicate_query(self):
        # Regression test for #18354
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
        """
        Tests the month archive view for books, ensuring it returns a 200 status code, uses the correct template, and provides the expected date and book data in the response context.
        """
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
        Tests the month view functionality, specifically the allow_empty parameter, to ensure it correctly handles 
        months with no data and provides the expected context variables, including date and book lists, as well as 
        previous and next month links, or the absence thereof when at the current month.
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
        Test that the month view for books functions correctly with and without the allow_future parameter.

        Tests that the view returns a 404 when future dates are not allowed and a 200 when they are, 
        and verifies that the correct context data is provided in both cases.
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
        Tests the HTTP response and context of the paginated month view for books.

        Verifies that the view returns a successful status code, includes the correct list of books
        for the specified month and year in the context, and uses the expected template.
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
        Tests that the datetime month view for BookSignings returns a successful response.

            Verifies that a GET request to the month view URL for a specific month (April 2008)
            returns a 200 status code, indicating a successful response.
        """
        BookSigning.objects.create(event_date=datetime.datetime(2008, 2, 1, 12, 0))
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        BookSigning.objects.create(event_date=datetime.datetime(2008, 6, 3, 12, 0))
        res = self.client.get("/dates/booksignings/2008/apr/")
        self.assertEqual(res.status_code, 200)

    def test_month_view_get_month_from_request(self):
        """
        Tests that the month view correctly retrieves a month from a request and returns the corresponding month, date list, and book list in the response context.
        """
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
        """
        Tests that the month view for BookSigning events works correctly with aware datetime objects and the Africa/Nairobi time zone
        """
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
        Tests the week view for book archives, verifying a successful response, 
        correct template usage, and accurate data retrieval for a specific week.
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
        """

        Tests the week view functionality for the book list, specifically the allow_empty parameter.
        Verifies that an empty book list is returned successfully when allow_empty is True, and a 404 status code is returned when it is False.
        Also checks that the context contains the correct week, next week, and previous week dates, and handles the case where there is no next week.

        """
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
        Tests whether the week view allows for displaying future dates.

        Verifies that a 404 status code is returned when attempting to display a future week without the 'allow_future' parameter,
        and a 200 status code is returned when the parameter is present.

        Also checks that the displayed book list, week, next week, and previous week are correctly set when displaying a future week.
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
        Tests that the week view of the book archive is correctly paginated, by verifying that it returns a 200 status code, contains the correct list of books published during the specified week, and uses the correct template.
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
        Tests that the week start date is correctly calculated and returned when the week number and year are provided, with and without the 'monday' parameter.
        """
        res = self.client.get("/dates/books/2008/week/39/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 28))

        res = self.client.get("/dates/books/2008/week/39/monday/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 29))

    def test_week_iso_format(self):
        """
        Tests the view that returns books for a specific week in ISO format.

        Verifies that the view returns a 200 status code, uses the correct template, 
        and contains the expected book list and week context variables.
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
        """
        Checks the functionality of the day view page for books, verifying that it returns a successful response, uses the correct template, and correctly populates the book list and date context variables.
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
        """
        Tests the day view functionality, specifically handling of empty book lists. 
        Verifies that requests to a day view with an \"allow_empty\" parameter return a successful response 
        even if no books are associated with the requested date, and that the response includes the 
        correct day, next day, and previous day context values.
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
        """

        Tests the day view for books, specifically the allow_future parameter.

        This test case verifies that a 404 status code is returned when attempting to access a future date without
        the allow_future parameter, and that the book list and context are correctly populated when the parameter
        is present. It also checks the navigation links to previous and next days, including edge cases where there
        are no books on adjacent days.

        """
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

        Tests the day view for a paginated list of books.

        Verifies that the view returns a 200 status code, renders the correct template,
        and includes the expected book objects based on the specified date.

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
        Tests the today view function to ensure it behaves correctly, returning a 404 status code when no results are found and a 200 status code when the allow_empty parameter is provided, with the day in the response context set to the current date.
        """
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
        """
        Tests the day view for a book signing event, ensuring that immediately following dates are accessible but events occurring after midnight are not accessible on the same day's view, using timezone-aware datetime objects.
        """
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
        Tests the detail view of a book by its primary key, verifying that the view returns a successful response, renders the correct template, and provides the expected context data.
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
        """
        Tests that the book detail view returns a 404 when trying to access a future book's page by default,
        but returns a 200 when the 'allow_future' parameter is specified in the URL.
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
        """
        Tests that URLs with years out of range return a 404 status code and an exception indicating the date is out of range.
        """
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
        with self.assertNumQueries(1):
            self.client.get("/dates/books/get_object_custom_queryset/2006/may/01/2/")

    def test_datetime_date_detail(self):
        bs = BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        res = self.client.get("/dates/booksignings/2008/apr/2/%d/" % bs.pk)
        self.assertEqual(res.status_code, 200)

    @requires_tz_support
    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Nairobi")
    def test_aware_datetime_date_detail(self):
        """
        Tests the detail view of a book signing event to ensure correct status codes are returned based on the event's date, specifically when the event date is on or near the date specified in the URL.
        """
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
