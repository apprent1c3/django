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

        Checks if the HTML output of a widget matches the expected HTML.

        This function takes a widget, a name, a value, and the expected HTML output.
        It renders the widget using both a Jinja2 renderer (if available) and a Django renderer,
        and then checks if the rendered HTML matches the expected HTML output.

        The comparison can be done in strict or non-strict mode. In strict mode, the
        HTML outputs must match exactly, while in non-strict mode, some HTML differences
        are tolerated.

        Additional keyword arguments can be passed to customize the rendering of the widget.

        Parameters
        ----------
        widget : object
            The widget to render
        name : str
            The name of the widget
        value : str
            The value of the widget
        html : str
            The expected HTML output
        attrs : dict
            Additional attributes to pass to the widget
        strict : bool
            Whether to perform a strict comparison of the HTML outputs
        **kwargs : dict
            Additional keyword arguments to pass to the widget

        Raises
        ------
        AssertionError
            If the rendered HTML output does not match the expected HTML output

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
