from django.db.models import Func, Index
from django.utils.functional import cached_property

__all__ = [
    "BloomIndex",
    "BrinIndex",
    "BTreeIndex",
    "GinIndex",
    "GistIndex",
    "HashIndex",
    "SpGistIndex",
]


class PostgresIndex(Index):
    @cached_property
    def max_name_length(self):
        # Allow an index name longer than 30 characters when the suffix is
        # longer than the usual 3 character limit. The 30 character limit for
        # cross-database compatibility isn't applicable to PostgreSQL-specific
        # indexes.
        return Index.max_name_length - len(Index.suffix) + len(self.suffix)

    def create_sql(self, model, schema_editor, using="", **kwargs):
        self.check_supported(schema_editor)
        statement = super().create_sql(
            model, schema_editor, using=" USING %s" % (using or self.suffix), **kwargs
        )
        with_params = self.get_with_params()
        if with_params:
            statement.parts["extra"] = " WITH (%s)%s" % (
                ", ".join(with_params),
                statement.parts["extra"],
            )
        return statement

    def check_supported(self, schema_editor):
        pass

    def get_with_params(self):
        return []


class BloomIndex(PostgresIndex):
    suffix = "bloom"

    def __init__(self, *expressions, length=None, columns=(), **kwargs):
        super().__init__(*expressions, **kwargs)
        if len(self.fields) > 32:
            raise ValueError("Bloom indexes support a maximum of 32 fields.")
        if not isinstance(columns, (list, tuple)):
            raise ValueError("BloomIndex.columns must be a list or tuple.")
        if len(columns) > len(self.fields):
            raise ValueError("BloomIndex.columns cannot have more values than fields.")
        if not all(0 < col <= 4095 for col in columns):
            raise ValueError(
                "BloomIndex.columns must contain integers from 1 to 4095.",
            )
        if length is not None and not 0 < length <= 4096:
            raise ValueError(
                "BloomIndex.length must be None or an integer from 1 to 4096.",
            )
        self.length = length
        self.columns = columns

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if self.length is not None:
            kwargs["length"] = self.length
        if self.columns:
            kwargs["columns"] = self.columns
        return path, args, kwargs

    def get_with_params(self):
        """
        Returns a list of string representations of the object's parameters, as if they were being passed to a constructor or function.

        The returned list includes string representations of 'length' if it is not None, and 'colX' for each column, where X is the column's 1-based index. The format of each string is 'parameter_name = value'. 

        The returned list can be used to generate a human-readable description of the object's parameters, for example, for logging or debugging purposes.
        """
        with_params = []
        if self.length is not None:
            with_params.append("length = %d" % self.length)
        if self.columns:
            with_params.extend(
                "col%d = %d" % (i, v) for i, v in enumerate(self.columns, start=1)
            )
        return with_params


class BrinIndex(PostgresIndex):
    suffix = "brin"

    def __init__(
        self, *expressions, autosummarize=None, pages_per_range=None, **kwargs
    ):
        if pages_per_range is not None and pages_per_range <= 0:
            raise ValueError("pages_per_range must be None or a positive integer")
        self.autosummarize = autosummarize
        self.pages_per_range = pages_per_range
        super().__init__(*expressions, **kwargs)

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if self.autosummarize is not None:
            kwargs["autosummarize"] = self.autosummarize
        if self.pages_per_range is not None:
            kwargs["pages_per_range"] = self.pages_per_range
        return path, args, kwargs

    def get_with_params(self):
        """
        Returns a list of string parameters that are set for the current object, 
        including 'autosummarize' and 'pages_per_range' if their respective values are not None. 
        Each parameter is represented as a string in the format 'parameter = value'. 
        The returned list can be used to construct a string representation of the object's settings.
        """
        with_params = []
        if self.autosummarize is not None:
            with_params.append(
                "autosummarize = %s" % ("on" if self.autosummarize else "off")
            )
        if self.pages_per_range is not None:
            with_params.append("pages_per_range = %d" % self.pages_per_range)
        return with_params


