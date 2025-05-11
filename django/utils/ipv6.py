import ipaddress

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def clean_ipv6_address(
    ip_str, unpack_ipv4=False, error_message=_("This is not a valid IPv6 address.")
):
    """
    Clean an IPv6 address string to a standardized format.

    This function validates the input IPv6 address and raises a ValidationError if it is invalid.
    It then normalizes the address by replacing the longest sequence of zeros with '::', removing leading zeros, and converting all hexadecimal values to lowercase.

    Parameters:
        ip_str (str): The IPv6 address to be cleaned.
        unpack_ipv4 (bool): If True, returns the plain IPv4 address if the input is an IPv4-mapped address (default is False).
        error_message (str): The error message to be used in the ValidationError (default is 'This is not a valid IPv6 address.').

    Returns:
        str: The cleaned IPv6 address or the plain IPv4 address if unpack_ipv4 is True.
    """
    try:
        addr = ipaddress.IPv6Address(int(ipaddress.IPv6Address(ip_str)))
    except ValueError:
        raise ValidationError(
            error_message, code="invalid", params={"protocol": _("IPv6")}
        )

    if unpack_ipv4 and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    elif addr.ipv4_mapped:
        return "::ffff:%s" % str(addr.ipv4_mapped)

    return str(addr)


def is_valid_ipv6_address(ip_str):
    """
    Returns whether a given string represents a valid IPv6 address.
    """
    try:
        ipaddress.IPv6Address(ip_str)
    except ValueError:
        return False
    return True
