import datetime
from unittest import mock

from django.test import SimpleTestCase
from django.utils import feedgenerator
from django.utils.functional import SimpleLazyObject
from django.utils.timezone import get_fixed_timezone


class FeedgeneratorTests(SimpleTestCase):
    """
    Tests for the low-level syndication feed framework.
    """

    def test_get_tag_uri(self):
        """
        get_tag_uri() correctly generates TagURIs.
        """
        self.assertEqual(
            feedgenerator.get_tag_uri(
                "http://example.org/foo/bar#headline", datetime.date(2004, 10, 25)
            ),
            "tag:example.org,2004-10-25:/foo/bar/headline",
        )

    def test_get_tag_uri_with_port(self):
        """
        get_tag_uri() correctly generates TagURIs from URLs with port numbers.
        """
        self.assertEqual(
            feedgenerator.get_tag_uri(
                "http://www.example.org:8000/2008/11/14/django#headline",
                datetime.datetime(2008, 11, 14, 13, 37, 0),
            ),
            "tag:www.example.org,2008-11-14:/2008/11/14/django/headline",
        )

    def test_rfc2822_date(self):
        """
        rfc2822_date() correctly formats datetime objects.
        """
        self.assertEqual(
            feedgenerator.rfc2822_date(datetime.datetime(2008, 11, 14, 13, 37, 0)),
            "Fri, 14 Nov 2008 13:37:00 -0000",
        )

    def test_rfc2822_date_with_timezone(self):
        """
        rfc2822_date() correctly formats datetime objects with tzinfo.
        """
        self.assertEqual(
            feedgenerator.rfc2822_date(
                datetime.datetime(
                    2008, 11, 14, 13, 37, 0, tzinfo=get_fixed_timezone(60)
                )
            ),
            "Fri, 14 Nov 2008 13:37:00 +0100",
        )

    def test_rfc2822_date_without_time(self):
        """
        rfc2822_date() correctly formats date objects.
        """
        self.assertEqual(
            feedgenerator.rfc2822_date(datetime.date(2008, 11, 14)),
            "Fri, 14 Nov 2008 00:00:00 -0000",
        )

    def test_rfc3339_date(self):
        """
        rfc3339_date() correctly formats datetime objects.
        """
        self.assertEqual(
            feedgenerator.rfc3339_date(datetime.datetime(2008, 11, 14, 13, 37, 0)),
            "2008-11-14T13:37:00Z",
        )

    def test_rfc3339_date_with_timezone(self):
        """
        rfc3339_date() correctly formats datetime objects with tzinfo.
        """
        self.assertEqual(
            feedgenerator.rfc3339_date(
                datetime.datetime(
                    2008, 11, 14, 13, 37, 0, tzinfo=get_fixed_timezone(120)
                )
            ),
            "2008-11-14T13:37:00+02:00",
        )

    def test_rfc3339_date_without_time(self):
        """
        rfc3339_date() correctly formats date objects.
        """
        self.assertEqual(
            feedgenerator.rfc3339_date(datetime.date(2008, 11, 14)),
            "2008-11-14T00:00:00Z",
        )

    def test_atom1_mime_type(self):
        """
        Atom MIME type has UTF8 Charset parameter set
        """
        atom_feed = feedgenerator.Atom1Feed("title", "link", "description")
        self.assertEqual(atom_feed.content_type, "application/atom+xml; charset=utf-8")

    def test_rss_mime_type(self):
        """
        RSS MIME type has UTF8 Charset parameter set
        """
        rss_feed = feedgenerator.Rss201rev2Feed("title", "link", "description")
        self.assertEqual(rss_feed.content_type, "application/rss+xml; charset=utf-8")

    # Two regression tests for #14202

    def test_feed_without_feed_url_gets_rendered_without_atom_link(self):
        """
        Tests that a feed without a specified feed URL is rendered correctly.

        The function verifies that when a feed is created without a feed URL, the
        resulting feed content does not contain an Atom link element. This ensures
        that the feed is properly formatted and does not reference a non-existent
        feed URL. The test checks the feed's content for the absence of specific
        attributes and elements that would indicate the presence of an Atom link.
        """
        feed = feedgenerator.Rss201rev2Feed("title", "/link/", "descr")
        self.assertIsNone(feed.feed["feed_url"])
        feed_content = feed.writeString("utf-8")
        self.assertNotIn("<atom:link", feed_content)
        self.assertNotIn('href="/feed/"', feed_content)
        self.assertNotIn('rel="self"', feed_content)

    def test_feed_with_feed_url_gets_rendered_with_atom_link(self):
        """
        Tests that an RSS feed with a specified feed URL is correctly rendered with an Atom link.

        This test case verifies that the feed URL is properly included in the RSS feed's metadata and 
        that the corresponding Atom link is correctly generated in the feed's content.

        It checks that the feed URL is correctly set, and that the rendered feed content includes 
        the expected Atom link with the 'self' relation and the specified href attribute.
        """
        feed = feedgenerator.Rss201rev2Feed(
            "title", "/link/", "descr", feed_url="/feed/"
        )
        self.assertEqual(feed.feed["feed_url"], "/feed/")
        feed_content = feed.writeString("utf-8")
        self.assertIn("<atom:link", feed_content)
        self.assertIn('href="/feed/"', feed_content)
        self.assertIn('rel="self"', feed_content)

    def test_atom_add_item(self):
        # Not providing any optional arguments to Atom1Feed.add_item()
        feed = feedgenerator.Atom1Feed("title", "/link/", "descr")
        feed.add_item("item_title", "item_link", "item_description")
        feed.writeString("utf-8")

    def test_deterministic_attribute_order(self):
        feed = feedgenerator.Atom1Feed("title", "/link/", "desc")
        feed_content = feed.writeString("utf-8")
        self.assertIn('href="/link/" rel="alternate"', feed_content)

    def test_latest_post_date_returns_utc_time(self):
        """
        Tests whether the latest post date returned by an RSS feed is in UTC time, 
        regardless of whether timezone support is enabled or disabled in the application settings.
        """
        for use_tz in (True, False):
            with self.settings(USE_TZ=use_tz):
                rss_feed = feedgenerator.Rss201rev2Feed("title", "link", "description")
                self.assertEqual(
                    rss_feed.latest_post_date().tzinfo,
                    datetime.timezone.utc,
                )

    def test_stylesheet_keeps_lazy_urls(self):
        """

        Tests that a stylesheet correctly handles lazy URLs.

        This test case verifies that the Stylesheet class does not prematurely
        evaluate a lazy URL until its string representation is requested.
        When the string representation is requested, the lazy URL is evaluated
        and its value is used to construct the stylesheet string.

        The resulting stylesheet string is then verified to contain the expected
        attributes, including the evaluated lazy URL as the 'href' value.

        """
        m = mock.Mock(return_value="test.css")
        stylesheet = feedgenerator.Stylesheet(SimpleLazyObject(m))
        m.assert_not_called()
        self.assertEqual(
            str(stylesheet), 'href="test.css" type="text/css" media="screen"'
        )
        m.assert_called_once()
