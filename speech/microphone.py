import logging

import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis.microphone")


def record_until_silence(
    samplerate: int,
    max_seconds: float,
    silence_threshold: float,
    silence_duration: float,
    should_cancel=None,
) -> np.ndarray:
    """Record int16 mono audio from the default mic until a trailing silence gap
    is detected, or until max_seconds elapses. Returns the recorded samples.

    should_cancel: optional zero-arg callable; if it returns True, recording stops
    early and whatever was captured so far is returned.
    """
    block_duration = 0.1
    block_size = int(samplerate * block_duration)
    silence_blocks_needed = max(1, int(silence_duration / block_duration))
    max_blocks = max(1, int(max_seconds / block_duration))

    frames = []
    trailing_silence = 0
    heard_speech = False

    with sd.InputStream(
        samplerate=samplerate, channels=1, dtype="int16", blocksize=block_size
    ) as stream:
        for _ in range(max_blocks):
            if should_cancel is not None and should_cancel():
                log.info("Recording cancelled.")
                break
            block, _ = stream.read(block_size)
            frames.append(block.copy())

            rms = float(np.sqrt(np.mean(np.square(block.astype(np.float32)))))
            if rms >= silence_threshold:
                heard_speech = True
                trailing_silence = 0
            elif heard_speech:
                trailing_silence += 1
                if trailing_silence >= silence_blocks_needed:
                    break

    if not frames:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(frames, axis=0).flatten()
