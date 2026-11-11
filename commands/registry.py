import difflib
import random
import re

from commands import app_launcher

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")

CLOSE_SESSION = "close_session"

# Near-miss tolerance for a single mangled word, e.g. offline STT hearing "code"
# as "cold". Not a cure for a wholly different transcription — only for a word
# that still looks close to the real one. 0.75 is deliberately strict: looser
# cutoffs started matching unrelated real words (e.g. "store" against "stop").
_TOKEN_RATIO_CUTOFF = 0.75


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = _PUNCT_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text


def _token_matches_keyword(token: str, keyword: str, near_miss_words: set) -> bool:
    if len(token) < 2:
        return False
    if token in near_miss_words:
        return True
    return difflib.SequenceMatcher(None, token, keyword).ratio() >= _TOKEN_RATIO_CUTOFF


def _handle_open_vscode(settings: dict) -> tuple[bool, str]:
    app_config = settings["apps"]["vscode"]
    success, message = app_launcher.launch(app_config)
    if success:
        return True, random.choice([
            "Opening VS Code now.",
            "Sure, launching VS Code.",
            "Got it, VS Code is coming up.",
        ])
    return False, message


def _handle_close_session(settings: dict) -> tuple[bool, str]:
    return True, random.choice([
        "Alright, signing off.",
        "Okay, closing down.",
        "Got it, see you.",
    ])


def _handle_greeting(settings: dict) -> tuple[bool, str]:
    return True, random.choice([
        "Hey! What can I do for you?",
        "Hi there, I'm listening.",
        "Hey, what's up?",
        "Hi! Go ahead.",
    ])


COMMANDS = [
    {
        "name": "open_vscode",
        "aliases": [
            "open vs code",
            "open visual studio code",
            "launch vs code",
            "launch visual studio code",
        ],
        # Used only as a last-resort fallback when the whole phrase doesn't match
        # closely enough — catches a single garbled word around a clean intent.
        "keywords": ["code", "vscode", "studio"],
        "near_miss_words": {"coal", "call", "goal", "cole", "co"},
        "handler": _handle_open_vscode,
    },
    {
        "name": CLOSE_SESSION,
        "aliases": [
            "close",
            "stop",
            "stop listening",
            "jarvis close",
            "jarvis stop",
            "ok jarvis close",
            "that's all",
            "thats all",
            "goodbye jarvis",
            "never mind",
            "exit",
        ],
        # No keyword fallback here on purpose: "close"/"stop" are common real
        # words, and the exact/fuzzy phrase passes above already catch the
        # intended short close phrases without risking an unrelated sentence
        # ("close to the store") ending the session.
        "handler": _handle_close_session,
    },
    {
        "name": "greeting",
        "aliases": [
            "hi",
            "hey",
            "hello",
            "hey jarvis",
            "hi jarvis",
            "yo",
            "sup",
            "whats up",
            "what's up",
        ],
        # No keyword fallback: greeting only triggers on the phrase itself, so
        # "hey" inside "hey jarvis open vs code" can't hijack a real command.
        "handler": _handle_greeting,
    },
]


def match_command(raw_text: str, fuzzy_cutoff: float = 0.75):
    """Match recognized speech against the command registry.

    Returns the matching command dict, or None if nothing matched closely enough.
    Only commands explicitly registered above can ever be returned — unknown or
    ambiguous phrases never trigger an action.

    Matching is tried in three passes, each only applied if the previous found
    nothing: 1) the full phrase said exactly, 2) the full phrase close enough to
    an alias (handles stray words, e.g. "hey jarvis open vs code"), 3) a single
    keyword fuzzily/phonetically close to a command's core keyword (handles one
    mangled word inside an otherwise clear phrase).
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

    tokens = text.split()
    for command in COMMANDS:
        keywords = command.get("keywords")
        if not keywords:
            continue
        near_miss_words = command.get("near_miss_words", set())
        for token in tokens:
            if any(
                _token_matches_keyword(token, kw, near_miss_words) for kw in keywords
            ):
                return command

    return None
