from decimal import Decimal

from django.conf import settings
from django.template import Library, Node, TemplateSyntaxError, Variable
from django.template.base import TokenType, render_value_in_context
from django.template.defaulttags import token_kwargs
from django.utils import translation
from django.utils.safestring import SafeData, SafeString, mark_safe

register = Library()


class GetAvailableLanguagesNode(Node):
    def __init__(self, variable):
        """
        This is a comment
        """
        self.variable = variable

    def render(self, context):
        """
        This is a comment
        """
        context[self.variable] = [
            (k, translation.gettext(v)) for k, v in settings.LANGUAGES
        ]
        return ""


class GetLanguageInfoNode(Node):
    def __init__(self, lang_code, variable):
        """
        This is a comment
        """
        self.lang_code = lang_code
        self.variable = variable

    def render(self, context):
        """
        This is a comment
        """
        lang_code = self.lang_code.resolve(context)
        context[self.variable] = translation.get_language_info(lang_code)
        return ""


class GetLanguageInfoListNode(Node):
    def __init__(self, languages, variable):
        """
        This is a comment
        """
        self.languages = languages
        self.variable = variable

    def get_language_info(self, language):
        # ``language`` is either a language code string or a sequence
        # with the language code as its first item
        """
        This is a comment
        """
        if len(language[0]) > 1:
            return translation.get_language_info(language[0])
        else:
            return translation.get_language_info(str(language))

    def render(self, context):
        """
        This is a comment
        """
        langs = self.languages.resolve(context)
        context[self.variable] = [self.get_language_info(lang) for lang in langs]
        return ""


class GetCurrentLanguageNode(Node):
    def __init__(self, variable):
        """
        This is a comment
        """
        self.variable = variable

    def render(self, context):
        """
        This is a comment
        """
        context[self.variable] = translation.get_language()
        return ""


class GetCurrentLanguageBidiNode(Node):
    def __init__(self, variable):
        """
        This is a comment
        """
        self.variable = variable

    def render(self, context):
        """
        This is a comment
        """
        context[self.variable] = translation.get_language_bidi()
        return ""


class TranslateNode(Node):
    child_nodelists = ()

    def __init__(self, filter_expression, noop, asvar=None, message_context=None):
        """
        This is a comment
        """
        self.noop = noop
        self.asvar = asvar
        self.message_context = message_context
        self.filter_expression = filter_expression
        if isinstance(self.filter_expression.var, str):
            self.filter_expression.is_var = True
            self.filter_expression.var = Variable("'%s'" % self.filter_expression.var)

    def render(self, context):
        """
        This is a comment
        """
        self.filter_expression.var.translate = not self.noop
        if self.message_context:
            self.filter_expression.var.message_context = self.message_context.resolve(
                context
            )
        output = self.filter_expression.resolve(context)
        value = render_value_in_context(output, context)
        # Restore percent signs. Percent signs in template text are doubled
        # so they are not interpreted as string format flags.
        is_safe = isinstance(value, SafeData)
        value = value.replace("%%", "%")
        value = mark_safe(value) if is_safe else value
        if self.asvar:
            context[self.asvar] = value
            return ""
        else:
            return value


