"""
Sets up the terminal color scheme.
"""

import functools
import os
import sys

from django.utils import termcolors

try:
    import colorama

    # Avoid initializing colorama in non-Windows platforms.
    colorama.just_fix_windows_console()
except (
    AttributeError,  # colorama <= 0.4.6.
    ImportError,  # colorama is not installed.
    # If just_fix_windows_console() accesses sys.stdout with
    # WSGIRestrictedStdout.
    OSError,
):
    HAS_COLORAMA = False
else:
    HAS_COLORAMA = True


def supports_color():
    """
    Return True if the running system's terminal supports color, 
    and False otherwise. This check applies various methods to 
    determine color support, including platform detection, environment 
    variable checks, and registry inspection for Windows platforms.
    """

    def vt_codes_enabled_in_windows_registry():
        """
        Check if VT code handling is enabled in the Windows Registry by default, indicating support for ANSI escape sequences in the console.
        """
        try:
            # winreg is only available on Windows.
            import winreg
        except ImportError:
            return False
        else:
            try:
                reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Console")
                reg_key_value, _ = winreg.QueryValueEx(reg_key, "VirtualTerminalLevel")
            except FileNotFoundError:
                return False
            else:
                return reg_key_value == 1

    # isatty is not always implemented, #6223.
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    return is_a_tty and (
        sys.platform != "win32"
        or (HAS_COLORAMA and getattr(colorama, "fixed_windows_console", False))
        or "ANSICON" in os.environ
        or
        # Windows Terminal supports VT codes.
        "WT_SESSION" in os.environ
        or
        # Microsoft Visual Studio Code's built-in terminal supports colors.
        os.environ.get("TERM_PROGRAM") == "vscode"
        or vt_codes_enabled_in_windows_registry()
    )


class Style:
    pass


def make_style(config_string=""):
    """
    Create a Style object from the given configuration string, 
    falling back to the default color palette if no configuration is provided. 
    The resulting Style object encapsulates color settings for various roles, 
    allowing for styled output in a terminal environment.
    """

    style = Style()

    color_settings = termcolors.parse_color_setting(config_string)

    # The nocolor palette has all available roles.
    # Use that palette as the basis for populating
    # the palette as defined in the environment.
    for role in termcolors.PALETTES[termcolors.NOCOLOR_PALETTE]:
        if color_settings:
            format = color_settings.get(role, {})
            style_func = termcolors.make_style(**format)
        else:

            def style_func(x):
                return x

        setattr(style, role, style_func)

    # For backwards compatibility,
    # set style for ERROR_OUTPUT == ERROR
    style.ERROR_OUTPUT = style.ERROR

    return style


@functools.cache
def no_style():
    """
    Return a Style object with no color scheme.
    """
    return make_style("nocolor")


def color_style(force_color=False):
    """
    Return a Style object from the Django color scheme.
    """
    if not force_color and not supports_color():
        return no_style()
    return make_style(os.environ.get("DJANGO_COLORS", ""))
