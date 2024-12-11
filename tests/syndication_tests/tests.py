import datetime
from xml.dom import minidom

from django.contrib.sites.models import Site
from django.contrib.syndication import views
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.test import TestCase, override_settings
from django.test.utils import requires_tz_support
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.feedgenerator import (
    Atom1Feed,
    Rss201rev2Feed,
    Stylesheet,
    SyndicationFeed,
    rfc2822_date,
    rfc3339_date,
)

from .models import Article, Entry

TZ = timezone.get_default_timezone()


class FeedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Setup test data for the application.

        This class method is used to create test data that can be used throughout the application's tests.
        It creates five entries with different titles and publication dates, and one article linked to the first entry.
        The created test data includes various date combinations to ensure correct functionality in different scenarios.

        """
        cls.e1 = Entry.objects.create(
            title="My first entry",
            updated=datetime.datetime(1980, 1, 1, 12, 30),
            published=datetime.datetime(1986, 9, 25, 20, 15, 00),
        )
        cls.e2 = Entry.objects.create(
            title="My second entry",
            updated=datetime.datetime(2008, 1, 2, 12, 30),
            published=datetime.datetime(2006, 3, 17, 18, 0),
        )
        cls.e3 = Entry.objects.create(
            title="My third entry",
            updated=datetime.datetime(2008, 1, 2, 13, 30),
            published=datetime.datetime(2005, 6, 14, 10, 45),
        )
        cls.e4 = Entry.objects.create(
            title="A & B < C > D",
            updated=datetime.datetime(2008, 1, 3, 13, 30),
            published=datetime.datetime(2005, 11, 25, 12, 11, 23),
        )
        cls.e5 = Entry.objects.create(
            title="My last entry",
            updated=datetime.datetime(2013, 1, 20, 0, 0),
            published=datetime.datetime(2013, 3, 25, 20, 0),
        )
        cls.a1 = Article.objects.create(
            title="My first article",
            entry=cls.e1,
            updated=datetime.datetime(1986, 11, 21, 9, 12, 18),
            published=datetime.datetime(1986, 10, 21, 9, 12, 18),
        )

    def assertChildNodes(self, elem, expected):
        """
        Verify that the child nodes of an element match the expected set of node names.

        Args:
            elem: The parent element to check.
            expected: A list or iterable of expected child node names.

        This assertion checks that the names of the child nodes of the given element
        are identical to the expected set of node names. The comparison is case-sensitive
        and does not consider the order or frequency of the node names, only their presence.

        Raises:
            AssertionError: If the actual child node names do not match the expected set.

        """
        actual = {n.nodeName for n in elem.childNodes}
        expected = set(expected)
        self.assertEqual(actual, expected)

    def assertChildNodeContent(self, elem, expected):
        """
        Asserts that the content of specific child nodes within an XML element matches the expected values.

        :param elem: The parent XML element to search for child nodes.
        :param expected: A dictionary where keys are the names of child nodes and values are the expected text content of those nodes.

        :raises AssertionError: If any of the child nodes do not have the expected text content.

        :note: This method assumes that all specified child nodes exist within the parent element and contain text content.

        """
        for k, v in expected.items():
            self.assertEqual(elem.getElementsByTagName(k)[0].firstChild.wholeText, v)

    def assertCategories(self, elem, expected):
        self.assertEqual(
            {
                i.firstChild.wholeText
                for i in elem.childNodes
                if i.nodeName == "category"
            },
            set(expected),
        )


@override_settings(ROOT_URLCONF="syndication_tests.urls")
class SyndicationFeedTest(FeedTestCase):
    """
    Tests for the high-level syndication feed framework.
    """

    @classmethod
    def setUpClass(cls):
        """

        Set up class-wide state before running any tests in the class.

        This method is called once before the first test in the class and is used to
        initialize class-level state. It clears the cache of Site objects to ensure
        tests start with a clean slate.

        Note
        ----
        This method is a class method and should not be called directly. It is invoked
        automatically by the testing framework.

        """
        super().setUpClass()
        # This cleanup is necessary because contrib.sites cache
        # makes tests interfere with each other, see #11505
        Site.objects.clear_cache()

    def test_rss2_feed(self):
        """
        Test the structure and content of feeds generated by Rss201rev2Feed.
        """
        response = self.client.get("/syndication/rss2/")
        doc = minidom.parseString(response.content)

        # Making sure there's only 1 `rss` element and that the correct
        # RSS version was specified.
        feed_elem = doc.getElementsByTagName("rss")
        self.assertEqual(len(feed_elem), 1)
        feed = feed_elem[0]
        self.assertEqual(feed.getAttribute("version"), "2.0")
        self.assertEqual(
            feed.getElementsByTagName("language")[0].firstChild.nodeValue, "en"
        )

        # Making sure there's only one `channel` element w/in the
        # `rss` element.
        chan_elem = feed.getElementsByTagName("channel")
        self.assertEqual(len(chan_elem), 1)
        chan = chan_elem[0]

        # Find the last build date
        d = Entry.objects.latest("published").published
        last_build_date = rfc2822_date(timezone.make_aware(d, TZ))

        self.assertChildNodes(
            chan,
            [
                "title",
                "link",
                "description",
                "language",
                "lastBuildDate",
                "item",
                "atom:link",
                "ttl",
                "copyright",
                "category",
            ],
        )
        self.assertChildNodeContent(
            chan,
            {
                "title": "My blog",
                "description": "A more thorough description of my blog.",
                "link": "http://example.com/blog/",
                "language": "en",
                "lastBuildDate": last_build_date,
                "ttl": "600",
                "copyright": "Copyright (c) 2007, Sally Smith",
            },
        )
        self.assertCategories(chan, ["python", "django"])

        # Ensure the content of the channel is correct
        self.assertChildNodeContent(
            chan,
            {
                "title": "My blog",
                "link": "http://example.com/blog/",
            },
        )

        # Check feed_url is passed
        self.assertEqual(
            chan.getElementsByTagName("atom:link")[0].getAttribute("href"),
            "http://example.com/syndication/rss2/",
        )

        # Find the pubdate of the first feed item
        d = Entry.objects.get(pk=self.e1.pk).published
        pub_date = rfc2822_date(timezone.make_aware(d, TZ))

        items = chan.getElementsByTagName("item")
        self.assertEqual(len(items), Entry.objects.count())
        self.assertChildNodeContent(
            items[0],
            {
                "title": "My first entry",
                "description": "Overridden description: My first entry",
                "link": "http://example.com/blog/%s/" % self.e1.pk,
                "guid": "http://example.com/blog/%s/" % self.e1.pk,
                "pubDate": pub_date,
                "author": "test@example.com (Sally Smith)",
                "comments": "/blog/%s/comments" % self.e1.pk,
            },
        )
        self.assertCategories(items[0], ["python", "testing"])
        for item in items:
            self.assertChildNodes(
                item,
                [
                    "title",
                    "link",
                    "description",
                    "guid",
                    "category",
                    "pubDate",
                    "author",
                    "comments",
                ],
            )
            # Assert that <guid> does not have any 'isPermaLink' attribute
            self.assertIsNone(
                item.getElementsByTagName("guid")[0].attributes.get("isPermaLink")
            )

    def test_rss2_feed_with_callable_object(self):
        response = self.client.get("/syndication/rss2/with-callable-object/")
        doc = minidom.parseString(response.content)
        chan = doc.getElementsByTagName("rss")[0].getElementsByTagName("channel")[0]
        self.assertChildNodeContent(chan, {"ttl": "700"})

    def test_rss2_feed_with_decorated_methods(self):
        """
        Test the RSS 2.0 feed with decorated methods.

        This test case verifies that the RSS 2.0 feed is correctly generated when using decorated methods.
        It checks the feed's channel and item elements for the expected metadata and content, 
        including title, description, categories, and copyright information.

        The test asserts that the feed contains the correct data, including overridden values 
        applied by the decorators, to ensure that the decoration process is applied correctly 
        to the feed's content.

        Parameters: None

        Returns: None

        Raises: AssertionError if the feed content does not match the expected values.
        """
        response = self.client.get("/syndication/rss2/with-decorated-methods/")
        doc = minidom.parseString(response.content)
        chan = doc.getElementsByTagName("rss")[0].getElementsByTagName("channel")[0]
        self.assertCategories(chan, ["javascript", "vue"])
        self.assertChildNodeContent(
            chan,
            {
                "title": "Overridden title -- decorated by @wraps.",
                "description": "Overridden description -- decorated by @wraps.",
                "ttl": "800 -- decorated by @wraps.",
                "copyright": "Copyright (c) 2022, John Doe -- decorated by @wraps.",
            },
        )
        items = chan.getElementsByTagName("item")
        self.assertChildNodeContent(
            items[0],
            {
                "title": (
                    f"Overridden item title: {self.e1.title} -- decorated by @wraps."
                ),
                "description": "Overridden item description -- decorated by @wraps.",
            },
        )

    def test_rss2_feed_with_wrong_decorated_methods(self):
        msg = (
            "Feed method 'item_description' decorated by 'wrapper' needs to use "
            "@functools.wraps."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/syndication/rss2/with-wrong-decorated-methods/")

    def test_rss2_feed_guid_permalink_false(self):
        """
        Test if the 'isPermaLink' attribute of <guid> element of an item
        in the RSS feed is 'false'.
        """
        response = self.client.get("/syndication/rss2/guid_ispermalink_false/")
        doc = minidom.parseString(response.content)
        chan = doc.getElementsByTagName("rss")[0].getElementsByTagName("channel")[0]
        items = chan.getElementsByTagName("item")
        for item in items:
            self.assertEqual(
                item.getElementsByTagName("guid")[0]
                .attributes.get("isPermaLink")
                .value,
                "false",
            )

    def test_rss2_feed_guid_permalink_true(self):
        """
        Test if the 'isPermaLink' attribute of <guid> element of an item
        in the RSS feed is 'true'.
        """
        response = self.client.get("/syndication/rss2/guid_ispermalink_true/")
        doc = minidom.parseString(response.content)
        chan = doc.getElementsByTagName("rss")[0].getElementsByTagName("channel")[0]
        items = chan.getElementsByTagName("item")
        for item in items:
            self.assertEqual(
                item.getElementsByTagName("guid")[0]
                .attributes.get("isPermaLink")
                .value,
                "true",
            )

    def test_rss2_single_enclosure(self):
        """

        Tests the RSS 2.0 feed with a single enclosure.

        Verifies that the feed contains items with exactly one enclosure element.
        The test retrieves the RSS 2.0 feed, parses the XML response, and checks
        each item in the feed to ensure it has only one enclosure.

        """
        response = self.client.get("/syndication/rss2/single-enclosure/")
        doc = minidom.parseString(response.content)
        chan = doc.getElementsByTagName("rss")[0].getElementsByTagName("channel")[0]
        items = chan.getElementsByTagName("item")
        for item in items:
            enclosures = item.getElementsByTagName("enclosure")
            self.assertEqual(len(enclosures), 1)

    def test_rss2_multiple_enclosures(self):
        with self.assertRaisesMessage(
            ValueError,
            "RSS feed items may only have one enclosure, see "
            "http://www.rssboard.org/rss-profile#element-channel-item-enclosure",
        ):
            self.client.get("/syndication/rss2/multiple-enclosure/")

    def test_rss091_feed(self):
        """
        Test the structure and content of feeds generated by RssUserland091Feed.
        """
        response = self.client.get("/syndication/rss091/")
        doc = minidom.parseString(response.content)

        # Making sure there's only 1 `rss` element and that the correct
        # RSS version was specified.
        feed_elem = doc.getElementsByTagName("rss")
        self.assertEqual(len(feed_elem), 1)
        feed = feed_elem[0]
        self.assertEqual(feed.getAttribute("version"), "0.91")

        # Making sure there's only one `channel` element w/in the
        # `rss` element.
        chan_elem = feed.getElementsByTagName("channel")
        self.assertEqual(len(chan_elem), 1)
        chan = chan_elem[0]
        self.assertChildNodes(
            chan,
            [
                "title",
                "link",
                "description",
                "language",
                "lastBuildDate",
                "item",
                "atom:link",
                "ttl",
                "copyright",
                "category",
            ],
        )

        # Ensure the content of the channel is correct
        self.assertChildNodeContent(
            chan,
            {
                "title": "My blog",
                "link": "http://example.com/blog/",
            },
        )
        self.assertCategories(chan, ["python", "django"])

        # Check feed_url is passed
        self.assertEqual(
            chan.getElementsByTagName("atom:link")[0].getAttribute("href"),
            "http://example.com/syndication/rss091/",
        )

        items = chan.getElementsByTagName("item")
        self.assertEqual(len(items), Entry.objects.count())
        self.assertChildNodeContent(
            items[0],
            {
                "title": "My first entry",
                "description": "Overridden description: My first entry",
                "link": "http://example.com/blog/%s/" % self.e1.pk,
            },
        )
        for item in items:
            self.assertChildNodes(item, ["title", "link", "description"])
            self.assertCategories(item, [])

    def test_atom_feed(self):
        """
        Test the structure and content of feeds generated by Atom1Feed.
        """
        response = self.client.get("/syndication/atom/")
        feed = minidom.parseString(response.content).firstChild

        self.assertEqual(feed.nodeName, "feed")
        self.assertEqual(feed.getAttribute("xmlns"), "http://www.w3.org/2005/Atom")
        self.assertChildNodes(
            feed,
            [
                "title",
                "subtitle",
                "link",
                "id",
                "updated",
                "entry",
                "rights",
                "category",
                "author",
            ],
        )
        for link in feed.getElementsByTagName("link"):
            if link.getAttribute("rel") == "self":
                self.assertEqual(
                    link.getAttribute("href"), "http://example.com/syndication/atom/"
                )

        entries = feed.getElementsByTagName("entry")
        self.assertEqual(len(entries), Entry.objects.count())
        for entry in entries:
            self.assertChildNodes(
                entry,
                [
                    "title",
                    "link",
                    "id",
                    "summary",
                    "category",
                    "updated",
                    "published",
                    "rights",
                    "author",
                ],
            )
            summary = entry.getElementsByTagName("summary")[0]
            self.assertEqual(summary.getAttribute("type"), "html")

    def test_atom_feed_published_and_updated_elements(self):
        """
        The published and updated elements are not
        the same and now adhere to RFC 4287.
        """
        response = self.client.get("/syndication/atom/")
        feed = minidom.parseString(response.content).firstChild
        entries = feed.getElementsByTagName("entry")

        published = entries[0].getElementsByTagName("published")[0].firstChild.wholeText
        updated = entries[0].getElementsByTagName("updated")[0].firstChild.wholeText

        self.assertNotEqual(published, updated)

    def test_atom_single_enclosure(self):
        """
        Verifies the atom feed at the '/syndication/atom/single-enclosure/' endpoint contains entries with a single enclosure link.

         Checks the presence and uniqueness of enclosure links within each entry of the feed. 

         This test ensures that each entry in the feed has exactly one link with a 'rel' attribute set to 'enclosure', as per the Atom feed specification.
        """
        response = self.client.get("/syndication/atom/single-enclosure/")
        feed = minidom.parseString(response.content).firstChild
        items = feed.getElementsByTagName("entry")
        for item in items:
            links = item.getElementsByTagName("link")
            links = [link for link in links if link.getAttribute("rel") == "enclosure"]
            self.assertEqual(len(links), 1)

    def test_atom_multiple_enclosures(self):
        response = self.client.get("/syndication/atom/multiple-enclosure/")
        feed = minidom.parseString(response.content).firstChild
        items = feed.getElementsByTagName("entry")
        for item in items:
            links = item.getElementsByTagName("link")
            links = [link for link in links if link.getAttribute("rel") == "enclosure"]
            self.assertEqual(len(links), 2)

    def test_latest_post_date(self):
        """
        Both the published and updated dates are
        considered when determining the latest post date.
        """
        # this feed has a `published` element with the latest date
        response = self.client.get("/syndication/atom/")
        feed = minidom.parseString(response.content).firstChild
        updated = feed.getElementsByTagName("updated")[0].firstChild.wholeText

        d = Entry.objects.latest("published").published
        latest_published = rfc3339_date(timezone.make_aware(d, TZ))

        self.assertEqual(updated, latest_published)

        # this feed has an `updated` element with the latest date
        response = self.client.get("/syndication/latest/")
        feed = minidom.parseString(response.content).firstChild
        updated = feed.getElementsByTagName("updated")[0].firstChild.wholeText

        d = Entry.objects.exclude(title="My last entry").latest("updated").updated
        latest_updated = rfc3339_date(timezone.make_aware(d, TZ))

        self.assertEqual(updated, latest_updated)

    def test_custom_feed_generator(self):
        response = self.client.get("/syndication/custom/")
        feed = minidom.parseString(response.content).firstChild

        self.assertEqual(feed.nodeName, "feed")
        self.assertEqual(feed.getAttribute("django"), "rocks")
        self.assertChildNodes(
            feed,
            [
                "title",
                "subtitle",
                "link",
                "id",
                "updated",
                "entry",
                "spam",
                "rights",
                "category",
                "author",
            ],
        )

        entries = feed.getElementsByTagName("entry")
        self.assertEqual(len(entries), Entry.objects.count())
        for entry in entries:
            self.assertEqual(entry.getAttribute("bacon"), "yum")
            self.assertChildNodes(
                entry,
                [
                    "title",
                    "link",
                    "id",
                    "summary",
                    "ministry",
                    "rights",
                    "author",
                    "updated",
                    "published",
                    "category",
                ],
            )
            summary = entry.getElementsByTagName("summary")[0]
            self.assertEqual(summary.getAttribute("type"), "html")

    def test_feed_generator_language_attribute(self):
        response = self.client.get("/syndication/language/")
        feed = minidom.parseString(response.content).firstChild
        self.assertEqual(
            feed.firstChild.getElementsByTagName("language")[0].firstChild.nodeValue,
            "de",
        )

    def test_title_escaping(self):
        """
        Titles are escaped correctly in RSS feeds.
        """
        response = self.client.get("/syndication/rss2/")
        doc = minidom.parseString(response.content)
        for item in doc.getElementsByTagName("item"):
            link = item.getElementsByTagName("link")[0]
            if link.firstChild.wholeText == "http://example.com/blog/4/":
                title = item.getElementsByTagName("title")[0]
                self.assertEqual(title.firstChild.wholeText, "A &amp; B &lt; C &gt; D")

    def test_naive_datetime_conversion(self):
        """
        Datetimes are correctly converted to the local time zone.
        """
        # Naive date times passed in get converted to the local time zone, so
        # check the received zone offset against the local offset.
        response = self.client.get("/syndication/naive-dates/")
        doc = minidom.parseString(response.content)
        updated = doc.getElementsByTagName("updated")[0].firstChild.wholeText

        d = Entry.objects.latest("published").published
        latest = rfc3339_date(timezone.make_aware(d, TZ))

        self.assertEqual(updated, latest)

    def test_aware_datetime_conversion(self):
        """
        Datetimes with timezones don't get trodden on.
        """
        response = self.client.get("/syndication/aware-dates/")
        doc = minidom.parseString(response.content)
        published = doc.getElementsByTagName("published")[0].firstChild.wholeText
        self.assertEqual(published[-6:], "+00:42")

    def test_feed_no_content_self_closing_tag(self):
        """
        Test that feed generators produce self-closing tags when no content is provided.

        This test ensures that different feed generators (Atom and RSS) correctly 
        generate self-closing tags for links when no additional content is provided. 

        The test verifies that the generated feed contains the expected self-closing 
        tag with the correct href and rel attributes.

        :raises AssertionError: if the expected self-closing tag is not found in the 
            generated feed document.

        """
        tests = [
            (Atom1Feed, "link"),
            (Rss201rev2Feed, "atom:link"),
        ]
        for feedgenerator, tag in tests:
            with self.subTest(feedgenerator=feedgenerator.__name__):
                feed = feedgenerator(
                    title="title",
                    link="https://example.com",
                    description="self closing tags test",
                    feed_url="https://feed.url.com",
                )
                doc = feed.writeString("utf-8")
                self.assertIn(f'<{tag} href="https://feed.url.com" rel="self"/>', doc)

    def test_stylesheets_none(self):
        feed = Rss201rev2Feed(
            title="test",
            link="https://example.com",
            description="test",
            stylesheets=None,
        )
        self.assertNotIn("xml-stylesheet", feed.writeString("utf-8"))

    def test_stylesheets(self):
        testdata = [
            # Plain strings.
            ("/test.xsl", 'href="/test.xsl" type="text/xsl" media="screen"'),
            ("/test.xslt", 'href="/test.xslt" type="text/xsl" media="screen"'),
            ("/test.css", 'href="/test.css" type="text/css" media="screen"'),
            ("/test", 'href="/test" media="screen"'),
            (
                "https://example.com/test.xsl",
                'href="https://example.com/test.xsl" type="text/xsl" media="screen"',
            ),
            (
                "https://example.com/test.css",
                'href="https://example.com/test.css" type="text/css" media="screen"',
            ),
            (
                "https://example.com/test",
                'href="https://example.com/test" media="screen"',
            ),
            ("/♥.xsl", 'href="/%E2%99%A5.xsl" type="text/xsl" media="screen"'),
            (
                static("stylesheet.xsl"),
                'href="/static/stylesheet.xsl" type="text/xsl" media="screen"',
            ),
            (
                static("stylesheet.css"),
                'href="/static/stylesheet.css" type="text/css" media="screen"',
            ),
            (static("stylesheet"), 'href="/static/stylesheet" media="screen"'),
            (
                reverse("syndication-xsl-stylesheet"),
                'href="/syndication/stylesheet.xsl" type="text/xsl" media="screen"',
            ),
            (
                reverse_lazy("syndication-xsl-stylesheet"),
                'href="/syndication/stylesheet.xsl" type="text/xsl" media="screen"',
            ),
            # Stylesheet objects.
            (
                Stylesheet("/test.xsl"),
                'href="/test.xsl" type="text/xsl" media="screen"',
            ),
            (Stylesheet("/test.xsl", mimetype=None), 'href="/test.xsl" media="screen"'),
            (Stylesheet("/test.xsl", media=None), 'href="/test.xsl" type="text/xsl"'),
            (Stylesheet("/test.xsl", mimetype=None, media=None), 'href="/test.xsl"'),
            (
                Stylesheet("/test.xsl", mimetype="text/xml"),
                'href="/test.xsl" type="text/xml" media="screen"',
            ),
        ]
        for stylesheet, expected in testdata:
            feed = Rss201rev2Feed(
                title="test",
                link="https://example.com",
                description="test",
                stylesheets=[stylesheet],
            )
            doc = feed.writeString("utf-8")
            with self.subTest(expected=expected):
                self.assertIn(f"<?xml-stylesheet {expected}?>", doc)

    def test_stylesheets_instructions_are_at_the_top(self):
        """

        Verify that the XML stylesheet instructions are correctly placed at the top of the XML document.

        This test case checks the response from the '/syndication/stylesheet/' endpoint to ensure that the xml-stylesheet instructions
        are the first child nodes of the document. It also verifies that the attributes of these instructions, such as the href, type,
        and media, match the expected values for two specific stylesheets, '/stylesheet1.xsl' and '/stylesheet2.xsl'.

        """
        response = self.client.get("/syndication/stylesheet/")
        doc = minidom.parseString(response.content)
        self.assertEqual(doc.childNodes[0].nodeName, "xml-stylesheet")
        self.assertEqual(
            doc.childNodes[0].data,
            'href="/stylesheet1.xsl" type="text/xsl" media="screen"',
        )
        self.assertEqual(doc.childNodes[1].nodeName, "xml-stylesheet")
        self.assertEqual(
            doc.childNodes[1].data,
            'href="/stylesheet2.xsl" type="text/xsl" media="screen"',
        )

    def test_stylesheets_typeerror_if_str_or_stylesheet(self):
        for stylesheet, error_message in [
            ("/stylesheet.xsl", "stylesheets should be a list, not <class 'str'>"),
            (
                Stylesheet("/stylesheet.xsl"),
                "stylesheets should be a list, "
                "not <class 'django.utils.feedgenerator.Stylesheet'>",
            ),
        ]:
            args = ("title", "/link", "description")
            with self.subTest(stylesheets=stylesheet):
                self.assertRaisesMessage(
                    TypeError,
                    error_message,
                    SyndicationFeed,
                    *args,
                    stylesheets=stylesheet,
                )

    def test_stylesheets_repr(self):
        """

        Tests the string representation of a Stylesheet object.

        This function verifies that the repr method of a Stylesheet instance returns the expected string format, 
        covering various combinations of mime type and media settings.

        The test cases include scenarios with and without explicit mime type and media settings, 
        ensuring that the repr method behaves correctly in different situations.

        """
        testdata = [
            (Stylesheet("/test.xsl", mimetype=None), "('/test.xsl', None, 'screen')"),
            (Stylesheet("/test.xsl", media=None), "('/test.xsl', 'text/xsl', None)"),
            (
                Stylesheet("/test.xsl", mimetype=None, media=None),
                "('/test.xsl', None, None)",
            ),
            (
                Stylesheet("/test.xsl", mimetype="text/xml"),
                "('/test.xsl', 'text/xml', 'screen')",
            ),
        ]
        for stylesheet, expected in testdata:
            self.assertEqual(repr(stylesheet), expected)

    @requires_tz_support
    def test_feed_last_modified_time_naive_date(self):
        """
        Tests the Last-Modified header with naive publication dates.
        """
        response = self.client.get("/syndication/naive-dates/")
        self.assertEqual(
            response.headers["Last-Modified"], "Tue, 26 Mar 2013 01:00:00 GMT"
        )

    def test_feed_last_modified_time(self):
        """
        Tests the Last-Modified header with aware publication dates.
        """
        response = self.client.get("/syndication/aware-dates/")
        self.assertEqual(
            response.headers["Last-Modified"], "Mon, 25 Mar 2013 19:18:00 GMT"
        )

        # No last-modified when feed has no item_pubdate
        response = self.client.get("/syndication/no_pubdate/")
        self.assertFalse(response.has_header("Last-Modified"))

    def test_feed_url(self):
        """
        The feed_url can be overridden.
        """
        response = self.client.get("/syndication/feedurl/")
        doc = minidom.parseString(response.content)
        for link in doc.getElementsByTagName("link"):
            if link.getAttribute("rel") == "self":
                self.assertEqual(
                    link.getAttribute("href"), "http://example.com/customfeedurl/"
                )

    def test_secure_urls(self):
        """
        Test URLs are prefixed with https:// when feed is requested over HTTPS.
        """
        response = self.client.get(
            "/syndication/rss2/",
            **{
                "wsgi.url_scheme": "https",
            },
        )
        doc = minidom.parseString(response.content)
        chan = doc.getElementsByTagName("channel")[0]
        self.assertEqual(
            chan.getElementsByTagName("link")[0].firstChild.wholeText[0:5], "https"
        )
        atom_link = chan.getElementsByTagName("atom:link")[0]
        self.assertEqual(atom_link.getAttribute("href")[0:5], "https")
        for link in doc.getElementsByTagName("link"):
            if link.getAttribute("rel") == "self":
                self.assertEqual(link.getAttribute("href")[0:5], "https")

    def test_item_link_error(self):
        """
        An ImproperlyConfigured is raised if no link could be found for the
        item(s).
        """
        msg = (
            "Give your Article class a get_absolute_url() method, or define "
            "an item_link() method in your Feed class."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/syndication/articles/")

    def test_template_feed(self):
        """
        The item title and description can be overridden with templates.
        """
        response = self.client.get("/syndication/template/")
        doc = minidom.parseString(response.content)
        feed = doc.getElementsByTagName("rss")[0]
        chan = feed.getElementsByTagName("channel")[0]
        items = chan.getElementsByTagName("item")

        self.assertChildNodeContent(
            items[0],
            {
                "title": "Title in your templates: My first entry\n",
                "description": "Description in your templates: My first entry\n",
                "link": "http://example.com/blog/%s/" % self.e1.pk,
            },
        )

    def test_template_context_feed(self):
        """
        Custom context data can be passed to templates for title
        and description.
        """
        response = self.client.get("/syndication/template_context/")
        doc = minidom.parseString(response.content)
        feed = doc.getElementsByTagName("rss")[0]
        chan = feed.getElementsByTagName("channel")[0]
        items = chan.getElementsByTagName("item")

        self.assertChildNodeContent(
            items[0],
            {
                "title": "My first entry (foo is bar)\n",
                "description": "My first entry (foo is bar)\n",
            },
        )

    def test_add_domain(self):
        """
        add_domain() prefixes domains onto the correct URLs.
        """
        prefix_domain_mapping = (
            (("example.com", "/foo/?arg=value"), "http://example.com/foo/?arg=value"),
            (
                ("example.com", "/foo/?arg=value", True),
                "https://example.com/foo/?arg=value",
            ),
            (
                ("example.com", "http://djangoproject.com/doc/"),
                "http://djangoproject.com/doc/",
            ),
            (
                ("example.com", "https://djangoproject.com/doc/"),
                "https://djangoproject.com/doc/",
            ),
            (
                ("example.com", "mailto:uhoh@djangoproject.com"),
                "mailto:uhoh@djangoproject.com",
            ),
            (
                ("example.com", "//example.com/foo/?arg=value"),
                "http://example.com/foo/?arg=value",
            ),
        )
        for prefix in prefix_domain_mapping:
            with self.subTest(prefix=prefix):
                self.assertEqual(views.add_domain(*prefix[0]), prefix[1])

    def test_get_object(self):
        response = self.client.get("/syndication/rss2/articles/%s/" % self.e1.pk)
        doc = minidom.parseString(response.content)
        feed = doc.getElementsByTagName("rss")[0]
        chan = feed.getElementsByTagName("channel")[0]
        items = chan.getElementsByTagName("item")

        self.assertChildNodeContent(
            items[0],
            {
                "comments": "/blog/%s/article/%s/comments" % (self.e1.pk, self.a1.pk),
                "description": "Article description: My first article",
                "link": "http://example.com/blog/%s/article/%s/"
                % (self.e1.pk, self.a1.pk),
                "title": "Title: My first article",
                "pubDate": rfc2822_date(timezone.make_aware(self.a1.published, TZ)),
            },
        )

    def test_get_non_existent_object(self):
        response = self.client.get("/syndication/rss2/articles/0/")
        self.assertEqual(response.status_code, 404)
