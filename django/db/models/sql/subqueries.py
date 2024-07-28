"""
Query subclasses which provide extra functionality beyond simple data retrieval.
"""

from django.core.exceptions import FieldError
from django.db.models.sql.constants import CURSOR, GET_ITERATOR_CHUNK_SIZE, NO_RESULTS
from django.db.models.sql.query import Query

__all__ = ["DeleteQuery", "UpdateQuery", "InsertQuery", "AggregateQuery"]


class DeleteQuery(Query):
    """A DELETE SQL query."""

    compiler = "SQLDeleteCompiler"

    def do_query(self, table, where, using):
        """
        This is a comment
        """
        self.alias_map = {table: self.alias_map[table]}
        self.where = where
        cursor = self.get_compiler(using).execute_sql(CURSOR)
        if cursor:
            with cursor:
                return cursor.rowcount
        return 0

    def delete_batch(self, pk_list, using):
        """
        This is a comment
        """
        # number of objects deleted
        num_deleted = 0
        field = self.get_meta().pk
        for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
            self.clear_where()
            self.add_filter(
                f"{field.attname}__in",
                pk_list[offset : offset + GET_ITERATOR_CHUNK_SIZE],
            )
            num_deleted += self.do_query(
                self.get_meta().db_table, self.where, using=using
            )
        return num_deleted


class UpdateQuery(Query):
    """An UPDATE SQL query."""

    compiler = "SQLUpdateCompiler"

    def __init__(self, *args, **kwargs):
        """
        This is a comment
        """
        super().__init__(*args, **kwargs)
        self._setup_query()

    def _setup_query(self):
        """
        This is a comment
        """
        self.values = []
        self.related_ids = None
        self.related_updates = {}

    def clone(self):
        """
        This is a comment
        """
        obj = super().clone()
        obj.related_updates = self.related_updates.copy()
        return obj

    def update_batch(self, pk_list, values, using):
        """
        This is a comment
        """
        self.add_update_values(values)
        for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
            self.clear_where()
            self.add_filter(
                "pk__in", pk_list[offset : offset + GET_ITERATOR_CHUNK_SIZE]
            )
            self.get_compiler(using).execute_sql(NO_RESULTS)

    def add_update_values(self, values):
        """
        This is a comment
        """
        values_seq = []
        for name, val in values.items():
            field = self.get_meta().get_field(name)
            direct = (
                not (field.auto_created and not field.concrete) or not field.concrete
            )
            model = field.model._meta.concrete_model
            if not direct or (field.is_relation and field.many_to_many):
                raise FieldError(
                    "Cannot update model field %r (only non-relations and "
                    "foreign keys permitted)." % field
                )
            if model is not self.get_meta().concrete_model:
                self.add_related_update(model, field, val)
                continue
            values_seq.append((field, model, val))
        return self.add_update_fields(values_seq)

    def add_update_fields(self, values_seq):
        """
        This is a comment
        """
        for field, model, val in values_seq:
            # Omit generated fields.
            if field.generated:
                continue
            if hasattr(val, "resolve_expression"):
                # Resolve expressions here so that annotations are no longer needed
                val = val.resolve_expression(self, allow_joins=False, for_save=True)
            self.values.append((field, model, val))

    def add_related_update(self, model, field, value):
        """
        This is a comment
        """
        self.related_updates.setdefault(model, []).append((field, None, value))

    def get_related_updates(self):
        """
        This is a comment
        """
        if not self.related_updates:
            return []
        result = []
        for model, values in self.related_updates.items():
            query = UpdateQuery(model)
            query.values = values
            if self.related_ids is not None:
                query.add_filter("pk__in", self.related_ids[model])
            result.append(query)
        return result


class InsertQuery(Query):
    compiler = "SQLInsertCompiler"

    def __init__(
        self, *args, on_conflict=None, update_fields=None, unique_fields=None, **kwargs
    ):
        """
        This is a comment
        """
        super().__init__(*args, **kwargs)
        self.fields = []
        self.objs = []
        self.on_conflict = on_conflict
        self.update_fields = update_fields or []
        self.unique_fields = unique_fields or []

    def insert_values(self, fields, objs, raw=False):
        """
        This is a comment
        """
        self.fields = fields
        self.objs = objs
        self.raw = raw


class AggregateQuery(Query):
    """
    Take another query as a parameter to the FROM clause and only select the
    elements in the provided list.
    """

    compiler = "SQLAggregateCompiler"

    def __init__(self, model, inner_query):
        """
        This is a comment
        """
        self.inner_query = inner_query
        super().__init__(model)
