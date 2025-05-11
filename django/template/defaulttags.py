"""Default tags used by the template system, available to all templates."""

import re
import sys
import warnings
from collections import namedtuple
from collections.abc import Iterable
from datetime import datetime
from itertools import cycle as itertools_cycle
from itertools import groupby

from django.conf import settings
from django.utils import timezone
from django.utils.html import conditional_escape, escape, format_html
from django.utils.lorem_ipsum import paragraphs, words
from django.utils.safestring import mark_safe

from .base import (
    BLOCK_TAG_END,
    BLOCK_TAG_START,
    COMMENT_TAG_END,
    COMMENT_TAG_START,
    FILTER_SEPARATOR,
    SINGLE_BRACE_END,
    SINGLE_BRACE_START,
    VARIABLE_ATTRIBUTE_SEPARATOR,
    VARIABLE_TAG_END,
    VARIABLE_TAG_START,
    Node,
    NodeList,
    TemplateSyntaxError,
    VariableDoesNotExist,
    kwarg_re,
    render_value_in_context,
    token_kwargs,
)
from .context import Context
from .defaultfilters import date
from .library import Library
from .smartif import IfParser, Literal

register = Library()


class AutoEscapeControlNode(Node):
    """Implement the actions of the autoescape tag."""

    def __init__(self, setting, nodelist):
        self.setting = setting
        self.nodelist = nodelist

    def render(self, context):
        """

        Renders the node list within the given context, applying autoescaping settings as specified by the node.

        The function temporarily overrides the context's autoescape setting, renders the node list, and then restores the original setting.
        If autoescaping is enabled, the rendered output is marked as safe. Otherwise, the output is returned as is.

        """
        old_setting = context.autoescape
        context.autoescape = self.setting
        output = self.nodelist.render(context)
        context.autoescape = old_setting
        if self.setting:
            return mark_safe(output)
        else:
            return output


class CommentNode(Node):
    child_nodelists = ()

    def render(self, context):
        return ""


class CsrfTokenNode(Node):
    child_nodelists = ()

    def render(self, context):
        """
        Renders a CSRF token field based on the provided context.

        Returns a hidden input field containing the CSRF token if available in the context,
        otherwise returns an empty string. If the context is missing the CSRF token during
        debug mode, a warning is raised to indicate a potential configuration issue.
        """
        csrf_token = context.get("csrf_token")
        if csrf_token:
            if csrf_token == "NOTPROVIDED":
                return format_html("")
            else:
                return format_html(
                    '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
                    csrf_token,
                )
        else:
            # It's very probable that the token is missing because of
            # misconfiguration, so we raise a warning
            if settings.DEBUG:
                warnings.warn(
                    "A {% csrf_token %} was used in a template, but the context "
                    "did not provide the value.  This is usually caused by not "
                    "using RequestContext."
                )
            return ""


class CycleNode(Node):
    def __init__(self, cyclevars, variable_name=None, silent=False):
        self.cyclevars = cyclevars
        self.variable_name = variable_name
        self.silent = silent

    def render(self, context):
        """
        Render a value from a cycle of values, updating the context with the rendered value if a variable name is specified.
        """
        if self not in context.render_context:
            # First time the node is rendered in template
            context.render_context[self] = itertools_cycle(self.cyclevars)
        cycle_iter = context.render_context[self]
        value = next(cycle_iter).resolve(context)
        if self.variable_name:
            context.set_upward(self.variable_name, value)
        if self.silent:
            return ""
        return render_value_in_context(value, context)

    def reset(self, context):
        """
        Reset the cycle iteration back to the beginning.
        """
        context.render_context[self] = itertools_cycle(self.cyclevars)


class DebugNode(Node):
    def render(self, context):
        """

        Renders the current context for debugging purposes.

        When not in debug mode, an empty string is returned.
        Otherwise, it formats and escapes the context values and the loaded modules as a string, making it easier to inspect and debug the current state.

        """
        if not settings.DEBUG:
            return ""

        from pprint import pformat

        output = [escape(pformat(val)) for val in context]
        output.append("\n\n")
        output.append(escape(pformat(sys.modules)))
        return "".join(output)


class FilterNode(Node):
    def __init__(self, filter_expr, nodelist):
        self.filter_expr = filter_expr
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        # Apply filters.
        with context.push(var=output):
            return self.filter_expr.resolve(context)


class FirstOfNode(Node):
    def __init__(self, variables, asvar=None):
        self.vars = variables
        self.asvar = asvar

    def render(self, context):
        """
        Renders the first non-empty value of the variables in the given context.

        The rendered value is either returned directly or stored in the context under a specified key if :attr:`asvar` is set.

        :param context: The context to resolve the variables in
        :return: The rendered value or an empty string if :attr:`asvar` is set
        """
        first = ""
        for var in self.vars:
            value = var.resolve(context, ignore_failures=True)
            if value:
                first = render_value_in_context(value, context)
                break
        if self.asvar:
            context[self.asvar] = first
            return ""
        return first


