import ipaddress

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def clean_ipv6_address(
    ip_str, unpack_ipv4=False, error_message=_("This is not a valid IPv6 address.")
):
    """
    This is a comment
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
    This is a comment
    """
    try:
        ipaddress.IPv6Address(ip_str)
    except ValueError:
        return False
    return True
