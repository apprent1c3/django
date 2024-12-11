import datetime
import sys
import unittest

from django.contrib.admin import (
    AllValuesFieldListFilter,
    BooleanFieldListFilter,
    EmptyFieldListFilter,
    FieldListFilter,
    ModelAdmin,
    RelatedOnlyFieldListFilter,
    SimpleListFilter,
    site,
)
from django.contrib.admin.filters import FacetsMixin
from django.contrib.admin.options import IncorrectLookupParameters, ShowFacets
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, models
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from .models import Book, Bookmark, Department, Employee, ImprovedBook, TaggedItem


def select_by(dictlist, key, value):
    return [x for x in dictlist if x[key] == value][0]


class DecadeListFilter(SimpleListFilter):
    def lookups(self, request, model_admin):
        return (
            ("the 80s", "the 1980's"),
            ("the 90s", "the 1990's"),
            ("the 00s", "the 2000's"),
            ("other", "other decades"),
        )

    def queryset(self, request, queryset):
        """

        Filters a queryset based on a specified decade.

        This method narrows down a queryset to include only items from a particular decade, 
        as determined by the value of the decade filter. The decade is specified as a string, 
        such as 'the 80s', 'the 90s', or 'the 00s', which correspond to the years 1980-1989, 
        1990-1999, and 2000-2009, respectively. The filtered queryset is then returned.

        :param request: The current request object
        :param queryset: The queryset to be filtered
        :return: The filtered queryset

        """
        decade = self.value()
        if decade == "the 80s":
            return queryset.filter(year__gte=1980, year__lte=1989)
        if decade == "the 90s":
            return queryset.filter(year__gte=1990, year__lte=1999)
        if decade == "the 00s":
            return queryset.filter(year__gte=2000, year__lte=2009)


class NotNinetiesListFilter(SimpleListFilter):
    title = "Not nineties books"
    parameter_name = "book_year"

    def lookups(self, request, model_admin):
        return (("the 90s", "the 1990's"),)

    def queryset(self, request, queryset):
        if self.value() == "the 90s":
            return queryset.filter(year__gte=1990, year__lte=1999)
        else:
            return queryset.exclude(year__gte=1990, year__lte=1999)


class DecadeListFilterWithTitleAndParameter(DecadeListFilter):
    title = "publication decade"
    parameter_name = "publication-decade"


class DecadeListFilterWithoutTitle(DecadeListFilter):
    parameter_name = "publication-decade"


class DecadeListFilterWithoutParameter(DecadeListFilter):
    title = "publication decade"


class DecadeListFilterWithNoneReturningLookups(DecadeListFilterWithTitleAndParameter):
    def lookups(self, request, model_admin):
        pass


class DecadeListFilterWithFailingQueryset(DecadeListFilterWithTitleAndParameter):
    def queryset(self, request, queryset):
        raise 1 / 0


class DecadeListFilterWithQuerysetBasedLookups(DecadeListFilterWithTitleAndParameter):
    def lookups(self, request, model_admin):
        """
        Generates a set of lookup choices for decades based on the existence of data within those decades.

        This function inspects the queryset associated with the given model admin and yields tuples
        containing a short label and a long label for each decade (1980s, 1990s, 2000s) that contains data.
        The yielded tuples can be used to populate a lookup field, allowing users to filter data by decade.

        The lookup choices are generated based on the presence of data in the queryset for each decade.
        Decades without any data are not included in the lookup choices.

        """
        qs = model_admin.get_queryset(request)
        if qs.filter(year__gte=1980, year__lte=1989).exists():
            yield ("the 80s", "the 1980's")
        if qs.filter(year__gte=1990, year__lte=1999).exists():
            yield ("the 90s", "the 1990's")
        if qs.filter(year__gte=2000, year__lte=2009).exists():
            yield ("the 00s", "the 2000's")


class DecadeListFilterParameterEndsWith__In(DecadeListFilter):
    title = "publication decade"
    parameter_name = "decade__in"  # Ends with '__in"


class DecadeListFilterParameterEndsWith__Isnull(DecadeListFilter):
    title = "publication decade"
    parameter_name = "decade__isnull"  # Ends with '__isnull"


