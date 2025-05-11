from . import engines
from .exceptions import TemplateDoesNotExist


def get_template(template_name, using=None):
    """
    Loads and returns a template based on the provided name, utilizing the specified template engine if given, otherwise iterating through available engines until a match is found.
    """
    chain = []
    engines = _engine_list(using)
    for engine in engines:
        try:
            return engine.get_template(template_name)
        except TemplateDoesNotExist as e:
            chain.append(e)

    raise TemplateDoesNotExist(template_name, chain=chain)


def select_template(template_name_list, using=None):
    """
    Loads and returns the first existing template from a given list of template names, attempting each in order. If none of the templates exist, it raises a TemplateDoesNotExist exception.
    """
    if isinstance(template_name_list, str):
        raise TypeError(
            "select_template() takes an iterable of template names but got a "
            "string: %r. Use get_template() if you want to load a single "
            "template by name." % template_name_list
        )

    chain = []
    engines = _engine_list(using)
    for template_name in template_name_list:
        for engine in engines:
            try:
                return engine.get_template(template_name)
            except TemplateDoesNotExist as e:
                chain.append(e)

    if template_name_list:
        raise TemplateDoesNotExist(", ".join(template_name_list), chain=chain)
    else:
        raise TemplateDoesNotExist("No template names provided")


def render_to_string(template_name, context=None, request=None, using=None):
    """
    Render a Django template as a string.

    :param template_name: Name of the template to render, or a list of template names to try in order
    :param context: Dictionary of context variables to use when rendering the template
    :param request: The current request object, used to access request-specific data
    :param using: The template engine to use for rendering

    :return: The rendered template as a string
    """
    if isinstance(template_name, (list, tuple)):
        template = select_template(template_name, using=using)
    else:
        template = get_template(template_name, using=using)
    return template.render(context, request)


def _engine_list(using=None):
    return engines.all() if using is None else [engines[using]]
