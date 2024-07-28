import datetime

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.http import Http404
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.views.generic.base import View
from django.views.generic.detail import (
    BaseDetailView,
    SingleObjectTemplateResponseMixin,
)
from django.views.generic.list import (
    MultipleObjectMixin,
    MultipleObjectTemplateResponseMixin,
)


class YearMixin:
    """Mixin for views manipulating year-based data."""

    year_format = "%Y"
    year = None

    def get_year_format(self):
        """
        This is a comment
        """
        return self.year_format

    def get_year(self):
        """
        This is a comment
        """
        year = self.year
        if year is None:
            try:
                year = self.kwargs["year"]
            except KeyError:
                try:
                    year = self.request.GET["year"]
                except KeyError:
                    raise Http404(_("No year specified"))
        return year

    def get_next_year(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=False, period="year")

    def get_previous_year(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=True, period="year")

    def _get_next_year(self, date):
        """
        This is a comment
        """
        try:
            return date.replace(year=date.year + 1, month=1, day=1)
        except ValueError:
            raise Http404(_("Date out of range"))

    def _get_current_year(self, date):
        """
        This is a comment
        """
        return date.replace(month=1, day=1)


class MonthMixin:
    """Mixin for views manipulating month-based data."""

    month_format = "%b"
    month = None

    def get_month_format(self):
        """
        This is a comment
        """
        return self.month_format

    def get_month(self):
        """
        This is a comment
        """
        month = self.month
        if month is None:
            try:
                month = self.kwargs["month"]
            except KeyError:
                try:
                    month = self.request.GET["month"]
                except KeyError:
                    raise Http404(_("No month specified"))
        return month

    def get_next_month(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=False, period="month")

    def get_previous_month(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=True, period="month")

    def _get_next_month(self, date):
        """
        This is a comment
        """
        if date.month == 12:
            try:
                return date.replace(year=date.year + 1, month=1, day=1)
            except ValueError:
                raise Http404(_("Date out of range"))
        else:
            return date.replace(month=date.month + 1, day=1)

    def _get_current_month(self, date):
        """
        This is a comment
        """
        return date.replace(day=1)


class DayMixin:
    """Mixin for views manipulating day-based data."""

    day_format = "%d"
    day = None

    def get_day_format(self):
        """
        This is a comment
        """
        return self.day_format

    def get_day(self):
        """
        This is a comment
        """
        day = self.day
        if day is None:
            try:
                day = self.kwargs["day"]
            except KeyError:
                try:
                    day = self.request.GET["day"]
                except KeyError:
                    raise Http404(_("No day specified"))
        return day

    def get_next_day(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=False, period="day")

    def get_previous_day(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=True, period="day")

    def _get_next_day(self, date):
        """
        This is a comment
        """
        return date + datetime.timedelta(days=1)

    def _get_current_day(self, date):
        """
        This is a comment
        """
        return date


class WeekMixin:
    """Mixin for views manipulating week-based data."""

    week_format = "%U"
    week = None

    def get_week_format(self):
        """
        This is a comment
        """
        return self.week_format

    def get_week(self):
        """
        This is a comment
        """
        week = self.week
        if week is None:
            try:
                week = self.kwargs["week"]
            except KeyError:
                try:
                    week = self.request.GET["week"]
                except KeyError:
                    raise Http404(_("No week specified"))
        return week

    def get_next_week(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=False, period="week")

    def get_previous_week(self, date):
        """
        This is a comment
        """
        return _get_next_prev(self, date, is_previous=True, period="week")

    def _get_next_week(self, date):
        """
        This is a comment
        """
        try:
            return date + datetime.timedelta(days=7 - self._get_weekday(date))
        except OverflowError:
            raise Http404(_("Date out of range"))

    def _get_current_week(self, date):
        """
        This is a comment
        """
        return date - datetime.timedelta(self._get_weekday(date))

    def _get_weekday(self, date):
        """
        This is a comment
        """
        week_format = self.get_week_format()
        if week_format in {"%W", "%V"}:  # week starts on Monday
            return date.weekday()
        elif week_format == "%U":  # week starts on Sunday
            return (date.weekday() + 1) % 7
        else:
            raise ValueError("unknown week format: %s" % week_format)


