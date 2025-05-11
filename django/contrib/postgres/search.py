from django.db.models import (
    CharField,
    Expression,
    Field,
    FloatField,
    Func,
    Lookup,
    TextField,
    Value,
)
from django.db.models.expressions import CombinedExpression, register_combinable_fields
from django.db.models.functions import Cast, Coalesce


class SearchVectorExact(Lookup):
    lookup_name = "exact"

    def process_rhs(self, qn, connection):
        """
        Ensures the right-hand side (RHS) of a query is properly formatted by wrapping it in a SearchQuery if necessary, and then delegates processing to the parent class.
        """
        if not isinstance(self.rhs, (SearchQuery, CombinedSearchQuery)):
            config = getattr(self.lhs, "config", None)
            self.rhs = SearchQuery(self.rhs, config=config)
        rhs, rhs_params = super().process_rhs(qn, connection)
        return rhs, rhs_params

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return "%s @@ %s" % (lhs, rhs), params


class SearchVectorField(Field):
    def db_type(self, connection):
        return "tsvector"


class SearchQueryField(Field):
    def db_type(self, connection):
        return "tsquery"


class _Float4Field(Field):
    def db_type(self, connection):
        return "float4"


class SearchConfig(Expression):
    def __init__(self, config):
        super().__init__()
        if not hasattr(config, "resolve_expression"):
            config = Value(config)
        self.config = config

    @classmethod
    def from_parameter(cls, config):
        if config is None or isinstance(config, cls):
            return config
        return cls(config)

    def get_source_expressions(self):
        return [self.config]

    def set_source_expressions(self, exprs):
        (self.config,) = exprs

    def as_sql(self, compiler, connection):
        sql, params = compiler.compile(self.config)
        return "%s::regconfig" % sql, params


class SearchVectorCombinable:
    ADD = "||"

    def _combine(self, other, connector, reversed):
        """
        Combines the current search vector with another, using a specified logical connector.

        :param other: The other search vector to combine with.
        :param connector: The logical connector to use for combining.
        :param reversed: Whether to reverse the order of the combined vectors.
        :raises TypeError: If the other object is not a SearchVectorCombinable instance.
        :return: A new CombinedSearchVector instance representing the combined search query.

        """
        if not isinstance(other, SearchVectorCombinable):
            raise TypeError(
                "SearchVector can only be combined with other SearchVector "
                "instances, got %s." % type(other).__name__
            )
        if reversed:
            return CombinedSearchVector(other, connector, self, self.config)
        return CombinedSearchVector(self, connector, other, self.config)


register_combinable_fields(
    SearchVectorField, SearchVectorCombinable.ADD, SearchVectorField, SearchVectorField
)


class SearchVector(SearchVectorCombinable, Func):
    function = "to_tsvector"
    arg_joiner = " || ' ' || "
    output_field = SearchVectorField()

    def __init__(self, *expressions, config=None, weight=None):
        """
        Initializes a search query object, setting its configuration and weight for ranking results. The configuration is derived from the provided parameters, and the weight is optionally set to influence the search result ordering.
        """
        super().__init__(*expressions)
        self.config = SearchConfig.from_parameter(config)
        if weight is not None and not hasattr(weight, "resolve_expression"):
            weight = Value(weight)
        self.weight = weight

    def resolve_expression(
        self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False
    ):
        resolved = super().resolve_expression(
            query, allow_joins, reuse, summarize, for_save
        )
        if self.config:
            resolved.config = self.config.resolve_expression(
                query, allow_joins, reuse, summarize, for_save
            )
        return resolved

    def as_sql(self, compiler, connection, function=None, template=None):
        """
        Returns the SQL representation of a search vector query.

         :param compiler: The SQL compiler to use.
         :param connection: The database connection to use.
         :param function: Optional function to apply to the result.
         :param template: Optional template to use for the SQL query.

         :return: A tuple containing the SQL query and a list of parameters.

         This function generates the SQL required to create a search vector, handling
         configuration and weighting as necessary. It ensures that all expressions
         are coerced to a compatible text type, and allows for custom templates and
         functions to be applied to the query result.
        """
        clone = self.copy()
        clone.set_source_expressions(
            [
                Coalesce(
                    (
                        expression
                        if isinstance(expression.output_field, (CharField, TextField))
                        else Cast(expression, TextField())
                    ),
                    Value(""),
                )
                for expression in clone.get_source_expressions()
            ]
        )
        config_sql = None
        config_params = []
        if template is None:
            if clone.config:
                config_sql, config_params = compiler.compile(clone.config)
                template = "%(function)s(%(config)s, %(expressions)s)"
            else:
                template = clone.template
        sql, params = super(SearchVector, clone).as_sql(
            compiler,
            connection,
            function=function,
            template=template,
            config=config_sql,
        )
        extra_params = []
        if clone.weight:
            weight_sql, extra_params = compiler.compile(clone.weight)
            sql = "setweight({}, {})".format(sql, weight_sql)

        return sql, config_params + params + extra_params


