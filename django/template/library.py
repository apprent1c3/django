from collections.abc import Iterable
from functools import wraps
from importlib import import_module
from inspect import getfullargspec, unwrap

from django.utils.html import conditional_escape

from .base import Node, Template, token_kwargs
from .exceptions import TemplateSyntaxError


class InvalidTemplateLibrary(Exception):
    pass


class Library:
    """
    A class for registering template tags and filters. Compiled filter and
    template tag functions are stored in the filters and tags attributes.
    The filter, simple_tag, and inclusion_tag methods provide a convenient
    way to register callables as tags.
    """

    def __init__(self):
        self.filters = {}
        self.tags = {}

    def tag(self, name=None, compile_function=None):
        """

        Tag a function or retrieve a tag function.

        This method can be used in multiple ways:

        * Without any arguments, it returns the current tag function.
        * With a single string argument, it returns a decorator that tags a function with the given name.
        * With a single callable argument, it tags the given function with a generated name.
        * With both a string name and a compile function, it registers the compile function under the given name.

        The compile function is stored internally and can be retrieved later.

        Args:
            name (str, optional): The name of the tag.
            compile_function (callable, optional): The function to be tagged or registered.

        Returns:
            The tag function, a decorator, or the registered compile function.

        Raises:
            ValueError: If the arguments are not supported.

        """
        if name is None and compile_function is None:
            # @register.tag()
            return self.tag_function
        elif name is not None and compile_function is None:
            if callable(name):
                # @register.tag
                return self.tag_function(name)
            else:
                # @register.tag('somename') or @register.tag(name='somename')
                def dec(func):
                    return self.tag(name, func)

                return dec
        elif name is not None and compile_function is not None:
            # register.tag('somename', somefunc)
            self.tags[name] = compile_function
            return compile_function
        else:
            raise ValueError(
                "Unsupported arguments to Library.tag: (%r, %r)"
                % (name, compile_function),
            )

    def tag_function(self, func):
        self.tags[func.__name__] = func
        return func

    def filter(self, name=None, filter_func=None, **flags):
        """
        Register a callable as a template filter. Example:

        @register.filter
        def lower(value):
            return value.lower()
        """
        if name is None and filter_func is None:
            # @register.filter()
            def dec(func):
                return self.filter_function(func, **flags)

            return dec
        elif name is not None and filter_func is None:
            if callable(name):
                # @register.filter
                return self.filter_function(name, **flags)
            else:
                # @register.filter('somename') or @register.filter(name='somename')
                def dec(func):
                    return self.filter(name, func, **flags)

                return dec
        elif name is not None and filter_func is not None:
            # register.filter('somename', somefunc)
            self.filters[name] = filter_func
            for attr in ("expects_localtime", "is_safe", "needs_autoescape"):
                if attr in flags:
                    value = flags[attr]
                    # set the flag on the filter for FilterExpression.resolve
                    setattr(filter_func, attr, value)
                    # set the flag on the innermost decorated function
                    # for decorators that need it, e.g. stringfilter
                    setattr(unwrap(filter_func), attr, value)
            filter_func._filter_name = name
            return filter_func
        else:
            raise ValueError(
                "Unsupported arguments to Library.filter: (%r, %r)"
                % (name, filter_func),
            )

    def filter_function(self, func, **flags):
        return self.filter(func.__name__, func, **flags)

    def simple_tag(self, func=None, takes_context=None, name=None):
        """
        Register a callable as a compiled template tag. Example:

        @register.simple_tag
        def hello(*args, **kwargs):
            return 'world'
        """

        def dec(func):
            (
                params,
                varargs,
                varkw,
                defaults,
                kwonly,
                kwonly_defaults,
                _,
            ) = getfullargspec(unwrap(func))
            function_name = name or func.__name__

            @wraps(func)
            def compile_func(parser, token):
                """
                Compile a function for use in a templating engine.

                This function takes in a parser and a token, parses the token into arguments and keyword arguments,
                and then returns a SimpleNode object representing the compiled function. The function also supports
                assigning the result to a variable using the 'as' keyword.

                :param parser: The parser object used to parse the token.
                :param token: The token to be compiled.
                :returns: A SimpleNode object representing the compiled function.
                :raises: Exceptions may be raised if the token is invalid or cannot be parsed.
                """
                bits = token.split_contents()[1:]
                target_var = None
                if len(bits) >= 2 and bits[-2] == "as":
                    target_var = bits[-1]
                    bits = bits[:-2]
                args, kwargs = parse_bits(
                    parser,
                    bits,
                    params,
                    varargs,
                    varkw,
                    defaults,
                    kwonly,
                    kwonly_defaults,
                    takes_context,
                    function_name,
                )
                return SimpleNode(func, takes_context, args, kwargs, target_var)

            self.tag(function_name, compile_func)
            return func

        if func is None:
            # @register.simple_tag(...)
            return dec
        elif callable(func):
            # @register.simple_tag
            return dec(func)
        else:
            raise ValueError("Invalid arguments provided to simple_tag")

    def inclusion_tag(self, filename, func=None, takes_context=None, name=None):
        """
        Register a callable as an inclusion tag:

        @register.inclusion_tag('results.html')
        def show_results(poll):
            choices = poll.choice_set.all()
            return {'choices': choices}
        """

        def dec(func):
            (
                params,
                varargs,
                varkw,
                defaults,
                kwonly,
                kwonly_defaults,
                _,
            ) = getfullargspec(unwrap(func))
            function_name = name or func.__name__

            @wraps(func)
            def compile_func(parser, token):
                bits = token.split_contents()[1:]
                args, kwargs = parse_bits(
                    parser,
                    bits,
                    params,
                    varargs,
                    varkw,
                    defaults,
                    kwonly,
                    kwonly_defaults,
                    takes_context,
                    function_name,
                )
                return InclusionNode(
                    func,
                    takes_context,
                    args,
                    kwargs,
                    filename,
                )

            self.tag(function_name, compile_func)
            return func

        return dec


