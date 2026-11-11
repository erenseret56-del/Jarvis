import logging
import threading

import pyttsx3

log = logging.getLogger("jarvis.tts")


class LocalTTS:
    """Local text-to-speech via Windows SAPI (through pyttsx3). Nothing sent to cloud."""

    def __init__(self, rate: int, volume: float):
        self._lock = threading.Lock()
        self._rate = rate
        self._volume = volume

    def speak(self, text: str):
        if not text:
            return
        with self._lock:
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", self._rate)
                engine.setProperty("volume", self._volume)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception:
                log.exception("TTS playback failed.")
