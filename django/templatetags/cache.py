from django.core.cache import InvalidCacheBackendError, caches
from django.core.cache.utils import make_template_fragment_key
from django.template import Library, Node, TemplateSyntaxError, VariableDoesNotExist

register = Library()


class CacheNode(Node):
    def __init__(self, nodelist, expire_time_var, fragment_name, vary_on, cache_name):
        """
        Initialize a cache configuration.

        This constructor sets up the basic properties for caching, including the list of nodes,
        the expiration time variable, and the name of the cache fragment. It also defines
        the variables that the cache varies on and the name of the cache to use.

        :param nodelist: A list of nodes for the cache configuration
        :param expire_time_var: The variable that determines the expiration time of the cache
        :param fragment_name: The name of the cache fragment
        :param vary_on: The variables that the cache varies on
        :param cache_name: The name of the cache to use
        """
        self.nodelist = nodelist
        self.expire_time_var = expire_time_var
        self.fragment_name = fragment_name
        self.vary_on = vary_on
        self.cache_name = cache_name

    def render(self, context):
        """

        Render a cached template fragment.

        This function attempts to retrieve a cached template fragment from the specified cache.
        If the fragment is not found in the cache, it is rendered and stored in the cache for future requests.

        The cache expiration time is determined by the `expire_time` variable, which must be an integer.
        If the `expire_time` variable is not provided or is not an integer, a `TemplateSyntaxError` is raised.

        The cache name can be specified using the `cache_name` variable. If not provided, the 'template_fragments' cache is used.
        If the specified cache name is invalid, a `TemplateSyntaxError` is raised.

        The cache key is generated based on the fragment name and the values of the `vary_on` variables.
        This allows the cache to be updated when any of the `vary_on` variables change.

        Args:
            context: The template rendering context.

        Returns:
            The rendered template fragment, either from the cache or rendered on the fly.

        Raises:
            TemplateSyntaxError: If the `expire_time` variable is not an integer or the cache name is invalid.

        """
        try:
            expire_time = self.expire_time_var.resolve(context)
        except VariableDoesNotExist:
            raise TemplateSyntaxError(
                '"cache" tag got an unknown variable: %r' % self.expire_time_var.var
            )
        if expire_time is not None:
            try:
                expire_time = int(expire_time)
            except (ValueError, TypeError):
                raise TemplateSyntaxError(
                    '"cache" tag got a non-integer timeout value: %r' % expire_time
                )
        if self.cache_name:
            try:
                cache_name = self.cache_name.resolve(context)
            except VariableDoesNotExist:
                raise TemplateSyntaxError(
                    '"cache" tag got an unknown variable: %r' % self.cache_name.var
                )
            try:
                fragment_cache = caches[cache_name]
            except InvalidCacheBackendError:
                raise TemplateSyntaxError(
                    "Invalid cache name specified for cache tag: %r" % cache_name
                )
        else:
            try:
                fragment_cache = caches["template_fragments"]
            except InvalidCacheBackendError:
                fragment_cache = caches["default"]

        vary_on = [var.resolve(context) for var in self.vary_on]
        cache_key = make_template_fragment_key(self.fragment_name, vary_on)
        value = fragment_cache.get(cache_key)
        if value is None:
            value = self.nodelist.render(context)
            fragment_cache.set(cache_key, value, expire_time)
        return value


@register.tag("cache")
def do_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% load cache %}
        {% cache [expire_time] [fragment_name] %}
            .. some expensive processing ..
        {% endcache %}

    This tag also supports varying by a list of arguments::

        {% load cache %}
        {% cache [expire_time] [fragment_name] [var1] [var2] .. %}
            .. some expensive processing ..
        {% endcache %}

    Optionally the cache to use may be specified thus::

        {% cache ....  using="cachename" %}

    Each unique set of arguments will result in a unique cache entry.
    """
    nodelist = parser.parse(("endcache",))
    parser.delete_first_token()
    tokens = token.split_contents()
    if len(tokens) < 3:
        raise TemplateSyntaxError("'%r' tag requires at least 2 arguments." % tokens[0])
    if len(tokens) > 3 and tokens[-1].startswith("using="):
        cache_name = parser.compile_filter(tokens[-1].removeprefix("using="))
        tokens = tokens[:-1]
    else:
        cache_name = None
    return CacheNode(
        nodelist,
        parser.compile_filter(tokens[1]),
        tokens[2],  # fragment_name can't be a variable.
        [parser.compile_filter(t) for t in tokens[3:]],
        cache_name,
    )
