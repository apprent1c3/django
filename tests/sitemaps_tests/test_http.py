import os
from datetime import date

from django.contrib.sitemaps import Sitemap
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.test import modify_settings, override_settings
from django.utils import translation
from django.utils.formats import localize

from .base import SitemapTestsBase
from .models import I18nTestModel, TestModel


class HTTPSitemapTests(SitemapTestsBase):
    use_sitemap_err_msg = (
        "To use sitemaps, either enable the sites framework or pass a "
        "Site/RequestSite object in your view."
    )

    def test_simple_sitemap_index(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/index.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>%s/simple/sitemap-simple.xml</loc><lastmod>%s</lastmod></sitemap>
</sitemapindex>
""" % (
            self.base_url,
            date.today(),
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_sitemap_not_callable(self):
        """
        This is a comment
        """
        response = self.client.get("/simple-not-callable/index.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>%s/simple/sitemap-simple.xml</loc><lastmod>%s</lastmod></sitemap>
</sitemapindex>
""" % (
            self.base_url,
            date.today(),
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_paged_sitemap(self):
        """
        This is a comment
        """
        response = self.client.get("/simple-paged/index.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>{0}/simple/sitemap-simple.xml</loc><lastmod>{1}</lastmod></sitemap><sitemap><loc>{0}/simple/sitemap-simple.xml?p=2</loc><lastmod>{1}</lastmod></sitemap>
</sitemapindex>
""".format(
            self.base_url, date.today()
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [os.path.join(os.path.dirname(__file__), "templates")],
            }
        ]
    )
    def test_simple_sitemap_custom_lastmod_index(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/custom-lastmod-index.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<!-- This is a customised template -->
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>%s/simple/sitemap-simple.xml</loc><lastmod>%s</lastmod></sitemap>
</sitemapindex>
""" % (
            self.base_url,
            date.today(),
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_simple_sitemap_section(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/sitemap-simple.xml")
        expected_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "<url><loc>%s/location/</loc><lastmod>%s</lastmod>"
            "<changefreq>never</changefreq><priority>0.5</priority></url>\n"
            "</urlset>"
        ) % (
            self.base_url,
            date.today(),
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_no_section(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/sitemap-simple2.xml")
        self.assertEqual(
            str(response.context["exception"]),
            "No sitemap available for section: 'simple2'",
        )
        self.assertEqual(response.status_code, 404)

    def test_empty_page(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/sitemap-simple.xml?p=0")
        self.assertEqual(str(response.context["exception"]), "Page 0 empty")
        self.assertEqual(response.status_code, 404)

    def test_page_not_int(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/sitemap-simple.xml?p=test")
        self.assertEqual(str(response.context["exception"]), "No page 'test'")
        self.assertEqual(response.status_code, 404)

    def test_simple_sitemap(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/sitemap.xml")
        expected_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "<url><loc>%s/location/</loc><lastmod>%s</lastmod>"
            "<changefreq>never</changefreq><priority>0.5</priority></url>\n"
            "</urlset>"
        ) % (
            self.base_url,
            date.today(),
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [os.path.join(os.path.dirname(__file__), "templates")],
            }
        ]
    )
    def test_simple_custom_sitemap(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/custom-sitemap.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<!-- This is a customised template -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>%s/location/</loc><lastmod>%s</lastmod><changefreq>never</changefreq><priority>0.5</priority></url>
</urlset>
""" % (
            self.base_url,
            date.today(),
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_sitemap_last_modified(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod/sitemap.xml")
        self.assertEqual(
            response.headers["Last-Modified"], "Wed, 13 Mar 2013 10:00:00 GMT"
        )

    def test_sitemap_last_modified_date(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod/date-sitemap.xml")
        self.assertEqual(
            response.headers["Last-Modified"], "Wed, 13 Mar 2013 00:00:00 GMT"
        )

    def test_sitemap_last_modified_tz(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod/tz-sitemap.xml")
        self.assertEqual(
            response.headers["Last-Modified"], "Wed, 13 Mar 2013 15:00:00 GMT"
        )

    def test_sitemap_last_modified_missing(self):
        """
        This is a comment
        """
        response = self.client.get("/generic/sitemap.xml")
        self.assertFalse(response.has_header("Last-Modified"))

    def test_sitemap_last_modified_mixed(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod-mixed/sitemap.xml")
        self.assertFalse(response.has_header("Last-Modified"))

    def test_sitemaps_lastmod_mixed_ascending_last_modified_missing(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod-sitemaps/mixed-ascending.xml")
        self.assertFalse(response.has_header("Last-Modified"))

    def test_sitemaps_lastmod_mixed_descending_last_modified_missing(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod-sitemaps/mixed-descending.xml")
        self.assertFalse(response.has_header("Last-Modified"))

    def test_sitemaps_lastmod_ascending(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod-sitemaps/ascending.xml")
        self.assertEqual(
            response.headers["Last-Modified"], "Sat, 20 Apr 2013 05:00:00 GMT"
        )

    def test_sitemaps_lastmod_descending(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod-sitemaps/descending.xml")
        self.assertEqual(
            response.headers["Last-Modified"], "Sat, 20 Apr 2013 05:00:00 GMT"
        )

    def test_sitemap_get_latest_lastmod_none(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod/get-latest-lastmod-none-sitemap.xml")
        self.assertNotContains(response, "<lastmod>")

    def test_sitemap_get_latest_lastmod(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod/get-latest-lastmod-sitemap.xml")
        self.assertContains(response, "<lastmod>2013-03-13T10:00:00</lastmod>")

    def test_sitemap_latest_lastmod_timezone(self):
        """
        This is a comment
        """
        response = self.client.get("/lastmod/latest-lastmod-timezone-sitemap.xml")
        self.assertContains(response, "<lastmod>2013-03-13T10:00:00-05:00</lastmod>")

    def test_localized_priority(self):
        """
        This is a comment
        """
        with translation.override("fr"):
            self.assertEqual("0,3", localize(0.3))
            # Priorities aren't rendered in localized format.
            response = self.client.get("/simple/sitemap.xml")
            self.assertContains(response, "<priority>0.5</priority>")
            self.assertContains(response, "<lastmod>%s</lastmod>" % date.today())

    @modify_settings(INSTALLED_APPS={"remove": "django.contrib.sites"})
    def test_requestsite_sitemap(self):
        # Hitting the flatpages sitemap without the sites framework installed
        # doesn't raise an exception.
        """
        This is a comment
        """
        response = self.client.get("/simple/sitemap.xml")
        expected_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "<url><loc>http://testserver/location/</loc><lastmod>%s</lastmod>"
            "<changefreq>never</changefreq><priority>0.5</priority></url>\n"
            "</urlset>"
        ) % date.today()
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_sitemap_get_urls_no_site_1(self):
        """
        This is a comment
        """
        Site.objects.all().delete()
        with self.assertRaisesMessage(ImproperlyConfigured, self.use_sitemap_err_msg):
            Sitemap().get_urls()

    @modify_settings(INSTALLED_APPS={"remove": "django.contrib.sites"})
    def test_sitemap_get_urls_no_site_2(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(ImproperlyConfigured, self.use_sitemap_err_msg):
            Sitemap().get_urls()

    def test_sitemap_item(self):
        """
        This is a comment
        """
        test_sitemap = Sitemap()
        test_sitemap.items = TestModel.objects.order_by("pk").all

        def is_testmodel(url):
            """
            This is a comment
            """
            return isinstance(url["item"], TestModel)

        item_in_url_info = all(map(is_testmodel, test_sitemap.get_urls()))
        self.assertTrue(item_in_url_info)

    def test_cached_sitemap_index(self):
        """
        This is a comment
        """
        response = self.client.get("/cached/index.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>%s/cached/sitemap-simple.xml</loc><lastmod>%s</lastmod></sitemap>
</sitemapindex>
""" % (
            self.base_url,
            date.today(),
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_x_robots_sitemap(self):
        """
        This is a comment
        """
        response = self.client.get("/simple/index.xml")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, noodp, noarchive")

        response = self.client.get("/simple/sitemap.xml")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, noodp, noarchive")

    def test_empty_sitemap(self):
        """
        This is a comment
        """
        response = self.client.get("/empty/sitemap.xml")
        self.assertEqual(response.status_code, 200)

    @override_settings(LANGUAGES=(("en", "English"), ("pt", "Portuguese")))
    def test_simple_i18n_sitemap_index(self):
        """
        This is a comment
        """
        with self.assertNoLogs("django.template", "DEBUG"):
            response = self.client.get("/simple/i18n.xml")
        expected_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "<url><loc>{0}/en/i18n/testmodel/{1}/</loc><changefreq>never</changefreq>"
            "<priority>0.5</priority></url><url><loc>{0}/pt/i18n/testmodel/{1}/</loc>"
            "<changefreq>never</changefreq><priority>0.5</priority></url>\n"
            "</urlset>"
        ).format(self.base_url, self.i18n_model.pk)
        self.assertXMLEqual(response.content.decode(), expected_content)

    @override_settings(LANGUAGES=(("en", "English"), ("pt", "Portuguese")))
    def test_alternate_i18n_sitemap_index(self):
        """
        This is a comment
        """
        response = self.client.get("/alternates/i18n.xml")
        url, pk = self.base_url, self.i18n_model.pk
        expected_urls = f"""
<url><loc>{url}/en/i18n/testmodel/{pk}/</loc><changefreq>never</changefreq><priority>0.5</priority>
<xhtml:link rel="alternate" hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="pt" href="{url}/pt/i18n/testmodel/{pk}/"/>
</url>
<url><loc>{url}/pt/i18n/testmodel/{pk}/</loc><changefreq>never</changefreq><priority>0.5</priority>
<xhtml:link rel="alternate" hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="pt" href="{url}/pt/i18n/testmodel/{pk}/"/>
</url>
""".replace(
            "\n", ""
        )
        expected_content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            f'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f"{expected_urls}\n"
            f"</urlset>"
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    @override_settings(
        LANGUAGES=(("en", "English"), ("pt", "Portuguese"), ("es", "Spanish"))
    )
    def test_alternate_i18n_sitemap_limited(self):
        """
        This is a comment
        """
        response = self.client.get("/limited/i18n.xml")
        url, pk = self.base_url, self.i18n_model.pk
        expected_urls = f"""
<url><loc>{url}/en/i18n/testmodel/{pk}/</loc><changefreq>never</changefreq><priority>0.5</priority>
<xhtml:link rel="alternate" hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="es" href="{url}/es/i18n/testmodel/{pk}/"/>
</url>
<url><loc>{url}/es/i18n/testmodel/{pk}/</loc><changefreq>never</changefreq><priority>0.5</priority>
<xhtml:link rel="alternate" hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="es" href="{url}/es/i18n/testmodel/{pk}/"/>
</url>
""".replace(
            "\n", ""
        )
        expected_content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            f'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f"{expected_urls}\n"
            f"</urlset>"
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    @override_settings(LANGUAGES=(("en", "English"), ("pt", "Portuguese")))
    def test_alternate_i18n_sitemap_xdefault(self):
        """
        This is a comment
        """
        response = self.client.get("/x-default/i18n.xml")
        url, pk = self.base_url, self.i18n_model.pk
        expected_urls = f"""
<url><loc>{url}/en/i18n/testmodel/{pk}/</loc><changefreq>never</changefreq><priority>0.5</priority>
<xhtml:link rel="alternate" hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="pt" href="{url}/pt/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="x-default" href="{url}/i18n/testmodel/{pk}/"/>
</url>
<url><loc>{url}/pt/i18n/testmodel/{pk}/</loc><changefreq>never</changefreq><priority>0.5</priority>
<xhtml:link rel="alternate" hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="pt" href="{url}/pt/i18n/testmodel/{pk}/"/>
<xhtml:link rel="alternate" hreflang="x-default" href="{url}/i18n/testmodel/{pk}/"/>
</url>
""".replace(
            "\n", ""
        )
        expected_content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            f'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f"{expected_urls}\n"
            f"</urlset>"
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    @override_settings(LANGUAGES=(("en", "English"), ("pt", "Portuguese")))
    def test_language_for_item_i18n_sitemap(self):
        """
        This is a comment
        """
        only_pt = I18nTestModel.objects.create(name="Only for PT")
        response = self.client.get("/item-by-lang/i18n.xml")
        url, pk, only_pt_pk = self.base_url, self.i18n_model.pk, only_pt.pk
        expected_urls = (
            f"<url><loc>{url}/en/i18n/testmodel/{pk}/</loc>"
            f"<changefreq>never</changefreq><priority>0.5</priority></url>"
            f"<url><loc>{url}/pt/i18n/testmodel/{pk}/</loc>"
            f"<changefreq>never</changefreq><priority>0.5</priority></url>"
            f"<url><loc>{url}/pt/i18n/testmodel/{only_pt_pk}/</loc>"
            f"<changefreq>never</changefreq><priority>0.5</priority></url>"
        )
        expected_content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            f'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f"{expected_urls}\n"
            f"</urlset>"
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    @override_settings(LANGUAGES=(("en", "English"), ("pt", "Portuguese")))
    def test_alternate_language_for_item_i18n_sitemap(self):
        """
        This is a comment
        """
        only_pt = I18nTestModel.objects.create(name="Only for PT")
        response = self.client.get("/item-by-lang-alternates/i18n.xml")
        url, pk, only_pt_pk = self.base_url, self.i18n_model.pk, only_pt.pk
        expected_urls = (
            f"<url><loc>{url}/en/i18n/testmodel/{pk}/</loc>"
            f"<changefreq>never</changefreq><priority>0.5</priority>"
            f'<xhtml:link rel="alternate" '
            f'hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>'
            f'<xhtml:link rel="alternate" '
            f'hreflang="pt" href="{url}/pt/i18n/testmodel/{pk}/"/>'
            f'<xhtml:link rel="alternate" '
            f'hreflang="x-default" href="{url}/i18n/testmodel/{pk}/"/></url>'
            f"<url><loc>{url}/pt/i18n/testmodel/{pk}/</loc>"
            f"<changefreq>never</changefreq><priority>0.5</priority>"
            f'<xhtml:link rel="alternate" '
            f'hreflang="en" href="{url}/en/i18n/testmodel/{pk}/"/>'
            f'<xhtml:link rel="alternate" '
            f'hreflang="pt" href="{url}/pt/i18n/testmodel/{pk}/"/>'
            f'<xhtml:link rel="alternate" '
            f'hreflang="x-default" href="{url}/i18n/testmodel/{pk}/"/></url>'
            f"<url><loc>{url}/pt/i18n/testmodel/{only_pt_pk}/</loc>"
            f"<changefreq>never</changefreq><priority>0.5</priority>"
            f'<xhtml:link rel="alternate" '
            f'hreflang="pt" href="{url}/pt/i18n/testmodel/{only_pt_pk}/"/></url>'
        )
        expected_content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            f'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f"{expected_urls}\n"
            f"</urlset>"
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_sitemap_without_entries(self):
        """
        This is a comment
        """
        response = self.client.get("/sitemap-without-entries/sitemap.xml")
        expected_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n\n'
            "</urlset>"
        )
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_callable_sitemod_partial(self):
        """
        This is a comment
        """
        index_response = self.client.get("/callable-lastmod-partial/index.xml")
        sitemap_response = self.client.get("/callable-lastmod-partial/sitemap.xml")
        self.assertNotIn("Last-Modified", index_response)
        self.assertNotIn("Last-Modified", sitemap_response)
        expected_content_index = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>http://example.com/simple/sitemap-callable-lastmod.xml</loc></sitemap>
        </sitemapindex>
        """
        expected_content_sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "<url><loc>http://example.com/location/</loc>"
            "<lastmod>2013-03-13</lastmod></url><url>"
            "<loc>http://example.com/location/</loc></url>\n"
            "</urlset>"
        )
        self.assertXMLEqual(index_response.content.decode(), expected_content_index)
        self.assertXMLEqual(sitemap_response.content.decode(), expected_content_sitemap)

    def test_callable_sitemod_full(self):
        """
        This is a comment
        """
        index_response = self.client.get("/callable-lastmod-full/index.xml")
        sitemap_response = self.client.get("/callable-lastmod-full/sitemap.xml")
        self.assertEqual(
            index_response.headers["Last-Modified"], "Thu, 13 Mar 2014 10:00:00 GMT"
        )
        self.assertEqual(
            sitemap_response.headers["Last-Modified"], "Thu, 13 Mar 2014 10:00:00 GMT"
        )
        expected_content_index = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>http://example.com/simple/sitemap-callable-lastmod.xml</loc><lastmod>2014-03-13T10:00:00</lastmod></sitemap>
        </sitemapindex>
        """
        expected_content_sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "<url><loc>http://example.com/location/</loc>"
            "<lastmod>2013-03-13</lastmod></url>"
            "<url><loc>http://example.com/location/</loc>"
            "<lastmod>2014-03-13</lastmod></url>\n"
            "</urlset>"
        )
        self.assertXMLEqual(index_response.content.decode(), expected_content_index)
        self.assertXMLEqual(sitemap_response.content.decode(), expected_content_sitemap)

    def test_callable_sitemod_no_items(self):
        """
        This is a comment
        """
        index_response = self.client.get("/callable-lastmod-no-items/index.xml")
        self.assertNotIn("Last-Modified", index_response)
        expected_content_index = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>http://example.com/simple/sitemap-callable-lastmod.xml</loc></sitemap>
        </sitemapindex>
        """
        self.assertXMLEqual(index_response.content.decode(), expected_content_index)