class ForNode(Node):
    child_nodelists = ("nodelist_loop", "nodelist_empty")

    def __init__(
        self, loopvars, sequence, is_reversed, nodelist_loop, nodelist_empty=None
    ):
        """


        Initializes a loop construct.

        :param loopvars: Loop variables to be used during iteration
        :param sequence: The sequence to be iterated over
        :param is_reversed: Flag indicating whether the sequence is reversed
        :param nodelist_loop: List of nodes to be executed during each iteration
        :param nodelist_empty: Optional list of nodes to be executed when the sequence is empty, defaults to an empty NodeList

        """
        self.loopvars = loopvars
        self.sequence = sequence
        self.is_reversed = is_reversed
        self.nodelist_loop = nodelist_loop
        if nodelist_empty is None:
            self.nodelist_empty = NodeList()
        else:
            self.nodelist_empty = nodelist_empty

    def __repr__(self):
        reversed_text = " reversed" if self.is_reversed else ""
        return "<%s: for %s in %s, tail_len: %d%s>" % (
            self.__class__.__name__,
            ", ".join(self.loopvars),
            self.sequence,
            len(self.nodelist_loop),
            reversed_text,
        )

    def render(self, context):
        """

        Render a for loop in a template, iterating over a sequence of values and rendering a specified template for each item.

        The loop context includes various counters and flags (e.g. counter, counter0, first, last) that can be used in the template.
        If the loop has multiple variables, the values are unpacked into each variable, otherwise a single variable is used.
        If the sequence is empty, an alternative template is rendered.

        """
        if "forloop" in context:
            parentloop = context["forloop"]
        else:
            parentloop = {}
        with context.push():
            values = self.sequence.resolve(context, ignore_failures=True)
            if values is None:
                values = []
            if not hasattr(values, "__len__"):
                values = list(values)
            len_values = len(values)
            if len_values < 1:
                return self.nodelist_empty.render(context)
            nodelist = []
            if self.is_reversed:
                values = reversed(values)
            num_loopvars = len(self.loopvars)
            unpack = num_loopvars > 1
            # Create a forloop value in the context.  We'll update counters on each
            # iteration just below.
            loop_dict = context["forloop"] = {"parentloop": parentloop}
            for i, item in enumerate(values):
                # Shortcuts for current loop iteration number.
                loop_dict["counter0"] = i
                loop_dict["counter"] = i + 1
                # Reverse counter iteration numbers.
                loop_dict["revcounter"] = len_values - i
                loop_dict["revcounter0"] = len_values - i - 1
                # Boolean values designating first and last times through loop.
                loop_dict["first"] = i == 0
                loop_dict["last"] = i == len_values - 1

                pop_context = False
                if unpack:
                    # If there are multiple loop variables, unpack the item into
                    # them.
                    try:
                        len_item = len(item)
                    except TypeError:  # not an iterable
                        len_item = 1
                    # Check loop variable count before unpacking
                    if num_loopvars != len_item:
                        raise ValueError(
                            "Need {} values to unpack in for loop; got {}. ".format(
                                num_loopvars, len_item
                            ),
                        )
                    unpacked_vars = dict(zip(self.loopvars, item))
                    pop_context = True
                    context.update(unpacked_vars)
                else:
                    context[self.loopvars[0]] = item

                for node in self.nodelist_loop:
                    nodelist.append(node.render_annotated(context))

                if pop_context:
                    # Pop the loop variables pushed on to the context to avoid
                    # the context ending up in an inconsistent state when other
                    # tags (e.g., include and with) push data to context.
                    context.pop()
        return mark_safe("".join(nodelist))


class IfChangedNode(Node):
    child_nodelists = ("nodelist_true", "nodelist_false")

    def __init__(self, nodelist_true, nodelist_false, *varlist):
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false
        self._varlist = varlist

    def render(self, context):
        # Init state storage
        """
        Renders the node list based on the comparison of the current state and the stored state.

        The function checks if the current state has changed compared to the previous state. If it has, 
        the function updates the state, returns the rendered true node list or a default value. 
        If the state hasn't changed, it returns the rendered false node list if available, otherwise an empty string.
        """
        state_frame = self._get_context_stack_frame(context)
        state_frame.setdefault(self)

        nodelist_true_output = None
        if self._varlist:
            # Consider multiple parameters. This behaves like an OR evaluation
            # of the multiple variables.
            compare_to = [
                var.resolve(context, ignore_failures=True) for var in self._varlist
            ]
        else:
            # The "{% ifchanged %}" syntax (without any variables) compares
            # the rendered output.
            compare_to = nodelist_true_output = self.nodelist_true.render(context)

        if compare_to != state_frame[self]:
            state_frame[self] = compare_to
            # render true block if not already rendered
            return nodelist_true_output or self.nodelist_true.render(context)
        elif self.nodelist_false:
            return self.nodelist_false.render(context)
        return ""

    def _get_context_stack_frame(self, context):
        # The Context object behaves like a stack where each template tag can
        # create a new scope. Find the place where to store the state to detect
        # changes.
        if "forloop" in context:
            # Ifchanged is bound to the local for loop.
            # When there is a loop-in-loop, the state is bound to the inner loop,
            # so it resets when the outer loop continues.
            return context["forloop"]
        else:
            # Using ifchanged outside loops. Effectively this is a no-op
            # because the state is associated with 'self'.
            return context.render_context


