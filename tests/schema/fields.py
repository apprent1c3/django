from functools import partial

from django.db import models
from django.db.models.fields.related import (
    RECURSIVE_RELATIONSHIP_CONSTANT,
    ManyToManyDescriptor,
    RelatedField,
    create_many_to_many_intermediary_model,
)


class CustomManyToManyField(RelatedField):
    """
    Ticket #24104 - Need to have a custom ManyToManyField,
    which is not an inheritor of ManyToManyField.
    """

    many_to_many = True

    def __init__(
        self,
        to,
        db_constraint=True,
        swappable=True,
        related_name=None,
        related_query_name=None,
        limit_choices_to=None,
        symmetrical=None,
        through=None,
        through_fields=None,
        db_table=None,
        **kwargs,
    ):
        """

        Initializes a Many-To-Many relationship field.

        This field is used to establish a many-to-many relationship between two models.
        It provides options to customize the relationship, such as specifying a custom database table,
        a related name, or a query name.

        The relationship can be defined as symmetrical, meaning that the relationship exists in both directions,
        or asymmetrical, where the relationship only exists in one direction.

        Additionally, this field supports using an intermediary model to represent the relationship,
        allowing for more complex and customized many-to-many relationships.

        :type to: Model or str
        :param to: The model or string representation of the model to establish a relationship with.
        :param db_constraint: Whether to create a database constraint for the relationship.
        :param swappable: Whether the model can be swapped out with another model.
        :param related_name: The name of the relationship as seen from the related model.
        :param related_query_name: The name of the relationship as seen in query lookups.
        :param limit_choices_to: A dictionary of lookup arguments to filter the related objects.
        :param symmetrical: Whether the relationship is symmetrical.
        :param through: The intermediary model representing the relationship.
        :param through_fields: The field names on the intermediary model that represent the relationship.
        :param db_table: The name of the database table to use for the relationship.

        """
        try:
            to._meta
        except AttributeError:
            to = str(to)
        kwargs["rel"] = models.ManyToManyRel(
            self,
            to,
            related_name=related_name,
            related_query_name=related_query_name,
            limit_choices_to=limit_choices_to,
            symmetrical=(
                symmetrical
                if symmetrical is not None
                else (to == RECURSIVE_RELATIONSHIP_CONSTANT)
            ),
            through=through,
            through_fields=through_fields,
            db_constraint=db_constraint,
        )
        self.swappable = swappable
        self.db_table = db_table
        if kwargs["rel"].through is not None and self.db_table is not None:
            raise ValueError(
                "Cannot specify a db_table if an intermediary model is used."
            )
        super().__init__(
            related_name=related_name,
            related_query_name=related_query_name,
            limit_choices_to=limit_choices_to,
            **kwargs,
        )

    def contribute_to_class(self, cls, name, **kwargs):
        """

        Contribute this many-to-many relationship field to the given class.

        This method is responsible for setting up the relationship between the current
        model and the target model, including creating a through table if necessary,
        and setting the related name for the relationship. It also adds a descriptor
        to the class to provide easy access to the related objects.

        The relationship is symmetrical if the target model is the same as the current
        model, and the related name will be automatically set in this case. If the
        relationship is not symmetrical, the related name must be provided manually.

        Once this method is called, the relationship is fully set up and can be used
        to retrieve and manipulate related objects.

        """
        if self.remote_field.symmetrical and (
            self.remote_field.model == "self"
            or self.remote_field.model == cls._meta.object_name
        ):
            self.remote_field.related_name = "%s_rel_+" % name
        super().contribute_to_class(cls, name, **kwargs)
        if (
            not self.remote_field.through
            and not cls._meta.abstract
            and not cls._meta.swapped
        ):
            self.remote_field.through = create_many_to_many_intermediary_model(
                self, cls
            )
        setattr(cls, self.name, ManyToManyDescriptor(self.remote_field))
        self.m2m_db_table = partial(self._get_m2m_db_table, cls._meta)

    def get_internal_type(self):
        return "ManyToManyField"

    # Copy those methods from ManyToManyField because they don't call super() internally
    contribute_to_related_class = models.ManyToManyField.__dict__[
        "contribute_to_related_class"
    ]
    _get_m2m_attr = models.ManyToManyField.__dict__["_get_m2m_attr"]
    _get_m2m_reverse_attr = models.ManyToManyField.__dict__["_get_m2m_reverse_attr"]
    _get_m2m_db_table = models.ManyToManyField.__dict__["_get_m2m_db_table"]


class InheritedManyToManyField(models.ManyToManyField):
    pass


class MediumBlobField(models.BinaryField):
    """
    A MySQL BinaryField that uses a different blob size.
    """

    def db_type(self, connection):
        return "MEDIUMBLOB"