class BTreeIndex(PostgresIndex):
    suffix = "btree"

    def __init__(self, *expressions, fillfactor=None, deduplicate_items=None, **kwargs):
        self.fillfactor = fillfactor
        self.deduplicate_items = deduplicate_items
        super().__init__(*expressions, **kwargs)

    def deconstruct(self):
        """
        Deconstructs the object into its constituent parts for serialization purposes.

        This method extends the default deconstruction behavior by including any specified fill factor and deduplicate items settings, allowing for accurate recreation of the object during deserialization. 

        The deconstructed parts include the object's path, positional arguments, and keyword arguments. 

        :returns: A tuple containing the object's path, arguments, and keyword arguments.
        """
        path, args, kwargs = super().deconstruct()
        if self.fillfactor is not None:
            kwargs["fillfactor"] = self.fillfactor
        if self.deduplicate_items is not None:
            kwargs["deduplicate_items"] = self.deduplicate_items
        return path, args, kwargs

    def get_with_params(self):
        with_params = []
        if self.fillfactor is not None:
            with_params.append("fillfactor = %d" % self.fillfactor)
        if self.deduplicate_items is not None:
            with_params.append(
                "deduplicate_items = %s" % ("on" if self.deduplicate_items else "off")
            )
        return with_params


class GinIndex(PostgresIndex):
    suffix = "gin"

    def __init__(
        self, *expressions, fastupdate=None, gin_pending_list_limit=None, **kwargs
    ):
        self.fastupdate = fastupdate
        self.gin_pending_list_limit = gin_pending_list_limit
        super().__init__(*expressions, **kwargs)

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if self.fastupdate is not None:
            kwargs["fastupdate"] = self.fastupdate
        if self.gin_pending_list_limit is not None:
            kwargs["gin_pending_list_limit"] = self.gin_pending_list_limit
        return path, args, kwargs

    def get_with_params(self):
        with_params = []
        if self.gin_pending_list_limit is not None:
            with_params.append(
                "gin_pending_list_limit = %d" % self.gin_pending_list_limit
            )
        if self.fastupdate is not None:
            with_params.append("fastupdate = %s" % ("on" if self.fastupdate else "off"))
        return with_params


class GistIndex(PostgresIndex):
    suffix = "gist"

    def __init__(self, *expressions, buffering=None, fillfactor=None, **kwargs):
        self.buffering = buffering
        self.fillfactor = fillfactor
        super().__init__(*expressions, **kwargs)

    def deconstruct(self):
        """

        Deconstructs the object into its constituent parts for serialization or other purposes.

        This method extends the deconstruction behavior of its parent class by including
        any specified buffering and fill factor settings. The resulting deconstructed
        representation is suitable for use in database migration or other serialization
        scenarios.

        Returns:
            tuple: A tuple containing the path, positional arguments, and keyword arguments
                representing the deconstructed object.

        """
        path, args, kwargs = super().deconstruct()
        if self.buffering is not None:
            kwargs["buffering"] = self.buffering
        if self.fillfactor is not None:
            kwargs["fillfactor"] = self.fillfactor
        return path, args, kwargs

    def get_with_params(self):
        with_params = []
        if self.buffering is not None:
            with_params.append("buffering = %s" % ("on" if self.buffering else "off"))
        if self.fillfactor is not None:
            with_params.append("fillfactor = %d" % self.fillfactor)
        return with_params


class HashIndex(PostgresIndex):
    suffix = "hash"

    def __init__(self, *expressions, fillfactor=None, **kwargs):
        self.fillfactor = fillfactor
        super().__init__(*expressions, **kwargs)

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if self.fillfactor is not None:
            kwargs["fillfactor"] = self.fillfactor
        return path, args, kwargs

    def get_with_params(self):
        """
        #: Returns a list of parameters for a SQL WITH clause.
        #: 
        #: The parameters in the list are determined by the properties of the current object,
        #: specifically the fill factor value. If the fill factor is set, it is included in the list.
        #: 
        #: :return: A list of strings representing the parameters for the SQL WITH clause.
        """
        with_params = []
        if self.fillfactor is not None:
            with_params.append("fillfactor = %d" % self.fillfactor)
        return with_params


class SpGistIndex(PostgresIndex):
    suffix = "spgist"

    def __init__(self, *expressions, fillfactor=None, **kwargs):
        self.fillfactor = fillfactor
        super().__init__(*expressions, **kwargs)

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        if self.fillfactor is not None:
            kwargs["fillfactor"] = self.fillfactor
        return path, args, kwargs

    def get_with_params(self):
        with_params = []
        if self.fillfactor is not None:
            with_params.append("fillfactor = %d" % self.fillfactor)
        return with_params


class OpClass(Func):
    template = "%(expressions)s %(name)s"
    constraint_validation_compatible = False

    def __init__(self, expression, name):
        super().__init__(expression, name=name)
