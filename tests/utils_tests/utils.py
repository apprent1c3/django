import platform


def on_macos_with_hfs():
    """
    Checks if the current macOS version is using HFS+ filepath, where time resolution is limited to one second, affecting test reliability.
    """
    macos_version = platform.mac_ver()[0]
    if macos_version != "":
        parsed_macos_version = tuple(int(x) for x in macos_version.split("."))
        return parsed_macos_version < (10, 14)
    return False
