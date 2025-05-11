from django.core.cache import InvalidCacheBackendError, caches
from django.core.cache.utils import make_template_fragment_key
from django.template import Library, Node, TemplateSyntaxError, VariableDoesNotExist

register = Library()


class CacheNode(Node):
    def __init__(self, nodelist, expire_time_var, fragment_name, vary_on, cache_name):
        """
        Initializes a cache fragment configuration.

        :param nodelist: List of nodes to use for caching
        :param expire_time_var: Variable to control expiration time
        :param fragment_name: Name of the cache fragment
        :param vary_on: Parameters to vary the cache on
        :param cache_name: Name of the cache to use
        """
        self.nodelist = nodelist
        self.expire_time_var = expire_time_var
        self.fragment_name = fragment_name
        self.vary_on = vary_on
        self.cache_name = cache_name

    def render(self, context):
        """
        Renders a template fragment, either from cache or by executing the fragment and storing the result in the cache. 

        The fragment is cached with a key based on the fragment name and any specified vary-on variables. 

        The cache expiration time can be specified, defaulting to none if not provided. 

        The cache name can also be specified, falling back to a default cache if not provided or invalid. 

        Raises a TemplateSyntaxError if any of the provided variables or cache name are unknown or invalid.
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
    of time, reducing the overhead of expensive computations by reusing the
    cached result until it expires. The cache key can be customized to
    depend on a list of arguments, allowing different cache entries for
    different inputs. Optionally, a specific cache can be specified for
    use.
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