class IfNode(Node):
    def __init__(self, conditions_nodelists):
        self.conditions_nodelists = conditions_nodelists

    def __repr__(self):
        return "<%s>" % self.__class__.__name__

    def __iter__(self):
        for _, nodelist in self.conditions_nodelists:
            yield from nodelist

    @property
    def nodelist(self):
        return NodeList(self)

    def render(self, context):
        """

        Renders the first matching nodelist based on the given conditions.

        This method iterates through a list of conditions and corresponding nodelists.
        For each condition, it evaluates the condition in the given context and renders
        the corresponding nodelist if the condition is true. If no conditions match, an
        empty string is returned.

        """
        for condition, nodelist in self.conditions_nodelists:
            if condition is not None:  # if / elif clause
                try:
                    match = condition.eval(context)
                except VariableDoesNotExist:
                    match = None
            else:  # else clause
                match = True

            if match:
                return nodelist.render(context)

        return ""


class LoremNode(Node):
    def __init__(self, count, method, common):
        self.count = count
        self.method = method
        self.common = common

    def render(self, context):
        """
        Renders a specified amount of text based on the provided context.

        Generates a given number of words or paragraphs, formatted accordingly, 
        with the option to wrap paragraphs in HTML tags. 

        The number of text elements to generate is determined by the count resolved 
        from the context, defaulting to 1 if the count cannot be resolved.

        Returns the generated text as a string, separated by newline characters.
        """
        try:
            count = int(self.count.resolve(context))
        except (ValueError, TypeError):
            count = 1
        if self.method == "w":
            return words(count, common=self.common)
        else:
            paras = paragraphs(count, common=self.common)
        if self.method == "p":
            paras = ["<p>%s</p>" % p for p in paras]
        return "\n\n".join(paras)


GroupedResult = namedtuple("GroupedResult", ["grouper", "list"])


class RegroupNode(Node):
    def __init__(self, target, expression, var_name):
        self.target = target
        self.expression = expression
        self.var_name = var_name

    def resolve_expression(self, obj, context):
        # This method is called for each object in self.target. See regroup()
        # for the reason why we temporarily put the object in the context.
        context[self.var_name] = obj
        return self.expression.resolve(context, ignore_failures=True)

    def render(self, context):
        """
        **:param context: The rendering context
        :rtype: str
        Renders the target objects, grouping them by a dynamically resolved key and storing the result in the context variable specified by :attr:`var_name`.**
        """
        obj_list = self.target.resolve(context, ignore_failures=True)
        if obj_list is None:
            # target variable wasn't found in context; fail silently.
            context[self.var_name] = []
            return ""
        # List of dictionaries in the format:
        # {'grouper': 'key', 'list': [list of contents]}.
        context[self.var_name] = [
            GroupedResult(grouper=key, list=list(val))
            for key, val in groupby(
                obj_list, lambda obj: self.resolve_expression(obj, context)
            )
        ]
        return ""


class LoadNode(Node):
    child_nodelists = ()

    def render(self, context):
        return ""


class NowNode(Node):
    def __init__(self, format_string, asvar=None):
        self.format_string = format_string
        self.asvar = asvar

    def render(self, context):
        """
        Renders the current date based on the specified format string.

        Returns the formatted date as a string, unless the `asvar` attribute is set,
        in which case it assigns the formatted date to the given variable in the context
        and returns an empty string.
        """
        tzinfo = timezone.get_current_timezone() if settings.USE_TZ else None
        formatted = date(datetime.now(tz=tzinfo), self.format_string)

        if self.asvar:
            context[self.asvar] = formatted
            return ""
        else:
            return formatted


class ResetCycleNode(Node):
    def __init__(self, node):
        self.node = node

    def render(self, context):
        self.node.reset(context)
        return ""


