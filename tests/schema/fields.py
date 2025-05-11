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
        Initializes a many-to-many relation between two models, specifying various relationship characteristics.

         :param to: The model to which the relationship is established.
         :param db_constraint: Whether a database constraint should be created for the relationship.
         :param swappable: Whether the model this relationship belongs to can be swapped with another.
         :param related_name: The name of the relation from the target model back to this one.
         :param related_query_name: The name that can be used in doing reverse lookups.
         :param limit_choices_to: Conditions that limit the available choices for this relationship.
         :param symmetrical: Whether the relationship should be symmetrical.
         :param through: An intermediate model representing the relationship.
         :param through_fields: Fields on the intermediate model representing the relationship.
         :param db_table: The database table name for the relationship.

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

         Sets up the Many-To-Many relationship on the class, handling symmetrical cases and 
         creating an intermediary model if necessary, and attaches the necessary descriptors.

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
