from django.forms import CharField, Form, Media, MultiWidget, TextInput
from django.template import Context, Template
from django.templatetags.static import static
from django.test import SimpleTestCase, override_settings
from django.utils.html import format_html, html_safe


@override_settings(
    STATIC_URL="http://media.example.com/static/",
)
class FormsMediaTestCase(SimpleTestCase):
    """Tests for the media handling on widgets and forms"""

    def test_construction(self):
        # Check construction of media objects
        """
        Tests the construction of Media objects.

        This test case verifies that Media objects can be created with various
        combinations of CSS and JavaScript files. It checks that the `__str__`
        and `__repr__` methods produce the expected output, including the
        correct HTML tags for CSS and JavaScript files.

        The test also covers the case where a Media object is created from an
        object that has `css` and `js` attributes, demonstrating that Media
        objects can be instantiated from other objects that provide the
        necessary attributes.

        Additionally, it tests the integration of Media with widget objects,
        ensuring that the `media` attribute of a widget is correctly populated
        and that the `__str__` method produces the expected output for a widget
        with no media files attached.

        Ensures that Media objects are correctly constructed and provide the
        expected representations as strings and in their internal form, both
        when initialized with explicit CSS and JavaScript files and when
        initialized from other objects that provide the necessary attributes.
        """
        m = Media(
            css={"all": ("path/to/css1", "/path/to/css2")},
            js=(
                "/path/to/js1",
                "http://media.other.com/path/to/js2",
                "https://secure.other.com/path/to/js3",
            ),
        )
        self.assertEqual(
            str(m),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )
        self.assertEqual(
            repr(m),
            "Media(css={'all': ['path/to/css1', '/path/to/css2']}, "
            "js=['/path/to/js1', 'http://media.other.com/path/to/js2', "
            "'https://secure.other.com/path/to/js3'])",
        )

        class Foo:
            css = {"all": ("path/to/css1", "/path/to/css2")}
            js = (
                "/path/to/js1",
                "http://media.other.com/path/to/js2",
                "https://secure.other.com/path/to/js3",
            )

        m3 = Media(Foo)
        self.assertEqual(
            str(m3),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # A widget can exist without a media definition
        class MyWidget(TextInput):
            pass

        w = MyWidget()
        self.assertEqual(str(w.media), "")

    def test_media_dsl(self):
        ###############################################################
        # DSL Class-based media definitions
        ###############################################################

        # A widget can define media if it needs to.
        # Any absolute path will be preserved; relative paths are combined
        # with the value of settings.MEDIA_URL
        """

        Tests the media DSL (Domain Specific Language) for a custom widget.

        Verifies that the media attributes (CSS and JavaScript files) defined in the widget's Media class are correctly rendered as HTML tags.
        The test checks that both absolute and relative paths are properly handled, and that the media types (e.g., CSS, JavaScript) are correctly identified and rendered.

        Specifically, this test case covers the following scenarios:
        - Rendering of CSS files with absolute and relative paths
        - Rendering of JavaScript files with absolute and relative paths, including HTTP and HTTPS URLs
        - Accessing and rendering specific media types (CSS or JavaScript) from the widget's media object

        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        w1 = MyWidget1()
        self.assertEqual(
            str(w1.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # Media objects can be interrogated by media type
        self.assertEqual(
            str(w1.media["css"]),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">',
        )

        self.assertEqual(
            str(w1.media["js"]),
            """<script src="/path/to/js1"></script>
<script src="http://media.other.com/path/to/js2"></script>
<script src="https://secure.other.com/path/to/js3"></script>""",
        )

    def test_combine_media(self):
        # Media objects can be combined. Any given media resource will appear only
        # once. Duplicated media definitions are ignored.
        """
        Tests the combination of media (CSS and JavaScript files) from multiple widgets.

        This test case verifies that media files are correctly combined and rendered
        when multiple widgets are used together. Specifically, it checks for:

        *   Elimination of duplicate media files
        *   Preservation of the original order of media files
        *   Proper handling of media files with different protocols (e.g., HTTP, HTTPS)
        *   Correct rendering of CSS and JavaScript files as HTML tags

        The test uses custom widgets with predefined media files to simulate real-world
        scenarios and ensures that the resulting media output is as expected.
        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget2(TextInput):
            class Media:
                css = {"all": ("/path/to/css2", "/path/to/css3")}
                js = ("/path/to/js1", "/path/to/js4")

        class MyWidget3(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css3")}
                js = ("/path/to/js1", "/path/to/js4")

        w1 = MyWidget1()
        w2 = MyWidget2()
        w3 = MyWidget3()
        self.assertEqual(
            str(w1.media + w2.media + w3.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css3" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="/path/to/js4"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # media addition hasn't affected the original objects
        self.assertEqual(
            str(w1.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # Regression check for #12879: specifying the same CSS or JS file
        # multiple times in a single Media instance should result in that file
        # only being included once.
        class MyWidget4(TextInput):
            class Media:
                css = {"all": ("/path/to/css1", "/path/to/css1")}
                js = ("/path/to/js1", "/path/to/js1")

        w4 = MyWidget4()
        self.assertEqual(
            str(w4.media),
            """<link href="/path/to/css1" media="all" rel="stylesheet">
<script src="/path/to/js1"></script>""",
        )

    def test_media_deduplication(self):
        # A deduplication test applied directly to a Media object, to confirm
        # that the deduplication doesn't only happen at the point of merging
        # two or more media objects.
        """

        Tests the media deduplication functionality, ensuring that duplicate CSS and JS resources are correctly collapsed into a single instance.

        The function verifies that when multiple instances of the same media resource are provided, the resulting media string contains only one instance of each resource.

        """
        media = Media(
            css={"all": ("/path/to/css1", "/path/to/css1")},
            js=("/path/to/js1", "/path/to/js1"),
        )
        self.assertEqual(
            str(media),
            """<link href="/path/to/css1" media="all" rel="stylesheet">
<script src="/path/to/js1"></script>""",
        )

    def test_media_property(self):
        ###############################################################
        # Property-based media definitions
        ###############################################################

        # Widget media can be defined as a property
        class MyWidget4(TextInput):
            def _media(self):
                return Media(css={"all": ("/some/path",)}, js=("/some/js",))

            media = property(_media)

        w4 = MyWidget4()
        self.assertEqual(
            str(w4.media),
            """<link href="/some/path" media="all" rel="stylesheet">
<script src="/some/js"></script>""",
        )

        # Media properties can reference the media of their parents
        class MyWidget5(MyWidget4):
            def _media(self):
                return super().media + Media(
                    css={"all": ("/other/path",)}, js=("/other/js",)
                )

            media = property(_media)

        w5 = MyWidget5()
        self.assertEqual(
            str(w5.media),
            """<link href="/some/path" media="all" rel="stylesheet">
<link href="/other/path" media="all" rel="stylesheet">
<script src="/some/js"></script>
<script src="/other/js"></script>""",
        )

    def test_media_property_parent_references(self):
        # Media properties can reference the media of their parents,
        # even if the parent media was defined using a class
        """
        Tests that media property parent references are correctly inherited and rendered.

        This test verifies that a subclass's media property includes all the media files
        defined in its parent class, as well as any additional media files defined in the
        subclass itself. It checks that the resulting media property contains all the
        expected CSS and JavaScript files, and that they are correctly formatted as HTML
        links and script tags.

        The test covers both absolute and relative URLs for media files, as well as
        different protocols (http and https).
        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget6(MyWidget1):
            def _media(self):
                return super().media + Media(
                    css={"all": ("/other/path",)}, js=("/other/js",)
                )

            media = property(_media)

        w6 = MyWidget6()
        self.assertEqual(
            str(w6.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/other/path" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="/other/js"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

    def test_media_inheritance(self):
        ###############################################################
        # Inheritance of media
        ###############################################################

        # If a widget extends another but provides no media definition, it
        # inherits the parent widget's media.
        """

        Tests media inheritance in widget classes.

        Verifies that the media definitions from parent classes are correctly inherited
        and combined with the media definitions from child classes. This includes testing
        for CSS and JavaScript files, with both absolute and relative URLs.

        The test covers two scenarios: 

        1. A child widget with no media definition of its own, where the parent's
           media definition is expected to be used.
        2. A child widget with its own media definition, where the child's media
           definition is expected to be combined with the parent's.

        Ensures that the resulting media representation is correctly rendered as HTML,
        with the expected CSS and JavaScript tags.

        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget7(MyWidget1):
            pass

        w7 = MyWidget7()
        self.assertEqual(
            str(w7.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # If a widget extends another but defines media, it extends the parent
        # widget's media by default.
        class MyWidget8(MyWidget1):
            class Media:
                css = {"all": ("/path/to/css3", "path/to/css1")}
                js = ("/path/to/js1", "/path/to/js4")

        w8 = MyWidget8()
        self.assertEqual(
            str(w8.media),
            """<link href="/path/to/css3" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" media="all" rel="stylesheet">
<link href="/path/to/css2" media="all" rel="stylesheet">
<script src="/path/to/js1"></script>
<script src="http://media.other.com/path/to/js2"></script>
<script src="/path/to/js4"></script>
<script src="https://secure.other.com/path/to/js3"></script>""",
        )

    def test_media_inheritance_from_property(self):
        # If a widget extends another but defines media, it extends the parents
        # widget's media, even if the parent defined media using a property.
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget4(TextInput):
            def _media(self):
                return Media(css={"all": ("/some/path",)}, js=("/some/js",))

            media = property(_media)

        class MyWidget9(MyWidget4):
            class Media:
                css = {"all": ("/other/path",)}
                js = ("/other/js",)

        w9 = MyWidget9()
        self.assertEqual(
            str(w9.media),
            """<link href="/some/path" media="all" rel="stylesheet">
<link href="/other/path" media="all" rel="stylesheet">
<script src="/some/js"></script>
<script src="/other/js"></script>""",
        )

        # A widget can disable media inheritance by specifying 'extend=False'
        class MyWidget10(MyWidget1):
            class Media:
                extend = False
                css = {"all": ("/path/to/css3", "path/to/css1")}
                js = ("/path/to/js1", "/path/to/js4")

        w10 = MyWidget10()
        self.assertEqual(
            str(w10.media),
            """<link href="/path/to/css3" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" media="all" rel="stylesheet">
<script src="/path/to/js1"></script>
<script src="/path/to/js4"></script>""",
        )

    def test_media_inheritance_extends(self):
        # A widget can explicitly enable full media inheritance by specifying
        # 'extend=True'.
        """
        Tests the media inheritance when a subclass extends the media of its parent.

        This tests the ability of a widget to inherit media (css and js) from its parent
        class and extend it with its own media definitions. The test ensures that the
        media from the parent class is properly included in the output, and that any
        duplicates are handled correctly. The extend parameter in the Media class
        allows the subclass to build upon the media definitions of its parent, rather
        than replacing them entirely.
        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget11(MyWidget1):
            class Media:
                extend = True
                css = {"all": ("/path/to/css3", "path/to/css1")}
                js = ("/path/to/js1", "/path/to/js4")

        w11 = MyWidget11()
        self.assertEqual(
            str(w11.media),
            """<link href="/path/to/css3" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" media="all" rel="stylesheet">
<link href="/path/to/css2" media="all" rel="stylesheet">
<script src="/path/to/js1"></script>
<script src="http://media.other.com/path/to/js2"></script>
<script src="/path/to/js4"></script>
<script src="https://secure.other.com/path/to/js3"></script>""",
        )

    def test_media_inheritance_single_type(self):
        # A widget can enable inheritance of one media type by specifying
        # extend as a tuple.
        """

        Tests the media inheritance functionality when inheriting from a single parent widget.

        This test case verifies that the media assets (CSS and JavaScript files) from the parent widget are properly inherited and combined with the media assets defined in the child widget.

        The test assesses whether the `extend` attribute is correctly applied, allowing the child widget to extend the media assets of its parent. It also checks that the resulting media assets are correctly rendered as HTML tags.

        The expected outcome is that the child widget's media assets are merged with the parent's assets, resulting in a combined set of CSS and JavaScript files that are rendered as HTML links and script tags.

        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget12(MyWidget1):
            class Media:
                extend = ("css",)
                css = {"all": ("/path/to/css3", "path/to/css1")}
                js = ("/path/to/js1", "/path/to/js4")

        w12 = MyWidget12()
        self.assertEqual(
            str(w12.media),
            """<link href="/path/to/css3" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" media="all" rel="stylesheet">
<link href="/path/to/css2" media="all" rel="stylesheet">
<script src="/path/to/js1"></script>
<script src="/path/to/js4"></script>""",
        )

    def test_multi_media(self):
        ###############################################################
        # Multi-media handling for CSS
        ###############################################################

        # A widget can define CSS media for multiple output media types
        """

        Tests the rendering of media resources (CSS and JavaScript files) for a custom widget.

        The test verifies that the media resources are correctly ordered and formatted in the output,
        with CSS files rendered as link tags and JavaScript files rendered as script tags.
        The test also ensures that media resources are ordered based on their specified media types,
        with more specific types (e.g. 'screen') appearing before less specific types (e.g. 'screen, print').

        """
        class MultimediaWidget(TextInput):
            class Media:
                css = {
                    "screen, print": ("/file1", "/file2"),
                    "screen": ("/file3",),
                    "print": ("/file4",),
                }
                js = ("/path/to/js1", "/path/to/js4")

        multimedia = MultimediaWidget()
        self.assertEqual(
            str(multimedia.media),
            """<link href="/file4" media="print" rel="stylesheet">
<link href="/file3" media="screen" rel="stylesheet">
<link href="/file1" media="screen, print" rel="stylesheet">
<link href="/file2" media="screen, print" rel="stylesheet">
<script src="/path/to/js1"></script>
<script src="/path/to/js4"></script>""",
        )

    def test_multi_widget(self):
        ###############################################################
        # Multiwidget media handling
        ###############################################################

        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget2(TextInput):
            class Media:
                css = {"all": ("/path/to/css2", "/path/to/css3")}
                js = ("/path/to/js1", "/path/to/js4")

        class MyWidget3(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css3")}
                js = ("/path/to/js1", "/path/to/js4")

        # MultiWidgets have a default media definition that gets all the
        # media from the component widgets
        class MyMultiWidget(MultiWidget):
            def __init__(self, attrs=None):
                """

                Initialize the object with optional attributes and predefined widgets.

                The object is initialized with a selection of predefined widgets, including 
                MyWidget1, MyWidget2, and MyWidget3. Additional attributes can be provided 
                through the attrs parameter to further customize the object's behavior.

                :param attrs: Optional attributes to customize the object's behavior.

                """
                widgets = [MyWidget1, MyWidget2, MyWidget3]
                super().__init__(widgets, attrs)

        mymulti = MyMultiWidget()
        self.assertEqual(
            str(mymulti.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css3" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="/path/to/js4"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

    def test_form_media(self):
        ###############################################################
        # Media processing for forms
        ###############################################################

        """
        Tests the media generation of Django forms.

        Ensures that the `media` attribute of a form is correctly generated based on the media defined in its fields' widgets and the form itself.

        Checks the resulting media HTML for various cases, including:

        - Multiple forms with overlapping media
        - Media defined at the form level and at the widget level
        - Rendering of media in a Django template

        The testing covers both CSS and JavaScript media.
        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                )

        class MyWidget2(TextInput):
            class Media:
                css = {"all": ("/path/to/css2", "/path/to/css3")}
                js = ("/path/to/js1", "/path/to/js4")

        class MyWidget3(TextInput):
            class Media:
                css = {"all": ("path/to/css1", "/path/to/css3")}
                js = ("/path/to/js1", "/path/to/js4")

        # You can ask a form for the media required by its widgets.
        class MyForm(Form):
            field1 = CharField(max_length=20, widget=MyWidget1())
            field2 = CharField(max_length=20, widget=MyWidget2())

        f1 = MyForm()
        self.assertEqual(
            str(f1.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css3" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="/path/to/js4"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # Form media can be combined to produce a single media definition.
        class AnotherForm(Form):
            field3 = CharField(max_length=20, widget=MyWidget3())

        f2 = AnotherForm()
        self.assertEqual(
            str(f1.media + f2.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css3" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="/path/to/js4"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # Forms can also define media, following the same rules as widgets.
        class FormWithMedia(Form):
            field1 = CharField(max_length=20, widget=MyWidget1())
            field2 = CharField(max_length=20, widget=MyWidget2())

            class Media:
                js = ("/some/form/javascript",)
                css = {"all": ("/some/form/css",)}

        f3 = FormWithMedia()
        self.assertEqual(
            str(f3.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/some/form/css" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css3" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="/some/form/javascript"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="/path/to/js4"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>',
        )

        # Media works in templates
        self.assertEqual(
            Template("{{ form.media.js }}{{ form.media.css }}").render(
                Context({"form": f3})
            ),
            '<script src="/path/to/js1"></script>\n'
            '<script src="/some/form/javascript"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="/path/to/js4"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>'
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/some/form/css" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css3" media="all" rel="stylesheet">',
        )

    def test_html_safe(self):
        media = Media(css={"all": ["/path/to/css"]}, js=["/path/to/js"])
        self.assertTrue(hasattr(Media, "__html__"))
        self.assertEqual(str(media), media.__html__())

    def test_merge(self):
        test_values = (
            (([1, 2], [3, 4]), [1, 3, 2, 4]),
            (([1, 2], [2, 3]), [1, 2, 3]),
            (([2, 3], [1, 2]), [1, 2, 3]),
            (([1, 3], [2, 3]), [1, 2, 3]),
            (([1, 2], [1, 3]), [1, 2, 3]),
            (([1, 2], [3, 2]), [1, 3, 2]),
            (([1, 2], [1, 2]), [1, 2]),
            (
                [[1, 2], [1, 3], [2, 3], [5, 7], [5, 6], [6, 7, 9], [8, 9]],
                [1, 5, 8, 2, 6, 3, 7, 9],
            ),
            ((), []),
            (([1, 2],), [1, 2]),
        )
        for lists, expected in test_values:
            with self.subTest(lists=lists):
                self.assertEqual(Media.merge(*lists), expected)

    def test_merge_warning(self):
        """
        Tests the merge functionality of Media objects when duplicate media files are detected in an opposite order, verifying that a RuntimeWarning is raised with the expected message. The test ensures that despite the warning, the merge operation returns the correct result.
        """
        msg = "Detected duplicate Media files in an opposite order: [1, 2], [2, 1]"
        with self.assertWarnsMessage(RuntimeWarning, msg):
            self.assertEqual(Media.merge([1, 2], [2, 1], None), [1, 2])

    def test_merge_js_three_way(self):
        """
        The relative order of scripts is preserved in a three-way merge.
        """
        widget1 = Media(js=["color-picker.js"])
        widget2 = Media(js=["text-editor.js"])
        widget3 = Media(
            js=["text-editor.js", "text-editor-extras.js", "color-picker.js"]
        )
        merged = widget1 + widget2 + widget3
        self.assertEqual(
            merged._js, ["text-editor.js", "text-editor-extras.js", "color-picker.js"]
        )

    def test_merge_js_three_way2(self):
        # The merge prefers to place 'c' before 'b' and 'g' before 'h' to
        # preserve the original order. The preference 'c'->'b' is overridden by
        # widget3's media, but 'g'->'h' survives in the final ordering.
        """
        Tests the three-way merge of JavaScript files between multiple Media objects.

        This test case verifies that the Media class correctly merges JavaScript files 
        when adding multiple Media objects together, ensuring that the resulting 
        Media object contains a deduplicated list of JavaScript files.

        The merge is tested with three Media objects containing different sets of 
        JavaScript files, and the test asserts that the resulting list of JavaScript 
        files is as expected, with no duplicates and including all files from the 
        original Media objects.
        """
        widget1 = Media(js=["a", "c", "f", "g", "k"])
        widget2 = Media(js=["a", "b", "f", "h", "k"])
        widget3 = Media(js=["b", "c", "f", "k"])
        merged = widget1 + widget2 + widget3
        self.assertEqual(merged._js, ["a", "b", "c", "f", "g", "h", "k"])

    def test_merge_css_three_way(self):
        widget1 = Media(css={"screen": ["c.css"], "all": ["d.css", "e.css"]})
        widget2 = Media(css={"screen": ["a.css"]})
        widget3 = Media(css={"screen": ["a.css", "b.css", "c.css"], "all": ["e.css"]})
        widget4 = Media(css={"all": ["d.css", "e.css"], "screen": ["c.css"]})
        merged = widget1 + widget2
        # c.css comes before a.css because widget1 + widget2 establishes this
        # order.
        self.assertEqual(
            merged._css, {"screen": ["c.css", "a.css"], "all": ["d.css", "e.css"]}
        )
        merged += widget3
        # widget3 contains an explicit ordering of c.css and a.css.
        self.assertEqual(
            merged._css,
            {"screen": ["a.css", "b.css", "c.css"], "all": ["d.css", "e.css"]},
        )
        # Media ordering does not matter.
        merged = widget1 + widget4
        self.assertEqual(merged._css, {"screen": ["c.css"], "all": ["d.css", "e.css"]})

    def test_add_js_deduplication(self):
        """
        Tests the addition of Media objects with JavaScript files to ensure deduplication.

        The function checks that when two Media objects are added together, their JavaScript files are merged and duplicates are removed.
        It also verifies that the order of the files is preserved and that a warning is raised when duplicate files are detected in a different order.

        If the same JavaScript files are present in both Media objects but in a different order, the function checks that a RuntimeWarning is raised to indicate the presence of duplicate files.
        The goal of this test is to ensure that the Media class correctly handles the addition of JavaScript files from multiple sources and provides a clear warning when duplicate files are found in an unexpected order.
        """
        widget1 = Media(js=["a", "b", "c"])
        widget2 = Media(js=["a", "b"])
        widget3 = Media(js=["a", "c", "b"])
        merged = widget1 + widget1
        self.assertEqual(merged._js_lists, [["a", "b", "c"]])
        self.assertEqual(merged._js, ["a", "b", "c"])
        merged = widget1 + widget2
        self.assertEqual(merged._js_lists, [["a", "b", "c"], ["a", "b"]])
        self.assertEqual(merged._js, ["a", "b", "c"])
        # Lists with items in a different order are preserved when added.
        merged = widget1 + widget3
        self.assertEqual(merged._js_lists, [["a", "b", "c"], ["a", "c", "b"]])
        msg = (
            "Detected duplicate Media files in an opposite order: "
            "['a', 'b', 'c'], ['a', 'c', 'b']"
        )
        with self.assertWarnsMessage(RuntimeWarning, msg):
            merged._js

    def test_add_css_deduplication(self):
        """
        Tests the addition of Media objects with CSS files, ensuring deduplication and correct handling of ordering.

        The addition of Media objects results in a merged Media object that combines the CSS files from the original objects.
        In case of duplicate CSS files, they are automatically deduplicated to prevent multiple inclusions.
        The function also verifies that the order of CSS files is preserved and that a warning is raised when duplicate files are detected in an opposite order.

        The following scenarios are tested:
        - Merging of identical Media objects
        - Merging of Media objects with different CSS files
        - Merging of Media objects with duplicate CSS files in the same and opposite orders

        The resulting merged Media object is checked for correctness of its CSS lists and files.
        A warning is expected when duplicate CSS files are detected in an opposite order.

        """
        widget1 = Media(css={"screen": ["a.css"], "all": ["b.css"]})
        widget2 = Media(css={"screen": ["c.css"]})
        widget3 = Media(css={"screen": ["a.css"], "all": ["b.css", "c.css"]})
        widget4 = Media(css={"screen": ["a.css"], "all": ["c.css", "b.css"]})
        merged = widget1 + widget1
        self.assertEqual(merged._css_lists, [{"screen": ["a.css"], "all": ["b.css"]}])
        self.assertEqual(merged._css, {"screen": ["a.css"], "all": ["b.css"]})
        merged = widget1 + widget2
        self.assertEqual(
            merged._css_lists,
            [
                {"screen": ["a.css"], "all": ["b.css"]},
                {"screen": ["c.css"]},
            ],
        )
        self.assertEqual(merged._css, {"screen": ["a.css", "c.css"], "all": ["b.css"]})
        merged = widget3 + widget4
        # Ordering within lists is preserved.
        self.assertEqual(
            merged._css_lists,
            [
                {"screen": ["a.css"], "all": ["b.css", "c.css"]},
                {"screen": ["a.css"], "all": ["c.css", "b.css"]},
            ],
        )
        msg = (
            "Detected duplicate Media files in an opposite order: "
            "['b.css', 'c.css'], ['c.css', 'b.css']"
        )
        with self.assertWarnsMessage(RuntimeWarning, msg):
            merged._css

    def test_add_empty(self):
        media = Media(css={"screen": ["a.css"]}, js=["a"])
        empty_media = Media()
        merged = media + empty_media
        self.assertEqual(merged._css_lists, [{"screen": ["a.css"]}])
        self.assertEqual(merged._js_lists, [["a"]])


@html_safe
class Asset:
    def __init__(self, path):
        self.path = path

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and self.path == other.path) or (
            other.__class__ == str and self.path == other
        )

    def __hash__(self):
        return hash(self.path)

    def __str__(self):
        return self.absolute_path(self.path)

    def absolute_path(self, path):
        """
        Given a relative or absolute path to a static asset, return an absolute
        path. An absolute path will be returned unchanged while a relative path
        will be passed to django.templatetags.static.static().
        """
        if path.startswith(("http://", "https://", "/")):
            return path
        return static(path)

    def __repr__(self):
        return f"{self.path!r}"


class CSS(Asset):
    def __init__(self, path, medium):
        """

        Initializes a new instance of the class.

        :param path: The path associated with this instance.
        :param medium: The medium associated with this instance.

        This method sets up the basic properties of the class, including the path and medium, 
        which are used throughout the class. The path is inherited from the parent class, 
        while the medium is specific to this instance.

        """
        super().__init__(path)
        self.medium = medium

    def __str__(self):
        path = super().__str__()
        return format_html(
            '<link href="{}" media="{}" rel="stylesheet">',
            self.absolute_path(path),
            self.medium,
        )


class JS(Asset):
    def __init__(self, path, integrity=None):
        """
        Initializes a new instance of the class.

        :param path: The path associated with this instance.
        :param integrity: An optional integrity value, defaults to an empty string if not provided.

        """
        super().__init__(path)
        self.integrity = integrity or ""

    def __str__(self, integrity=None):
        """
        :return: A string representation of the script element, including the source URL and optional integrity attribute.
        :rtype: str
        :description: This method generates a HTML script tag with the specified source URL and integrity attribute, if provided. The resulting string can be used directly in HTML templates to include the script.
        """
        path = super().__str__()
        template = '<script src="{}"%s></script>' % (
            ' integrity="{}"' if self.integrity else "{}"
        )
        return format_html(template, self.absolute_path(path), self.integrity)


@override_settings(
    STATIC_URL="http://media.example.com/static/",
)
class FormsMediaObjectTestCase(SimpleTestCase):
    """Media handling when media are objects instead of raw strings."""

    def test_construction(self):
        """
        Test the construction of a Media object, verifying that it correctly handles CSS and JavaScript resources, 
        including getPathToxss and JavaScripts from different sources, and properly encodes them into HTML strings.
        The test checks both the string representation of the Media object, which should produce valid HTML tags for 
        the CSS and JavaScript resources, and the repr representation, which should provide a human-readable 
        summary of the Media object's contents.
        """
        m = Media(
            css={"all": (CSS("path/to/css1", "all"), CSS("/path/to/css2", "all"))},
            js=(
                JS("/path/to/js1"),
                JS("http://media.other.com/path/to/js2"),
                JS(
                    "https://secure.other.com/path/to/js3",
                    integrity="9d947b87fdeb25030d56d01f7aa75800",
                ),
            ),
        )
        self.assertEqual(
            str(m),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3" '
            'integrity="9d947b87fdeb25030d56d01f7aa75800"></script>',
        )
        self.assertEqual(
            repr(m),
            "Media(css={'all': ['path/to/css1', '/path/to/css2']}, "
            "js=['/path/to/js1', 'http://media.other.com/path/to/js2', "
            "'https://secure.other.com/path/to/js3'])",
        )

    def test_simplest_class(self):
        @html_safe
        """
        Tests that the simplest possible asset class can be used with the Media class.

        This test verifies that an asset class that only defines a string representation
        can be properly rendered as part of a Media object. The test checks that the
        string representation of the Media object matches the expected HTML output.

        The test case uses a simple asset class that generates a script tag referencing
        an external JavaScript file. The resulting Media object is then converted to a
        string and compared to the expected output to ensure correctness.
        """
        class SimpleJS:
            """The simplest possible asset class."""

            def __str__(self):
                return '<script src="https://example.org/asset.js" rel="stylesheet">'

        m = Media(js=(SimpleJS(),))
        self.assertEqual(
            str(m),
            '<script src="https://example.org/asset.js" rel="stylesheet">',
        )

    def test_combine_media(self):
        """
        Tests the combination of media from two widgets, ensuring that CSS and JavaScript files are correctly concatenated and rendered as HTML tags. The test verifies that duplicate files are included only once and that the order of inclusion is preserved. It also checks the correct rendering of media files with different protocols (HTTP, HTTPS) and integrity attributes (SRI).
        """
        class MyWidget1(TextInput):
            class Media:
                css = {"all": (CSS("path/to/css1", "all"), "/path/to/css2")}
                js = (
                    "/path/to/js1",
                    "http://media.other.com/path/to/js2",
                    "https://secure.other.com/path/to/js3",
                    JS("/path/to/js4", integrity="9d947b87fdeb25030d56d01f7aa75800"),
                )

        class MyWidget2(TextInput):
            class Media:
                css = {"all": (CSS("/path/to/css2", "all"), "/path/to/css3")}
                js = (JS("/path/to/js1"), "/path/to/js4")

        w1 = MyWidget1()
        w2 = MyWidget2()
        self.assertEqual(
            str(w1.media + w2.media),
            '<link href="http://media.example.com/static/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<link href="/path/to/css3" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>\n'
            '<script src="/path/to/js4" integrity="9d947b87fdeb25030d56d01f7aa75800">'
            "</script>",
        )

    def test_media_deduplication(self):
        # The deduplication doesn't only happen at the point of merging two or
        # more media objects.
        """
        Tests the deduplication of media assets, such as CSS and JavaScript files.

        Ensures that when multiple identical media assets are added, only one instance is included in the output.

        Checks that the resulting string representation of the media object contains the expected deduplicated media assets.
        """
        media = Media(
            css={
                "all": (
                    CSS("/path/to/css1", "all"),
                    CSS("/path/to/css1", "all"),
                    "/path/to/css1",
                )
            },
            js=(JS("/path/to/js1"), JS("/path/to/js1"), "/path/to/js1"),
        )
        self.assertEqual(
            str(media),
            '<link href="/path/to/css1" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>',
        )
