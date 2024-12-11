from django.db import models


class CurrentTranslation(models.ForeignObject):
    """
    Creates virtual relation to the translation with model cache enabled.
    """

    # Avoid validation
    requires_unique_target = False

    def __init__(self, to, on_delete, from_fields, to_fields, **kwargs):
        # Disable reverse relation
        """
        Initializes a one-to-one relationship between two models, where one model instance is uniquely related to another model instance.

        :param to: The model that this relationship points to.
        :param on_delete: The action to perform when the related object is deleted.
        :param from_fields: The fields on the current model that are used to establish the relationship.
        :param to_fields: The fields on the related model that are used to establish the relationship.
        :param kwargs: Additional keyword arguments to customize the relationship. Note that 'related_name' is set to '+' and 'unique' is set to True by default, ensuring a one-to-one relationship without a reverse reference.
        """
        kwargs["related_name"] = "+"
        # Set unique to enable model cache.
        kwargs["unique"] = True
        super().__init__(to, on_delete, from_fields, to_fields, **kwargs)


class ArticleTranslation(models.Model):
    article = models.ForeignKey("indexes.Article", models.CASCADE)
    article_no_constraint = models.ForeignKey(
        "indexes.Article", models.CASCADE, db_constraint=False, related_name="+"
    )
    language = models.CharField(max_length=10, unique=True)
    content = models.TextField()


class Article(models.Model):
    headline = models.CharField(max_length=100)
    pub_date = models.DateTimeField()
    published = models.BooleanField(default=False)

    # Add virtual relation to the ArticleTranslation model.
    translation = CurrentTranslation(
        ArticleTranslation, models.CASCADE, ["id"], ["article"]
    )

    class Meta:
        indexes = [models.Index(fields=["headline", "pub_date"])]


class IndexedArticle(models.Model):
    headline = models.CharField(max_length=100, db_index=True)
    body = models.TextField(db_index=True)
    slug = models.CharField(max_length=40, unique=True)

    class Meta:
        required_db_features = {"supports_index_on_text_field"}


class IndexedArticle2(models.Model):
    headline = models.CharField(max_length=100)
    body = models.TextField()