class DepartmentListFilterLookupWithNonStringValue(SimpleListFilter):
    title = "department"
    parameter_name = "department"

    def lookups(self, request, model_admin):
        return sorted(
            {
                (
                    employee.department.id,  # Intentionally not a string (Refs #19318)
                    employee.department.code,
                )
                for employee in model_admin.get_queryset(request)
            }
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(department__id=self.value())


class DepartmentListFilterLookupWithUnderscoredParameter(
    DepartmentListFilterLookupWithNonStringValue
):
    parameter_name = "department__whatever"


class DepartmentListFilterLookupWithDynamicValue(DecadeListFilterWithTitleAndParameter):
    def lookups(self, request, model_admin):
        """
        Returns a list of lookup tuples based on the current value of the field.

        The function checks the current value and returns a specific pair of lookups if it matches 'the 80s' or 'the 90s'. 
        Otherwise, it returns both available options.

        The returned tuples contain a value and a human-readable name, suitable for display in a user interface.

        :returns: A list of tuples, where each tuple contains a lookup value and its corresponding display name.
        """
        if self.value() == "the 80s":
            return (("the 90s", "the 1990's"),)
        elif self.value() == "the 90s":
            return (("the 80s", "the 1980's"),)
        else:
            return (
                ("the 80s", "the 1980's"),
                ("the 90s", "the 1990's"),
            )


class EmployeeNameCustomDividerFilter(FieldListFilter):
    list_separator = "|"

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.lookup_kwarg = "%s__in" % field_path
        super().__init__(field, request, params, model, model_admin, field_path)

    def expected_parameters(self):
        return [self.lookup_kwarg]


class DepartmentOwnershipListFilter(SimpleListFilter):
    title = "Department Ownership"
    parameter_name = "department_ownership"

    def lookups(self, request, model_admin):
        return [
            ("DEV_OWNED", "Owned by Dev Department"),
            ("OTHER", "Other"),
        ]

    def queryset(self, request, queryset):
        queryset = queryset.annotate(
            owned_book_count=models.Count(
                "employee__department",
                filter=models.Q(employee__department__code="DEV"),
            ),
        )

        if self.value() == "DEV_OWNED":
            return queryset.filter(owned_book_count__gt=0)
        elif self.value() == "OTHER":
            return queryset.filter(owned_book_count=0)


class CustomUserAdmin(UserAdmin):
    list_filter = ("books_authored", "books_contributed")


class BookAdmin(ModelAdmin):
    list_filter = (
        "year",
        "author",
        "contributors",
        "is_best_seller",
        "date_registered",
        "no",
        "availability",
    )
    ordering = ("-id",)


class BookAdminWithTupleBooleanFilter(BookAdmin):
    list_filter = (
        "year",
        "author",
        "contributors",
        ("is_best_seller", BooleanFieldListFilter),
        "date_registered",
        "no",
        ("availability", BooleanFieldListFilter),
    )


class BookAdminWithUnderscoreLookupAndTuple(BookAdmin):
    list_filter = (
        "year",
        ("author__email", AllValuesFieldListFilter),
        "contributors",
        "is_best_seller",
        "date_registered",
        "no",
    )


class BookAdminWithCustomQueryset(ModelAdmin):
    def __init__(self, user, *args, **kwargs):
        """
        Initializes the object with a user and additional keyword arguments.

        :param user: The user to associate with this object.
        :param args: Variable number of positional arguments to be passed to the parent class.
        :param kwargs: Variable number of keyword arguments to be passed to the parent class.

        This constructor sets the user attribute and then calls the parent class's constructor with the provided arguments. It allows for flexible initialization of the object while ensuring the user is always set. 
        """
        self.user = user
        super().__init__(*args, **kwargs)

    list_filter = ("year",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(author=self.user)


class BookAdminRelatedOnlyFilter(ModelAdmin):
    list_filter = (
        "year",
        "is_best_seller",
        "date_registered",
        "no",
        ("author", RelatedOnlyFieldListFilter),
        ("contributors", RelatedOnlyFieldListFilter),
        ("employee__department", RelatedOnlyFieldListFilter),
    )
    ordering = ("-id",)


class DecadeFilterBookAdmin(ModelAdmin):
    empty_value_display = "???"
    list_filter = (
        "author",
        DecadeListFilterWithTitleAndParameter,
        "is_best_seller",
        "category",
        "date_registered",
        ("author__email", AllValuesFieldListFilter),
        ("contributors", RelatedOnlyFieldListFilter),
        ("category", EmptyFieldListFilter),
        DepartmentOwnershipListFilter,
    )
    ordering = ("-id",)


class DecadeFilterBookAdminWithAlwaysFacets(DecadeFilterBookAdmin):
    show_facets = ShowFacets.ALWAYS


class DecadeFilterBookAdminDisallowFacets(DecadeFilterBookAdmin):
    show_facets = ShowFacets.NEVER


class NotNinetiesListFilterAdmin(ModelAdmin):
    list_filter = (NotNinetiesListFilter,)


class DecadeFilterBookAdminWithoutTitle(ModelAdmin):
    list_filter = (DecadeListFilterWithoutTitle,)


class DecadeFilterBookAdminWithoutParameter(ModelAdmin):
    list_filter = (DecadeListFilterWithoutParameter,)


class DecadeFilterBookAdminWithNoneReturningLookups(ModelAdmin):
    list_filter = (DecadeListFilterWithNoneReturningLookups,)


class DecadeFilterBookAdminWithFailingQueryset(ModelAdmin):
    list_filter = (DecadeListFilterWithFailingQueryset,)


class DecadeFilterBookAdminWithQuerysetBasedLookups(ModelAdmin):
    list_filter = (DecadeListFilterWithQuerysetBasedLookups,)


class DecadeFilterBookAdminParameterEndsWith__In(ModelAdmin):
    list_filter = (DecadeListFilterParameterEndsWith__In,)


class DecadeFilterBookAdminParameterEndsWith__Isnull(ModelAdmin):
    list_filter = (DecadeListFilterParameterEndsWith__Isnull,)


class EmployeeAdmin(ModelAdmin):
    list_display = ["name", "department"]
    list_filter = ["department"]


class EmployeeCustomDividerFilterAdmin(EmployeeAdmin):
    list_filter = [
        ("name", EmployeeNameCustomDividerFilter),
    ]


class DepartmentFilterEmployeeAdmin(EmployeeAdmin):
    list_filter = [DepartmentListFilterLookupWithNonStringValue]


class DepartmentFilterUnderscoredEmployeeAdmin(EmployeeAdmin):
    list_filter = [DepartmentListFilterLookupWithUnderscoredParameter]


class DepartmentFilterDynamicValueBookAdmin(EmployeeAdmin):
    list_filter = [DepartmentListFilterLookupWithDynamicValue]


class BookmarkAdminGenericRelation(ModelAdmin):
    list_filter = ["tags__tag"]


class BookAdminWithEmptyFieldListFilter(ModelAdmin):
    list_filter = [
        ("author", EmptyFieldListFilter),
        ("title", EmptyFieldListFilter),
        ("improvedbook", EmptyFieldListFilter),
    ]


class DepartmentAdminWithEmptyFieldListFilter(ModelAdmin):
    list_filter = [
        ("description", EmptyFieldListFilter),
        ("employee", EmptyFieldListFilter),
    ]


class ListFiltersTests(TestCase):
    request_factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the application.

        This method creates a set of predefined data, including dates, users, departments, employees, and books, 
        which can be used to test the application's functionality.

        The test data includes:
        - Various dates (today, tomorrow, one week ago, next month, next year)
        - Three users (alfred, bob, lisa) with different levels of access
        - Two departments (Development, Design)
        - Two employees (John, Jack) assigned to the departments
        - Four books with different attributes (title, year, author, availability, category, etc.)

        This data is used as a foundation for testing the application's features and ensuring they work as expected.

        """
        cls.today = datetime.date.today()
        cls.tomorrow = cls.today + datetime.timedelta(days=1)
        cls.one_week_ago = cls.today - datetime.timedelta(days=7)
        if cls.today.month == 12:
            cls.next_month = cls.today.replace(year=cls.today.year + 1, month=1, day=1)
        else:
            cls.next_month = cls.today.replace(month=cls.today.month + 1, day=1)
        cls.next_year = cls.today.replace(year=cls.today.year + 1, month=1, day=1)

        # Users
        cls.alfred = User.objects.create_superuser(
            "alfred", "alfred@example.com", "password"
        )
        cls.bob = User.objects.create_user("bob", "bob@example.com")
        cls.lisa = User.objects.create_user("lisa", "lisa@example.com")

        # Departments
        cls.dev = Department.objects.create(code="DEV", description="Development")
        cls.design = Department.objects.create(code="DSN", description="Design")

        # Employees
        cls.john = Employee.objects.create(name="John Blue", department=cls.dev)
        cls.jack = Employee.objects.create(name="Jack Red", department=cls.design)

        # Books
        cls.djangonaut_book = Book.objects.create(
            title="Djangonaut: an art of living",
            year=2009,
            author=cls.alfred,
            is_best_seller=True,
            date_registered=cls.today,
            availability=True,
            category="non-fiction",
            employee=cls.john,
        )
        cls.bio_book = Book.objects.create(
            title="Django: a biography",
            year=1999,
            author=cls.alfred,
            is_best_seller=False,
            no=207,
            availability=False,
            category="fiction",
            employee=cls.john,
        )
        cls.django_book = Book.objects.create(
            title="The Django Book",
            year=None,
            author=cls.bob,
            is_best_seller=None,
            date_registered=cls.today,
            no=103,
            availability=True,
            employee=cls.jack,
        )
        cls.guitar_book = Book.objects.create(
            title="Guitar for dummies",
            year=2002,
            is_best_seller=True,
            date_registered=cls.one_week_ago,
            availability=None,
            category="",
        )
        cls.guitar_book.contributors.set([cls.bob, cls.lisa])

    def assertChoicesDisplay(self, choices, expected_displays):
        """
        Asserts that the display text of each choice matches the expected display text.

        :param choices: A list of choices, where each choice is a dictionary containing a 'display' key.
        :param expected_displays: A list of expected display texts, in the same order as the choices.
        :raises AssertionError: If any choice's display text does not match the corresponding expected display text.

        This method checks that the display text of each choice aligns with the expected display text, ensuring consistency and accuracy in the choices' presentation.
        """
        for choice, expected_display in zip(choices, expected_displays, strict=True):
            self.assertEqual(choice["display"], expected_display)

    def test_choicesfieldlistfilter_has_none_choice(self):
        """
        The last choice is for the None value.
        """

        class BookmarkChoicesAdmin(ModelAdmin):
            list_display = ["none_or_null"]
            list_filter = ["none_or_null"]

        modeladmin = BookmarkChoicesAdmin(Bookmark, site)
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[-1]["display"], "None")
        self.assertEqual(choices[-1]["query_string"], "?none_or_null__isnull=True")

    def test_datefieldlistfilter(self):
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist(request)

        request = self.request_factory.get(
            "/",
            {"date_registered__gte": self.today, "date_registered__lt": self.tomorrow},
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.django_book, self.djangonaut_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][4]
        self.assertEqual(filterspec.title, "date registered")
        choice = select_by(filterspec.choices(changelist), "display", "Today")
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"],
            "?date_registered__gte=%s&date_registered__lt=%s"
            % (
                self.today,
                self.tomorrow,
            ),
        )

        request = self.request_factory.get(
            "/",
            {
                "date_registered__gte": self.today.replace(day=1),
                "date_registered__lt": self.next_month,
            },
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        if (self.today.year, self.today.month) == (
            self.one_week_ago.year,
            self.one_week_ago.month,
        ):
            # In case one week ago is in the same month.
            self.assertEqual(
                list(queryset),
                [self.guitar_book, self.django_book, self.djangonaut_book],
            )
        else:
            self.assertEqual(list(queryset), [self.django_book, self.djangonaut_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][4]
        self.assertEqual(filterspec.title, "date registered")
        choice = select_by(filterspec.choices(changelist), "display", "This month")
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"],
            "?date_registered__gte=%s&date_registered__lt=%s"
            % (
                self.today.replace(day=1),
                self.next_month,
            ),
        )

        request = self.request_factory.get(
            "/",
            {
                "date_registered__gte": self.today.replace(month=1, day=1),
                "date_registered__lt": self.next_year,
            },
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        if self.today.year == self.one_week_ago.year:
            # In case one week ago is in the same year.
            self.assertEqual(
                list(queryset),
                [self.guitar_book, self.django_book, self.djangonaut_book],
            )
        else:
            self.assertEqual(list(queryset), [self.django_book, self.djangonaut_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][4]
        self.assertEqual(filterspec.title, "date registered")
        choice = select_by(filterspec.choices(changelist), "display", "This year")
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"],
            "?date_registered__gte=%s&date_registered__lt=%s"
            % (
                self.today.replace(month=1, day=1),
                self.next_year,
            ),
        )

        request = self.request_factory.get(
            "/",
            {
                "date_registered__gte": str(self.one_week_ago),
                "date_registered__lt": str(self.tomorrow),
            },
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(
            list(queryset), [self.guitar_book, self.django_book, self.djangonaut_book]
        )

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][4]
        self.assertEqual(filterspec.title, "date registered")
        choice = select_by(filterspec.choices(changelist), "display", "Past 7 days")
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"],
            "?date_registered__gte=%s&date_registered__lt=%s"
            % (
                str(self.one_week_ago),
                str(self.tomorrow),
            ),
        )

        # Null/not null queries
        request = self.request_factory.get("/", {"date_registered__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset[0], self.bio_book)

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][4]
        self.assertEqual(filterspec.title, "date registered")
        choice = select_by(filterspec.choices(changelist), "display", "No date")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?date_registered__isnull=True")

        request = self.request_factory.get("/", {"date_registered__isnull": "False"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(queryset.count(), 3)
        self.assertEqual(
            list(queryset), [self.guitar_book, self.django_book, self.djangonaut_book]
        )

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][4]
        self.assertEqual(filterspec.title, "date registered")
        choice = select_by(filterspec.choices(changelist), "display", "Has date")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?date_registered__isnull=False")

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows doesn't support setting a timezone that differs from the "
        "system timezone.",
    )
    @override_settings(USE_TZ=True)
    def test_datefieldlistfilter_with_time_zone_support(self):
        # Regression for #17830
        self.test_datefieldlistfilter()

    def test_allvaluesfieldlistfilter(self):
        """
        Tests the filtering functionality of the AllValuesFieldListFilter.

        Verifies that the filter correctly handles null and non-null values, 
        and that the selected value is properly highlighted in the filter choices.

        The test checks the 'year' field filter, covering the following scenarios:
        - Filtering by 'isnull' condition
        - Filtering by a specific 'year' value

        It ensures that the filter returns the correct queryset and 
        that the filter choices are correctly marked as selected based on the request parameters.
        """
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/", {"year__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.django_book])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "year")
        choices = list(filterspec.choices(changelist))
        self.assertIs(choices[-1]["selected"], True)
        self.assertEqual(choices[-1]["query_string"], "?year__isnull=True")

        request = self.request_factory.get("/", {"year": "2002"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "year")
        choices = list(filterspec.choices(changelist))
        self.assertIs(choices[2]["selected"], True)
        self.assertEqual(choices[2]["query_string"], "?year=2002")

    def test_allvaluesfieldlistfilter_custom_qs(self):
        # Make sure that correct filters are returned with custom querysets
        """
        Tests the AllValuesFieldListFilter with custom queryset functionality.

        This test case verifies that the filter correctly generates a list of choices 
        based on the data in the model. It checks that the filter produces the expected 
        number of choices and that the query string for each choice is correct. The test 
        covers the scenario where the filter is applied to a model with a custom queryset, 
        ensuring that the filtering logic works as expected in this context.
        """
        modeladmin = BookAdminWithCustomQueryset(self.alfred, Book, site)
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        filterspec = changelist.get_filters(request)[0][0]
        choices = list(filterspec.choices(changelist))
        # Should have 'All', 1999 and 2009 options i.e. the subset of years of
        # books written by alfred (which is the filtering criteria set by
        # BookAdminWithCustomQueryset.get_queryset())
        self.assertEqual(3, len(choices))
        self.assertEqual(choices[0]["query_string"], "?")
        self.assertEqual(choices[1]["query_string"], "?year=1999")
        self.assertEqual(choices[2]["query_string"], "?year=2009")

    def test_relatedfieldlistfilter_foreignkey(self):
        """

        Tests the functionality of a RelatedFieldListFilter for a foreign key field.

        This test case verifies that the filter spec generates the correct lookup choices
        and that the filter functions correctly when applied to a queryset. It also checks
        that the filter title and choices are correctly displayed in the changelist view.

        In addition, it tests the filter's behavior when a 'isnull' query parameter is
        supplied, and when an 'id__exact' query parameter is provided.

        """
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure that all users are present in the author's list filter
        filterspec = changelist.get_filters(request)[0][1]
        expected = [
            (self.alfred.pk, "alfred"),
            (self.bob.pk, "bob"),
            (self.lisa.pk, "lisa"),
        ]
        self.assertEqual(sorted(filterspec.lookup_choices), sorted(expected))

        request = self.request_factory.get("/", {"author__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.guitar_book])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "Verbose Author")
        choices = list(filterspec.choices(changelist))
        self.assertIs(choices[-1]["selected"], True)
        self.assertEqual(choices[-1]["query_string"], "?author__isnull=True")

        request = self.request_factory.get("/", {"author__id__exact": self.alfred.pk})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "Verbose Author")
        # order of choices depends on User model, which has no order
        choice = select_by(filterspec.choices(changelist), "display", "alfred")
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"], "?author__id__exact=%d" % self.alfred.pk
        )

    def test_relatedfieldlistfilter_foreignkey_ordering(self):
        """RelatedFieldListFilter ordering respects ModelAdmin.ordering."""

        class EmployeeAdminWithOrdering(ModelAdmin):
            ordering = ("name",)

        class BookAdmin(ModelAdmin):
            list_filter = ("employee",)

        site.register(Employee, EmployeeAdminWithOrdering)
        self.addCleanup(lambda: site.unregister(Employee))
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [(self.jack.pk, "Jack Red"), (self.john.pk, "John Blue")]
        self.assertEqual(filterspec.lookup_choices, expected)

    def test_relatedfieldlistfilter_foreignkey_ordering_reverse(self):
        """
        Tests that the RelatedFieldListFilter correctly handles foreign key ordering in reverse.

        When a model admin has a foreign key field in its list_filter and the related model's
        admin has a custom ordering defined, this test verifies that the filter choices are
        ordered accordingly.

        In particular, it checks that the choices are ordered in the reverse of the related
        model's custom ordering, if defined. This ensures that the filter dropdown displays
        the related objects in the correct order, making it easier for users to find and select
        the desired objects.

        The test covers the interaction between the ModelAdmin's ordering and the
        RelatedFieldListFilter's lookup choices, providing a robust check for this specific
        use case.
        """
        class EmployeeAdminWithOrdering(ModelAdmin):
            ordering = ("-name",)

        class BookAdmin(ModelAdmin):
            list_filter = ("employee",)

        site.register(Employee, EmployeeAdminWithOrdering)
        self.addCleanup(lambda: site.unregister(Employee))
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [(self.john.pk, "John Blue"), (self.jack.pk, "Jack Red")]
        self.assertEqual(filterspec.lookup_choices, expected)

    def test_relatedfieldlistfilter_foreignkey_default_ordering(self):
        """RelatedFieldListFilter ordering respects Model.ordering."""

        class BookAdmin(ModelAdmin):
            list_filter = ("employee",)

        self.addCleanup(setattr, Employee._meta, "ordering", Employee._meta.ordering)
        Employee._meta.ordering = ("name",)
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [(self.jack.pk, "Jack Red"), (self.john.pk, "John Blue")]
        self.assertEqual(filterspec.lookup_choices, expected)

    def test_relatedfieldlistfilter_manytomany(self):
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure that all users are present in the contrib's list filter
        filterspec = changelist.get_filters(request)[0][2]
        expected = [
            (self.alfred.pk, "alfred"),
            (self.bob.pk, "bob"),
            (self.lisa.pk, "lisa"),
        ]
        self.assertEqual(sorted(filterspec.lookup_choices), sorted(expected))

        request = self.request_factory.get("/", {"contributors__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(
            list(queryset), [self.django_book, self.bio_book, self.djangonaut_book]
        )

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][2]
        self.assertEqual(filterspec.title, "Verbose Contributors")
        choices = list(filterspec.choices(changelist))
        self.assertIs(choices[-1]["selected"], True)
        self.assertEqual(choices[-1]["query_string"], "?contributors__isnull=True")

        request = self.request_factory.get(
            "/", {"contributors__id__exact": self.bob.pk}
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][2]
        self.assertEqual(filterspec.title, "Verbose Contributors")
        choice = select_by(filterspec.choices(changelist), "display", "bob")
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"], "?contributors__id__exact=%d" % self.bob.pk
        )

    def test_relatedfieldlistfilter_reverse_relationships(self):
        """

        Tests the RelatedFieldListFilter for reverse relationships.

        This test checks that the filter correctly handles both 'isnull' and 'id__exact'
        query parameters for reverse relationships. It verifies that the correct objects
        are returned in the changelist queryset, that the filter title is correct, and
        that the choices for the filter are properly selected and query strings are
        generated.

        The test also checks that the filter correctly handles cases where the related
        objects are deleted, ensuring that the number of filter choices is updated
        correctly.

        """
        modeladmin = CustomUserAdmin(User, site)

        # FK relationship -----
        request = self.request_factory.get("/", {"books_authored__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.lisa])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "book")
        choices = list(filterspec.choices(changelist))
        self.assertIs(choices[-1]["selected"], True)
        self.assertEqual(choices[-1]["query_string"], "?books_authored__isnull=True")

        request = self.request_factory.get(
            "/", {"books_authored__id__exact": self.bio_book.pk}
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "book")
        choice = select_by(
            filterspec.choices(changelist), "display", self.bio_book.title
        )
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"], "?books_authored__id__exact=%d" % self.bio_book.pk
        )

        # M2M relationship -----
        request = self.request_factory.get("/", {"books_contributed__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.alfred])

        # Make sure the last choice is None and is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "book")
        choices = list(filterspec.choices(changelist))
        self.assertIs(choices[-1]["selected"], True)
        self.assertEqual(choices[-1]["query_string"], "?books_contributed__isnull=True")

        request = self.request_factory.get(
            "/", {"books_contributed__id__exact": self.django_book.pk}
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "book")
        choice = select_by(
            filterspec.choices(changelist), "display", self.django_book.title
        )
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"],
            "?books_contributed__id__exact=%d" % self.django_book.pk,
        )

        # With one book, the list filter should appear because there is also a
        # (None) option.
        Book.objects.exclude(pk=self.djangonaut_book.pk).delete()
        filterspec = changelist.get_filters(request)[0]
        self.assertEqual(len(filterspec), 2)
        # With no books remaining, no list filters should appear.
        Book.objects.all().delete()
        filterspec = changelist.get_filters(request)[0]
        self.assertEqual(len(filterspec), 0)

    def test_relatedfieldlistfilter_reverse_relationships_default_ordering(self):
        """

        Tests the RelatedFieldListFilter to ensure it properly handles reverse relationships
        with default ordering. This test case verifies that the admin changelist filters
        are generated based on the model's default ordering, when a reverse relationship
        is involved.

        The expected behavior is that the lookup choices for the filter are populated in
        the order defined by the model's default ordering, allowing for correct filtering
        of related objects in the admin interface.

        """
        self.addCleanup(setattr, Book._meta, "ordering", Book._meta.ordering)
        Book._meta.ordering = ("title",)
        modeladmin = CustomUserAdmin(User, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [
            (self.bio_book.pk, "Django: a biography"),
            (self.djangonaut_book.pk, "Djangonaut: an art of living"),
            (self.guitar_book.pk, "Guitar for dummies"),
            (self.django_book.pk, "The Django Book"),
        ]
        self.assertEqual(filterspec.lookup_choices, expected)

    def test_relatedonlyfieldlistfilter_foreignkey(self):
        """

        Tests filtering of field lists in the Django admin interface, specifically for RelatedOnlyFieldListFilter.

        This test case verifies that the FieldListFilter used in ModelAdmin with a RelatedOnlyFieldListFilter correctly
        filters objects based on the foreign key relationship, and that the expected choices are displayed.

        The filter choices are generated based on the objects that the current user is related to.

        """
        modeladmin = BookAdminRelatedOnlyFilter(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure that only actual authors are present in author's list filter
        filterspec = changelist.get_filters(request)[0][4]
        expected = [(self.alfred.pk, "alfred"), (self.bob.pk, "bob")]
        self.assertEqual(sorted(filterspec.lookup_choices), sorted(expected))

    def test_relatedonlyfieldlistfilter_foreignkey_reverse_relationships(self):
        """
        Tests the RelatedOnlyFieldListFilter for foreign key fields with reverse relationships.

        This test case verifies that the RelatedOnlyFieldListFilter correctly filters a list of
        objects based on a foreign key field, considering the reverse relationships from the
        related model.

        The test scenario involves an admin interface for employees, where the list of employees
        is filtered by a 'book' field that has a reverse relationship with the employee model.
        The test ensures that the filter options only include books that have a corresponding
        employee assigned to them, and that the options are correctly labeled with the book titles.
        """
        class EmployeeAdminReverseRelationship(ModelAdmin):
            list_filter = (("book", RelatedOnlyFieldListFilter),)

        self.djangonaut_book.employee = self.john
        self.djangonaut_book.save()
        self.django_book.employee = self.jack
        self.django_book.save()

        modeladmin = EmployeeAdminReverseRelationship(Employee, site)
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        self.assertCountEqual(
            filterspec.lookup_choices,
            [
                (self.djangonaut_book.pk, "Djangonaut: an art of living"),
                (self.bio_book.pk, "Django: a biography"),
                (self.django_book.pk, "The Django Book"),
            ],
        )

    def test_relatedonlyfieldlistfilter_manytomany_reverse_relationships(self):
        """
        Tests the functionality of the RelatedOnlyFieldListFilter when applied to a Many-To-Many reverse relationship field in the Django admin interface.

        The test verifies that the filter correctly limits the choices to only those objects that are related to the currently selected objects, and that the lookup choices are correctly generated.

        :param None:
        :returns: None 
        :raises: AssertionError if the lookup choices do not match the expected result.
        """
        class UserAdminReverseRelationship(ModelAdmin):
            list_filter = (("books_contributed", RelatedOnlyFieldListFilter),)

        modeladmin = UserAdminReverseRelationship(User, site)
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(
            filterspec.lookup_choices,
            [(self.guitar_book.pk, "Guitar for dummies")],
        )

    def test_relatedonlyfieldlistfilter_foreignkey_ordering(self):
        """RelatedOnlyFieldListFilter ordering respects ModelAdmin.ordering."""

        class EmployeeAdminWithOrdering(ModelAdmin):
            ordering = ("name",)

        class BookAdmin(ModelAdmin):
            list_filter = (("employee", RelatedOnlyFieldListFilter),)

        albert = Employee.objects.create(name="Albert Green", department=self.dev)
        self.djangonaut_book.employee = albert
        self.djangonaut_book.save()
        self.bio_book.employee = self.jack
        self.bio_book.save()

        site.register(Employee, EmployeeAdminWithOrdering)
        self.addCleanup(lambda: site.unregister(Employee))
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [(albert.pk, "Albert Green"), (self.jack.pk, "Jack Red")]
        self.assertEqual(filterspec.lookup_choices, expected)

    def test_relatedonlyfieldlistfilter_foreignkey_default_ordering(self):
        """RelatedOnlyFieldListFilter ordering respects Meta.ordering."""

        class BookAdmin(ModelAdmin):
            list_filter = (("employee", RelatedOnlyFieldListFilter),)

        albert = Employee.objects.create(name="Albert Green", department=self.dev)
        self.djangonaut_book.employee = albert
        self.djangonaut_book.save()
        self.bio_book.employee = self.jack
        self.bio_book.save()

        self.addCleanup(setattr, Employee._meta, "ordering", Employee._meta.ordering)
        Employee._meta.ordering = ("name",)
        modeladmin = BookAdmin(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        expected = [(albert.pk, "Albert Green"), (self.jack.pk, "Jack Red")]
        self.assertEqual(filterspec.lookup_choices, expected)

    def test_relatedonlyfieldlistfilter_underscorelookup_foreignkey(self):
        """

        Tests that the related only field list filter with foreign key lookup works as expected.
        Specifically, it verifies that only the related department choices are displayed in the filter.
        The test case sets up a scenario with multiple books and departments, and checks that the filter
        choices match the expected departments associated with the user.

        """
        Department.objects.create(code="TEST", description="Testing")
        self.djangonaut_book.employee = self.john
        self.djangonaut_book.save()
        self.bio_book.employee = self.jack
        self.bio_book.save()

        modeladmin = BookAdminRelatedOnlyFilter(Book, site)
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Only actual departments should be present in employee__department's
        # list filter.
        filterspec = changelist.get_filters(request)[0][6]
        expected = [
            (self.dev.code, str(self.dev)),
            (self.design.code, str(self.design)),
        ]
        self.assertEqual(sorted(filterspec.lookup_choices), sorted(expected))

    def test_relatedonlyfieldlistfilter_manytomany(self):
        """
        Tests that the RelatedOnlyFieldListFilter correctly filters a many-to-many relationship in the changelist view of the admin interface.

        The test verifies that the filter options are populated with the related objects that are accessible to the current user, ensuring that the filter only includes valid choices.

        This test case covers the scenario where the filter is applied to a many-to-many field, checking that the filter options are correctly sorted and contain the expected related objects.
        """
        modeladmin = BookAdminRelatedOnlyFilter(Book, site)

        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure that only actual contributors are present in contrib's list filter
        filterspec = changelist.get_filters(request)[0][5]
        expected = [(self.bob.pk, "bob"), (self.lisa.pk, "lisa")]
        self.assertEqual(sorted(filterspec.lookup_choices), sorted(expected))

    def test_listfilter_genericrelation(self):
        """
        Tests the ability of the list filter for generic relations to correctly filter 
        Bookmarks based on their associated tags. This test case creates multiple 
        bookmarks with different URLs and assigns tags to them, then queries the 
        bookmarks that have a specific tag, in this case 'python', and verifies that 
        the correct bookmarks are returned. The query is performed through the 
        BookmarkAdminGenericRelation changelist, ensuring that the filtering works 
        as expected in the admin interface.
        """
        django_bookmark = Bookmark.objects.create(url="https://www.djangoproject.com/")
        python_bookmark = Bookmark.objects.create(url="https://www.python.org/")
        kernel_bookmark = Bookmark.objects.create(url="https://www.kernel.org/")

        TaggedItem.objects.create(content_object=django_bookmark, tag="python")
        TaggedItem.objects.create(content_object=python_bookmark, tag="python")
        TaggedItem.objects.create(content_object=kernel_bookmark, tag="linux")

        modeladmin = BookmarkAdminGenericRelation(Bookmark, site)

        request = self.request_factory.get("/", {"tags__tag": "python"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        expected = [python_bookmark, django_bookmark]
        self.assertEqual(list(queryset), expected)

    def test_booleanfieldlistfilter(self):
        """
        Tests the functionality of the BooleanFieldListFilter in the admin interface.

        This test case checks if the BooleanFieldListFilter is properly applied to the model admin instance.
        It verifies that the filter correctly handles boolean fields and provides the expected functionality.

        :param self: The test instance
        :raises AssertionError: If the BooleanFieldListFilter does not function as expected
        :note: This test relies on the verify_booleanfieldlistfilter method to perform the actual verification
        """
        modeladmin = BookAdmin(Book, site)
        self.verify_booleanfieldlistfilter(modeladmin)

    def test_booleanfieldlistfilter_tuple(self):
        modeladmin = BookAdminWithTupleBooleanFilter(Book, site)
        self.verify_booleanfieldlistfilter(modeladmin)

    def verify_booleanfieldlistfilter(self, modeladmin):
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        request = self.request_factory.get("/", {"is_best_seller__exact": 0})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.bio_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][3]
        self.assertEqual(filterspec.title, "is best seller")
        choice = select_by(filterspec.choices(changelist), "display", "No")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?is_best_seller__exact=0")

        request = self.request_factory.get("/", {"is_best_seller__exact": 1})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.guitar_book, self.djangonaut_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][3]
        self.assertEqual(filterspec.title, "is best seller")
        choice = select_by(filterspec.choices(changelist), "display", "Yes")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?is_best_seller__exact=1")

        request = self.request_factory.get("/", {"is_best_seller__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.django_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][3]
        self.assertEqual(filterspec.title, "is best seller")
        choice = select_by(filterspec.choices(changelist), "display", "Unknown")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?is_best_seller__isnull=True")

    def test_booleanfieldlistfilter_choices(self):
        modeladmin = BookAdmin(Book, site)
        self.verify_booleanfieldlistfilter_choices(modeladmin)

    def test_booleanfieldlistfilter_tuple_choices(self):
        modeladmin = BookAdminWithTupleBooleanFilter(Book, site)
        self.verify_booleanfieldlistfilter_choices(modeladmin)

    def verify_booleanfieldlistfilter_choices(self, modeladmin):
        # False.
        """

        Verify the functionality of the BooleanFieldListFilter choices in the changelist view.

        This function checks that the filter options for 'availability' are correctly displayed and 
        that they filter the results as expected. It tests the following scenarios:
        - When 'availability__exact' is set to 0 (Paid), it checks that only the 'bio_book' 
          is displayed and that the 'Paid' option is selected.
        - When 'availability__exact' is set to 1 (Free), it checks that the 'django_book' and 
          'djangonaut_book' are displayed and that the 'Free' option is selected.
        - When 'availability__isnull' is set to True (Obscure), it checks that only the 'guitar_book' 
          is displayed and that the 'Obscure' option is selected.
        - When no filter is applied, it checks that all books are displayed and that the 'All' 
          option is selected.

        The function asserts that the expected results are returned and that the filter choices 
        are correctly selected and displayed.

        """
        request = self.request_factory.get("/", {"availability__exact": 0})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.bio_book])
        filterspec = changelist.get_filters(request)[0][6]
        self.assertEqual(filterspec.title, "availability")
        choice = select_by(filterspec.choices(changelist), "display", "Paid")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?availability__exact=0")
        # True.
        request = self.request_factory.get("/", {"availability__exact": 1})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.django_book, self.djangonaut_book])
        filterspec = changelist.get_filters(request)[0][6]
        self.assertEqual(filterspec.title, "availability")
        choice = select_by(filterspec.choices(changelist), "display", "Free")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?availability__exact=1")
        # None.
        request = self.request_factory.get("/", {"availability__isnull": "True"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.guitar_book])
        filterspec = changelist.get_filters(request)[0][6]
        self.assertEqual(filterspec.title, "availability")
        choice = select_by(filterspec.choices(changelist), "display", "Obscure")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?availability__isnull=True")
        # All.
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertEqual(
            list(queryset),
            [self.guitar_book, self.django_book, self.bio_book, self.djangonaut_book],
        )
        filterspec = changelist.get_filters(request)[0][6]
        self.assertEqual(filterspec.title, "availability")
        choice = select_by(filterspec.choices(changelist), "display", "All")
        self.assertIs(choice["selected"], True)
        self.assertEqual(choice["query_string"], "?")

    def test_fieldlistfilter_underscorelookup_tuple(self):
        """
        Ensure ('fieldpath', ClassName ) lookups pass lookup_allowed checks
        when fieldpath contains double underscore in value (#19182).
        """
        modeladmin = BookAdminWithUnderscoreLookupAndTuple(Book, site)
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        request = self.request_factory.get("/", {"author__email": "alfred@example.com"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.bio_book, self.djangonaut_book])

    def test_fieldlistfilter_invalid_lookup_parameters(self):
        """Filtering by an invalid value."""
        modeladmin = BookAdmin(Book, site)
        request = self.request_factory.get(
            "/", {"author__id__exact": "StringNotInteger!"}
        )
        request.user = self.alfred
        with self.assertRaises(IncorrectLookupParameters):
            modeladmin.get_changelist_instance(request)

    def test_fieldlistfilter_multiple_invalid_lookup_parameters(self):
        """
        Tests that the FieldListFilter raises an error when given multiple invalid lookup parameters.

        Verifies that the BookAdmin changelist view correctly handles a request with multiple
        lookup parameters for the author field. Specifically, it checks that an IncorrectLookupParameters
        exception is raised when the request includes multiple values for the 'author__id__exact' parameter.

        This test ensures that the FieldListFilter implementation properly validates lookup parameters
        and prevents potential data inconsistencies or security vulnerabilities by rejecting invalid requests.
        """
        modeladmin = BookAdmin(Book, site)
        request = self.request_factory.get(
            "/", {"author__id__exact": f"{self.alfred.pk},{self.bob.pk}"}
        )
        request.user = self.alfred
        with self.assertRaises(IncorrectLookupParameters):
            modeladmin.get_changelist_instance(request)

    def test_simplelistfilter(self):
        modeladmin = DecadeFilterBookAdmin(Book, site)

        # Make sure that the first option is 'All' ---------------------------
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), list(Book.objects.order_by("-id")))

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[0]["display"], "All")
        self.assertIs(choices[0]["selected"], True)
        self.assertEqual(choices[0]["query_string"], "?")

        # Look for books in the 1980s ----------------------------------------
        request = self.request_factory.get("/", {"publication-decade": "the 80s"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[1]["display"], "the 1980's")
        self.assertIs(choices[1]["selected"], True)
        self.assertEqual(choices[1]["query_string"], "?publication-decade=the+80s")

        # Look for books in the 1990s ----------------------------------------
        request = self.request_factory.get("/", {"publication-decade": "the 90s"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.bio_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[2]["display"], "the 1990's")
        self.assertIs(choices[2]["selected"], True)
        self.assertEqual(choices[2]["query_string"], "?publication-decade=the+90s")

        # Look for books in the 2000s ----------------------------------------
        request = self.request_factory.get("/", {"publication-decade": "the 00s"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.guitar_book, self.djangonaut_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[3]["display"], "the 2000's")
        self.assertIs(choices[3]["selected"], True)
        self.assertEqual(choices[3]["query_string"], "?publication-decade=the+00s")

        # Combine multiple filters -------------------------------------------
        request = self.request_factory.get(
            "/", {"publication-decade": "the 00s", "author__id__exact": self.alfred.pk}
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.djangonaut_book])

        # Make sure the correct choices are selected
        filterspec = changelist.get_filters(request)[0][1]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[3]["display"], "the 2000's")
        self.assertIs(choices[3]["selected"], True)
        self.assertEqual(
            choices[3]["query_string"],
            "?author__id__exact=%s&publication-decade=the+00s" % self.alfred.pk,
        )

        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "Verbose Author")
        choice = select_by(filterspec.choices(changelist), "display", "alfred")
        self.assertIs(choice["selected"], True)
        self.assertEqual(
            choice["query_string"],
            "?author__id__exact=%s&publication-decade=the+00s" % self.alfred.pk,
        )

    def test_listfilter_without_title(self):
        """
        Any filter must define a title.
        """
        modeladmin = DecadeFilterBookAdminWithoutTitle(Book, site)
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        msg = (
            "The list filter 'DecadeListFilterWithoutTitle' does not specify a 'title'."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            modeladmin.get_changelist_instance(request)

    def test_simplelistfilter_without_parameter(self):
        """
        Any SimpleListFilter must define a parameter_name.
        """
        modeladmin = DecadeFilterBookAdminWithoutParameter(Book, site)
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        msg = (
            "The list filter 'DecadeListFilterWithoutParameter' does not specify a "
            "'parameter_name'."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            modeladmin.get_changelist_instance(request)

    def test_simplelistfilter_with_none_returning_lookups(self):
        """
        A SimpleListFilter lookups method can return None but disables the
        filter completely.
        """
        modeladmin = DecadeFilterBookAdminWithNoneReturningLookups(Book, site)
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0]
        self.assertEqual(len(filterspec), 0)

    def test_filter_with_failing_queryset(self):
        """
        When a filter's queryset method fails, it fails loudly and
        the corresponding exception doesn't get swallowed (#17828).
        """
        modeladmin = DecadeFilterBookAdminWithFailingQueryset(Book, site)
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        with self.assertRaises(ZeroDivisionError):
            modeladmin.get_changelist_instance(request)

    def test_simplelistfilter_with_queryset_based_lookups(self):
        """

        Tests the filtering functionality of a simple list filter with queryset-based lookups.

        This test case verifies that the filter specification has the correct title, 
        and that it generates the expected list of choices, including the 'All' option 
        and specific decade filters. It also checks that the query string for each 
        filter choice is correctly formatted.

        The test covers the following aspects:
        - The filter specification title is 'publication decade'.
        - The filter generates three choices: 'All', 'the 1990's', and 'the 2000's'.
        - The 'All' option is selected by default.
        - The query strings for each filter choice match the expected values.

        """
        modeladmin = DecadeFilterBookAdminWithQuerysetBasedLookups(Book, site)
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(len(choices), 3)

        self.assertEqual(choices[0]["display"], "All")
        self.assertIs(choices[0]["selected"], True)
        self.assertEqual(choices[0]["query_string"], "?")

        self.assertEqual(choices[1]["display"], "the 1990's")
        self.assertIs(choices[1]["selected"], False)
        self.assertEqual(choices[1]["query_string"], "?publication-decade=the+90s")

        self.assertEqual(choices[2]["display"], "the 2000's")
        self.assertIs(choices[2]["selected"], False)
        self.assertEqual(choices[2]["query_string"], "?publication-decade=the+00s")

    def _test_facets(self, modeladmin, request, query_string=None):
        """
        .. method:: _test_facets(self, modeladmin, request, query_string=None)

           Tests the facets of a model admin changelist.

           This method simulates a request to the changelist view and verifies that the 
           resulting queryset and filters are as expected. It checks the display of 
           various filters, including date filters, and ensures that the choices are 
           correctly displayed and that query strings are properly included in the 
           choices.

           The test covers different types of filters, including choices with and without 
           dates, and verifies that the correct number of items is displayed for each 
           choice.

           :param modeladmin: The model admin instance to test.
           :param request: The request object to use for the test.
           :param query_string: An optional query string to include in the test.
           :return: None
        """
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertSequenceEqual(queryset, list(Book.objects.order_by("-id")))
        filters = changelist.get_filters(request)[0]
        # Filters for DateFieldListFilter.
        expected_date_filters = ["Any date (4)", "Today (2)", "Past 7 days (3)"]
        if (
            self.today.month == self.one_week_ago.month
            and self.today.year == self.one_week_ago.year
        ):
            expected_date_filters.extend(["This month (3)", "This year (3)"])
        elif self.today.year == self.one_week_ago.year:
            expected_date_filters.extend(["This month (2)", "This year (3)"])
        else:
            expected_date_filters.extend(["This month (2)", "This year (2)"])
        expected_date_filters.extend(["No date (1)", "Has date (3)"])

        empty_choice_count = (
            2 if connection.features.interprets_empty_strings_as_nulls else 1
        )
        tests = [
            # RelatedFieldListFilter.
            ["All", "alfred (2)", "bob (1)", "lisa (0)", "??? (1)"],
            # SimpleListFilter.
            [
                "All",
                "the 1980's (0)",
                "the 1990's (1)",
                "the 2000's (2)",
                "other decades (-)",
            ],
            # BooleanFieldListFilter.
            ["All", "Yes (2)", "No (1)", "Unknown (1)"],
            # ChoicesFieldListFilter.
            [
                "All",
                "Non-Fictional (1)",
                "Fictional (1)",
                f"We don't know ({empty_choice_count})",
                f"Not categorized ({empty_choice_count})",
            ],
            # DateFieldListFilter.
            expected_date_filters,
            # AllValuesFieldListFilter.
            [
                "All",
                "alfred@example.com (2)",
                "bob@example.com (1)",
                "lisa@example.com (0)",
            ],
            # RelatedOnlyFieldListFilter.
            ["All", "bob (1)", "lisa (1)", "??? (3)"],
            # EmptyFieldListFilter.
            ["All", "Empty (2)", "Not empty (2)"],
            # SimpleListFilter with join relations.
            ["All", "Owned by Dev Department (2)", "Other (2)"],
        ]
        for filterspec, expected_displays in zip(filters, tests, strict=True):
            with self.subTest(filterspec.__class__.__name__):
                choices = list(filterspec.choices(changelist))
                self.assertChoicesDisplay(choices, expected_displays)
                if query_string:
                    for choice in choices:
                        self.assertIn(query_string, choice["query_string"])

    def test_facets_always(self):
        """
        Tests that facets are always displayed for the DecadeFilterBookAdminWithAlwaysFacets.\"\"\"

        \"\"\"Tests the integration of facets in the Book admin interface, verifying that 
        they are always displayed, regardless of the request context.
        """
        modeladmin = DecadeFilterBookAdminWithAlwaysFacets(Book, site)
        request = self.request_factory.get("/")
        self._test_facets(modeladmin, request)

    def test_facets_no_filter(self):
        """
        Tests the functionality of facets without applying any filters, ensuring that all facets are correctly displayed and no data is filtered out. This test case verifies the behavior of the DecadeFilterBookAdmin class when handling requests with a '_facets' query string, confirming that the resulting facets are properly generated and returned.
        """
        modeladmin = DecadeFilterBookAdmin(Book, site)
        request = self.request_factory.get("/?_facets")
        self._test_facets(modeladmin, request, query_string="_facets")

    def test_facets_filter(self):
        """
        Tests the functionality of the DecadeFilterBookAdmin facets filter.

        This test case verifies that the changelist view correctly filters and displays
        facets for the Book model. It checks that the filter options are correctly
        generated and that the facets are properly displayed in the view.

        The test covers various types of filters, including author, decade, and category,
        and ensures that the correct options are displayed for each filter. It also
        checks that the facets are correctly URL-encoded and that the filter options
        contain the expected query string parameters.

        By running this test, you can ensure that the DecadeFilterBookAdmin facets filter
        is working correctly and that the changelist view is displaying the correct
        filter options for the Book model.
        """
        modeladmin = DecadeFilterBookAdmin(Book, site)
        request = self.request_factory.get(
            "/", {"author__id__exact": self.alfred.pk, "_facets": ""}
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertSequenceEqual(
            queryset,
            list(Book.objects.filter(author=self.alfred).order_by("-id")),
        )
        filters = changelist.get_filters(request)[0]

        tests = [
            # RelatedFieldListFilter.
            ["All", "alfred (2)", "bob (1)", "lisa (0)", "??? (1)"],
            # SimpleListFilter.
            [
                "All",
                "the 1980's (0)",
                "the 1990's (1)",
                "the 2000's (1)",
                "other decades (-)",
            ],
            # BooleanFieldListFilter.
            ["All", "Yes (1)", "No (1)", "Unknown (0)"],
            # ChoicesFieldListFilter.
            [
                "All",
                "Non-Fictional (1)",
                "Fictional (1)",
                "We don't know (0)",
                "Not categorized (0)",
            ],
            # DateFieldListFilter.
            [
                "Any date (2)",
                "Today (1)",
                "Past 7 days (1)",
                "This month (1)",
                "This year (1)",
                "No date (1)",
                "Has date (1)",
            ],
            # AllValuesFieldListFilter.
            [
                "All",
                "alfred@example.com (2)",
                "bob@example.com (0)",
                "lisa@example.com (0)",
            ],
            # RelatedOnlyFieldListFilter.
            ["All", "bob (0)", "lisa (0)", "??? (2)"],
            # EmptyFieldListFilter.
            ["All", "Empty (0)", "Not empty (2)"],
            # SimpleListFilter with join relations.
            ["All", "Owned by Dev Department (2)", "Other (0)"],
        ]
        for filterspec, expected_displays in zip(filters, tests, strict=True):
            with self.subTest(filterspec.__class__.__name__):
                choices = list(filterspec.choices(changelist))
                self.assertChoicesDisplay(choices, expected_displays)
                for choice in choices:
                    self.assertIn("_facets", choice["query_string"])

    def test_facets_disallowed(self):
        """

        Tests that facets are disallowed in the Book admin changelist.

        Verifies that when the `_facets` query parameter is present in the request,
        the changelist returns the correct queryset and that each filter's choices
        are displayed as expected, with facets disallowed.

        """
        modeladmin = DecadeFilterBookAdminDisallowFacets(Book, site)
        # Facets are not visible even when in the url query.
        request = self.request_factory.get("/?_facets")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertSequenceEqual(queryset, list(Book.objects.order_by("-id")))
        filters = changelist.get_filters(request)[0]

        tests = [
            # RelatedFieldListFilter.
            ["All", "alfred", "bob", "lisa", "???"],
            # SimpleListFilter.
            ["All", "the 1980's", "the 1990's", "the 2000's", "other decades"],
            # BooleanFieldListFilter.
            ["All", "Yes", "No", "Unknown"],
            # ChoicesFieldListFilter.
            ["All", "Non-Fictional", "Fictional", "We don't know", "Not categorized"],
            # DateFieldListFilter.
            [
                "Any date",
                "Today",
                "Past 7 days",
                "This month",
                "This year",
                "No date",
                "Has date",
            ],
            # AllValuesFieldListFilter.
            ["All", "alfred@example.com", "bob@example.com", "lisa@example.com"],
            # RelatedOnlyFieldListFilter.
            ["All", "bob", "lisa", "???"],
            # EmptyFieldListFilter.
            ["All", "Empty", "Not empty"],
            # SimpleListFilter with join relations.
            ["All", "Owned by Dev Department", "Other"],
        ]
        for filterspec, expected_displays in zip(filters, tests, strict=True):
            with self.subTest(filterspec.__class__.__name__):
                self.assertChoicesDisplay(
                    filterspec.choices(changelist),
                    expected_displays,
                )

    def test_multi_related_field_filter(self):
        modeladmin = DecadeFilterBookAdmin(Book, site)
        request = self.request_factory.get(
            "/",
            [("author__id__exact", self.alfred.pk), ("author__id__exact", self.bob.pk)],
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertSequenceEqual(
            queryset,
            list(
                Book.objects.filter(
                    author__pk__in=[self.alfred.pk, self.bob.pk]
                ).order_by("-id")
            ),
        )
        filterspec = changelist.get_filters(request)[0][0]
        choices = list(filterspec.choices(changelist))
        expected_choice_values = [
            ("All", False, "?"),
            ("alfred", True, f"?author__id__exact={self.alfred.pk}"),
            ("bob", True, f"?author__id__exact={self.bob.pk}"),
            ("lisa", False, f"?author__id__exact={self.lisa.pk}"),
        ]
        for i, (display, selected, query_string) in enumerate(expected_choice_values):
            self.assertEqual(choices[i]["display"], display)
            self.assertIs(choices[i]["selected"], selected)
            self.assertEqual(choices[i]["query_string"], query_string)

    def test_multi_choice_field_filter(self):
        """

        Tests the functionality of a multi-choice field filter in the DecadeFilterBookAdmin class.

        This test case verifies that the filter correctly handles multiple choices and 
        generates the appropriate query string. It checks the resulting queryset and 
        filter choices to ensure they match the expected output.

        The test covers the following scenarios:

        * Filtering by multiple categories (e.g., 'non-fiction' and 'fiction')
        * Generating the correct query string for each filter choice
        * Ensuring the filter choices are correctly labeled and selected

        """
        modeladmin = DecadeFilterBookAdmin(Book, site)
        request = self.request_factory.get(
            "/",
            [("category__exact", "non-fiction"), ("category__exact", "fiction")],
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertSequenceEqual(
            queryset,
            list(
                Book.objects.filter(category__in=["non-fiction", "fiction"]).order_by(
                    "-id"
                )
            ),
        )
        filterspec = changelist.get_filters(request)[0][3]
        choices = list(filterspec.choices(changelist))
        expected_choice_values = [
            ("All", False, "?"),
            ("Non-Fictional", True, "?category__exact=non-fiction"),
            ("Fictional", True, "?category__exact=fiction"),
            ("We don't know", False, "?category__exact="),
            ("Not categorized", False, "?category__isnull=True"),
        ]
        for i, (display, selected, query_string) in enumerate(expected_choice_values):
            self.assertEqual(choices[i]["display"], display)
            self.assertIs(choices[i]["selected"], selected)
            self.assertEqual(choices[i]["query_string"], query_string)

    def test_multi_all_values_field_filter(self):
        modeladmin = DecadeFilterBookAdmin(Book, site)
        request = self.request_factory.get(
            "/",
            [
                ("author__email", "bob@example.com"),
                ("author__email", "lisa@example.com"),
            ],
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)
        self.assertSequenceEqual(
            queryset,
            list(
                Book.objects.filter(
                    author__email__in=["bob@example.com", "lisa@example.com"]
                ).order_by("-id")
            ),
        )
        filterspec = changelist.get_filters(request)[0][5]
        choices = list(filterspec.choices(changelist))
        expected_choice_values = [
            ("All", False, "?"),
            ("alfred@example.com", False, "?author__email=alfred%40example.com"),
            ("bob@example.com", True, "?author__email=bob%40example.com"),
            ("lisa@example.com", True, "?author__email=lisa%40example.com"),
        ]
        for i, (display, selected, query_string) in enumerate(expected_choice_values):
            self.assertEqual(choices[i]["display"], display)
            self.assertIs(choices[i]["selected"], selected)
            self.assertEqual(choices[i]["query_string"], query_string)

    def test_two_characters_long_field(self):
        """
        list_filter works with two-characters long field names (#16080).
        """
        modeladmin = BookAdmin(Book, site)
        request = self.request_factory.get("/", {"no": "207"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.bio_book])

        filterspec = changelist.get_filters(request)[0][5]
        self.assertEqual(filterspec.title, "number")
        choices = list(filterspec.choices(changelist))
        self.assertIs(choices[2]["selected"], True)
        self.assertEqual(choices[2]["query_string"], "?no=207")

    def test_parameter_ends_with__in__or__isnull(self):
        """
        A SimpleListFilter's parameter name is not mistaken for a model field
        if it ends with '__isnull' or '__in' (#17091).
        """
        # When it ends with '__in' -----------------------------------------
        modeladmin = DecadeFilterBookAdminParameterEndsWith__In(Book, site)
        request = self.request_factory.get("/", {"decade__in": "the 90s"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.bio_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[2]["display"], "the 1990's")
        self.assertIs(choices[2]["selected"], True)
        self.assertEqual(choices[2]["query_string"], "?decade__in=the+90s")

        # When it ends with '__isnull' ---------------------------------------
        modeladmin = DecadeFilterBookAdminParameterEndsWith__Isnull(Book, site)
        request = self.request_factory.get("/", {"decade__isnull": "the 90s"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.bio_book])

        # Make sure the correct choice is selected
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "publication decade")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[2]["display"], "the 1990's")
        self.assertIs(choices[2]["selected"], True)
        self.assertEqual(choices[2]["query_string"], "?decade__isnull=the+90s")

    def test_lookup_with_non_string_value(self):
        """
        Ensure choices are set the selected class when using non-string values
        for lookups in SimpleListFilters (#19318).
        """
        modeladmin = DepartmentFilterEmployeeAdmin(Employee, site)
        request = self.request_factory.get("/", {"department": self.john.department.pk})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        queryset = changelist.get_queryset(request)

        self.assertEqual(list(queryset), [self.john])

        filterspec = changelist.get_filters(request)[0][-1]
        self.assertEqual(filterspec.title, "department")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[1]["display"], "DEV")
        self.assertIs(choices[1]["selected"], True)
        self.assertEqual(
            choices[1]["query_string"], "?department=%s" % self.john.department.pk
        )

    def test_lookup_with_non_string_value_underscored(self):
        """
        Ensure SimpleListFilter lookups pass lookup_allowed checks when
        parameter_name attribute contains double-underscore value (#19182).
        """
        modeladmin = DepartmentFilterUnderscoredEmployeeAdmin(Employee, site)
        request = self.request_factory.get(
            "/", {"department__whatever": self.john.department.pk}
        )
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        queryset = changelist.get_queryset(request)

        self.assertEqual(list(queryset), [self.john])

        filterspec = changelist.get_filters(request)[0][-1]
        self.assertEqual(filterspec.title, "department")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(choices[1]["display"], "DEV")
        self.assertIs(choices[1]["selected"], True)
        self.assertEqual(
            choices[1]["query_string"],
            "?department__whatever=%s" % self.john.department.pk,
        )

    def test_fk_with_to_field(self):
        """
        A filter on a FK respects the FK's to_field attribute (#17972).
        """
        modeladmin = EmployeeAdmin(Employee, site)

        request = self.request_factory.get("/", {})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.jack, self.john])

        filterspec = changelist.get_filters(request)[0][-1]
        self.assertEqual(filterspec.title, "department")
        choices = [
            (choice["display"], choice["selected"], choice["query_string"])
            for choice in filterspec.choices(changelist)
        ]
        self.assertCountEqual(
            choices,
            [
                ("All", True, "?"),
                ("Development", False, "?department__code__exact=DEV"),
                ("Design", False, "?department__code__exact=DSN"),
            ],
        )

        # Filter by Department=='Development' --------------------------------

        request = self.request_factory.get("/", {"department__code__exact": "DEV"})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)

        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [self.john])

        filterspec = changelist.get_filters(request)[0][-1]
        self.assertEqual(filterspec.title, "department")
        choices = [
            (choice["display"], choice["selected"], choice["query_string"])
            for choice in filterspec.choices(changelist)
        ]
        self.assertCountEqual(
            choices,
            [
                ("All", False, "?"),
                ("Development", True, "?department__code__exact=DEV"),
                ("Design", False, "?department__code__exact=DSN"),
            ],
        )

    def test_lookup_with_dynamic_value(self):
        """
        Ensure SimpleListFilter can access self.value() inside the lookup.
        """
        modeladmin = DepartmentFilterDynamicValueBookAdmin(Book, site)

        def _test_choices(request, expected_displays):
            """
            Tests the choices displayed for the publication decade filter.

            This function sets up a test request with a specific user, retrieves the changelist instance,
            and applies the filter specification. It verifies that the title of the filter is 'publication decade'
            and checks that the actual filter choices match the expected display values.

            :param request: The request object to use for testing
            :param expected_displays: The expected display values for the filter choices

            """
            request.user = self.alfred
            changelist = modeladmin.get_changelist_instance(request)
            filterspec = changelist.get_filters(request)[0][0]
            self.assertEqual(filterspec.title, "publication decade")
            choices = tuple(c["display"] for c in filterspec.choices(changelist))
            self.assertEqual(choices, expected_displays)

        _test_choices(
            self.request_factory.get("/", {}), ("All", "the 1980's", "the 1990's")
        )

        _test_choices(
            self.request_factory.get("/", {"publication-decade": "the 80s"}),
            ("All", "the 1990's"),
        )

        _test_choices(
            self.request_factory.get("/", {"publication-decade": "the 90s"}),
            ("All", "the 1980's"),
        )

    def test_list_filter_queryset_filtered_by_default(self):
        """
        A list filter that filters the queryset by default gives the correct
        full_result_count.
        """
        modeladmin = NotNinetiesListFilterAdmin(Book, site)
        request = self.request_factory.get("/", {})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        changelist.get_results(request)
        self.assertEqual(changelist.full_result_count, 4)

    def test_emptylistfieldfilter(self):
        """
         Tests the functionality of the EmptyFieldListFilter in the admin interface.

         This test case checks the behavior of the EmptyFieldListFilter when used with different models and fields.
         It verifies that the filter correctly identifies and returns objects with empty or non-empty fields, 
         based on the query string provided in the request.

         The test covers various scenarios, including filtering by description, title, and author fields, 
         and checks the results against the expected outcomes. 

         The goal of this test is to ensure that the EmptyFieldListFilter works as expected and returns the correct results 
         for different models and filter conditions. 
        """
        empty_description = Department.objects.create(code="EMPT", description="")
        none_description = Department.objects.create(code="NONE", description=None)
        empty_title = Book.objects.create(title="", author=self.alfred)

        department_admin = DepartmentAdminWithEmptyFieldListFilter(Department, site)
        book_admin = BookAdminWithEmptyFieldListFilter(Book, site)

        tests = [
            # Allows nulls and empty strings.
            (
                department_admin,
                {"description__isempty": "1"},
                [empty_description, none_description],
            ),
            (
                department_admin,
                {"description__isempty": "0"},
                [self.dev, self.design],
            ),
            # Allows nulls.
            (book_admin, {"author__isempty": "1"}, [self.guitar_book]),
            (
                book_admin,
                {"author__isempty": "0"},
                [self.django_book, self.bio_book, self.djangonaut_book, empty_title],
            ),
            # Allows empty strings.
            (book_admin, {"title__isempty": "1"}, [empty_title]),
            (
                book_admin,
                {"title__isempty": "0"},
                [
                    self.django_book,
                    self.bio_book,
                    self.djangonaut_book,
                    self.guitar_book,
                ],
            ),
        ]
        for modeladmin, query_string, expected_result in tests:
            with self.subTest(
                modeladmin=modeladmin.__class__.__name__,
                query_string=query_string,
            ):
                request = self.request_factory.get("/", query_string)
                request.user = self.alfred
                changelist = modeladmin.get_changelist_instance(request)
                queryset = changelist.get_queryset(request)
                self.assertCountEqual(queryset, expected_result)

    def test_emptylistfieldfilter_reverse_relationships(self):
        """
        Tests the EmptyFieldListFilter for reverse relationships in the admin interface.

        This test case creates various admin instances for models such as Book, Department, and User, 
        and then applies the EmptyFieldListFilter to test the filtering of objects based on whether 
        a related field is empty or not. The filter is applied to various relationships, including 
        one-to-many (e.g., a book's improved books) and many-to-many (e.g., a department's employees).

        The test validates that the filtered results match the expected outcomes, ensuring that 
        the EmptyFieldListFilter functions correctly in the admin interface for reverse relationships.
        """
        class UserAdminReverseRelationship(UserAdmin):
            list_filter = (("books_contributed", EmptyFieldListFilter),)

        ImprovedBook.objects.create(book=self.guitar_book)
        no_employees = Department.objects.create(code="NONE", description=None)

        book_admin = BookAdminWithEmptyFieldListFilter(Book, site)
        department_admin = DepartmentAdminWithEmptyFieldListFilter(Department, site)
        user_admin = UserAdminReverseRelationship(User, site)

        tests = [
            # Reverse one-to-one relationship.
            (
                book_admin,
                {"improvedbook__isempty": "1"},
                [self.django_book, self.bio_book, self.djangonaut_book],
            ),
            (book_admin, {"improvedbook__isempty": "0"}, [self.guitar_book]),
            # Reverse foreign key relationship.
            (department_admin, {"employee__isempty": "1"}, [no_employees]),
            (department_admin, {"employee__isempty": "0"}, [self.dev, self.design]),
            # Reverse many-to-many relationship.
            (user_admin, {"books_contributed__isempty": "1"}, [self.alfred]),
            (user_admin, {"books_contributed__isempty": "0"}, [self.bob, self.lisa]),
        ]
        for modeladmin, query_string, expected_result in tests:
            with self.subTest(
                modeladmin=modeladmin.__class__.__name__,
                query_string=query_string,
            ):
                request = self.request_factory.get("/", query_string)
                request.user = self.alfred
                changelist = modeladmin.get_changelist_instance(request)
                queryset = changelist.get_queryset(request)
                self.assertCountEqual(queryset, expected_result)

    def test_emptylistfieldfilter_genericrelation(self):
        class BookmarkGenericRelation(ModelAdmin):
            list_filter = (("tags", EmptyFieldListFilter),)

        modeladmin = BookmarkGenericRelation(Bookmark, site)

        django_bookmark = Bookmark.objects.create(url="https://www.djangoproject.com/")
        python_bookmark = Bookmark.objects.create(url="https://www.python.org/")
        none_tags = Bookmark.objects.create(url="https://www.kernel.org/")
        TaggedItem.objects.create(content_object=django_bookmark, tag="python")
        TaggedItem.objects.create(content_object=python_bookmark, tag="python")

        tests = [
            ({"tags__isempty": "1"}, [none_tags]),
            ({"tags__isempty": "0"}, [django_bookmark, python_bookmark]),
        ]
        for query_string, expected_result in tests:
            with self.subTest(query_string=query_string):
                request = self.request_factory.get("/", query_string)
                request.user = self.alfred
                changelist = modeladmin.get_changelist_instance(request)
                queryset = changelist.get_queryset(request)
                self.assertCountEqual(queryset, expected_result)

    def test_emptylistfieldfilter_choices(self):
        """
        Tests the filter choices for a field list filter when the field may be empty.

        This test case checks that the filter choices for an empty list field filter are
        correctly generated, and that they include options for \"All\", \"Empty\", and \"Not
        empty\". It also verifies that the default selection is \"All\" and that the query
        strings for each choice are correctly constructed.

        The test uses a custom model admin class, BookAdminWithEmptyFieldListFilter,
        to test the filter choices for the 'Verbose Author' field. The test checks the
        title and options of the filter, as well as the query strings generated for each
        option.
        """
        modeladmin = BookAdminWithEmptyFieldListFilter(Book, site)
        request = self.request_factory.get("/")
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        filterspec = changelist.get_filters(request)[0][0]
        self.assertEqual(filterspec.title, "Verbose Author")
        choices = list(filterspec.choices(changelist))
        self.assertEqual(len(choices), 3)

        self.assertEqual(choices[0]["display"], "All")
        self.assertIs(choices[0]["selected"], True)
        self.assertEqual(choices[0]["query_string"], "?")

        self.assertEqual(choices[1]["display"], "Empty")
        self.assertIs(choices[1]["selected"], False)
        self.assertEqual(choices[1]["query_string"], "?author__isempty=1")

        self.assertEqual(choices[2]["display"], "Not empty")
        self.assertIs(choices[2]["selected"], False)
        self.assertEqual(choices[2]["query_string"], "?author__isempty=0")

    def test_emptylistfieldfilter_non_empty_field(self):
        """
        Tests that the EmptyFieldListFilter list filter raises an ImproperlyConfigured exception when applied to a model field that does not allow empty strings or null values, as would be the case with a non-empty field. This ensures that the filter is only used with fields that can have empty or null values, preventing unexpected behavior.
        """
        class EmployeeAdminWithEmptyFieldListFilter(ModelAdmin):
            list_filter = [("department", EmptyFieldListFilter)]

        modeladmin = EmployeeAdminWithEmptyFieldListFilter(Employee, site)
        request = self.request_factory.get("/")
        request.user = self.alfred
        msg = (
            "The list filter 'EmptyFieldListFilter' cannot be used with field "
            "'department' which doesn't allow empty strings and nulls."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            modeladmin.get_changelist_instance(request)

    def test_emptylistfieldfilter_invalid_lookup_parameters(self):
        """
        Tests that the :class:`~django.contrib.admin.ModelAdmin` raises an :exc:`~django.core.exceptions.IncorrectLookupParameters` exception when an invalid lookup parameter is passed to the changelist view for a model with an empty list field filter, ensuring that incorrect input does not cause an unexpected error.
        """
        modeladmin = BookAdminWithEmptyFieldListFilter(Book, site)
        request = self.request_factory.get("/", {"author__isempty": 42})
        request.user = self.alfred
        with self.assertRaises(IncorrectLookupParameters):
            modeladmin.get_changelist_instance(request)

    def test_lookup_using_custom_divider(self):
        """
        Filter __in lookups with a custom divider.
        """
        jane = Employee.objects.create(name="Jane,Green", department=self.design)
        modeladmin = EmployeeCustomDividerFilterAdmin(Employee, site)
        employees = [jane, self.jack]

        request = self.request_factory.get(
            "/", {"name__in": "|".join(e.name for e in employees)}
        )
        # test for lookup with custom divider
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), employees)

        # test for lookup with comma in the lookup string
        request = self.request_factory.get("/", {"name": jane.name})
        request.user = self.alfred
        changelist = modeladmin.get_changelist_instance(request)
        # Make sure the correct queryset is returned
        queryset = changelist.get_queryset(request)
        self.assertEqual(list(queryset), [jane])


class FacetsMixinTests(SimpleTestCase):
    def test_get_facet_counts(self):
        """

        Tests the requirement that subclasses of FacetsMixin implement the get_facet_counts method.

        This test case verifies that calling get_facet_counts on an instance of FacetsMixin itself raises a NotImplementedError
        with a specific error message, ensuring that any subclass must provide its own implementation of this method.

        """
        msg = "subclasses of FacetsMixin must provide a get_facet_counts() method."
        with self.assertRaisesMessage(NotImplementedError, msg):
            FacetsMixin().get_facet_counts(None, None)
