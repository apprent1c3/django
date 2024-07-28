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
        """
        This is a comment
        """
        self.setting = setting
        self.nodelist = nodelist

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        return ""


class CsrfTokenNode(Node):
    child_nodelists = ()

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.cyclevars = cyclevars
        self.variable_name = variable_name
        self.silent = silent

    def render(self, context):
        """
        This is a comment
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
        This is a comment
        """
        context.render_context[self] = itertools_cycle(self.cyclevars)


class DebugNode(Node):
    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.filter_expr = filter_expr
        self.nodelist = nodelist

    def render(self, context):
        """
        This is a comment
        """
        output = self.nodelist.render(context)
        # Apply filters.
        with context.push(var=output):
            return self.filter_expr.resolve(context)


class FirstOfNode(Node):
    def __init__(self, variables, asvar=None):
        """
        This is a comment
        """
        self.vars = variables
        self.asvar = asvar

    def render(self, context):
        """
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
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
        This is a comment
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
        """
        This is a comment
        """
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false
        self._varlist = varlist

    def render(self, context):
        # Init state storage
        """
        This is a comment
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        self.conditions_nodelists = conditions_nodelists

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s>" % self.__class__.__name__

    def __iter__(self):
        """
        This is a comment
        """
        for _, nodelist in self.conditions_nodelists:
            yield from nodelist

    @property
    def nodelist(self):
        """
        This is a comment
        """
        return NodeList(self)

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.count = count
        self.method = method
        self.common = common

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.target = target
        self.expression = expression
        self.var_name = var_name

    def resolve_expression(self, obj, context):
        # This method is called for each object in self.target. See regroup()
        # for the reason why we temporarily put the object in the context.
        """
        This is a comment
        """
        context[self.var_name] = obj
        return self.expression.resolve(context, ignore_failures=True)

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        return ""


class NowNode(Node):
    def __init__(self, format_string, asvar=None):
        """
        This is a comment
        """
        self.format_string = format_string
        self.asvar = asvar

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.node = node

    def render(self, context):
        """
        This is a comment
        """
        self.node.reset(context)
        return ""


class SpacelessNode(Node):
    def __init__(self, nodelist):
        """
        This is a comment
        """
        self.nodelist = nodelist

    def render(self, context):
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        self.tagtype = tagtype

    def render(self, context):
        """
        This is a comment
        """
        return self.mapping.get(self.tagtype, "")


class URLNode(Node):
    child_nodelists = ()

    def __init__(self, view_name, args, kwargs, asvar):
        """
        This is a comment
        """
        self.view_name = view_name
        self.args = args
        self.kwargs = kwargs
        self.asvar = asvar

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s view_name='%s' args=%s kwargs=%s as=%s>" % (
            self.__class__.__qualname__,
            self.view_name,
            repr(self.args),
            repr(self.kwargs),
            repr(self.asvar),
        )

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.content = content

    def render(self, context):
        """
        This is a comment
        """
        return self.content


class WidthRatioNode(Node):
    def __init__(self, val_expr, max_expr, max_width, asvar=None):
        """
        This is a comment
        """
        self.val_expr = val_expr
        self.max_expr = max_expr
        self.max_width = max_width
        self.asvar = asvar

    def render(self, context):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.nodelist = nodelist
        # var and name are legacy attributes, being left in case they are used
        # by third-party subclasses of this Node.
        self.extra_context = extra_context or {}
        if name:
            self.extra_context[name] = var

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s>" % self.__class__.__name__

    def render(self, context):
        """
        This is a comment
        """
        values = {key: val.resolve(context) for key, val in self.extra_context.items()}
        with context.push(**values):
            return self.nodelist.render(context)


@register.tag
def autoescape(parser, token):
    """
    This is a comment
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
    This is a comment
    """
    parser.skip_past("endcomment")
    return CommentNode()


@register.tag
def cycle(parser, token):
    """
    This is a comment
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
    """
    This is a comment
    """
    return CsrfTokenNode()


@register.tag
def debug(parser, token):
    """
    This is a comment
    """
    return DebugNode()


@register.tag("filter")
def do_filter(parser, token):
    """
    This is a comment
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
    This is a comment
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
    This is a comment
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
        """
        This is a comment
        """
        self.value = value
        self.text = text  # for better error messages

    def display(self):
        """
        This is a comment
        """
        return self.text

    def eval(self, context):
        """
        This is a comment
        """
        return self.value.resolve(context, ignore_failures=True)


class TemplateIfParser(IfParser):
    error_class = TemplateSyntaxError

    def __init__(self, parser, *args, **kwargs):
        """
        This is a comment
        """
        self.template_parser = parser
        super().__init__(*args, **kwargs)

    def create_var(self, value):
        """
        This is a comment
        """
        return TemplateLiteral(self.template_parser.compile_filter(value), value)


@register.tag("if")
def do_if(parser, token):
    """
    This is a comment
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
    This is a comment
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
    """
    This is a comment
    """
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
    This is a comment
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
    This is a comment
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
    This is a comment
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
    This is a comment
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
    This is a comment
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
    This is a comment
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
    This is a comment
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
    This is a comment
    """
    nodelist = parser.parse(("endspaceless",))
    parser.delete_first_token()
    return SpacelessNode(nodelist)


@register.tag
def templatetag(parser, token):
    """
    This is a comment
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
    This is a comment
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
    This is a comment
    """
    nodelist = parser.parse(("endverbatim",))
    parser.delete_first_token()
    return VerbatimNode(nodelist.render(Context()))


@register.tag
def widthratio(parser, token):
    """
    This is a comment
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
    This is a comment
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
