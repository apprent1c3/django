from datetime import datetime

from django.contrib.sitemaps import GenericSitemap
from django.test import override_settings

from .base import SitemapTestsBase
from .models import TestModel


@override_settings(ABSOLUTE_URL_OVERRIDES={})
class GenericViewsSitemapTests(SitemapTestsBase):
    def test_generic_sitemap_attributes(self):
        """

        Test validation of generic sitemap attributes.

        This function tests that a GenericSitemap object is correctly initialized with its attributes, 
        including the queryset, date field, priority, changefreq, and protocol. It checks that each 
        attribute is properly set to its expected value, ensuring that the sitemap is correctly configured.
        The test also verifies that the queryset associated with the sitemap matches the original queryset.

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
        """
        Tests the generic sitemap lastmod functionality.

        Verifies that the sitemap.xml returns the correct 'lastmod' date for a given model instance.
        The test case updates the 'lastmod' field of a TestModel instance, then makes a GET request to the sitemap endpoint.
        It checks that the response content matches the expected XML structure, including the correct 'lastmod' date, and that the 'Last-Modified' header is set accordingly.

        The test ensures that the sitemap generation accurately reflects the 'lastmod' date of the model instances, which is essential for search engine crawlers to determine the frequency of updates to the site's content.

        """
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
        """
        Tests the get_protocol method of the GenericSitemap class to ensure it returns the protocol defined in the constructor.

        The test iterates over common HTTP protocols ('http' and 'https') and verifies that the get_protocol method returns the expected protocol after instantiating the GenericSitemap class with the respective protocol.
        """
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
        sitemap = GenericSitemap({"queryset": None})
        self.assertEqual(sitemap.get_protocol(), "https")

    def test_generic_sitemap_index(self):
        """
        Tests the rendering of a generic sitemap index.

        This test case verifies that the sitemap index is generated correctly, including the last modification date.
        It checks that the response from the server matches the expected XML content, which includes the sitemap location and last modification timestamp.

        The test scenario involves updating the last modification date of a test model and then requesting the sitemap index via HTTP GET.
        The expected output is a sitemap index XML document that conforms to the sitemaps.org schema, with the correct last modification date and sitemap URL.
        """
        TestModel.objects.update(lastmod=datetime(2013, 3, 13, 10, 0, 0))
        response = self.client.get("/generic-lastmod/index.xml")
        expected_content = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>http://example.com/simple/sitemap-generic.xml</loc><lastmod>2013-03-13T10:00:00</lastmod></sitemap>
</sitemapindex>"""
        self.assertXMLEqual(response.content.decode("utf-8"), expected_content)
