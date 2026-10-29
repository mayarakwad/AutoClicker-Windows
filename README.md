# AutoClicker for Windows

A lightweight auto clicker for Windows 10 and 11, modeled on OP Auto Clicker.
Python 3.12 and tkinter, with pynput and Win32 for mouse control and global hotkeys.

This is the Windows-only copy of [AutoClicker](https://github.com/mayarakwad/AutoClicker), which also has a macOS version. Changes are made there and exported here.

## Install

### Installer (recommended)

Download **[AutoClicker-Setup.exe](https://github.com/mayarakwad/AutoClicker-Windows/releases/latest/download/AutoClicker-Setup.exe)** from the latest release and run it. Setup asks:

- **Install for all users or just for you.** All users installs to `C:\Program Files\AutoClicker` and needs admin rights. Just me installs to `%LOCALAPPDATA%\Programs\AutoClicker` and doesn't.
- **Where to install.** Click **Browse** to choose another folder.
- **Shortcuts.** A Start menu shortcut is always made. **Create a desktop shortcut** and **Pin to taskbar** are ticked; untick the ones you don't want.
  - For all users, the desktop shortcut goes on every user's desktop. The taskbar pin is only for the user who runs Setup.
  - Windows has no supported way for installers to pin apps, and newer Windows 11 builds ignore Setup's request. If that happens, the last page of Setup says so: open Start, type **AutoClicker**, right-click it in the results and choose **Pin to taskbar**.

To update, run the newer Setup. It closes AutoClicker first, installs to the same folder and remembers your choices. To move AutoClicker to another folder, uninstall it, then install again.

To uninstall, open **Settings > Apps** (**Installed apps** on Windows 11, **Apps & features** on Windows 10), find **AutoClicker** and choose **Uninstall** (on Windows 11 it's in the **...** menu). This also unpins it from the taskbar for the account that runs the uninstall; anyone else who pinned it right-clicks the icon and chooses **Unpin from taskbar**. Your settings in `%APPDATA%\AutoClicker` are kept.

Silent installs take the same choices on the command line. In PowerShell or cmd, in the folder with the download:

```
.\AutoClicker-Setup.exe /VERYSILENT /ALLUSERS /DIR="D:\Apps\AutoClicker" /TASKS="desktopicon,taskbarpin"
```

Use `/CURRENTUSER` for just me. `/TASKS` lists the shortcuts to make. Without it, a first install makes both and an update keeps your earlier choices.

### Without installing: one command

Paste this into PowerShell. It downloads the latest release to `%LOCALAPPDATA%\AutoClicker` and starts it, with no Start menu entry or uninstaller:

```
$ProgressPreference='SilentlyContinue'; $d="$env:LOCALAPPDATA\AutoClicker"; New-Item -ItemType Directory -Force $d | Out-Null; Invoke-WebRequest https://github.com/mayarakwad/AutoClicker-Windows/releases/latest/download/AutoClicker.exe -OutFile "$d\AutoClicker.exe"; Start-Process "$d\AutoClicker.exe"
```

Run the same line again to update; close AutoClicker first.

### Download with caution

Neither the installer nor the exe is code-signed, which matters in two cases.

- **Smart App Control:** Windows 11's Smart App Control blocks unsigned programs outright, with no "Run anyway". The error is "An Application Control policy has blocked this file".
  - On a PC with it turned on, run from source instead (below).
  - `make_shortcut.bat` then puts an **AutoClicker** shortcut on the Desktop that runs the app through the virtual environment's `pythonw.exe`. That file is signed by the Python Software Foundation, so it's allowed.
- **SmartScreen:** a copy downloaded with a browser shows a SmartScreen warning the first time. Click **More info**, then **Run anyway**.

## Build the .exe

```
build.bat
```

This creates the virtual environment if needed, installs `requirements.txt`, and builds `dist\AutoClicker.exe`: a single file of about 11 MB with no console window, made by PyInstaller `--onefile --windowed`. The exe has the app icon and version details (Properties > Details).

To change the icon, edit and run `.venv\Scripts\python assets\make_icon.py`, then rebuild.

## Build the installer

Install [Inno Setup](https://jrsoftware.org/isdl.php) 6.3 or later (or `winget install JRSoftware.InnoSetup`), then:

```
build_installer.bat
```

This runs `build.bat` if `dist\AutoClicker.exe` isn't built yet, then compiles `installer\AutoClicker.iss` into `dist\AutoClicker-Setup.exe`. The installer's version is read from the exe. `installer\pin_taskbar.ps1` pins and unpins the taskbar shortcut.

## Publish a release

Update the version in `version_info.txt`, then push a version tag: `git tag v1.0.2` then `git push origin v1.0.2`. Or, on GitHub, open **Actions > Windows build > Run workflow** and enter the tag (for example `v1.0.2`). Either way, the GitHub build tests everything, then publishes `AutoClicker-Setup.exe` and `AutoClicker.exe` to the release. The tag must match the version in `version_info.txt`.

## Run from source

Install Python 3.12 from [python.org](https://www.python.org/downloads/windows/), then:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pythonw main.py
```

Use `python` instead of `pythonw` to keep a console window open for error messages.

## How to use

- **Click interval:** hours, mins, secs, milliseconds and nanoseconds, at least 0.1 ms (100000 ns) in total. For example, 1 ms + 500000 ns = 1.5 ms. Tick **Random offset ± N ms** to vary each delay randomly by up to N ms; a delay never drops below 0.1 ms.
  - Intervals under 2 ms are timed by watching the clock instead of sleeping, so one CPU core stays busy while clicking that fast.
  - Windows limits how fast clicks actually go through. On the development PC that was about 3,500 clicks a second at the cursor and 1,500 at a picked location. Shorter intervals just click that fast, and many apps and games don't register clicks that quickly.
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
