import platform


def on_macos_with_hfs():
    """
    This is a comment
    """
    macos_version = platform.mac_ver()[0]
    if macos_version != "":
        parsed_macos_version = tuple(int(x) for x in macos_version.split("."))
        return parsed_macos_version < (10, 14)
    return False
