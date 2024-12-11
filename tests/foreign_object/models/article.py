from django.db import models
from django.db.models.fields.related import ForwardManyToOneDescriptor
from django.utils.translation import get_language


class ArticleTranslationDescriptor(ForwardManyToOneDescriptor):
    """
    The set of articletranslation should not set any local fields.
    """

    def __set__(self, instance, value):
        if instance is None:
            raise AttributeError("%s must be accessed via instance" % self.field.name)
        self.field.set_cached_value(instance, value)
        if value is not None and not self.field.remote_field.multiple:
            self.field.remote_field.set_cached_value(value, instance)


class ColConstraint:
    # Anything with as_sql() method works in get_extra_restriction().
    def __init__(self, alias, col, value):
        self.alias, self.col, self.value = alias, col, value

    def as_sql(self, compiler, connection):
        """
        Generates a SQL string for equality comparison.

        This method constructs a SQL snippet in the form 'alias.column = %s' and 
        returns it along with a parameter list containing the value to compare. 

        The alias and column names are properly quoted to prevent SQL injection and 
        adapt to the specific database dialect being used.

        :return: A tuple containing the SQL string and a list of parameters.
        :rtype: tuple
        """
        qn = compiler.quote_name_unless_alias
        return "%s.%s = %%s" % (qn(self.alias), qn(self.col)), [self.value]


class ActiveTranslationField(models.ForeignObject):
    """
    This field will allow querying and fetching the currently active translation
    for Article from ArticleTranslation.
    """

    requires_unique_target = False

    def get_extra_restriction(self, alias, related_alias):
        return ColConstraint(alias, "lang", get_language())

    def get_extra_descriptor_filter(self, instance):
        return {"lang": get_language()}

    def contribute_to_class(self, cls, name):
        """
        Contributes this descriptor to a class, enabling article translation functionality.

        This method is called when the descriptor is assigned to a class attribute.
        It sets up the article translation descriptor for the specified class, allowing
        for easy access to translated article data.

        :param cls: The class to which this descriptor is being contributed.
        :param name: The name of the attribute on the class where this descriptor is being assigned.

        """
        super().contribute_to_class(cls, name)
        setattr(cls, self.name, ArticleTranslationDescriptor(self))


class ActiveTranslationFieldWithQ(ActiveTranslationField):
    def get_extra_descriptor_filter(self, instance):
        return models.Q(lang=get_language())


class Article(models.Model):
    active_translation = ActiveTranslationField(
        "ArticleTranslation",
        from_fields=["id"],
        to_fields=["article"],
        related_name="+",
        on_delete=models.CASCADE,
        null=True,
    )
    active_translation_q = ActiveTranslationFieldWithQ(
        "ArticleTranslation",
        from_fields=["id"],
        to_fields=["article"],
        related_name="+",
        on_delete=models.CASCADE,
        null=True,
    )
    pub_date = models.DateField()

    def __str__(self):
        """
        Returns a string representation of the object, specifically the title of the active translation if it exists.

        If no active translation is found, it returns a message indicating that no translation was available.

        This method is used to provide a human-readable representation of the object and is typically used for display or logging purposes.

        :return: A string representing the object's active translation title or a 'No translation found' message.

        """
        try:
            return self.active_translation.title
        except ArticleTranslation.DoesNotExist:
            return "[No translation found]"


class NewsArticle(Article):
    pass


class ArticleTranslation(models.Model):
    article = models.ForeignKey(Article, models.CASCADE)
    lang = models.CharField(max_length=2)
    title = models.CharField(max_length=100)
    body = models.TextField()
    abstract = models.TextField(null=True)

    class Meta:
        unique_together = ("article", "lang")


class ArticleTag(models.Model):
    article = models.ForeignKey(
        Article,
        models.CASCADE,
        related_name="tags",
        related_query_name="tag",
    )
    name = models.CharField(max_length=255)


class ArticleIdea(models.Model):
    articles = models.ManyToManyField(
        Article,
        related_name="ideas",
        related_query_name="idea_things",
    )
    name = models.CharField(max_length=255)
