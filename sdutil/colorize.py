from enum import Enum


class Color(Enum):
    """Enumeration defining the colors that are supported."""
    BOLD = '1'
    CYAN = '0;36'
    GREEN = '0;32'
    RED = '0;31'
    YELLOW = '0;33'


def bold(text: str) -> str:
    """Return text formatted in bold."""
    return colorize(text, Color.BOLD)


def cyan(text: str) -> str:
    """Return text formatted in cyan."""
    return colorize(text, Color.CYAN)


def green(text: str) -> str:
    """Return text formatted in green."""
    return colorize(text, Color.GREEN)


def red(text: str) -> str:
    """Return text formatted in red."""
    return colorize(text, Color.RED)


def yellow(text: str) -> str:
    """Return text formatted in yellow."""
    return colorize(text, Color.YELLOW)


def colorize(text: str, color: Color) -> str:
    """Return text formatted in the specified color."""
    return f'\033[{color.value}m{text}\033[0m'
