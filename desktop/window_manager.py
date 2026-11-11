import logging

from PySide6.QtCore import QObject, QThread, Signal

from commands.registry import CLOSE_SESSION, HANDLERS
from speech.microphone import record_until_silence

log = logging.getLogger("jarvis.window_manager")


class ListenWorker(QThread):
    status_changed = Signal(str)
    transcript_ready = Signal(str)
    finished_cycle = Signal(str, str)

    def __init__(self, settings, stt, tts, ai):
        super().__init__()
        self._settings = settings
        self._stt = stt
        self._tts = tts
        self._ai = ai
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

        self.status_changed.emit("Transcribing...")
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
        self.status_changed.emit("Thinking...")

        command_name, reply = self._ai.think(text)
        if self._cancelled:
            return

        if command_name:
            handler = HANDLERS.get(command_name)
            success, failure_message = handler(s) if handler else (True, "")
            if not success:
                # The model assumed success when it wrote its reply; a real,
                # concrete failure (e.g. app not found) overrides that.
                reply = failure_message

        self.status_changed.emit(reply)
        self._tts.speak(reply)
        self.finished_cycle.emit(reply, command_name)


class SessionController(QObject):
    """Owns overlay + hotkey + speech/AI engines and drives a continuous listen/
    respond session: one hotkey press opens it, it keeps catching requests
    back-to-back, and it only closes when the user says a close phrase or
    presses the hotkey again.
    """

    IDLE = "idle"
    LISTENING = "listening"

    def __init__(self, overlay, settings, stt, tts, ai):
        super().__init__()
        self.overlay = overlay
        self.settings = settings
        self.stt = stt
        self.tts = tts
        self.ai = ai
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

        self._worker = ListenWorker(self.settings, self.stt, self.tts, self.ai)
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
