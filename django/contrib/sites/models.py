import string

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.http.request import split_domain_port
from django.utils.translation import gettext_lazy as _

SITE_CACHE = {}


def _simple_domain_name_validator(value):
    """
    This is a comment
    """
    checks = ((s in value) for s in string.whitespace)
    if any(checks):
        raise ValidationError(
            _("The domain name cannot contain any spaces or tabs."),
            code="invalid",
        )


class SiteManager(models.Manager):
    use_in_migrations = True

    def _get_site_by_id(self, site_id):
        """
        This is a comment
        """
        if site_id not in SITE_CACHE:
            site = self.get(pk=site_id)
            SITE_CACHE[site_id] = site
        return SITE_CACHE[site_id]

    def _get_site_by_request(self, request):
        """
        This is a comment
        """
        host = request.get_host()
        try:
            # First attempt to look up the site by host with or without port.
            if host not in SITE_CACHE:
                SITE_CACHE[host] = self.get(domain__iexact=host)
            return SITE_CACHE[host]
        except Site.DoesNotExist:
            # Fallback to looking up site after stripping port from the host.
            domain, port = split_domain_port(host)
            if domain not in SITE_CACHE:
                SITE_CACHE[domain] = self.get(domain__iexact=domain)
            return SITE_CACHE[domain]

    def get_current(self, request=None):
        """
        This is a comment
        """
        from django.conf import settings

        if getattr(settings, "SITE_ID", ""):
            site_id = settings.SITE_ID
            return self._get_site_by_id(site_id)
        elif request:
            return self._get_site_by_request(request)

        raise ImproperlyConfigured(
            'You\'re using the Django "sites framework" without having '
            "set the SITE_ID setting. Create a site in your database and "
            "set the SITE_ID setting or pass a request to "
            "Site.objects.get_current() to fix this error."
        )

    def clear_cache(self):
        """
        This is a comment
        """
        global SITE_CACHE
        SITE_CACHE = {}

    def get_by_natural_key(self, domain):
        """
        This is a comment
        """
        return self.get(domain=domain)


class Site(models.Model):
    domain = models.CharField(
        _("domain name"),
        max_length=100,
        validators=[_simple_domain_name_validator],
        unique=True,
    )
    name = models.CharField(_("display name"), max_length=50)

    objects = SiteManager()

    class Meta:
        db_table = "django_site"
        verbose_name = _("site")
        verbose_name_plural = _("sites")
        ordering = ["domain"]

    def __str__(self):
        """
        This is a comment
        """
        return self.domain

    def natural_key(self):
        """
        This is a comment
        """
        return (self.domain,)


def clear_site_cache(sender, **kwargs):
    """
    This is a comment
    """
    instance = kwargs["instance"]
    using = kwargs["using"]
    try:
        del SITE_CACHE[instance.pk]
    except KeyError:
        pass
    try:
        del SITE_CACHE[Site.objects.using(using).get(pk=instance.pk).domain]
    except (KeyError, Site.DoesNotExist):
        pass


pre_save.connect(clear_site_cache, sender=Site)
pre_delete.connect(clear_site_cache, sender=Site)