class TagHelperNode(Node):
    """
    Base class for tag helper nodes such as SimpleNode and InclusionNode.
    Manages the positional and keyword arguments to be passed to the decorated
    function.
    """

    def __init__(self, func, takes_context, args, kwargs):
        self.func = func
        self.takes_context = takes_context
        self.args = args
        self.kwargs = kwargs

    def get_resolved_arguments(self, context):
        """

        Resolve function arguments and keyword arguments within a given context.

        This function takes into account whether the function requires context to be passed
        as the first argument. It resolves each argument and keyword argument by calling
        their respective resolve methods with the provided context.

        Returns:
            A tuple containing two elements: a list of resolved positional arguments and
            a dictionary of resolved keyword arguments.

        """
        resolved_args = [var.resolve(context) for var in self.args]
        if self.takes_context:
            resolved_args = [context] + resolved_args
        resolved_kwargs = {k: v.resolve(context) for k, v in self.kwargs.items()}
        return resolved_args, resolved_kwargs


class SimpleNode(TagHelperNode):
    child_nodelists = ()

    def __init__(self, func, takes_context, args, kwargs, target_var):
        super().__init__(func, takes_context, args, kwargs)
        self.target_var = target_var

    def render(self, context):
        resolved_args, resolved_kwargs = self.get_resolved_arguments(context)
        output = self.func(*resolved_args, **resolved_kwargs)
        if self.target_var is not None:
            context[self.target_var] = output
            return ""
        if context.autoescape:
            output = conditional_escape(output)
        return output


