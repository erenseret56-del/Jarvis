import difflib
import re

from commands import app_launcher

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = _PUNCT_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text


def _handle_open_vscode(settings: dict) -> tuple[bool, str]:
    app_config = settings["apps"]["vscode"]
    success, message = app_launcher.launch(app_config)
    if success:
        return True, "Opening Visual Studio Code."
    return False, message


COMMANDS = [
    {
        "name": "open_vscode",
        "aliases": [
            "open vs code",
            "open visual studio code",
            "launch vs code",
            "launch visual studio code",
        ],
        "handler": _handle_open_vscode,
    },
]


def match_command(raw_text: str, fuzzy_cutoff: float = 0.75):
    """Match recognized speech against the command registry.

    Returns the matching command dict, or None if nothing matched closely enough.
    Only commands explicitly registered above can ever be returned — unknown or
    ambiguous phrases never trigger an action.
    """
    text = normalize(raw_text)
    if not text:
        return None

    for command in COMMANDS:
        if text in command["aliases"]:
            return command

    alias_to_command = {
        alias: command for command in COMMANDS for alias in command["aliases"]
    }
    close = difflib.get_close_matches(
        text, alias_to_command.keys(), n=1, cutoff=fuzzy_cutoff
    )
    if close:
        return alias_to_command[close[0]]

    return None
