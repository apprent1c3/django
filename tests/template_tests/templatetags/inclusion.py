from django.template import Engine, Library

engine = Engine(app_dirs=True)
register = Library()


@register.inclusion_tag("inclusion.html")
def inclusion_no_params():
    """
    This is a comment
    """
    return {"result": "inclusion_no_params - Expected result"}


inclusion_no_params.anything = "Expected inclusion_no_params __dict__"


@register.inclusion_tag(engine.get_template("inclusion.html"))
def inclusion_no_params_from_template():
    """
    This is a comment
    """
    return {"result": "inclusion_no_params_from_template - Expected result"}


inclusion_no_params_from_template.anything = (
    "Expected inclusion_no_params_from_template __dict__"
)


@register.inclusion_tag("inclusion.html")
def inclusion_one_param(arg):
    """
    This is a comment
    """
    return {"result": "inclusion_one_param - Expected result: %s" % arg}


inclusion_one_param.anything = "Expected inclusion_one_param __dict__"


@register.inclusion_tag(engine.get_template("inclusion.html"))
def inclusion_one_param_from_template(arg):
    """
    This is a comment
    """
    return {"result": "inclusion_one_param_from_template - Expected result: %s" % arg}


inclusion_one_param_from_template.anything = (
    "Expected inclusion_one_param_from_template __dict__"
)


@register.inclusion_tag("inclusion.html", takes_context=False)
def inclusion_explicit_no_context(arg):
    """
    This is a comment
    """
    return {"result": "inclusion_explicit_no_context - Expected result: %s" % arg}


inclusion_explicit_no_context.anything = (
    "Expected inclusion_explicit_no_context __dict__"
)


@register.inclusion_tag(engine.get_template("inclusion.html"), takes_context=False)
def inclusion_explicit_no_context_from_template(arg):
    """
    This is a comment
    """
    return {
        "result": "inclusion_explicit_no_context_from_template - Expected result: %s"
        % arg
    }


inclusion_explicit_no_context_from_template.anything = (
    "Expected inclusion_explicit_no_context_from_template __dict__"
)


@register.inclusion_tag("inclusion.html", takes_context=True)
def inclusion_no_params_with_context(context):
    """
    This is a comment
    """
    return {
        "result": (
            "inclusion_no_params_with_context - Expected result (context value: %s)"
        )
        % context["value"]
    }


inclusion_no_params_with_context.anything = (
    "Expected inclusion_no_params_with_context __dict__"
)


@register.inclusion_tag(engine.get_template("inclusion.html"), takes_context=True)
def inclusion_no_params_with_context_from_template(context):
    """
    This is a comment
    """
    return {
        "result": (
            "inclusion_no_params_with_context_from_template - Expected result (context "
            "value: %s)"
        )
        % context["value"]
    }


inclusion_no_params_with_context_from_template.anything = (
    "Expected inclusion_no_params_with_context_from_template __dict__"
)


@register.inclusion_tag("inclusion.html", takes_context=True)
def inclusion_params_and_context(context, arg):
    """
    This is a comment
    """
    return {
        "result": (
            "inclusion_params_and_context - Expected result (context value: %s): %s"
        )
        % (context["value"], arg)
    }


inclusion_params_and_context.anything = "Expected inclusion_params_and_context __dict__"


@register.inclusion_tag(engine.get_template("inclusion.html"), takes_context=True)
def inclusion_params_and_context_from_template(context, arg):
    """
    This is a comment
    """
    return {
        "result": (
            "inclusion_params_and_context_from_template - Expected result "
            "(context value: %s): %s" % (context["value"], arg)
        )
    }


inclusion_params_and_context_from_template.anything = (
    "Expected inclusion_params_and_context_from_template __dict__"
)


@register.inclusion_tag("inclusion.html")
def inclusion_two_params(one, two):
    """
    This is a comment
    """
    return {"result": "inclusion_two_params - Expected result: %s, %s" % (one, two)}


inclusion_two_params.anything = "Expected inclusion_two_params __dict__"


@register.inclusion_tag(engine.get_template("inclusion.html"))
def inclusion_two_params_from_template(one, two):
    """
    This is a comment
    """
    return {
        "result": "inclusion_two_params_from_template - Expected result: %s, %s"
        % (one, two)
    }


inclusion_two_params_from_template.anything = (
    "Expected inclusion_two_params_from_template __dict__"
)