class InclusionNode(TagHelperNode):
    def __init__(self, func, takes_context, args, kwargs, filename):
        super().__init__(func, takes_context, args, kwargs)
        self.filename = filename

    def render(self, context):
        """
        Render the specified template and context. Cache the template object
        in render_context to avoid reparsing and loading when used in a for
        loop.
        """
        resolved_args, resolved_kwargs = self.get_resolved_arguments(context)
        _dict = self.func(*resolved_args, **resolved_kwargs)

        t = context.render_context.get(self)
        if t is None:
            if isinstance(self.filename, Template):
                t = self.filename
            elif isinstance(getattr(self.filename, "template", None), Template):
                t = self.filename.template
            elif not isinstance(self.filename, str) and isinstance(
                self.filename, Iterable
            ):
                t = context.template.engine.select_template(self.filename)
            else:
                t = context.template.engine.get_template(self.filename)
            context.render_context[self] = t
        new_context = context.new(_dict)
        # Copy across the CSRF token, if present, because inclusion tags are
        # often used for forms, and we need instructions for using CSRF
        # protection to be as simple as possible.
        csrf_token = context.get("csrf_token")
        if csrf_token is not None:
            new_context["csrf_token"] = csrf_token
        return t.render(new_context)


def parse_bits(
    parser,
    bits,
    params,
    varargs,
    varkw,
    defaults,
    kwonly,
    kwonly_defaults,
    takes_context,
    name,
):
    """
    Parse bits for template tag helpers simple_tag and inclusion_tag, in
    particular by detecting syntax errors and by extracting positional and
    keyword arguments.
    """
    if takes_context:
        if params and params[0] == "context":
            params = params[1:]
        else:
            raise TemplateSyntaxError(
                "'%s' is decorated with takes_context=True so it must "
                "have a first argument of 'context'" % name
            )
    args = []
    kwargs = {}
    unhandled_params = list(params)
    unhandled_kwargs = [
        kwarg for kwarg in kwonly if not kwonly_defaults or kwarg not in kwonly_defaults
    ]
    for bit in bits:
        # First we try to extract a potential kwarg from the bit
        kwarg = token_kwargs([bit], parser)
        if kwarg:
            # The kwarg was successfully extracted
            param, value = kwarg.popitem()
            if param not in params and param not in kwonly and varkw is None:
                # An unexpected keyword argument was supplied
                raise TemplateSyntaxError(
                    "'%s' received unexpected keyword argument '%s'" % (name, param)
                )
            elif param in kwargs:
                # The keyword argument has already been supplied once
                raise TemplateSyntaxError(
                    "'%s' received multiple values for keyword argument '%s'"
                    % (name, param)
                )
            else:
                # All good, record the keyword argument
                kwargs[str(param)] = value
                if param in unhandled_params:
                    # If using the keyword syntax for a positional arg, then
                    # consume it.
                    unhandled_params.remove(param)
                elif param in unhandled_kwargs:
                    # Same for keyword-only arguments
                    unhandled_kwargs.remove(param)
        else:
            if kwargs:
                raise TemplateSyntaxError(
                    "'%s' received some positional argument(s) after some "
                    "keyword argument(s)" % name
                )
            else:
                # Record the positional argument
                args.append(parser.compile_filter(bit))
                try:
                    # Consume from the list of expected positional arguments
                    unhandled_params.pop(0)
                except IndexError:
                    if varargs is None:
                        raise TemplateSyntaxError(
                            "'%s' received too many positional arguments" % name
                        )
    if defaults is not None:
        # Consider the last n params handled, where n is the
        # number of defaults.
        unhandled_params = unhandled_params[: -len(defaults)]
    if unhandled_params or unhandled_kwargs:
        # Some positional arguments were not supplied
        raise TemplateSyntaxError(
            "'%s' did not receive value(s) for the argument(s): %s"
            % (name, ", ".join("'%s'" % p for p in unhandled_params + unhandled_kwargs))
        )
    return args, kwargs


def import_library(name):
    """
    Load a Library object from a template tag module.
    """
    try:
        module = import_module(name)
    except ImportError as e:
        raise InvalidTemplateLibrary(
            "Invalid template library specified. ImportError raised when "
            "trying to load '%s': %s" % (name, e)
        )
    try:
        return module.register
    except AttributeError:
        raise InvalidTemplateLibrary(
            "Module  %s does not have a variable named 'register'" % name,
        )
