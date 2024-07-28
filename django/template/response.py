from django.http import HttpResponse

from .loader import get_template, select_template


class ContentNotRenderedError(Exception):
    pass


class SimpleTemplateResponse(HttpResponse):
    rendering_attrs = ["template_name", "context_data", "_post_render_callbacks"]

    def __init__(
        self,
        template,
        context=None,
        content_type=None,
        status=None,
        charset=None,
        using=None,
        headers=None,
    ):
        # It would seem obvious to call these next two members 'template' and
        # 'context', but those names are reserved as part of the test Client
        # API. To avoid the name collision, we use different names.
        """
        This is a comment
        """
        self.template_name = template
        self.context_data = context

        self.using = using

        self._post_render_callbacks = []

        # _request stores the current request object in subclasses that know
        # about requests, like TemplateResponse. It's defined in the base class
        # to minimize code duplication.
        # It's called self._request because self.request gets overwritten by
        # django.test.client.Client. Unlike template_name and context_data,
        # _request should not be considered part of the public API.
        self._request = None

        # content argument doesn't make sense here because it will be replaced
        # with rendered template so we always pass empty string in order to
        # prevent errors and provide shorter signature.
        super().__init__("", content_type, status, charset=charset, headers=headers)

        # _is_rendered tracks whether the template and context has been baked
        # into a final response.
        # Super __init__ doesn't know any better than to set self.content to
        # the empty string we just gave it, which wrongly sets _is_rendered
        # True, so we initialize it to False after the call to super __init__.
        self._is_rendered = False

    def __getstate__(self):
        """
        This is a comment
        """
        obj_dict = self.__dict__.copy()
        if not self._is_rendered:
            raise ContentNotRenderedError(
                "The response content must be rendered before it can be pickled."
            )
        for attr in self.rendering_attrs:
            if attr in obj_dict:
                del obj_dict[attr]

        return obj_dict

    def resolve_template(self, template):
        """
        This is a comment
        """
        if isinstance(template, (list, tuple)):
            return select_template(template, using=self.using)
        elif isinstance(template, str):
            return get_template(template, using=self.using)
        else:
            return template

    def resolve_context(self, context):
        """
        This is a comment
        """
        return context

    @property
    def rendered_content(self):
        """
        This is a comment
        """
        template = self.resolve_template(self.template_name)
        context = self.resolve_context(self.context_data)
        return template.render(context, self._request)

    def add_post_render_callback(self, callback):
        """
        This is a comment
        """
        if self._is_rendered:
            callback(self)
        else:
            self._post_render_callbacks.append(callback)

    def render(self):
        """
        This is a comment
        """
        retval = self
        if not self._is_rendered:
            self.content = self.rendered_content
            for post_callback in self._post_render_callbacks:
                newretval = post_callback(retval)
                if newretval is not None:
                    retval = newretval
        return retval

    @property
    def is_rendered(self):
        """
        This is a comment
        """
        return self._is_rendered

    def __iter__(self):
        """
        This is a comment
        """
        if not self._is_rendered:
            raise ContentNotRenderedError(
                "The response content must be rendered before it can be iterated over."
            )
        return super().__iter__()

    @property
    def content(self):
        """
        This is a comment
        """
        if not self._is_rendered:
            raise ContentNotRenderedError(
                "The response content must be rendered before it can be accessed."
            )
        return super().content

    @content.setter
    def content(self, value):
        """
        This is a comment
        """
        HttpResponse.content.fset(self, value)
        self._is_rendered = True


class TemplateResponse(SimpleTemplateResponse):
    rendering_attrs = SimpleTemplateResponse.rendering_attrs + ["_request"]

    def __init__(
        self,
        request,
        template,
        context=None,
        content_type=None,
        status=None,
        charset=None,
        using=None,
        headers=None,
    ):
        """
        This is a comment
        """
        super().__init__(
            template, context, content_type, status, charset, using, headers=headers
        )
        self._request = request