class SpacelessNode(Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        from django.utils.html import strip_spaces_between_tags

        return strip_spaces_between_tags(self.nodelist.render(context).strip())


class TemplateTagNode(Node):
    mapping = {
        "openblock": BLOCK_TAG_START,
        "closeblock": BLOCK_TAG_END,
        "openvariable": VARIABLE_TAG_START,
        "closevariable": VARIABLE_TAG_END,
        "openbrace": SINGLE_BRACE_START,
        "closebrace": SINGLE_BRACE_END,
        "opencomment": COMMENT_TAG_START,
        "closecomment": COMMENT_TAG_END,
    }

    def __init__(self, tagtype):
        self.tagtype = tagtype

    def render(self, context):
        return self.mapping.get(self.tagtype, "")


class URLNode(Node):
    child_nodelists = ()

    def __init__(self, view_name, args, kwargs, asvar):
        self.view_name = view_name
        self.args = args
        self.kwargs = kwargs
        self.asvar = asvar

    def __repr__(self):
        return "<%s view_name='%s' args=%s kwargs=%s as=%s>" % (
            self.__class__.__qualname__,
            self.view_name,
            repr(self.args),
            repr(self.kwargs),
            repr(self.asvar),
        )

    def render(self, context):
        """

        Renders a URL using Django's reverse function with provided view name, arguments, and keyword arguments.

        The function takes into account the current application and handles cases where it is not provided.
        If the URL cannot be reversed, it raises an exception unless an 'asvar' variable is provided.
        The rendered URL can be either returned directly or stored in the context under the 'asvar' key.

        :param context: The template context
        :return: The rendered URL or an empty string if 'asvar' is provided

        """
        from django.urls import NoReverseMatch, reverse

        args = [arg.resolve(context) for arg in self.args]
        kwargs = {k: v.resolve(context) for k, v in self.kwargs.items()}
        view_name = self.view_name.resolve(context)
        try:
            current_app = context.request.current_app
        except AttributeError:
            try:
                current_app = context.request.resolver_match.namespace
            except AttributeError:
                current_app = None
        # Try to look up the URL. If it fails, raise NoReverseMatch unless the
        # {% url ... as var %} construct is used, in which case return nothing.
        url = ""
        try:
            url = reverse(view_name, args=args, kwargs=kwargs, current_app=current_app)
        except NoReverseMatch:
            if self.asvar is None:
                raise

        if self.asvar:
            context[self.asvar] = url
            return ""
        else:
            if context.autoescape:
                url = conditional_escape(url)
            return url


class VerbatimNode(Node):
    def __init__(self, content):
        self.content = content

    def render(self, context):
        return self.content


class WidthRatioNode(Node):
    def __init__(self, val_expr, max_expr, max_width, asvar=None):
        self.val_expr = val_expr
        self.max_expr = max_expr
        self.max_width = max_width
        self.asvar = asvar

    def render(self, context):
        """

        Calculate and render a width ratio based on provided values.

        :param context: The template context to resolve values from.
        :returns: The calculated width ratio as a string, or an empty string if errors occur.
        :raises TemplateSyntaxError: If the final argument is not a number.

        """
        try:
            value = self.val_expr.resolve(context)
            max_value = self.max_expr.resolve(context)
            max_width = int(self.max_width.resolve(context))
        except VariableDoesNotExist:
            return ""
        except (ValueError, TypeError):
            raise TemplateSyntaxError("widthratio final argument must be a number")
        try:
            value = float(value)
            max_value = float(max_value)
            ratio = (value / max_value) * max_width
            result = str(round(ratio))
        except ZeroDivisionError:
            result = "0"
        except (ValueError, TypeError, OverflowError):
            result = ""

        if self.asvar:
            context[self.asvar] = result
            return ""
        else:
            return result


class WithNode(Node):
    def __init__(self, var, name, nodelist, extra_context=None):
        self.nodelist = nodelist
        # var and name are legacy attributes, being left in case they are used
        # by third-party subclasses of this Node.
        self.extra_context = extra_context or {}
        if name:
            self.extra_context[name] = var

    def __repr__(self):
        return "<%s>" % self.__class__.__name__

    def render(self, context):
        values = {key: val.resolve(context) for key, val in self.extra_context.items()}
        with context.push(**values):
            return self.nodelist.render(context)


@register.tag
def autoescape(parser, token):
    """

    Enable or disable autoescaping of template content within a block.

    This tag takes a single argument, either 'on' or 'off', to control the autoescape behavior.
    It parses the content of the block until it encounters an 'endautoescape' tag.
    The autoescape behavior is then applied to the parsed content based on the specified argument.

    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    args = token.contents.split()
    if len(args) != 2:
        raise TemplateSyntaxError("'autoescape' tag requires exactly one argument.")
    arg = args[1]
    if arg not in ("on", "off"):
        raise TemplateSyntaxError("'autoescape' argument should be 'on' or 'off'")
    nodelist = parser.parse(("endautoescape",))
    parser.delete_first_token()
    return AutoEscapeControlNode((arg == "on"), nodelist)


@register.tag
def comment(parser, token):
    """
    Ignore everything between ``{% comment %}`` and ``{% endcomment %}``.
    """
    parser.skip_past("endcomment")
    return CommentNode()


@register.tag
def cycle(parser, token):
    """
    Cycle among the given strings each time this tag is encountered, often used within loops to alternate between different values, such as CSS classes or colors. Can also be used outside of loops by giving a unique name to the cycle values and referencing them on subsequent calls. Supports an optional \"silent\" flag to prevent the cycle declaration from returning a value.
    """
    # Note: This returns the exact same node on each {% cycle name %} call;
    # that is, the node object returned from {% cycle a b c as name %} and the
    # one returned from {% cycle name %} are the exact same object. This
    # shouldn't cause problems (heh), but if it does, now you know.
    #
    # Ugly hack warning: This stuffs the named template dict into parser so
    # that names are only unique within each template (as opposed to using
    # a global variable, which would make cycle names have to be unique across
    # *all* templates.
    #
    # It keeps the last node in the parser to be able to reset it with
    # {% resetcycle %}.

    args = token.split_contents()

    if len(args) < 2:
        raise TemplateSyntaxError("'cycle' tag requires at least two arguments")

    if len(args) == 2:
        # {% cycle foo %} case.
        name = args[1]
        if not hasattr(parser, "_named_cycle_nodes"):
            raise TemplateSyntaxError(
                "No named cycles in template. '%s' is not defined" % name
            )
        if name not in parser._named_cycle_nodes:
            raise TemplateSyntaxError("Named cycle '%s' does not exist" % name)
        return parser._named_cycle_nodes[name]

    as_form = False

    if len(args) > 4:
        # {% cycle ... as foo [silent] %} case.
        if args[-3] == "as":
            if args[-1] != "silent":
                raise TemplateSyntaxError(
                    "Only 'silent' flag is allowed after cycle's name, not '%s'."
                    % args[-1]
                )
            as_form = True
            silent = True
            args = args[:-1]
        elif args[-2] == "as":
            as_form = True
            silent = False

    if as_form:
        name = args[-1]
        values = [parser.compile_filter(arg) for arg in args[1:-2]]
        node = CycleNode(values, name, silent=silent)
        if not hasattr(parser, "_named_cycle_nodes"):
            parser._named_cycle_nodes = {}
        parser._named_cycle_nodes[name] = node
    else:
        values = [parser.compile_filter(arg) for arg in args[1:]]
        node = CycleNode(values)
    parser._last_cycle_node = node
    return node


@register.tag
def csrf_token(parser, token):
    return CsrfTokenNode()


@register.tag
def debug(parser, token):
    """
    Output a whole load of debugging information, including the current
    context and imported modules.

    Sample usage::

        <pre>
            {% debug %}
        </pre>
    """
    return DebugNode()


@register.tag("filter")
def do_filter(parser, token):
    """
    Apply filters to a block of template content, allowing for chaining and argument passing, to modify the output.
    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    _, rest = token.contents.split(None, 1)
    filter_expr = parser.compile_filter("var|%s" % (rest))
    for func, unused in filter_expr.filters:
        filter_name = getattr(func, "_filter_name", None)
        if filter_name in ("escape", "safe"):
            raise TemplateSyntaxError(
                '"filter %s" is not permitted.  Use the "autoescape" tag instead.'
                % filter_name
            )
    nodelist = parser.parse(("endfilter",))
    parser.delete_first_token()
    return FilterNode(filter_expr, nodelist)


@register.tag
def firstof(parser, token):
    """
    Output the first variable passed that is not False, allowing for a fallback value and optional assignment to a variable.
    """
    bits = token.split_contents()[1:]
    asvar = None
    if not bits:
        raise TemplateSyntaxError("'firstof' statement requires at least one argument")

    if len(bits) >= 2 and bits[-2] == "as":
        asvar = bits[-1]
        bits = bits[:-2]
    return FirstOfNode([parser.compile_filter(bit) for bit in bits], asvar)


@register.tag("for")
def do_for(parser, token):
    """
    Loop over each item in an array, allowing iteration over sequences and setting variables for loop tracking.

    Can be used to display lists of items, iterate over dictionary key-value pairs, and more. Supports reversing iteration order, empty result handling, and loop tracking variables. 

    Tracking variables available within the loop include counters, first and last iteration indicators, and nested loop tracking. The optional ``{% empty %}`` clause allows customization for empty result sets.
    """
    bits = token.split_contents()
    if len(bits) < 4:
        raise TemplateSyntaxError(
            "'for' statements should have at least four words: %s" % token.contents
        )

    is_reversed = bits[-1] == "reversed"
    in_index = -3 if is_reversed else -2
    if bits[in_index] != "in":
        raise TemplateSyntaxError(
            "'for' statements should use the format"
            " 'for x in y': %s" % token.contents
        )

    invalid_chars = frozenset((" ", '"', "'", FILTER_SEPARATOR))
    loopvars = re.split(r" *, *", " ".join(bits[1:in_index]))
    for var in loopvars:
        if not var or not invalid_chars.isdisjoint(var):
            raise TemplateSyntaxError(
                "'for' tag received an invalid argument: %s" % token.contents
            )

    sequence = parser.compile_filter(bits[in_index + 1])
    nodelist_loop = parser.parse(
        (
            "empty",
            "endfor",
        )
    )
    token = parser.next_token()
    if token.contents == "empty":
        nodelist_empty = parser.parse(("endfor",))
        parser.delete_first_token()
    else:
        nodelist_empty = None
    return ForNode(loopvars, sequence, is_reversed, nodelist_loop, nodelist_empty)


class TemplateLiteral(Literal):
    def __init__(self, value, text):
        self.value = value
        self.text = text  # for better error messages

    def display(self):
        return self.text

    def eval(self, context):
        return self.value.resolve(context, ignore_failures=True)


class TemplateIfParser(IfParser):
    error_class = TemplateSyntaxError

    def __init__(self, parser, *args, **kwargs):
        self.template_parser = parser
        super().__init__(*args, **kwargs)

    def create_var(self, value):
        return TemplateLiteral(self.template_parser.compile_filter(value), value)


@register.tag("if")
def do_if(parser, token):
    """
    Evaluates a condition or a series of conditions and renders a block of template code based on the result. Conditions can be combined using logical operators like \"and\", \"or\", and \"not\", and can also include comparisons and \"in\" checks. The function can handle multiple elif clauses and an optional else clause.
    """
    # {% if ... %}
    bits = token.split_contents()[1:]
    condition = TemplateIfParser(parser, bits).parse()
    nodelist = parser.parse(("elif", "else", "endif"))
    conditions_nodelists = [(condition, nodelist)]
    token = parser.next_token()

    # {% elif ... %} (repeatable)
    while token.contents.startswith("elif"):
        bits = token.split_contents()[1:]
        condition = TemplateIfParser(parser, bits).parse()
        nodelist = parser.parse(("elif", "else", "endif"))
        conditions_nodelists.append((condition, nodelist))
        token = parser.next_token()

    # {% else %} (optional)
    if token.contents == "else":
        nodelist = parser.parse(("endif",))
        conditions_nodelists.append((None, nodelist))
        token = parser.next_token()

    # {% endif %}
    if token.contents != "endif":
        raise TemplateSyntaxError(
            'Malformed template tag at line {}: "{}"'.format(
                token.lineno, token.contents
            )
        )

    return IfNode(conditions_nodelists)


@register.tag
def ifchanged(parser, token):
    """
    Check if a value has changed from the last iteration of a loop.

    The ``{% ifchanged %}`` block tag is used within a loop. It has two
    possible uses.

    1. Check its own rendered contents against its previous state and only
       displays the content if it has changed.

    2. If given one or more variables, check whether any variable has changed.
       This allows for displaying certain content only when a specific condition
       changes.

    It can be used to reduce repetition in loop outputs by only showing
    content when it changes, making the output more concise and easier to read.
    """
    bits = token.split_contents()
    nodelist_true = parser.parse(("else", "endifchanged"))
    token = parser.next_token()
    if token.contents == "else":
        nodelist_false = parser.parse(("endifchanged",))
        parser.delete_first_token()
    else:
        nodelist_false = NodeList()
    values = [parser.compile_filter(bit) for bit in bits[1:]]
    return IfChangedNode(nodelist_true, nodelist_false, *values)


def find_library(parser, name):
    try:
        return parser.libraries[name]
    except KeyError:
        raise TemplateSyntaxError(
            "'%s' is not a registered tag library. Must be one of:\n%s"
            % (
                name,
                "\n".join(sorted(parser.libraries)),
            ),
        )


def load_from_library(library, label, names):
    """
    Retrieves a subset of tags and filters from a specified library, 
    raising an error if any requested item does not exist.
    """
    subset = Library()
    for name in names:
        found = False
        if name in library.tags:
            found = True
            subset.tags[name] = library.tags[name]
        if name in library.filters:
            found = True
            subset.filters[name] = library.filters[name]
        if found is False:
            raise TemplateSyntaxError(
                "'%s' is not a valid tag or filter in tag library '%s'"
                % (
                    name,
                    label,
                ),
            )
    return subset


@register.tag
def load(parser, token):
    """
    Register a custom template tag library into the parser for use within templates, allowing access to custom tags and filters.\"\"\"

    Alternatively: 
    \"\"\"Loads custom template tags into the parser, enabling their use within templates, either by loading entire libraries or specific tags/filters from a library.
    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    bits = token.contents.split()
    if len(bits) >= 4 and bits[-2] == "from":
        # from syntax is used; load individual tags from the library
        name = bits[-1]
        lib = find_library(parser, name)
        subset = load_from_library(lib, name, bits[1:-2])
        parser.add_library(subset)
    else:
        # one or more libraries are specified; load and add them to the parser
        for name in bits[1:]:
            lib = find_library(parser, name)
            parser.add_library(lib)
    return LoadNode()


@register.tag
def lorem(parser, token):
    """
    Create random Latin text useful for providing test data in templates.

    Usage format::

        {% lorem [count] [method] [random] %}

    ``count`` is a number (or variable) containing the number of paragraphs or
    words to generate (default is 1).

    ``method`` is either ``w`` for words, ``p`` for HTML paragraphs, ``b`` for
    plain-text paragraph blocks (default is ``b``).

    ``random`` is the word ``random``, which if given, does not use the common
    paragraph (starting \"Lorem ipsum dolor sit amet, consectetuer...\").

    Examples:

    * ``{% lorem %}`` outputs the common \"lorem ipsum\" paragraph
    * ``{% lorem 3 p %}`` outputs the common \"lorem ipsum\" paragraph
      and two random paragraphs each wrapped in HTML ``<p>`` tags
    * ``{% lorem 2 w random %}`` outputs two random latin words
    """
    bits = list(token.split_contents())
    tagname = bits[0]
    # Random bit
    common = bits[-1] != "random"
    if not common:
        bits.pop()
    # Method bit
    if bits[-1] in ("w", "p", "b"):
        method = bits.pop()
    else:
        method = "b"
    # Count bit
    if len(bits) > 1:
        count = bits.pop()
    else:
        count = "1"
    count = parser.compile_filter(count)
    if len(bits) != 1:
        raise TemplateSyntaxError("Incorrect format for %r tag" % tagname)
    return LoremNode(count, method, common)


@register.tag
def now(parser, token):
    """
    Display the current date and time, formatted according to a given string, using a format compatible with PHP's date() function.
    """
    bits = token.split_contents()
    asvar = None
    if len(bits) == 4 and bits[-2] == "as":
        asvar = bits[-1]
        bits = bits[:-2]
    if len(bits) != 2:
        raise TemplateSyntaxError("'now' statement takes one argument")
    format_string = bits[1][1:-1]
    return NowNode(format_string, asvar)


@register.simple_tag(name="querystring", takes_context=True)
def querystring(context, query_dict=None, **kwargs):
    """
    Add, remove, and change parameters of a query string.
    Allows modifying the query string by adding, removing, or changing its parameters.
    Supports pagination and custom query dictionaries.
    """
    if query_dict is None:
        query_dict = context.request.GET
    query_dict = query_dict.copy()
    for key, value in kwargs.items():
        if value is None:
            if key in query_dict:
                del query_dict[key]
        elif isinstance(value, Iterable) and not isinstance(value, str):
            query_dict.setlist(key, value)
        else:
            query_dict[key] = value
    if not query_dict:
        return ""
    query_string = query_dict.urlencode()
    return f"?{query_string}"


@register.tag
def regroup(parser, token):
    """
    def regroup(parser, token):
        \"\"\"
        Regroups a list of objects by a common attribute.

        Takes a list of objects and groups them by a specified attribute, returning a list of objects with 'grouper' and 'list' attributes.
        The 'grouper' attribute contains the item that was grouped by, and the 'list' attribute contains the list of objects that share that 'grouper'.
        The input list must be sorted by the key being grouped by.

    """
    bits = token.split_contents()
    if len(bits) != 6:
        raise TemplateSyntaxError("'regroup' tag takes five arguments")
    target = parser.compile_filter(bits[1])
    if bits[2] != "by":
        raise TemplateSyntaxError("second argument to 'regroup' tag must be 'by'")
    if bits[4] != "as":
        raise TemplateSyntaxError("next-to-last argument to 'regroup' tag must be 'as'")
    var_name = bits[5]
    # RegroupNode will take each item in 'target', put it in the context under
    # 'var_name', evaluate 'var_name'.'expression' in the current context, and
    # group by the resulting value. After all items are processed, it will
    # save the final result in the context under 'var_name', thus clearing the
    # temporary values. This hack is necessary because the template engine
    # doesn't provide a context-aware equivalent of Python's getattr.
    expression = parser.compile_filter(
        var_name + VARIABLE_ATTRIBUTE_SEPARATOR + bits[3]
    )
    return RegroupNode(target, expression, var_name)


@register.tag
def resetcycle(parser, token):
    """
    Reset a cycle tag in a template.

    If an argument is given, reset the last rendered cycle tag with the matching name; 
    otherwise, reset the last rendered cycle tag, regardless of whether it was named or unnamed.
    """
    args = token.split_contents()

    if len(args) > 2:
        raise TemplateSyntaxError("%r tag accepts at most one argument." % args[0])

    if len(args) == 2:
        name = args[1]
        try:
            return ResetCycleNode(parser._named_cycle_nodes[name])
        except (AttributeError, KeyError):
            raise TemplateSyntaxError("Named cycle '%s' does not exist." % name)
    try:
        return ResetCycleNode(parser._last_cycle_node)
    except AttributeError:
        raise TemplateSyntaxError("No cycles in template.")


@register.tag
def spaceless(parser, token):
    """
    Remove whitespace between HTML tags, including tab and newline characters.

    Example usage::

        {% spaceless %}
            <p>
                <a href="foo/">Foo</a>
            </p>
        {% endspaceless %}

    This example returns this HTML::

        <p><a href="foo/">Foo</a></p>

    Only space between *tags* is normalized -- not space between tags and text.
    In this example, the space around ``Hello`` isn't stripped::

        {% spaceless %}
            <strong>
                Hello
            </strong>
        {% endspaceless %}
    """
    nodelist = parser.parse(("endspaceless",))
    parser.delete_first_token()
    return SpacelessNode(nodelist)


@register.tag
def templatetag(parser, token):
    """
    Output one of the bits used to compose template tags, such as block or variable delimiters, escaping the template system's syntax to display them as literal text. The tag accepts a single argument specifying which template bit to output, including openblock, closeblock, openvariable, closevariable, openbrace, closebrace, opencomment, and closecomment.
    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    bits = token.contents.split()
    if len(bits) != 2:
        raise TemplateSyntaxError("'templatetag' statement takes one argument")
    tag = bits[1]
    if tag not in TemplateTagNode.mapping:
        raise TemplateSyntaxError(
            "Invalid templatetag argument: '%s'."
            " Must be one of: %s" % (tag, list(TemplateTagNode.mapping))
        )
    return TemplateTagNode(tag)


@register.tag
def url(parser, token):
    """
    Return an absolute URL matching the given view with its parameters.

    This template tag allows defining links that aren't tied to a particular URL
    configuration, by providing the view name and its required arguments.

    It supports both positional and keyword arguments, and can also use template
    variables as the view name or URL name.

    The resulting URL will be resolved based on the provided view name and arguments,
    and can be used to create links in templates.

    Example usage:
        {% url \"view_name\" arg1 arg2 %}
        {% url \"view_name\" name1=value1 name2=value2 %}
    """
    bits = token.split_contents()
    if len(bits) < 2:
        raise TemplateSyntaxError(
            "'%s' takes at least one argument, a URL pattern name." % bits[0]
        )
    viewname = parser.compile_filter(bits[1])
    args = []
    kwargs = {}
    asvar = None
    bits = bits[2:]
    if len(bits) >= 2 and bits[-2] == "as":
        asvar = bits[-1]
        bits = bits[:-2]

    for bit in bits:
        match = kwarg_re.match(bit)
        if not match:
            raise TemplateSyntaxError("Malformed arguments to url tag")
        name, value = match.groups()
        if name:
            kwargs[name] = parser.compile_filter(value)
        else:
            args.append(parser.compile_filter(value))

    return URLNode(viewname, args, kwargs, asvar)


@register.tag
def verbatim(parser, token):
    """
    Stop the template engine from rendering the contents of this block tag.

    Usage::

        {% verbatim %}
            {% don't process this %}
        {% endverbatim %}

    You can also designate a specific closing tag block (allowing the
    unrendered use of ``{% endverbatim %}``)::

        {% verbatim myblock %}
            ...
        {% endverbatim myblock %}
    """
    nodelist = parser.parse(("endverbatim",))
    parser.delete_first_token()
    return VerbatimNode(nodelist.render(Context()))


@register.tag
def widthratio(parser, token):
    """
    Calculates the ratio of a given value to a maximum value and applies it to a constant, commonly used for creating bar charts and similar visualizations where a value needs to be proportionally represented. The result can be used directly in a template or captured in a variable for further use.
    """
    bits = token.split_contents()
    if len(bits) == 4:
        tag, this_value_expr, max_value_expr, max_width = bits
        asvar = None
    elif len(bits) == 6:
        tag, this_value_expr, max_value_expr, max_width, as_, asvar = bits
        if as_ != "as":
            raise TemplateSyntaxError(
                "Invalid syntax in widthratio tag. Expecting 'as' keyword"
            )
    else:
        raise TemplateSyntaxError("widthratio takes at least three arguments")

    return WidthRatioNode(
        parser.compile_filter(this_value_expr),
        parser.compile_filter(max_value_expr),
        parser.compile_filter(max_width),
        asvar=asvar,
    )


@register.tag("with")
def do_with(parser, token):
    """
    Adds variables to the template context within a block for caching and easy access, allowing for concise and readable template code.
    """
    bits = token.split_contents()
    remaining_bits = bits[1:]
    extra_context = token_kwargs(remaining_bits, parser, support_legacy=True)
    if not extra_context:
        raise TemplateSyntaxError(
            "%r expected at least one variable assignment" % bits[0]
        )
    if remaining_bits:
        raise TemplateSyntaxError(
            "%r received an invalid token: %r" % (bits[0], remaining_bits[0])
        )
    nodelist = parser.parse(("endwith",))
    parser.delete_first_token()
    return WithNode(None, None, nodelist, extra_context=extra_context)
