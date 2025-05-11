from hashlib import md5

TEMPLATE_FRAGMENT_KEY_TEMPLATE = "template.cache.%s.%s"


def make_template_fragment_key(fragment_name, vary_on=None):
    """

    Generate a cache key for a template fragment.

    The key is based on the fragment name and can be varied by additional arguments.
    This is used to uniquely cache different versions of a template fragment.

    """
    hasher = md5(usedforsecurity=False)
    if vary_on is not None:
        for arg in vary_on:
            hasher.update(str(arg).encode())
            hasher.update(b":")
    return TEMPLATE_FRAGMENT_KEY_TEMPLATE % (fragment_name, hasher.hexdigest())
