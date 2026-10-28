# AutoClicker for Windows

A lightweight auto clicker for Windows 10 and 11, modeled on OP Auto Clicker.
Python 3.12 and tkinter, with pynput and Win32 for mouse control and global hotkeys.

This is the Windows-only copy of [AutoClicker](https://github.com/mayarakwad/AutoClicker), which also has a macOS version. Changes are made there and exported here.

## Install with one command

Paste this into PowerShell. It downloads the latest release to `%LOCALAPPDATA%\AutoClicker` and starts it:

```
$ProgressPreference='SilentlyContinue'; $d="$env:LOCALAPPDATA\AutoClicker"; New-Item -ItemType Directory -Force $d | Out-Null; Invoke-WebRequest https://github.com/mayarakwad/AutoClicker-Windows/releases/latest/download/AutoClicker.exe -OutFile "$d\AutoClicker.exe"; Start-Process "$d\AutoClicker.exe"
```

Run the same line again to update; close AutoClicker first.

**Download with caution:** the exe isn't code-signed, which matters in two cases.

- **Smart App Control:** Windows 11's Smart App Control blocks unsigned programs outright, with no "Run anyway". The error is "An Application Control policy has blocked this file".
  - On a PC with it turned on, run from source instead (below).
  - `make_shortcut.bat` then puts an **AutoClicker** shortcut on the Desktop that runs the app through the virtual environment's `pythonw.exe`. That file is signed by the Python Software Foundation, so it's allowed.
- **SmartScreen:** a copy downloaded with a browser shows a SmartScreen warning the first time. Click **More info**, then **Run anyway**.

Releases are published by the GitHub build when a version tag is pushed: `git tag v1.0.1` then `git push origin v1.0.1`.

## Build the .exe

```
build.bat
```

This creates the virtual environment if needed, installs `requirements.txt`, and builds `dist\AutoClicker.exe`: a single file of about 11 MB with no console window, made by PyInstaller `--onefile --windowed`. The exe has the app icon and version details (Properties > Details).

To change the icon, edit and run `.venv\Scripts\python assets\make_icon.py`, then rebuild.

## Run from source

Install Python 3.12 from [python.org](https://www.python.org/downloads/windows/), then:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pythonw main.py
```

Use `python` instead of `pythonw` to keep a console window open for error messages.

## How to use

- **Click interval:** hours, mins, secs and milliseconds (at least 1 ms in total). Tick **Random offset ± N ms** to vary each delay randomly by up to N ms; a delay never drops below 1 ms.
- **Click options:** mouse button (Left/Right/Middle) and click type (Single/Double). A double click counts as one click in the status line.
- **Click repeat:** stop after N clicks, or repeat until stopped.
- **Cursor position:**
  - **Current location** clicks wherever the cursor is.
  - **Pick location** clicks at X/Y. Press the **Pick location** button, then click anywhere on screen. That click is captured, not passed to the app underneath. Press Esc to cancel.
  - With a picked location, the cursor jumps to X/Y for each click and straight back, so you can still move the mouse.
  - X/Y can be negative on screens left of or above the main one.
- Press **Start** or **F6**. Press **Stop** or **F6** again to stop. F6 works even when the window is minimized or another app has focus.
- **Hotkey setting:** change F6 to another key or combination (for example F8 or Ctrl+Shift+S).
  - Click **Change**, press the new key, then **OK**. **Default (F6)** puts it back.
  - Esc is reserved for the fail-safe.
  - Letters, digits, Space and Enter need Ctrl or Alt. Keys still reach other apps, so a plain letter would start clicking while you type.
- **Record & Playback:** opens a window for recording a sequence of clicks and playing it back.
  - **Recording:** click **Record**, then click anywhere on screen. Each click's button, position and delay since the previous click is listed. The first delay counts from pressing Record. Clicks on AutoClicker's own windows aren't recorded, and the window stays on top while recording so **Stop** is always reachable. F6 or Esc also stops recording.
  - **Playback:** choose **Once** or **Loop until stopped**, then press **Play** or F6. The step being played is highlighted. F6, Esc or the top-left corner stops it. Like Pick location, the cursor jumps to each point and straight back.
  - While this window is open, F6 controls playback instead of the normal clicker.
  - The last recording is saved with your settings.
- **Personalize:** changes preview as you make them. **OK** keeps them, **Cancel** undoes them, and **Defaults** resets this dialog's options.
  - **Theme:** Same as Windows (follows Windows' light/dark app mode, even while AutoClicker is open), Light, or Dark. Dark covers every window, drop-down lists and title bars.
  - **Always on top:** keeps the main window above other apps.
  - **Opacity:** makes the main window see-through, from 40% to 100%.
  - **Sounds:** a rising beep when clicking starts and a falling one when it stops, whatever stopped it. **Test** plays it.
  - **Window position:** the window always reopens where you left it, as long as that spot is still on a screen.
- **Fail-safe:** press **Esc**, or move the mouse into the top-left corner of the main screen, and clicking stops immediately.
- The status line shows Running/Stopped, the click count, and why clicking stopped.
- **Saved settings:** all fields, the hotkey, the last recording, personalization and the window position are saved to `%APPDATA%\AutoClicker\settings.json` and restored on the next launch. Saving happens when you press Start, change the hotkey, press OK in Personalize, close the Record & Playback window, or close the app. Delete that file to go back to defaults. Missing or invalid values fall back to defaults.

Test stopping (F6, Esc, the corner) with a slow interval before trying very short ones.

Many online games ban auto clickers, so check a game's rules before using it there.

## Tests

```
.venv\Scripts\python -m unittest
```

The tests use a fake mouse and send no real input.

## Files

| File | What it does |
|---|---|
| `main.py` | Entry point. Turns on DPI awareness, then opens the window. |
| `ui.py` | tkinter window. Validates input and starts/stops the engine. |
| `engine.py` | Clicking and playback on a background thread. No UI code. |
| `recorder.py` | Records clicks anywhere on screen; converts recordings to and from JSON. |
| `recorder_window.py` | Record & Playback window. |
| `platforms/windows.py` | Everything Windows-specific: clicking (pynput plus one SendInput batch for clicks at X/Y), Pick location, recording, key events, screens, sounds, settings folder, title bars. |
| `hotkeys.py` | Global start/stop hotkey and Esc logic, key combos and their display names. |
| `hotkey_dialog.py` | Hotkey setting dialog. |
| `settings.py` | Reads and writes the settings JSON file. |
| `personalize_dialog.py` | Personalize dialog. |
| `theme.py` | Light/dark styling for every window, including title bars. |
| `tests/` | Unit tests. |
| `build.bat` | Builds `dist\AutoClicker.exe`. |
| `.github/workflows/build-windows.yml` | Builds and tests the exe on GitHub Actions, and publishes releases for version tags. |
| `make_shortcut.bat` | Creates a Desktop shortcut that runs the app from source (for PCs with Smart App Control on). |
| `version_info.txt` | Version details embedded in the exe. |
| `assets/` | `app.ico` and the script that draws it. |
