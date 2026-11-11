# JARVIS

Local, voice-controlled desktop assistant for Windows. A global hotkey opens a
floating overlay, an offline speech-to-text engine turns your voice into text,
a small local chat AI model (runs entirely on your machine, no cloud calls)
decides what you meant and replies naturally, and a fixed, explicit action
list is the only thing that ever actually executes. Nothing you say leaves
your device.

## Requirements

- Windows 10 or 11
- Python 3.12
- A microphone
- VS Code installed (the one action this build ships with opens it)
- ~1.2 GB free disk space (speech model + AI model)

## Setup

### 1. Get the code

Download the ZIP from GitHub and extract it, or clone it:

```
git clone https://github.com/erenseret56-del/Jarvis.git
cd Jarvis
```

### 2. Install Python dependencies

```
pip install -r requirements.txt
```

`llama-cpp-python` needs a C/C++ compiler to build from source. If the command
above fails on it, install the prebuilt Windows CPU wheel instead:

```
pip install llama-cpp-python --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

### 3. Download the offline speech recognition model (Vosk)

```
mkdir models
cd models
curl -L -o vosk-model.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
powershell -Command "Expand-Archive -Path vosk-model.zip -DestinationPath . -Force"
del vosk-model.zip
cd ..
```

This creates `models/vosk-model-small-en-us-0.15/`, which matches the default
`vosk_model_path` in `config/settings.json`.

### 4. Download the local AI model

This project uses **Qwen2.5-1.5B-Instruct**, quantized to GGUF (`Q4_K_M`,
~1.1 GB), run locally through `llama-cpp-python`. Any other instruct-tuned
GGUF model works too — point `llm_model_path` in `config/settings.json` at it
if you use a different one.

```
mkdir models\llm
cd models\llm
curl -L -o qwen2.5-1.5b-instruct-q4_k_m.gguf https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
cd ..\..
```

This creates `models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf`, which matches the
default `llm_model_path` in `config/settings.json`.

### 5. Run it

```
python main.py
```

A tray icon appears. Press **Ctrl+Space** to summon the overlay and start
talking.

## Configuration

All settings live in `config/settings.json`.

| Key | Meaning |
|---|---|
| `hotkey` | Global shortcut that opens/cancels the session |
| `vosk_model_path` | Folder of the offline speech recognition model |
| `sample_rate` | Microphone sample rate in Hz |
| `max_listen_seconds` | Hard cap on one recording |
| `silence_threshold` | Volume level below which audio counts as silence |
| `silence_duration` | Seconds of trailing silence that ends a recording |
| `tts_rate` | Speech speed for spoken replies |
| `tts_volume` | Speech volume, 0.0 to 1.0 |
| `llm_model_path` | Path to the local AI model `.gguf` file |
| `llm_n_ctx` | Context window size given to the model |
| `llm_n_threads` | CPU threads used for inference |
| `llm_temperature` | Reply randomness, 0.0 = deterministic |
| `llm_max_tokens` | Max tokens generated per reply |
| `apps.vscode.which` | Executable name to look up on PATH |
| `apps.vscode.fallback_paths` | Absolute paths tried if `which` fails |

## Usage

Press the hotkey, then speak. The session stays open and keeps listening for
more requests after each reply — it only closes when you say a close phrase
or press the hotkey again.

Examples of what you can say:

```
hey
open vs code
can you launch my editor
open vs coal          (still works even if your mic/STT mishears "code")
what is 5 times 6
jarvis stop            (ends the session)
```

The AI model understands free-form phrasing and chats back naturally for
anything that isn't an action it knows how to do. It can currently only
actually execute one action: opening VS Code. Everything else gets a spoken
reply with no action taken.

## Run automatically at login (optional)

```
$pythonw = Join-Path (Split-Path (Get-Command python).Source -Parent) "pythonw.exe"
$startupDir = [Environment]::GetFolderPath('Startup')
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $startupDir "JARVIS.lnk"))
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"<full path to Jarvis>\main.py"'
$shortcut.WorkingDirectory = "<full path to Jarvis>"
$shortcut.Save()
```

Replace `<full path to Jarvis>` with the folder you cloned/extracted into.
This runs JARVIS silently in the background (no console window) every time
you log in. Right-click the tray icon and choose **Quit JARVIS** to stop it;
delete the shortcut from `shell:startup` to remove autostart.

## Project structure

```
Jarvis/
  main.py                   entry point
  requirements.txt
  config/
    settings.json
  ai/
    local_model.py          local LLM: understands speech, writes replies
  desktop/
    overlay.py               floating status window
    hotkey.py                 global hotkey registration
    window_manager.py        listen/respond session loop
  speech/
    microphone.py             mic recording with silence detection
    speech_to_text.py        offline STT (Vosk)
    text_to_speech.py        offline TTS (Windows SAPI)
  commands/
    registry.py               the only actions that can ever execute
    app_launcher.py           launches configured apps
  models/                     downloaded models (not in the repo)
  logs/                       runtime log
```

## Safety design

The AI model never executes anything directly. It can only select from a
fixed, small set of action names (`open_vscode`, `close_session`, or `none`)
via grammar-constrained output, and that choice is checked again in code
against your actual words before `commands/registry.py` runs anything. If the
model ever claims to do something it has no real command for, the code-level
check overrides it and nothing runs.

## License

MIT — see [LICENSE](LICENSE).
