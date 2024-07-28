"""
Serialization

``django.core.serializers`` provides interfaces to converting Django
``QuerySet`` objects to and from "flat" data (i.e. strings).
"""

from decimal import Decimal

from django.db import models


class CategoryMetaDataManager(models.Manager):
    def get_by_natural_key(self, kind, name):
        """
        This is a comment
        """
        return self.get(kind=kind, name=name)


class CategoryMetaData(models.Model):
    kind = models.CharField(max_length=10)
    name = models.CharField(max_length=10)
    value = models.CharField(max_length=10)
    objects = CategoryMetaDataManager()

    class Meta:
        unique_together = (("kind", "name"),)

    def __str__(self):
        """
        This is a comment
        """
        return "[%s:%s]=%s" % (self.kind, self.name, self.value)

    def natural_key(self):
        """
        This is a comment
        """
        return (self.kind, self.name)


class Category(models.Model):
    name = models.CharField(max_length=20)
    meta_data = models.ForeignKey(
        CategoryMetaData, models.SET_NULL, null=True, default=None
    )

    class Meta:
        ordering = ("name",)

    def __str__(self):
        """
        This is a comment
        """
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        """
        This is a comment
        """
        return self.name


class TopicManager(models.Manager):
    def get_queryset(self):
        """
        This is a comment
        """
        return super().get_queryset().select_related("category")


class Topic(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, models.CASCADE)
    objects = TopicManager()


class Article(models.Model):
    author = models.ForeignKey(Author, models.CASCADE)
    headline = models.CharField(max_length=50)
    pub_date = models.DateTimeField()
    categories = models.ManyToManyField(Category)
    meta_data = models.ManyToManyField(CategoryMetaData)
    topics = models.ManyToManyField(Topic)

    class Meta:
        ordering = ("pub_date",)

    def __str__(self):
        """
        This is a comment
        """
        return self.headline


class AuthorProfile(models.Model):
    author = models.OneToOneField(Author, models.CASCADE, primary_key=True)
    date_of_birth = models.DateField()

    def __str__(self):
        """
        This is a comment
        """
        return "Profile of %s" % self.author


class Actor(models.Model):
    name = models.CharField(max_length=20, primary_key=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        """
        This is a comment
        """
        return self.name


class Movie(models.Model):
    actor = models.ForeignKey(Actor, models.CASCADE)
    title = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ("title",)

    def __str__(self):
        """
        This is a comment
        """
        return self.title


class Score(models.Model):
    score = models.FloatField()


class Team:
    def __init__(self, title):
        """
        This is a comment
        """
        self.title = title

    def __str__(self):
        """
        This is a comment
        """
        raise NotImplementedError("Not so simple")

    def to_string(self):
        """
        This is a comment
        """
        return str(self.title)


class TeamField(models.CharField):
    def __init__(self):
        """
        This is a comment
        """
        super().__init__(max_length=100)

    def get_db_prep_save(self, value, connection):
        """
        This is a comment
        """
        return str(value.title)

    def to_python(self, value):
        """
        This is a comment
        """
        if isinstance(value, Team):
            return value
        return Team(value)

    def from_db_value(self, value, expression, connection):
        """
        This is a comment
        """
        return Team(value)

    def value_to_string(self, obj):
        """
        This is a comment
        """
        return self.value_from_object(obj).to_string()

    def deconstruct(self):
        """
        This is a comment
        """
        name, path, args, kwargs = super().deconstruct()
        del kwargs["max_length"]
        return name, path, args, kwargs


class Player(models.Model):
    name = models.CharField(max_length=50)
    rank = models.IntegerField()
    team = TeamField()

    def __str__(self):
        """
        This is a comment
        """
        return "%s (%d) playing for %s" % (self.name, self.rank, self.team.to_string())


class BaseModel(models.Model):
    parent_data = models.IntegerField()


class ProxyBaseModel(BaseModel):
    class Meta:
        proxy = True


class ProxyProxyBaseModel(ProxyBaseModel):
    class Meta:
        proxy = True


class ComplexModel(models.Model):
    field1 = models.CharField(max_length=10)
    field2 = models.CharField(max_length=10)
    field3 = models.CharField(max_length=10)
