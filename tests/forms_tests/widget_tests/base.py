from django.forms.renderers import DjangoTemplates, Jinja2
from django.test import SimpleTestCase

try:
    import jinja2
except ImportError:
    jinja2 = None


class WidgetTest(SimpleTestCase):
    beatles = (("J", "John"), ("P", "Paul"), ("G", "George"), ("R", "Ringo"))

    @classmethod
    def setUpClass(cls):
        """

        Setup class method to initialize templating engines.

        This method sets up instances of Django and Jinja2 templating engines for use in the class.
        The Django templating engine is always initialized, while the Jinja2 templating engine is
        initialized only if the Jinja2 library is available. The initialized renderers are then
        stored in the class's renderers attribute for later use.

        Note: The parent class's setUpClass method is called at the end to ensure proper setup.

        """
        cls.django_renderer = DjangoTemplates()
        cls.jinja2_renderer = Jinja2() if jinja2 else None
        cls.renderers = [cls.django_renderer] + (
            [cls.jinja2_renderer] if cls.jinja2_renderer else []
        )
        super().setUpClass()

    def check_html(
        self, widget, name, value, html="", attrs=None, strict=False, **kwargs
    ):
        """
        Checks the HTML output of a widget rendering process.

        This function takes a widget and its rendering parameters, then compares the resulting HTML output with an expected result. The comparison can be strict or lenient, depending on the value of the `strict` parameter. 

        The comparison is performed with both Jinja2 and Django renderers, allowing for testing of widget rendering across different templating engines. Any additional keyword arguments (`kwargs`) are passed to the widget's rendering method.

        Parameters
        ----------
        widget : object
            The widget to be rendered.
        name : str
            The name of the widget.
        value : object
            The value of the widget.
        html : str, optional
            The expected HTML output.
        attrs : dict, optional
            Additional attributes for the widget.
        strict : bool, optional
            Whether to perform a strict comparison of the HTML output (default is False).
        **kwargs : dict
            Additional keyword arguments for the widget's rendering method.

        The function asserts that the rendered HTML matches the expected output, and will raise an assertion error if a mismatch is found.
        """
        assertEqual = self.assertEqual if strict else self.assertHTMLEqual
        if self.jinja2_renderer:
            output = widget.render(
                name, value, attrs=attrs, renderer=self.jinja2_renderer, **kwargs
            )
            # Django escapes quotes with '&quot;' while Jinja2 uses '&#34;'.
            output = output.replace("&#34;", "&quot;")
            # Django escapes single quotes with '&#x27;' while Jinja2 uses '&#39;'.
            output = output.replace("&#39;", "&#x27;")
            assertEqual(output, html)

        output = widget.render(
            name, value, attrs=attrs, renderer=self.django_renderer, **kwargs
        )
        assertEqual(output, html)