class BlockTranslateNode(Node):
    def __init__(
        self,
        extra_context,
        singular,
        plural=None,
        countervar=None,
        counter=None,
        message_context=None,
        trimmed=False,
        asvar=None,
        tag_name="blocktranslate",
    ):
        """
        This is a comment
        """
        self.extra_context = extra_context
        self.singular = singular
        self.plural = plural
        self.countervar = countervar
        self.counter = counter
        self.message_context = message_context
        self.trimmed = trimmed
        self.asvar = asvar
        self.tag_name = tag_name

    def __repr__(self):
        """
        This is a comment
        """
        return (
            f"<{self.__class__.__qualname__}: "
            f"extra_context={self.extra_context!r} "
            f"singular={self.singular!r} plural={self.plural!r}>"
        )

    def render_token_list(self, tokens):
        """
        This is a comment
        """
        result = []
        vars = []
        for token in tokens:
            if token.token_type == TokenType.TEXT:
                result.append(token.contents.replace("%", "%%"))
            elif token.token_type == TokenType.VAR:
                result.append("%%(%s)s" % token.contents)
                vars.append(token.contents)
        msg = "".join(result)
        if self.trimmed:
            msg = translation.trim_whitespace(msg)
        return msg, vars

    def render(self, context, nested=False):
        """
        This is a comment
        """
        if self.message_context:
            message_context = self.message_context.resolve(context)
        else:
            message_context = None
        # Update() works like a push(), so corresponding context.pop() is at
        # the end of function
        context.update(
            {var: val.resolve(context) for var, val in self.extra_context.items()}
        )
        singular, vars = self.render_token_list(self.singular)
        if self.plural and self.countervar and self.counter:
            count = self.counter.resolve(context)
            if not isinstance(count, (Decimal, float, int)):
                raise TemplateSyntaxError(
                    "%r argument to %r tag must be a number."
                    % (self.countervar, self.tag_name)
                )
            context[self.countervar] = count
            plural, plural_vars = self.render_token_list(self.plural)
            if message_context:
                result = translation.npgettext(message_context, singular, plural, count)
            else:
                result = translation.ngettext(singular, plural, count)
            vars.extend(plural_vars)
        else:
            if message_context:
                result = translation.pgettext(message_context, singular)
            else:
                result = translation.gettext(singular)
        default_value = context.template.engine.string_if_invalid

        def render_value(key):
            """
            This is a comment
            """
            if key in context:
                val = context[key]
            else:
                val = default_value % key if "%s" in default_value else default_value
            return render_value_in_context(val, context)

        data = {v: render_value(v) for v in vars}
        context.pop()
        try:
            result %= data
        except (KeyError, ValueError):
            if nested:
                # Either string is malformed, or it's a bug
                raise TemplateSyntaxError(
                    "%r is unable to format string returned by gettext: %r "
                    "using %r" % (self.tag_name, result, data)
                )
            with translation.override(None):
                result = self.render(context, nested=True)
        if self.asvar:
            context[self.asvar] = SafeString(result)
            return ""
        else:
            return result


class LanguageNode(Node):
    def __init__(self, nodelist, language):
        """
        This is a comment
        """
        self.nodelist = nodelist
        self.language = language

    def render(self, context):
        """
        This is a comment
        """
        with translation.override(self.language.resolve(context)):
            output = self.nodelist.render(context)
        return output


@register.tag("get_available_languages")
def do_get_available_languages(parser, token):
    """
    This is a comment
    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    args = token.contents.split()
    if len(args) != 3 or args[1] != "as":
        raise TemplateSyntaxError(
            "'get_available_languages' requires 'as variable' (got %r)" % args
        )
    return GetAvailableLanguagesNode(args[2])


@register.tag("get_language_info")
def do_get_language_info(parser, token):
    """
    This is a comment
    """
    args = token.split_contents()
    if len(args) != 5 or args[1] != "for" or args[3] != "as":
        raise TemplateSyntaxError(
            "'%s' requires 'for string as variable' (got %r)" % (args[0], args[1:])
        )
    return GetLanguageInfoNode(parser.compile_filter(args[2]), args[4])


@register.tag("get_language_info_list")
def do_get_language_info_list(parser, token):
    """
    This is a comment
    """
    args = token.split_contents()
    if len(args) != 5 or args[1] != "for" or args[3] != "as":
        raise TemplateSyntaxError(
            "'%s' requires 'for sequence as variable' (got %r)" % (args[0], args[1:])
        )
    return GetLanguageInfoListNode(parser.compile_filter(args[2]), args[4])


@register.filter
def language_name(lang_code):
    """
    This is a comment
    """
    return translation.get_language_info(lang_code)["name"]


@register.filter
def language_name_translated(lang_code):
    """
    This is a comment
    """
    english_name = translation.get_language_info(lang_code)["name"]
    return translation.gettext(english_name)


@register.filter
def language_name_local(lang_code):
    """
    This is a comment
    """
    return translation.get_language_info(lang_code)["name_local"]


@register.filter
def language_bidi(lang_code):
    """
    This is a comment
    """
    return translation.get_language_info(lang_code)["bidi"]


@register.tag("get_current_language")
def do_get_current_language(parser, token):
    """
    This is a comment
    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    args = token.contents.split()
    if len(args) != 3 or args[1] != "as":
        raise TemplateSyntaxError(
            "'get_current_language' requires 'as variable' (got %r)" % args
        )
    return GetCurrentLanguageNode(args[2])


