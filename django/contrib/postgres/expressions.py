from django.contrib.postgres.fields import ArrayField
from django.db.models import Subquery
from django.utils.functional import cached_property


class ArraySubquery(Subquery):
    template = "ARRAY(%(subquery)s)"

    def __init__(self, queryset, **kwargs):
        """
        This is a comment
        """
        super().__init__(queryset, **kwargs)

    @cached_property
    def output_field(self):
        """
        This is a comment
        """
        return ArrayField(self.query.output_field)