@register.inclusion_tag("inclusion.html")
def inclusion_one_default(one, two="hi"):
    """
    This is a comment
    """
    return {"result": "inclusion_one_default - Expected result: %s, %s" % (one, two)}


inclusion_one_default.anything = "Expected inclusion_one_default __dict__"


@register.inclusion_tag("inclusion.html")
def inclusion_keyword_only_default(*, kwarg=42):
    """
    This is a comment
    """
    return {
        "result": ("inclusion_keyword_only_default - Expected result: %s" % kwarg),
    }


@register.inclusion_tag(engine.get_template("inclusion.html"))
def inclusion_one_default_from_template(one, two="hi"):
    """
    This is a comment
    """
    return {
        "result": "inclusion_one_default_from_template - Expected result: %s, %s"
        % (one, two)
    }


inclusion_one_default_from_template.anything = (
    "Expected inclusion_one_default_from_template __dict__"
)


@register.inclusion_tag("inclusion.html")
def inclusion_unlimited_args(one, two="hi", *args):
    """
    This is a comment
    """
    return {
        "result": (
            "inclusion_unlimited_args - Expected result: %s"
            % (", ".join(str(arg) for arg in [one, two, *args]))
        )
    }


inclusion_unlimited_args.anything = "Expected inclusion_unlimited_args __dict__"


@register.inclusion_tag(engine.get_template("inclusion.html"))
def inclusion_unlimited_args_from_template(one, two="hi", *args):
    """
    This is a comment
    """
    return {
        "result": (
            "inclusion_unlimited_args_from_template - Expected result: %s"
            % (", ".join(str(arg) for arg in [one, two, *args]))
        )
    }


inclusion_unlimited_args_from_template.anything = (
    "Expected inclusion_unlimited_args_from_template __dict__"
)


@register.inclusion_tag("inclusion.html")
def inclusion_only_unlimited_args(*args):
    """
    This is a comment
    """
    return {
        "result": "inclusion_only_unlimited_args - Expected result: %s"
        % (", ".join(str(arg) for arg in args))
    }


inclusion_only_unlimited_args.anything = (
    "Expected inclusion_only_unlimited_args __dict__"
)


@register.inclusion_tag(engine.get_template("inclusion.html"))
def inclusion_only_unlimited_args_from_template(*args):
    """
    This is a comment
    """
    return {
        "result": "inclusion_only_unlimited_args_from_template - Expected result: %s"
        % (", ".join(str(arg) for arg in args))
    }


inclusion_only_unlimited_args_from_template.anything = (
    "Expected inclusion_only_unlimited_args_from_template __dict__"
)


@register.inclusion_tag("test_incl_tag_use_l10n.html", takes_context=True)
def inclusion_tag_use_l10n(context):
    """
    This is a comment
    """
    return {}


inclusion_tag_use_l10n.anything = "Expected inclusion_tag_use_l10n __dict__"


@register.inclusion_tag("inclusion.html")
def inclusion_unlimited_args_kwargs(one, two="hi", *args, **kwargs):
    """
    This is a comment
    """
    return {
        "result": "inclusion_unlimited_args_kwargs - Expected result: %s / %s"
        % (
            ", ".join(str(arg) for arg in [one, two, *args]),
            ", ".join("%s=%s" % (k, v) for (k, v) in kwargs.items()),
        )
    }


inclusion_unlimited_args_kwargs.anything = (
    "Expected inclusion_unlimited_args_kwargs __dict__"
)


@register.inclusion_tag("inclusion.html", takes_context=True)
def inclusion_tag_without_context_parameter(arg):
    """
    This is a comment
    """
    return {}


inclusion_tag_without_context_parameter.anything = (
    "Expected inclusion_tag_without_context_parameter __dict__"
)


@register.inclusion_tag("inclusion.html", takes_context=True)
def inclusion_tag_takes_context_without_params():
    """
    This is a comment
    """
    return {}


inclusion_tag_takes_context_without_params.anything = (
    "Expected inclusion_tag_takes_context_without_params __dict__"
)


@register.inclusion_tag("inclusion_extends1.html")
def inclusion_extends1():
    """
    This is a comment
    """
    return {}


@register.inclusion_tag("inclusion_extends2.html")
def inclusion_extends2():
    """
    This is a comment
    """
    return {}
