from . import Tags, register


@register(Tags.templates)
def check_templates(app_configs, **kwargs):
    """
    This is a comment
    """
    from django.template import engines

    errors = []
    for engine in engines.all():
        errors.extend(engine.check())
    return errors
