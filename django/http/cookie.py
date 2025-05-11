from http import cookies

# For backwards compatibility in Django 2.1.
SimpleCookie = cookies.SimpleCookie


def parse_cookie(cookie):
    """

    Return a dictionary parsed from a `Cookie:` header string.

    This function takes a string representing a Cookie header, parses its contents, 
    and returns a dictionary where keys are cookie names and values are their corresponding values.

    """
    cookiedict = {}
    for chunk in cookie.split(";"):
        if "=" in chunk:
            key, val = chunk.split("=", 1)
        else:
            # Assume an empty name per
            # https://bugzilla.mozilla.org/show_bug.cgi?id=169091
            key, val = "", chunk
        key, val = key.strip(), val.strip()
        if key or val:
            # unquote using Python's algorithm.
            cookiedict[key] = cookies._unquote(val)
    return cookiedict
