from datetime import datetime

from django.contrib.sitemaps import GenericSitemap
from django.test import override_settings

from .base import SitemapTestsBase
from .models import TestModel


@override_settings(ABSOLUTE_URL_OVERRIDES={})
class GenericViewsSitemapTests(SitemapTestsBase):
    def test_generic_sitemap_attributes(self):
        """
        Tests that a GenericSitemap instance has the expected attributes.

        Checks that the date_field, priority, changefreq, and protocol attributes are set correctly
        based on the provided info_dict and other initialization parameters. Also verifies that
        the queryset attribute matches the one passed during initialization. This ensures that
        the GenericSitemap class properly handles its attributes and initialization data.
        """
        datetime_value = datetime.now()
        queryset = TestModel.objects.all()
        generic_sitemap = GenericSitemap(
            info_dict={
                "queryset": queryset,
                "date_field": datetime_value,
            },
            priority=0.6,
            changefreq="monthly",
            protocol="https",
        )
        attr_values = (
            ("date_field", datetime_value),
            ("priority", 0.6),
            ("changefreq", "monthly"),
            ("protocol", "https"),
        )
        for attr_name, expected_value in attr_values:
            with self.subTest(attr_name=attr_name):
                self.assertEqual(getattr(generic_sitemap, attr_name), expected_value)
        self.assertCountEqual(generic_sitemap.queryset, queryset)

    def test_generic_sitemap(self):
        "A minimal generic sitemap can be rendered"
        response = self.client.get("/generic/sitemap.xml")
        expected = ""
        for pk in TestModel.objects.values_list("id", flat=True):
            expected += "<url><loc>%s/testmodel/%s/</loc></url>" % (self.base_url, pk)
        expected_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "%s\n"
            "</urlset>"
        ) % expected
        self.assertXMLEqual(response.content.decode(), expected_content)

    def test_generic_sitemap_lastmod(self):
        test_model = TestModel.objects.first()
        TestModel.objects.update(lastmod=datetime(2013, 3, 13, 10, 0, 0))
        response = self.client.get("/generic-lastmod/sitemap.xml")
        expected_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            "<url><loc>%s/testmodel/%s/</loc><lastmod>2013-03-13</lastmod></url>\n"
            "</urlset>"
        ) % (
            self.base_url,
            test_model.pk,
        )
        self.assertXMLEqual(response.content.decode(), expected_content)
        self.assertEqual(
            response.headers["Last-Modified"], "Wed, 13 Mar 2013 10:00:00 GMT"
        )

    def test_get_protocol_defined_in_constructor(self):
        for protocol in ["http", "https"]:
            with self.subTest(protocol=protocol):
                sitemap = GenericSitemap({"queryset": None}, protocol=protocol)
                self.assertEqual(sitemap.get_protocol(), protocol)

    def test_get_protocol_passed_as_argument(self):
        sitemap = GenericSitemap({"queryset": None})
        for protocol in ["http", "https"]:
            with self.subTest(protocol=protocol):
                self.assertEqual(sitemap.get_protocol(protocol), protocol)

    def test_get_protocol_default(self):
        """
        Tests the get_protocol method of the GenericSitemap class to ensure it returns 'https' as the default protocol when no other protocol is specified.
        """
        sitemap = GenericSitemap({"queryset": None})
        self.assertEqual(sitemap.get_protocol(), "https")

    def test_generic_sitemap_index(self):
        """

        Tests the 'generic-lastmod' sitemap index by verifying its XML structure and content.

        The test case updates the last modification date of a TestModel instance and then requests the 
        sitemap index. It checks if the response matches the expected XML content, including the 
        namespace, sitemap location, and last modification date.

        This test ensures that the sitemap index is correctly generated and formatted according to 
        the sitemap protocol specification.

        """
        TestModel.objects.update(lastmod=datetime(2013, 3, 13, 10, 0, 0))
        response = self.client.get("/generic-lastmod/index.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>http://example.com/simple/sitemap-generic.xml</loc><lastmod>2013-03-13T10:00:00</lastmod></sitemap>
</sitemapindex>"""
        self.assertXMLEqual(response.content.decode("utf-8"), expected_content)
