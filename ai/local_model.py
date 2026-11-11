import difflib
import json
import logging
import random
import re

from llama_cpp import Llama, LlamaGrammar

log = logging.getLogger("jarvis.ai")

# Forces the model's output into exactly this JSON shape. "reply" is generated
# before "command" on purpose: the model's own already-written sentence then
# grounds its command choice, instead of guessing the command cold.
_GRAMMAR = r"""
root    ::= "{" ws "\"reply\":" ws string "," ws "\"command\":" ws command ws "}"
command ::= "\"open_vscode\"" | "\"close_session\"" | "\"none\""
string  ::= "\"" char* "\""
char    ::= [^"\\\n] | "\\" ["\\/bfnrt]
ws      ::= [ \t\n]*
"""

_SYSTEM_PROMPT = """You are JARVIS, a local desktop voice assistant. You only know these actions:
- open_vscode: opens the VS Code editor. ONLY pick this if the user clearly asks to open/launch a code editor or VS Code (even if the words are garbled, e.g. "vs coal").
- close_session: ends this listening session. ONLY pick this if the user clearly wants to stop/end/close the conversation.
- none: no action. Use this for greetings, small talk, questions, or any request you cannot actually do (you have no other apps or abilities yet).

Examples:
User: hey there -> {"reply": "Hey! What can I do for you?", "command": "none"}
User: good morning -> {"reply": "Good morning to you too!", "command": "none"}
User: open vs coal -> {"reply": "Sure, opening VS Code now.", "command": "open_vscode"}
User: can you launch my editor -> {"reply": "Got it, launching VS Code.", "command": "open_vscode"}
User: okay stop -> {"reply": "Alright, signing off.", "command": "close_session"}
User: what is 2 plus 2 -> {"reply": "That is 4.", "command": "none"}
User: open photoshop -> {"reply": "I can not do that yet, I can only open VS Code for now.", "command": "none"}
User: play some music -> {"reply": "I do not have that ability yet.", "command": "none"}

Write "reply" FIRST, as your natural spoken answer to the user (under 20 words, no markdown). Then set "command" to match what that reply actually does. Never claim to do something you have no command for.
Respond ONLY with JSON matching: {"reply": "...", "command": "open_vscode"|"close_session"|"none"}"""

_VSCODE_KEYWORDS = ["code", "vscode", "studio", "editor"]
_VSCODE_NEAR_MISS = {"coal", "call", "goal", "cole", "co"}
_CLOSE_WORDS = {"close", "stop", "exit", "quit", "done", "bye", "goodbye"}
_WORD_RE = re.compile(r"[a-z']+")
_TOKEN_RATIO_CUTOFF = 0.75


def _looks_like_vscode_request(user_text: str) -> bool:
    tokens = _WORD_RE.findall(user_text.lower())
    for token in tokens:
        if token in _VSCODE_NEAR_MISS:
            return True
        for kw in _VSCODE_KEYWORDS:
            if difflib.SequenceMatcher(None, token, kw).ratio() >= _TOKEN_RATIO_CUTOFF:
                return True
    return False


def _looks_like_close_request(user_text: str) -> bool:
    lowered = user_text.lower()
    tokens = set(_WORD_RE.findall(lowered))
    if tokens & _CLOSE_WORDS:
        return True
    return "that's all" in lowered or "thats all" in lowered


class LocalAI:
    """Small local chat model (GGUF, CPU, via llama.cpp) that understands
    free-form speech, decides which (if any) allow-listed action it maps to, and
    writes the spoken reply. Runs fully offline — nothing leaves the device.

    Safety: the model's "command" choice is grammar-constrained to only ever be
    one of the fixed action names below, and is then double-checked in code
    against the user's actual words before anything is executed (see
    _looks_like_vscode_request / _looks_like_close_request). The model can talk
    about anything, but it can never cause an action it wasn't verified for.
    """

    def __init__(
        self,
        model_path: str,
        n_ctx: int,
        n_threads: int,
        temperature: float,
        max_tokens: int,
    ):
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._grammar = LlamaGrammar.from_string(_GRAMMAR)
        log.info("Loading local AI model from '%s'...", model_path)
        self._llm = Llama(
            model_path=model_path, n_ctx=n_ctx, n_threads=n_threads, verbose=False
        )
        log.info("Local AI model loaded.")

    def think(self, user_text: str) -> tuple[str, str]:
        """Returns (command_name, reply_text). command_name is "" when no
        allow-listed action applies — the reply is still spoken either way."""
        try:
            out = self._llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                grammar=self._grammar,
            )
            content = out["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            command = parsed.get("command", "none")
            reply = parsed.get("reply", "").strip()
        except Exception:
            log.exception("Local AI generation failed.")
            return "", random.choice([
                "Sorry, I had trouble thinking that through.",
                "Something went wrong on my end, try again.",
            ])

        if command == "open_vscode" and not _looks_like_vscode_request(user_text):
            log.info(
                "Overriding model's open_vscode choice; not confirmed by the words "
                "used: %r",
                user_text,
            )
            command = "none"
            reply = "I can only open VS Code right now, and that didn't sound like it."
        elif command == "close_session" and not _looks_like_close_request(user_text):
            log.info(
                "Overriding model's close_session choice; not confirmed by the "
                "words used: %r",
                user_text,
            )
            command = "none"

        if command not in ("open_vscode", "close_session"):
            command = ""
        if not reply:
            reply = "Okay."
        return command, reply
