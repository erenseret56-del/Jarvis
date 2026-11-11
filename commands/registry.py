from commands import app_launcher

OPEN_VSCODE = "open_vscode"
CLOSE_SESSION = "close_session"


def _handle_open_vscode(settings: dict) -> tuple[bool, str]:
    app_config = settings["apps"]["vscode"]
    return app_launcher.launch(app_config)


def _handle_close_session(settings: dict) -> tuple[bool, str]:
    return True, ""


# The only actions that can ever actually run. ai.local_model.LocalAI decides
# which (if any) of these names applies to what the user said, but execution
# always comes back through this fixed, explicit dispatch table — never
# anything the model generates directly.
HANDLERS = {
    OPEN_VSCODE: _handle_open_vscode,
    CLOSE_SESSION: _handle_close_session,
}