class CombinedSearchVector(SearchVectorCombinable, CombinedExpression):
    def __init__(self, lhs, connector, rhs, config, output_field=None):
        self.config = config
        super().__init__(lhs, connector, rhs, output_field)


class SearchQueryCombinable:
    BITAND = "&&"
    BITOR = "||"

    def _combine(self, other, connector, reversed):
        """
        Combines the current SearchQuery with another SearchQueryCombinable instance using a specified connector.

         :param other: The SearchQueryCombinable instance to combine with.
         :param connector: The connector to use for combining the search queries.
         :param reversed: Whether to reverse the order of the combined search queries.
         :raises TypeError: If the other instance is not a SearchQueryCombinable.
         :return: A new CombinedSearchQuery instance representing the combined search queries.
        """
        if not isinstance(other, SearchQueryCombinable):
            raise TypeError(
                "SearchQuery can only be combined with other SearchQuery "
                "instances, got %s." % type(other).__name__
            )
        if reversed:
            return CombinedSearchQuery(other, connector, self, self.config)
        return CombinedSearchQuery(self, connector, other, self.config)

    # On Combinable, these are not implemented to reduce confusion with Q. In
    # this case we are actually (ab)using them to do logical combination so
    # it's consistent with other usage in Django.
    def __or__(self, other):
        return self._combine(other, self.BITOR, False)

    def __ror__(self, other):
        return self._combine(other, self.BITOR, True)

    def __and__(self, other):
        return self._combine(other, self.BITAND, False)

    def __rand__(self, other):
        return self._combine(other, self.BITAND, True)


class SearchQuery(SearchQueryCombinable, Func):
    output_field = SearchQueryField()
    SEARCH_TYPES = {
        "plain": "plainto_tsquery",
        "phrase": "phraseto_tsquery",
        "raw": "to_tsquery",
        "websearch": "websearch_to_tsquery",
    }

    def __init__(
        self,
        value,
        output_field=None,
        *,
        config=None,
        invert=False,
        search_type="plain",
    ):
        """
        Initializes a search function with the given value and configuration.

        Parameters
        ----------
        value : any
            The value to search for.
        output_field : any, optional
            The output field for the search result.
        config : any, optional
            The search configuration.
        invert : bool, optional
            Whether to invert the search result.
        search_type : str, optional
            The type of search to perform (default is 'plain').

        Raises
        ------
        ValueError
            If the search type is unknown.

        Notes
        -----
        Configures the search function with the provided parameters and validates the search type.

        """
        self.function = self.SEARCH_TYPES.get(search_type)
        if self.function is None:
            raise ValueError("Unknown search_type argument '%s'." % search_type)
        if not hasattr(value, "resolve_expression"):
            value = Value(value)
        expressions = (value,)
        self.config = SearchConfig.from_parameter(config)
        if self.config is not None:
            expressions = (self.config,) + expressions
        self.invert = invert
        super().__init__(*expressions, output_field=output_field)

    def as_sql(self, compiler, connection, function=None, template=None):
        sql, params = super().as_sql(compiler, connection, function, template)
        if self.invert:
            sql = "!!(%s)" % sql
        return sql, params

    def __invert__(self):
        clone = self.copy()
        clone.invert = not self.invert
        return clone

    def __str__(self):
        result = super().__str__()
        return ("~%s" % result) if self.invert else result


