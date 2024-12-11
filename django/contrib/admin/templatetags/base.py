from inspect import getfullargspec

from django.template.library import InclusionNode, parse_bits


class InclusionAdminNode(InclusionNode):
    """
    Template tag that allows its template to be overridden per model, per app,
    or globally.
    """

    def __init__(self, parser, token, func, template_name, takes_context=True):
        """

        Initializes a custom template tag.

        This constructor takes several parameters to properly set up the template tag.
        The :param parser: is used to parse the tag's arguments, while the :param token: contains the tag's source code.
        The :param func: to be called when the tag is rendered, and the :param template_name: that identifies this tag.
        The :param takes_context: parameter determines whether the tag takes the current template context as an argument.
        It parses the tag's arguments using the provided parser and function signature, then calls the superclass's constructor to finalize the setup.

        """
        self.template_name = template_name
        params, varargs, varkw, defaults, kwonly, kwonly_defaults, _ = getfullargspec(
            func
        )
        bits = token.split_contents()
        args, kwargs = parse_bits(
            parser,
            bits[1:],
            params,
            varargs,
            varkw,
            defaults,
            kwonly,
            kwonly_defaults,
            takes_context,
            bits[0],
        )
        super().__init__(func, takes_context, args, kwargs, filename=None)

    def render(self, context):
        opts = context["opts"]
        app_label = opts.app_label.lower()
        object_name = opts.model_name
        # Load template for this render call. (Setting self.filename isn't
        # thread-safe.)
        context.render_context[self] = context.template.engine.select_template(
            [
                "admin/%s/%s/%s" % (app_label, object_name, self.template_name),
                "admin/%s/%s" % (app_label, self.template_name),
                "admin/%s" % self.template_name,
            ]
        )
        return super().render(context)
