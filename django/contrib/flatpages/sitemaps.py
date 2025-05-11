from django.apps import apps as django_apps
from django.contrib.sitemaps import Sitemap
from django.core.exceptions import ImproperlyConfigured


class FlatPageSitemap(Sitemap):
    def items(self):
        """
        Returns a list of flat pages for the current site that do not require registration.

        This function is used to generate a sitemap and requires the 'django.contrib.sites' app to be installed.

        :raises ImproperlyConfigured: If 'django.contrib.sites' is not installed
        :returns: A queryset of flat pages

        """
        if not django_apps.is_installed("django.contrib.sites"):
            raise ImproperlyConfigured(
                "FlatPageSitemap requires django.contrib.sites, which isn't installed."
            )
        Site = django_apps.get_model("sites.Site")
        current_site = Site.objects.get_current()
        return current_site.flatpage_set.filter(registration_required=False)
