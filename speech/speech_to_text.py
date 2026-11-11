import json
import logging
import os

import numpy as np
from vosk import KaldiRecognizer, Model

log = logging.getLogger("jarvis.stt")


class ModelNotFoundError(RuntimeError):
    pass


class VoskSTT:
    """Thin wrapper over an offline Vosk model. No audio ever leaves the device."""

    def __init__(self, model_path: str, samplerate: int):
        if not os.path.isdir(model_path):
            raise ModelNotFoundError(
                f"Vosk model not found at '{model_path}'. Download a model from "
                "https://alphacephei.com/vosk/models (e.g. vosk-model-small-en-us-0.15), "
                "extract it, and point config/settings.json 'vosk_model_path' at it."
            )
        self.samplerate = samplerate
        self._model = Model(model_path)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        recognizer = KaldiRecognizer(self._model, self.samplerate)
        recognizer.AcceptWaveform(audio.tobytes())
        result = json.loads(recognizer.FinalResult())
        return result.get("text", "").strip()
