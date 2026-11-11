import logging

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from commands.registry import match_command
from speech.microphone import record_until_silence

log = logging.getLogger("jarvis.window_manager")


class ListenWorker(QThread):
    status_changed = Signal(str)
    transcript_ready = Signal(str)
    finished_cycle = Signal(str)

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
        self.transcript_ready.emit(text if text else "(nothing recognized)")
        if self._cancelled:
            return

        command = match_command(text, fuzzy_cutoff=s["fuzzy_match_cutoff"])
        if command is None:
            response = "Command not recognized."
        else:
            try:
                success, response = command["handler"](s)
            except Exception:
                log.exception("Command handler '%s' raised an error.", command["name"])
                success, response = False, "That command failed to run."

        if self._cancelled:
            return

        self.status_changed.emit(response)
        self._tts.speak(response)
        self.finished_cycle.emit(response)


class SessionController(QObject):
    """Owns overlay + hotkey + speech engines and drives the summon/listen/respond loop."""

    IDLE_HIDDEN = "idle_hidden"
    LISTENING = "listening"
    IDLE_VISIBLE = "idle_visible"

    def __init__(self, overlay, settings, stt, tts):
        super().__init__()
        self.overlay = overlay
        self.settings = settings
        self.stt = stt
        self.tts = tts
        self.state = self.IDLE_HIDDEN
        self._worker = None

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)

        self.overlay.trigger_listen.connect(self.on_hotkey)

    def on_hotkey(self):
        if self.state in (self.LISTENING,):
            self._cancel_current()
            self.overlay.hide_overlay()
            self.state = self.IDLE_HIDDEN
        elif self.state == self.IDLE_VISIBLE:
            self._hide_timer.stop()
            self.overlay.hide_overlay()
            self.state = self.IDLE_HIDDEN
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

    def _on_cycle_finished(self, _response: str):
        self.state = self.IDLE_VISIBLE
        self._hide_timer.start(int(self.settings["hide_after_seconds"] * 1000))

    def _auto_hide(self):
        if self.state == self.IDLE_VISIBLE:
            self.overlay.hide_overlay()
            self.state = self.IDLE_HIDDEN

    def _cancel_current(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
