from . import Tags, register


@register(Tags.templates)
def check_templates(app_configs, **kwargs):
    """
    Checks all registered template engines for errors and returns a list of any issues found.
    """
    from django.template import engines

    errors = []
    for engine in engines.all():
        errors.extend(engine.check())
    return errors
