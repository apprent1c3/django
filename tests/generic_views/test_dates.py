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
        Sets up test data for the application, creating instances of Artist, Author, Book, and Page objects to be used in testing scenarios.
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
        Tests the book archive view, verifying a successful response, correct date list, and proper template usage.
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
        Tests the context object names of the archive view, ensuring it returns the correct status code, date list, and book list, while also verifying the correct template is used and the 'latest' key is absent from the context.
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
        Tests the allow empty archive view by verifying that an HTTP GET request to the view returns a successful response with an empty date list and the correct template.
        """
        Book.objects.all().delete()
        res = self.client.get("/dates/books/allow_empty/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(res.context["date_list"]), [])
        self.assertTemplateUsed(res, "generic_views/book_archive.html")

    def test_archive_view_template(self):
        """
        Tests the archive view template, ensuring it returns a 200 status code, 
        correctly populates the date list and latest book contexts, and uses the expected list.html template.
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
        Tests the archive view template suffix by verifying that the view returns a 200 status code, 
        correctly populates the date list and latest context variables, and uses the expected template.
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
        Tests the paginated archive view for books, ensuring correct pagination, date listing, and latest book retrieval.
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

        Tests that the paginated archive view does not load the entire table by verifying the number of database queries executed when accessing the paginated and non-paginated views.

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
        """
        Tests that the date list is sorted in descending order when retrieved from the '/dates/books/' endpoint.
        """
        _make_books(5, base_date=datetime.date(2011, 12, 25))
        res = self.client.get("/dates/books/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            list(res.context["date_list"]),
            sorted(res.context["date_list"], reverse=True),
        )

    def test_archive_view_custom_sorting(self):
        """
        Tests the archive view with custom sorting, verifying that books are displayed in the correct order by name and that the date list is sorted in descending order by publication year.
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
        Tests the book archive view's custom sorting functionality in descending order by name, verifying the correct status code, date list, and template usage.
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

        Tests the year view for the book archive.

        Verifies that the view returns a successful response, renders the correct template,
        and provides the expected context data, including the date list, year, and navigation links.

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
        Tests that the year view correctly generates the object list of books.

        Verifies the response status code, date list, book list, and object list for the
        specified year, and confirms the correct template is used for rendering.
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
        Tests the year view when no data is present, checking for correct HTTP status codes and context variables when accessing a year with and without allowing empty results.
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
        Tests the year view with future dates, ensuring that future books are not shown by default, but can be shown when allow_future is specified.
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
        Tests the paginated year view for books, verifying the response status code, 
        book list context, and template usage for a specific year.
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

        Tests the book archive year view with a custom sort order.

        Verifies that books are sorted correctly by name when the '/sortedbyname/' URL is used, 
        and that the correct template is rendered with the expected data.

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
        Tests the year view with two custom sort orders, verifying that the response status code is 200, the date and book lists are correctly sorted, and the expected template is used.
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

        Tests that MultipleObjectMixin.get_context_data() receives the correct context.
        Verifies that BaseYearArchiveView.get_dated_items() sets the context as expected
        and that it is properly passed to get_context_data.

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
        Tests the month view of the book archive, ensuring that the correct template is used and the expected data is provided in the context, including the list of dates and books for the given month.
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
        Tests the month view, verifying that it handles cases with and without data.

         Checks the response status code for a month with no data, and verifies that
         the view returns an empty list when the 'allow_empty' parameter is specified.

         Also tests that the view correctly populates context variables, including the
         current month, next month, and previous month, and handles the case where
         there is no next month (i.e., the current month is the last one in the data).
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
        Tests that the month view correctly handles future dates when the allow_future parameter is set, verifying that future dates are only shown when the parameter is present.
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
        Tests the month view pagination functionality, verifying that it returns the correct list of books and uses the expected template.\"\"\"



        \"\"\"Tests if the month view paginated page returns a successful response, contains the correct book list for a specific month and year, and renders the correct template.\"\"\"

         Both are good. 

        However, the second is more detailed and would be more helpful as a docstring because users can get more information from it. Therefore, the second docstring is better. 

        So the final answer is: 
        \"\"\"Tests if the month view paginated page returns a successful response, contains the correct book list for a specific month and year, and renders the correct template.
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
        """
        Tests that the 'previous_month' context variable is correctly calculated for the current month, 
        even if there is content on any day of the previous month.
        """
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
        Tests the datetime month view for BookSigning events, ensuring that a GET request to the month view returns a successful response.
        """
        BookSigning.objects.create(event_date=datetime.datetime(2008, 2, 1, 12, 0))
        BookSigning.objects.create(event_date=datetime.datetime(2008, 4, 2, 12, 0))
        BookSigning.objects.create(event_date=datetime.datetime(2008, 6, 3, 12, 0))
        res = self.client.get("/dates/booksignings/2008/apr/")
        self.assertEqual(res.status_code, 200)

    def test_month_view_get_month_from_request(self):
        """

        Tests that the month view correctly retrieves a month from a request and 
        renders the corresponding template with the expected data, including 
        book archives for that month.

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
        Tests the month view for aware datetime values, ensuring that a successful response is returned for a specific URL.
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
        Tests the week view by verifying that the correct template is used, the response status code is 200, and the context contains the expected book list and week navigation dates.
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
        Tests week view functionality, ensuring a 404 is returned when no books are found and the allow_empty parameter is not provided, 
        and verifying that the view correctly handles empty book lists and pagination when allow_empty is provided.
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
        Tests the week view for allowing future dates.

        Verifies that the view returns a 404 status code when future dates are not allowed,
        and a 200 status code when future dates are allowed. Also checks that the view
        correctly populates the book list and provides links to previous and next weeks
        when future dates are allowed.
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

        Tests the week view of a paginated book list, ensuring the correct books are displayed
        and the expected template is used, for a specific week (in this case, week 39 of 2008).

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
        Tests that the week start date is correctly calculated and returned when the start day of the week is set to Monday.
        """
        res = self.client.get("/dates/books/2008/week/39/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 28))

        res = self.client.get("/dates/books/2008/week/39/monday/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["week"], datetime.date(2008, 9, 29))

    def test_week_iso_format(self):
        """
        Tests the week ISO format view by making a GET request and verifying the response status code, template used, and context data.
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
        Tests the day view of the book archive, verifying that it returns a successful response, uses the correct template, and populates the context with the expected book list and date navigation information.
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
        Tests the day view functionality, specifically the 'allow_empty' parameter, ensuring it returns a 200 status code even when there are no books for a given date and correctly populates the context with relevant day, next day, and previous day information.
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
        Tests the day view functionality, ensuring that it properly handles dates in the future and returns the expected book list and navigation context when the 'allow_future' parameter is used.
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
        Tests the day view pagination for book archives, verifying a successful response, correct retrieval of books for the specified date, and the use of the correct template.
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
        Verify that the today view returns a 404 status code when no data is available, 
        and returns a 200 status code with the correct date when the allow_empty parameter is specified.
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

        Tests that the day view correctly handles cases where a BookSigning's event date crosses into the previous or next day due to timezone offset.

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

        Tests the detail view of a date by retrieving a book with a specific primary key.
        Verifies the HTTP response status code, context data, and the template used for rendering.

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
        Tests whether a book's detail page allows access to future dates when 'allow_future' is specified in the URL, but returns a 404 otherwise.
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
        Tests that requests to URLs with a year outside the valid range return a 404 status code and an 'Date out of range' exception message.
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
        Tests that BaseDateDetailView correctly retrieves an object using a custom queryset, verifying that the object is retrieved successfully when it exists and a 404 status code is returned when it does not.
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
        Tests the behavior of the date detail view for book signings with aware datetime objects, ensuring that requests for a specific date are handled correctly based on the UTC time of the book signing event, accounting for time zone differences.
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