class CombinedSearchQuery(SearchQueryCombinable, CombinedExpression):
    def __init__(self, lhs, connector, rhs, config, output_field=None):
        self.config = config
        super().__init__(lhs, connector, rhs, output_field)

    def __str__(self):
        return "(%s)" % super().__str__()


class SearchRank(Func):
    function = "ts_rank"
    output_field = FloatField()

    def __init__(
        self,
        vector,
        query,
        weights=None,
        normalization=None,
        cover_density=False,
    ):
        """
        Initializes a full-text search ranking function, which calculates the relevance of a document vector with respect to a given query, allowing for optional weighting and normalization of results.
        """
        from .fields.array import ArrayField

        if not hasattr(vector, "resolve_expression"):
            vector = SearchVector(vector)
        if not hasattr(query, "resolve_expression"):
            query = SearchQuery(query)
        expressions = (vector, query)
        if weights is not None:
            if not hasattr(weights, "resolve_expression"):
                weights = Value(weights)
            weights = Cast(weights, ArrayField(_Float4Field()))
            expressions = (weights,) + expressions
        if normalization is not None:
            if not hasattr(normalization, "resolve_expression"):
                normalization = Value(normalization)
            expressions += (normalization,)
        if cover_density:
            self.function = "ts_rank_cd"
        super().__init__(*expressions)


class SearchHeadline(Func):
    function = "ts_headline"
    template = "%(function)s(%(expressions)s%(options)s)"
    output_field = TextField()

    def __init__(
        self,
        expression,
        query,
        *,
        config=None,
        start_sel=None,
        stop_sel=None,
        max_words=None,
        min_words=None,
        short_word=None,
        highlight_all=None,
        max_fragments=None,
        fragment_delimiter=None,
    ):
        """
        Initializes a search object with an expression, query, and optional configuration settings to customize the search behavior.
        """
        if not hasattr(query, "resolve_expression"):
            query = SearchQuery(query)
        options = {
            "StartSel": start_sel,
            "StopSel": stop_sel,
            "MaxWords": max_words,
            "MinWords": min_words,
            "ShortWord": short_word,
            "HighlightAll": highlight_all,
            "MaxFragments": max_fragments,
            "FragmentDelimiter": fragment_delimiter,
        }
        self.options = {
            option: value for option, value in options.items() if value is not None
        }
        expressions = (expression, query)
        if config is not None:
            config = SearchConfig.from_parameter(config)
            expressions = (config,) + expressions
        super().__init__(*expressions)

    def as_sql(self, compiler, connection, function=None, template=None):
        """

        Generates the SQL string and parameters for this database operation, incorporating any specified options.

        :returns: A tuple containing the SQL string and a list of parameters.

        """
        options_sql = ""
        options_params = []
        if self.options:
            options_params.append(
                ", ".join(
                    connection.ops.compose_sql(f"{option}=%s", [value])
                    for option, value in self.options.items()
                )
            )
            options_sql = ", %s"
        sql, params = super().as_sql(
            compiler,
            connection,
            function=function,
            template=template,
            options=options_sql,
        )
        return sql, params + options_params


SearchVectorField.register_lookup(SearchVectorExact)


class TrigramBase(Func):
    output_field = FloatField()

    def __init__(self, expression, string, **extra):
        if not hasattr(string, "resolve_expression"):
            string = Value(string)
        super().__init__(expression, string, **extra)


class TrigramWordBase(Func):
    output_field = FloatField()

    def __init__(self, string, expression, **extra):
        if not hasattr(string, "resolve_expression"):
            string = Value(string)
        super().__init__(string, expression, **extra)


class TrigramSimilarity(TrigramBase):
    function = "SIMILARITY"


class TrigramDistance(TrigramBase):
    function = ""
    arg_joiner = " <-> "


class TrigramWordDistance(TrigramWordBase):
    function = ""
    arg_joiner = " <<-> "


class TrigramStrictWordDistance(TrigramWordBase):
    function = ""
    arg_joiner = " <<<-> "


class TrigramWordSimilarity(TrigramWordBase):
    function = "WORD_SIMILARITY"


class TrigramStrictWordSimilarity(TrigramWordBase):
    function = "STRICT_WORD_SIMILARITY"