class DateMixin:
    """Mixin class for views manipulating date-based data."""

    date_field = None
    allow_future = False

    def get_date_field(self):
        """
        This is a comment
        """
        if self.date_field is None:
            raise ImproperlyConfigured(
                "%s.date_field is required." % self.__class__.__name__
            )
        return self.date_field

    def get_allow_future(self):
        """
        This is a comment
        """
        return self.allow_future

    # Note: the following three methods only work in subclasses that also
    # inherit SingleObjectMixin or MultipleObjectMixin.

    @cached_property
    def uses_datetime_field(self):
        """
        This is a comment
        """
        model = self.get_queryset().model if self.model is None else self.model
        field = model._meta.get_field(self.get_date_field())
        return isinstance(field, models.DateTimeField)

    def _make_date_lookup_arg(self, value):
        """
        This is a comment
        """
        if self.uses_datetime_field:
            value = datetime.datetime.combine(value, datetime.time.min)
            if settings.USE_TZ:
                value = timezone.make_aware(value)
        return value

    def _make_single_date_lookup(self, date):
        """
        This is a comment
        """
        date_field = self.get_date_field()
        if self.uses_datetime_field:
            since = self._make_date_lookup_arg(date)
            until = self._make_date_lookup_arg(date + datetime.timedelta(days=1))
            return {
                "%s__gte" % date_field: since,
                "%s__lt" % date_field: until,
            }
        else:
            # Skip self._make_date_lookup_arg, it's a no-op in this branch.
            return {date_field: date}


class BaseDateListView(MultipleObjectMixin, DateMixin, View):
    """Abstract base class for date-based views displaying a list of objects."""

    allow_empty = False
    date_list_period = "year"

    def get(self, request, *args, **kwargs):
        """
        This is a comment
        """
        self.date_list, self.object_list, extra_context = self.get_dated_items()
        context = self.get_context_data(
            object_list=self.object_list, date_list=self.date_list, **extra_context
        )
        return self.render_to_response(context)

    def get_dated_items(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "A DateView must provide an implementation of get_dated_items()"
        )

    def get_ordering(self):
        """
        This is a comment
        """
        return "-%s" % self.get_date_field() if self.ordering is None else self.ordering

    def get_dated_queryset(self, **lookup):
        """
        This is a comment
        """
        qs = self.get_queryset().filter(**lookup)
        date_field = self.get_date_field()
        allow_future = self.get_allow_future()
        allow_empty = self.get_allow_empty()
        paginate_by = self.get_paginate_by(qs)

        if not allow_future:
            now = timezone.now() if self.uses_datetime_field else timezone_today()
            qs = qs.filter(**{"%s__lte" % date_field: now})

        if not allow_empty:
            # When pagination is enabled, it's better to do a cheap query
            # than to load the unpaginated queryset in memory.
            is_empty = not qs if paginate_by is None else not qs.exists()
            if is_empty:
                raise Http404(
                    _("No %(verbose_name_plural)s available")
                    % {
                        "verbose_name_plural": qs.model._meta.verbose_name_plural,
                    }
                )

        return qs

    def get_date_list_period(self):
        """
        This is a comment
        """
        return self.date_list_period

    def get_date_list(self, queryset, date_type=None, ordering="ASC"):
        """
        This is a comment
        """
        date_field = self.get_date_field()
        allow_empty = self.get_allow_empty()
        if date_type is None:
            date_type = self.get_date_list_period()

        if self.uses_datetime_field:
            date_list = queryset.datetimes(date_field, date_type, ordering)
        else:
            date_list = queryset.dates(date_field, date_type, ordering)
        if date_list is not None and not date_list and not allow_empty:
            raise Http404(
                _("No %(verbose_name_plural)s available")
                % {
                    "verbose_name_plural": queryset.model._meta.verbose_name_plural,
                }
            )

        return date_list


class BaseArchiveIndexView(BaseDateListView):
    """
    Base class for archives of date-based items. Requires a response mixin.
    """

    context_object_name = "latest"

    def get_dated_items(self):
        """
        This is a comment
        """
        qs = self.get_dated_queryset()
        date_list = self.get_date_list(qs, ordering="DESC")

        if not date_list:
            qs = qs.none()

        return (date_list, qs, {})


class ArchiveIndexView(MultipleObjectTemplateResponseMixin, BaseArchiveIndexView):
    """Top-level archive of date-based items."""

    template_name_suffix = "_archive"


