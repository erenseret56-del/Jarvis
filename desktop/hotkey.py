import logging

import keyboard

log = logging.getLogger("jarvis.hotkey")


class HotkeyManager:
    """Registers a global hotkey that invokes a callback from a background thread.

    keyboard.add_hotkey fires its callback on keyboard's own listener thread, not the
    Qt thread. The callback given here must be safe to call cross-thread (e.g. emitting
    a Qt Signal, which Qt marshals to the receiver's thread automatically).
    """

    def __init__(self, hotkey: str, on_trigger):
        self.hotkey = hotkey
        self.on_trigger = on_trigger
        self._registered = False

    def start(self):
        try:
            keyboard.add_hotkey(self.hotkey, self.on_trigger)
            self._registered = True
            log.info("Hotkey '%s' registered.", self.hotkey)
        except Exception:
            log.exception(
                "Failed to register hotkey '%s'. It may be in use by another "
                "application, or this process may need to run with sufficient "
                "privileges.",
                self.hotkey,
            )

    def stop(self):
        if self._registered:
            try:
                keyboard.remove_hotkey(self.hotkey)
            except KeyError:
                pass
            self._registered = False
