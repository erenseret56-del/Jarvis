import json
import logging
import os
import sys

# llama_cpp's native backend must finish loading its own DLLs before PySide6
# touches the process's DLL search path — importing Qt first makes llama.cpp's
# backend init segfault (access violation in llama_backend_init). Importing it
# here, before any PySide6 import, is what avoids that.
from ai.local_model import LocalAI

from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from desktop.hotkey import HotkeyManager
from desktop.overlay import OverlayWindow
from desktop.window_manager import SessionController
from speech.speech_to_text import ModelNotFoundError, VoskSTT
from speech.text_to_speech import LocalTTS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_logging():
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "jarvis.log"), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_settings():
    path = os.path.join(BASE_DIR, "config", "settings.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("#7ec8ff"))
    return QIcon(pixmap)


def main():
    setup_logging()
    log = logging.getLogger("jarvis.main")
    settings = load_settings()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    tray = QSystemTrayIcon(make_tray_icon())
    tray.setToolTip(f"JARVIS — {settings['hotkey']} to summon")
    tray_menu = QMenu()
    quit_action = tray_menu.addAction("Quit JARVIS")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(tray_menu)
    tray.show()

    overlay = OverlayWindow()

    model_path = os.path.join(BASE_DIR, settings["vosk_model_path"])
    try:
        stt = VoskSTT(model_path, settings["sample_rate"])
    except ModelNotFoundError as exc:
        log.error(str(exc))
        overlay.set_status("Setup needed")
        overlay.set_transcript(str(exc))
        overlay.show_overlay()
        return app.exec()

    llm_path = os.path.join(BASE_DIR, settings["llm_model_path"])
    if not os.path.isfile(llm_path):
        message = (
            f"Local AI model not found at '{llm_path}'. Download it (see README) "
            "and update config/settings.json 'llm_model_path' if needed."
        )
        log.error(message)
        overlay.set_status("Setup needed")
        overlay.set_transcript(message)
        overlay.show_overlay()
        return app.exec()

    overlay.set_status("Loading local AI model...")
    overlay.show_overlay()
    app.processEvents()
    ai = LocalAI(
        model_path=llm_path,
        n_ctx=settings["llm_n_ctx"],
        n_threads=settings["llm_n_threads"],
        temperature=settings["llm_temperature"],
        max_tokens=settings["llm_max_tokens"],
    )
    overlay.hide_overlay()

    tts = LocalTTS(settings["tts_rate"], settings["tts_volume"])

    controller = SessionController(overlay, settings, stt, tts, ai)

    hotkey_manager = HotkeyManager(settings["hotkey"], overlay.trigger_listen.emit)
    hotkey_manager.start()

    log.info("JARVIS ready. Press '%s' to summon.", settings["hotkey"])
    exit_code = app.exec()
    hotkey_manager.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger("jarvis.main").exception("JARVIS crashed.")
        raise