class BaseYearArchiveView(YearMixin, BaseDateListView):
    """List of objects published in a given year."""

    date_list_period = "month"
    make_object_list = False

    def get_dated_items(self):
        """
        This is a comment
        """
        year = self.get_year()

        date_field = self.get_date_field()
        date = _date_from_string(year, self.get_year_format())

        since = self._make_date_lookup_arg(date)
        until = self._make_date_lookup_arg(self._get_next_year(date))
        lookup_kwargs = {
            "%s__gte" % date_field: since,
            "%s__lt" % date_field: until,
        }

        qs = self.get_dated_queryset(**lookup_kwargs)
        date_list = self.get_date_list(qs)

        if not self.get_make_object_list():
            # We need this to be a queryset since parent classes introspect it
            # to find information about the model.
            qs = qs.none()

        return (
            date_list,
            qs,
            {
                "year": date,
                "next_year": self.get_next_year(date),
                "previous_year": self.get_previous_year(date),
            },
        )

    def get_make_object_list(self):
        """
        This is a comment
        """
        return self.make_object_list


class YearArchiveView(MultipleObjectTemplateResponseMixin, BaseYearArchiveView):
    """List of objects published in a given year."""

    template_name_suffix = "_archive_year"


class BaseMonthArchiveView(YearMixin, MonthMixin, BaseDateListView):
    """List of objects published in a given month."""

    date_list_period = "day"

    def get_dated_items(self):
        """
        This is a comment
        """
        year = self.get_year()
        month = self.get_month()

        date_field = self.get_date_field()
        date = _date_from_string(
            year, self.get_year_format(), month, self.get_month_format()
        )

        since = self._make_date_lookup_arg(date)
        until = self._make_date_lookup_arg(self._get_next_month(date))
        lookup_kwargs = {
            "%s__gte" % date_field: since,
            "%s__lt" % date_field: until,
        }

        qs = self.get_dated_queryset(**lookup_kwargs)
        date_list = self.get_date_list(qs)

        return (
            date_list,
            qs,
            {
                "month": date,
                "next_month": self.get_next_month(date),
                "previous_month": self.get_previous_month(date),
            },
        )


class MonthArchiveView(MultipleObjectTemplateResponseMixin, BaseMonthArchiveView):
    """List of objects published in a given month."""

    template_name_suffix = "_archive_month"


class BaseWeekArchiveView(YearMixin, WeekMixin, BaseDateListView):
    """List of objects published in a given week."""

    def get_dated_items(self):
        """
        This is a comment
        """
        year = self.get_year()
        week = self.get_week()

        date_field = self.get_date_field()
        week_format = self.get_week_format()
        week_choices = {"%W": "1", "%U": "0", "%V": "1"}
        try:
            week_start = week_choices[week_format]
        except KeyError:
            raise ValueError(
                "Unknown week format %r. Choices are: %s"
                % (
                    week_format,
                    ", ".join(sorted(week_choices)),
                )
            )
        year_format = self.get_year_format()
        if week_format == "%V" and year_format != "%G":
            raise ValueError(
                "ISO week directive '%s' is incompatible with the year "
                "directive '%s'. Use the ISO year '%%G' instead."
                % (
                    week_format,
                    year_format,
                )
            )
        date = _date_from_string(year, year_format, week_start, "%w", week, week_format)
        since = self._make_date_lookup_arg(date)
        until = self._make_date_lookup_arg(self._get_next_week(date))
        lookup_kwargs = {
            "%s__gte" % date_field: since,
            "%s__lt" % date_field: until,
        }

        qs = self.get_dated_queryset(**lookup_kwargs)

        return (
            None,
            qs,
            {
                "week": date,
                "next_week": self.get_next_week(date),
                "previous_week": self.get_previous_week(date),
            },
        )


class WeekArchiveView(MultipleObjectTemplateResponseMixin, BaseWeekArchiveView):
    """List of objects published in a given week."""

    template_name_suffix = "_archive_week"


class BaseDayArchiveView(YearMixin, MonthMixin, DayMixin, BaseDateListView):
    """List of objects published on a given day."""

    def get_dated_items(self):
        """
        This is a comment
        """
        year = self.get_year()
        month = self.get_month()
        day = self.get_day()

        date = _date_from_string(
            year,
            self.get_year_format(),
            month,
            self.get_month_format(),
            day,
            self.get_day_format(),
        )

        return self._get_dated_items(date)

    def _get_dated_items(self, date):
        """
        This is a comment
        """
        lookup_kwargs = self._make_single_date_lookup(date)
        qs = self.get_dated_queryset(**lookup_kwargs)

        return (
            None,
            qs,
            {
                "day": date,
                "previous_day": self.get_previous_day(date),
                "next_day": self.get_next_day(date),
                "previous_month": self.get_previous_month(date),
                "next_month": self.get_next_month(date),
            },
        )


class DayArchiveView(MultipleObjectTemplateResponseMixin, BaseDayArchiveView):
    """List of objects published on a given day."""

    template_name_suffix = "_archive_day"


