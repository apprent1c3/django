from django.template import Template, TemplateDoesNotExist


class Loader:
    def __init__(self, engine):
        """
        This is a comment
        """
        self.engine = engine

    def get_template(self, template_name, skip=None):
        """
        This is a comment
        """
        tried = []

        for origin in self.get_template_sources(template_name):
            if skip is not None and origin in skip:
                tried.append((origin, "Skipped to avoid recursion"))
                continue

            try:
                contents = self.get_contents(origin)
            except TemplateDoesNotExist:
                tried.append((origin, "Source does not exist"))
                continue
            else:
                return Template(
                    contents,
                    origin,
                    origin.template_name,
                    self.engine,
                )

        raise TemplateDoesNotExist(template_name, tried=tried)

    def get_template_sources(self, template_name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Loader must provide a get_template_sources() method"
        )

    def reset(self):
        """
        This is a comment
        """
        pass
