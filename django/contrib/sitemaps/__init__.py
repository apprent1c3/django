from django.apps import apps as django_apps
from django.conf import settings
from django.core import paginator
from django.core.exceptions import ImproperlyConfigured
from django.utils import translation


class Sitemap:
    # This limit is defined by Google. See the index documentation at
    # https://www.sitemaps.org/protocol.html#index.
    limit = 50000

    # If protocol is None, the URLs in the sitemap will use the protocol
    # with which the sitemap was requested.
    protocol = None

    # Enables generating URLs for all languages.
    i18n = False

    # Override list of languages to use.
    languages = None

    # Enables generating alternate/hreflang links.
    alternates = False

    # Add an alternate/hreflang link with value 'x-default'.
    x_default = False

    def _get(self, name, item, default=None):
        """
        Retrieves an attribute from the object by name, optionally invoking it if it's callable.

        :param name: The name of the attribute to retrieve.
        :param item: The item to pass to the attribute if it's callable.
        :param default: The value to return if the attribute does not exist (defaults to None).

        :returns: The attribute value, the result of invoking the attribute if it's callable, or the default value if not found. 
        """
        try:
            attr = getattr(self, name)
        except AttributeError:
            return default
        if callable(attr):
            if self.i18n:
                # Split the (item, lang_code) tuples again for the location,
                # priority, lastmod and changefreq method calls.
                item, lang_code = item
            return attr(item)
        return attr

    def get_languages_for_item(self, item):
        """Languages for which this item is displayed."""
        return self._languages()

    def _languages(self):
        if self.languages is not None:
            return self.languages
        return [lang_code for lang_code, _ in settings.LANGUAGES]

    def _items(self):
        if self.i18n:
            # Create (item, lang_code) tuples for all items and languages.
            # This is necessary to paginate with all languages already considered.
            items = [
                (item, lang_code)
                for item in self.items()
                for lang_code in self.get_languages_for_item(item)
            ]
            return items
        return self.items()

    def _location(self, item, force_lang_code=None):
        """

        Return the location for the given item.

        If internationalization (i18n) is enabled, the location is retrieved in the context of the item's language code or a specified force language code.

        :param item: The item for which to retrieve the location
        :param force_lang_code: Optional language code to override the item's language code
        :return: The location for the given item

        """
        if self.i18n:
            obj, lang_code = item
            # Activate language from item-tuple or forced one before calling location.
            with translation.override(force_lang_code or lang_code):
                return self._get("location", item)
        return self._get("location", item)

    @property
    def paginator(self):
        return paginator.Paginator(self._items(), self.limit)

    def items(self):
        return []

    def location(self, item):
        return item.get_absolute_url()

    def get_protocol(self, protocol=None):
        # Determine protocol
        return self.protocol or protocol or "https"

    def get_domain(self, site=None):
        # Determine domain
        """
        Return the domain associated with the current site.

        If a site is provided, its domain is returned. Otherwise, the function attempts
        to retrieve the current site using the Django sites framework, raising an error
        if it is not installed or no site is configured.
        """
        if site is None:
            if django_apps.is_installed("django.contrib.sites"):
                Site = django_apps.get_model("sites.Site")
                try:
                    site = Site.objects.get_current()
                except Site.DoesNotExist:
                    pass
            if site is None:
                raise ImproperlyConfigured(
                    "To use sitemaps, either enable the sites framework or pass "
                    "a Site/RequestSite object in your view."
                )
        return site.domain

    def get_urls(self, page=1, site=None, protocol=None):
        protocol = self.get_protocol(protocol)
        domain = self.get_domain(site)
        return self._urls(page, protocol, domain)

    def get_latest_lastmod(self):
        """
        Returns the latest 'last modified' timestamp, either by calling the `lastmod` method on each item in `self.items()` and returning the maximum, or directly returning the `lastmod` attribute if it is not callable.
        """
        if not hasattr(self, "lastmod"):
            return None
        if callable(self.lastmod):
            try:
                return max([self.lastmod(item) for item in self.items()], default=None)
            except TypeError:
                return None
        else:
            return self.lastmod

    def _urls(self, page, protocol, domain):
        """
        Generates a list of URLs with their metadata for the specified page, 
        including location, last modification date, change frequency, and priority.
        Supports internationalization (i18n) and alternative language URLs.
        """
        urls = []
        latest_lastmod = None
        all_items_lastmod = True  # track if all items have a lastmod

        paginator_page = self.paginator.page(page)
        for item in paginator_page.object_list:
            loc = f"{protocol}://{domain}{self._location(item)}"
            priority = self._get("priority", item)
            lastmod = self._get("lastmod", item)

            if all_items_lastmod:
                all_items_lastmod = lastmod is not None
                if all_items_lastmod and (
                    latest_lastmod is None or lastmod > latest_lastmod
                ):
                    latest_lastmod = lastmod

            url_info = {
                "item": item,
                "location": loc,
                "lastmod": lastmod,
                "changefreq": self._get("changefreq", item),
                "priority": str(priority if priority is not None else ""),
                "alternates": [],
            }

            if self.i18n and self.alternates:
                item_languages = self.get_languages_for_item(item[0])
                for lang_code in item_languages:
                    loc = f"{protocol}://{domain}{self._location(item, lang_code)}"
                    url_info["alternates"].append(
                        {
                            "location": loc,
                            "lang_code": lang_code,
                        }
                    )
                if self.x_default and settings.LANGUAGE_CODE in item_languages:
                    lang_code = settings.LANGUAGE_CODE
                    loc = f"{protocol}://{domain}{self._location(item, lang_code)}"
                    loc = loc.replace(f"/{lang_code}/", "/", 1)
                    url_info["alternates"].append(
                        {
                            "location": loc,
                            "lang_code": "x-default",
                        }
                    )

            urls.append(url_info)

        if all_items_lastmod and latest_lastmod:
            self.latest_lastmod = latest_lastmod

        return urls


class GenericSitemap(Sitemap):
    priority = None
    changefreq = None

    def __init__(self, info_dict, priority=None, changefreq=None, protocol=None):
        """
        Initializes a sitemap configuration object with provided metadata.

        :param info_dict: Dictionary containing required sitemap information, including the queryset.
        :param priority: Optional priority value for the sitemap entries (overrides the default).
        :param changefreq: Optional change frequency value for the sitemap entries (overrides the default).
        :param protocol: Optional protocol value for the sitemap entries (overrides the default).
        """
        self.queryset = info_dict["queryset"]
        self.date_field = info_dict.get("date_field")
        self.priority = self.priority or priority
        self.changefreq = self.changefreq or changefreq
        self.protocol = self.protocol or protocol

    def items(self):
        # Make sure to return a clone; we don't want premature evaluation.
        return self.queryset.filter()

    def lastmod(self, item):
        if self.date_field is not None:
            return getattr(item, self.date_field)
        return None

    def get_latest_lastmod(self):
        if self.date_field is not None:
            return (
                self.queryset.order_by("-" + self.date_field)
                .values_list(self.date_field, flat=True)
                .first()
            )
        return None
