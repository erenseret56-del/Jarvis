import logging
import random

from PySide6.QtCore import QObject, QThread, Signal

from commands.registry import CLOSE_SESSION, match_command
from speech.microphone import record_until_silence

log = logging.getLogger("jarvis.window_manager")


class ListenWorker(QThread):
    status_changed = Signal(str)
    transcript_ready = Signal(str)
    finished_cycle = Signal(str, str)

    def __init__(self, settings, stt, tts):
        super().__init__()
        self._settings = settings
        self._stt = stt
        self._tts = tts
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        s = self._settings
        self.status_changed.emit("Listening...")
        audio = record_until_silence(
            samplerate=s["sample_rate"],
            max_seconds=s["max_listen_seconds"],
            silence_threshold=s["silence_threshold"],
            silence_duration=s["silence_duration"],
            should_cancel=lambda: self._cancelled,
        )
        if self._cancelled:
            return

        self.status_changed.emit("Thinking...")
        text = self._stt.transcribe(audio)
        if self._cancelled:
            return

        if not text:
            # Nothing was said this round — loop back to listening quietly,
            # without speaking, instead of nagging the user every few seconds.
            self.transcript_ready.emit("(nothing heard)")
            self.finished_cycle.emit("", "")
            return

        self.transcript_ready.emit(text)

        command = match_command(text, fuzzy_cutoff=s["fuzzy_match_cutoff"])
        command_name = command["name"] if command else ""
        if command is None:
            response = random.choice([
                "Hmm, I didn't catch a command in that.",
                "I don't have a command for that yet.",
                "Not sure what you mean there, try again?",
            ])
        else:
            try:
                _success, response = command["handler"](s)
            except Exception:
                log.exception("Command handler '%s' raised an error.", command["name"])
                response = "That command failed to run."

        if self._cancelled:
            return

        self.status_changed.emit(response)
        self._tts.speak(response)
        self.finished_cycle.emit(response, command_name)


class SessionController(QObject):
    """Owns overlay + hotkey + speech engines and drives a continuous listen/respond
    session: one hotkey press opens it, it keeps catching commands back-to-back, and
    it only closes when the user says a close phrase or presses the hotkey again.
    """

    IDLE = "idle"
    LISTENING = "listening"

    def __init__(self, overlay, settings, stt, tts):
        super().__init__()
        self.overlay = overlay
        self.settings = settings
        self.stt = stt
        self.tts = tts
        self.state = self.IDLE
        self._worker = None

        self.overlay.trigger_listen.connect(self.on_hotkey)

    def on_hotkey(self):
        if self.state == self.LISTENING:
            self._cancel_current()
            self.overlay.hide_overlay()
            self.state = self.IDLE
        else:
            self._start_cycle()

    def _start_cycle(self):
        self.state = self.LISTENING
        self.overlay.set_transcript("")
        self.overlay.set_status("Listening...")
        self.overlay.show_overlay()

        self._worker = ListenWorker(self.settings, self.stt, self.tts)
        self._worker.status_changed.connect(self.overlay.set_status)
        self._worker.transcript_ready.connect(self.overlay.set_transcript)
        self._worker.finished_cycle.connect(self._on_cycle_finished)
        self._worker.start()

    def _on_cycle_finished(self, _response: str, command_name: str):
        if self.state != self.LISTENING:
            return  # session was cancelled via hotkey while this cycle was wrapping up
        if command_name == CLOSE_SESSION:
            self.overlay.hide_overlay()
            self.state = self.IDLE
        else:
            self._start_cycle()

    def _cancel_current(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
