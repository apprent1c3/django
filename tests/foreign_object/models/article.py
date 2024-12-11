from django.db import models
from django.db.models.fields.related import ForwardManyToOneDescriptor
from django.utils.translation import get_language


class ArticleTranslationDescriptor(ForwardManyToOneDescriptor):
    """
    The set of articletranslation should not set any local fields.
    """

    def __set__(self, instance, value):
        """
        Setter method for the attribute.

        Sets the value of the attribute on the given instance. The value is cached 
        internally for efficient access. If the attribute represents a single 
        relationship, the corresponding value on the related object is also updated 
        to maintain referential integrity.

        Raises:
            AttributeError: If the attribute is accessed without an instance.

        """
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
        Produce a SQL fragment representing an equality check.

        This function generates a string that can be used in a SQL query to check for equality between a column and a given value.
        It returns a tuple containing the SQL snippet and the value to be compared. The SQL snippet includes the fully qualified column name, 
        formatted according to the quoting conventions of the specified compiler.
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
        Contribute this descriptor to a class, making it accessible as an attribute.

        This method is called when the descriptor is assigned to a class attribute.
        It simply calls the superclass's implementation and then sets up the descriptor
        on the class, making it usable as an attribute. The descriptor is responsible
        for managing article translations, allowing for easy access and manipulation
        of translated content.

        :param cls: The class this descriptor is being contributed to.
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