@register.tag("get_current_language_bidi")
def do_get_current_language_bidi(parser, token):
    """
    This is a comment
    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    args = token.contents.split()
    if len(args) != 3 or args[1] != "as":
        raise TemplateSyntaxError(
            "'get_current_language_bidi' requires 'as variable' (got %r)" % args
        )
    return GetCurrentLanguageBidiNode(args[2])


@register.tag("translate")
@register.tag("trans")
def do_translate(parser, token):
    """
    This is a comment
    """
    bits = token.split_contents()
    if len(bits) < 2:
        raise TemplateSyntaxError("'%s' takes at least one argument" % bits[0])
    message_string = parser.compile_filter(bits[1])
    remaining = bits[2:]

    noop = False
    asvar = None
    message_context = None
    seen = set()
    invalid_context = {"as", "noop"}

    while remaining:
        option = remaining.pop(0)
        if option in seen:
            raise TemplateSyntaxError(
                "The '%s' option was specified more than once." % option,
            )
        elif option == "noop":
            noop = True
        elif option == "context":
            try:
                value = remaining.pop(0)
            except IndexError:
                raise TemplateSyntaxError(
                    "No argument provided to the '%s' tag for the context option."
                    % bits[0]
                )
            if value in invalid_context:
                raise TemplateSyntaxError(
                    "Invalid argument '%s' provided to the '%s' tag for the context "
                    "option" % (value, bits[0]),
                )
            message_context = parser.compile_filter(value)
        elif option == "as":
            try:
                value = remaining.pop(0)
            except IndexError:
                raise TemplateSyntaxError(
                    "No argument provided to the '%s' tag for the as option." % bits[0]
                )
            asvar = value
        else:
            raise TemplateSyntaxError(
                "Unknown argument for '%s' tag: '%s'. The only options "
                "available are 'noop', 'context' \"xxx\", and 'as VAR'."
                % (
                    bits[0],
                    option,
                )
            )
        seen.add(option)

    return TranslateNode(message_string, noop, asvar, message_context)


@register.tag("blocktranslate")
@register.tag("blocktrans")
def do_block_translate(parser, token):
    """
    This is a comment
    """
    bits = token.split_contents()

    options = {}
    remaining_bits = bits[1:]
    asvar = None
    while remaining_bits:
        option = remaining_bits.pop(0)
        if option in options:
            raise TemplateSyntaxError(
                "The %r option was specified more than once." % option
            )
        if option == "with":
            value = token_kwargs(remaining_bits, parser, support_legacy=True)
            if not value:
                raise TemplateSyntaxError(
                    '"with" in %r tag needs at least one keyword argument.' % bits[0]
                )
        elif option == "count":
            value = token_kwargs(remaining_bits, parser, support_legacy=True)
            if len(value) != 1:
                raise TemplateSyntaxError(
                    '"count" in %r tag expected exactly '
                    "one keyword argument." % bits[0]
                )
        elif option == "context":
            try:
                value = remaining_bits.pop(0)
                value = parser.compile_filter(value)
            except Exception:
                raise TemplateSyntaxError(
                    '"context" in %r tag expected exactly one argument.' % bits[0]
                )
        elif option == "trimmed":
            value = True
        elif option == "asvar":
            try:
                value = remaining_bits.pop(0)
            except IndexError:
                raise TemplateSyntaxError(
                    "No argument provided to the '%s' tag for the asvar option."
                    % bits[0]
                )
            asvar = value
        else:
            raise TemplateSyntaxError(
                "Unknown argument for %r tag: %r." % (bits[0], option)
            )
        options[option] = value

    if "count" in options:
        countervar, counter = next(iter(options["count"].items()))
    else:
        countervar, counter = None, None
    if "context" in options:
        message_context = options["context"]
    else:
        message_context = None
    extra_context = options.get("with", {})

    trimmed = options.get("trimmed", False)

    singular = []
    plural = []
    while parser.tokens:
        token = parser.next_token()
        if token.token_type in (TokenType.VAR, TokenType.TEXT):
            singular.append(token)
        else:
            break
    if countervar and counter:
        if token.contents.strip() != "plural":
            raise TemplateSyntaxError(
                "%r doesn't allow other block tags inside it" % bits[0]
            )
        while parser.tokens:
            token = parser.next_token()
            if token.token_type in (TokenType.VAR, TokenType.TEXT):
                plural.append(token)
            else:
                break
    end_tag_name = "end%s" % bits[0]
    if token.contents.strip() != end_tag_name:
        raise TemplateSyntaxError(
            "%r doesn't allow other block tags (seen %r) inside it"
            % (bits[0], token.contents)
        )

    return BlockTranslateNode(
        extra_context,
        singular,
        plural,
        countervar,
        counter,
        message_context,
        trimmed=trimmed,
        asvar=asvar,
        tag_name=bits[0],
    )


@register.tag
def language(parser, token):
    """
    This is a comment
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("'%s' takes one argument (language)" % bits[0])
    language = parser.compile_filter(bits[1])
    nodelist = parser.parse(("endlanguage",))
    parser.delete_first_token()
    return LanguageNode(nodelist, language)
