import logging
import os
import shutil
import subprocess

log = logging.getLogger("jarvis.app_launcher")


def launch(app_config: dict) -> tuple[bool, str]:
    """Launch an app described by a settings.json 'apps.<name>' entry.

    Tries `which` (an executable name resolvable on PATH) first, then falls back
    to configured absolute paths (with environment variables expanded).
    """
    which_name = app_config.get("which")
    if which_name:
        resolved = shutil.which(which_name)
        if resolved:
            return _spawn(resolved)

    for raw_path in app_config.get("fallback_paths", []):
        path = os.path.expandvars(raw_path)
        if os.path.isfile(path):
            return _spawn(path)

    return False, "Could not locate the application. Check config/settings.json app paths."


def _spawn(path: str) -> tuple[bool, str]:
    try:
        subprocess.Popen([path], close_fds=True)
        return True, "Launched."
    except Exception as exc:
        log.exception("Failed to launch '%s'", path)
        return False, f"Failed to launch: {exc}"