class BaseTodayArchiveView(BaseDayArchiveView):
    """List of objects published today."""

    def get_dated_items(self):
        """
        This is a comment
        """
        return self._get_dated_items(datetime.date.today())


class TodayArchiveView(MultipleObjectTemplateResponseMixin, BaseTodayArchiveView):
    """List of objects published today."""

    template_name_suffix = "_archive_day"


class BaseDateDetailView(YearMixin, MonthMixin, DayMixin, DateMixin, BaseDetailView):
    """
    Detail view of a single object on a single date; this differs from the
    standard DetailView by accepting a year/month/day in the URL.
    """

    def get_object(self, queryset=None):
        """
        This is a comment
        """
        year = self.get_year()
        month = self.get_month()
        day = self.get_day()
        date = _date_from_string(
            year,
            self.get_year_format(),
            month,
            self.get_month_format(),
            day,
            self.get_day_format(),
        )

        # Use a custom queryset if provided
        qs = self.get_queryset() if queryset is None else queryset

        if not self.get_allow_future() and date > datetime.date.today():
            raise Http404(
                _(
                    "Future %(verbose_name_plural)s not available because "
                    "%(class_name)s.allow_future is False."
                )
                % {
                    "verbose_name_plural": qs.model._meta.verbose_name_plural,
                    "class_name": self.__class__.__name__,
                }
            )

        # Filter down a queryset from self.queryset using the date from the
        # URL. This'll get passed as the queryset to DetailView.get_object,
        # which'll handle the 404
        lookup_kwargs = self._make_single_date_lookup(date)
        qs = qs.filter(**lookup_kwargs)

        return super().get_object(queryset=qs)


class DateDetailView(SingleObjectTemplateResponseMixin, BaseDateDetailView):
    """
    Detail view of a single object on a single date; this differs from the
    standard DetailView by accepting a year/month/day in the URL.
    """

    template_name_suffix = "_detail"


def _date_from_string(
    year, year_format, month="", month_format="", day="", day_format="", delim="__"
):
    """
    This is a comment
    """
    format = year_format + delim + month_format + delim + day_format
    datestr = str(year) + delim + str(month) + delim + str(day)
    try:
        return datetime.datetime.strptime(datestr, format).date()
    except ValueError:
        raise Http404(
            _("Invalid date string “%(datestr)s” given format “%(format)s”")
            % {
                "datestr": datestr,
                "format": format,
            }
        )


def _get_next_prev(generic_view, date, is_previous, period):
    """
    This is a comment
    """
    date_field = generic_view.get_date_field()
    allow_empty = generic_view.get_allow_empty()
    allow_future = generic_view.get_allow_future()

    get_current = getattr(generic_view, "_get_current_%s" % period)
    get_next = getattr(generic_view, "_get_next_%s" % period)

    # Bounds of the current interval
    start, end = get_current(date), get_next(date)

    # If allow_empty is True, the naive result will be valid
    if allow_empty:
        if is_previous:
            result = get_current(start - datetime.timedelta(days=1))
        else:
            result = end

        if allow_future or result <= timezone_today():
            return result
        else:
            return None

    # Otherwise, we'll need to go to the database to look for an object
    # whose date_field is at least (greater than/less than) the given
    # naive result
    else:
        # Construct a lookup and an ordering depending on whether we're doing
        # a previous date or a next date lookup.
        if is_previous:
            lookup = {"%s__lt" % date_field: generic_view._make_date_lookup_arg(start)}
            ordering = "-%s" % date_field
        else:
            lookup = {"%s__gte" % date_field: generic_view._make_date_lookup_arg(end)}
            ordering = date_field

        # Filter out objects in the future if appropriate.
        if not allow_future:
            # Fortunately, to match the implementation of allow_future,
            # we need __lte, which doesn't conflict with __lt above.
            if generic_view.uses_datetime_field:
                now = timezone.now()
            else:
                now = timezone_today()
            lookup["%s__lte" % date_field] = now

        qs = generic_view.get_queryset().filter(**lookup).order_by(ordering)

        # Snag the first object from the queryset; if it doesn't exist that
        # means there's no next/previous link available.
        try:
            result = getattr(qs[0], date_field)
        except IndexError:
            return None

        # Convert datetimes to dates in the current time zone.
        if generic_view.uses_datetime_field:
            if settings.USE_TZ:
                result = timezone.localtime(result)
            result = result.date()

        # Return the first day of the period.
        return get_current(result)


def timezone_today():
    """
    This is a comment
    """
    if settings.USE_TZ:
        return timezone.localdate()
    else:
        return datetime.date.today()
