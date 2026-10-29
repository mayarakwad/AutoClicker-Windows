# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## This repository is generated

This is the Windows-only copy of github.com/mayarakwad/AutoClicker (local folder `C:\Projects\AutoClicker`). `tools/export_windows.py` in that project writes this folder from its last commit:
- It copies everything except the macOS-only files.
- It lays the main project's `windows/` folder on top. That folder holds this README, this CLAUDE.md, the Windows-only `platforms/__init__.py`, `.github/workflows/build-windows.yml`, `.github/test_installer.ps1`, `build_installer.bat` and `installer/`.

**Make code changes in the main project, commit them there, then export:**

```
C:\Projects\AutoClicker\.venv\Scripts\python C:\Projects\AutoClicker\tools\export_windows.py C:\Projects\AutoClicker-Windows
```

Then commit and push here. Anything edited only here is overwritten by the next export. The shared modules still mention macOS in a few places (for example `theme.py`'s native-dark branch); that's expected.

## Project

Windows desktop auto clicker modeled on OP Auto Clicker. Python 3.12 + tkinter (UI) + pynput and Win32 (mouse control, global hotkeys), packaged as a single exe with PyInstaller.

Features:
- Interval clicking with a random offset.
- Single and double clicks.
- Pick location.
- Repeat N times or until stopped.
- Global F6 hotkey (configurable).
- Esc and top-left-corner fail-safe.
- Record & Playback.
- Personalize: theme, always on top, opacity, sounds.
- Settings saved to `%APPDATA%\AutoClicker\settings.json`.

Requirements that always apply:
- Clicking never blocks the UI.
- Esc or the mouse in the top-left corner stops clicking immediately.
- Inputs are validated (no empty/negative values, interval ≥ 0.1 ms, `engine.MIN_INTERVAL_NS`).
- The status line shows Running/Stopped and the click count.

## Commands

```
.venv\Scripts\python main.py              # run the app
.venv\Scripts\python -m unittest          # all tests
.venv\Scripts\pip install -r requirements.txt
build.bat                                 # -> dist\AutoClicker.exe
build_installer.bat                       # -> dist\AutoClicker-Setup.exe (needs Inno Setup 6.3+)
make_shortcut.bat                         # Desktop shortcut running from source (for Smart App Control PCs)
```

Pushing to GitHub runs `.github/workflows/build-windows.yml` on windows-latest: unit tests, build the exe and the installer, upload both, check the exe starts, then `.github/test_installer.ps1` installs and uninstalls the installer silently (just me in a chosen folder, and all users) and checks the files, shortcuts and Apps entry. Pushing a `v*` tag also publishes `AutoClicker-Setup.exe` and `AutoClicker.exe` as a release; the README links `releases/latest/download/AutoClicker-Setup.exe`, and its one-command install downloads `releases/latest/download/AutoClicker.exe`. The release version comes from `version_info.txt`; bump it before tagging.

## Installer

`installer/AutoClicker.iss` (Inno Setup 6.3 or later; 7 works too) packs `dist\AutoClicker.exe` into `dist\AutoClicker-Setup.exe`:
- `PrivilegesRequired=lowest` with `PrivilegesRequiredOverridesAllowed=dialog commandline` gives the "all users / just me" choice. All users installs to `C:\Program Files\AutoClicker`; just me to `%LOCALAPPDATA%\Programs\AutoClicker`. `{autoprograms}`/`{autodesktop}` follow that choice.
- Keep the `AppId` GUID unchanged; it ties upgrades and uninstall together. `.github/test_installer.ps1` uses it too.
- Asks for the folder only on a first install (`DisableDirPage=auto`); updates reuse it.
- Tasks: `desktopicon` and `taskbarpin`, both ticked by default (a first silent install without `/TASKS` does both; updates reuse the previous choices through the default `UsePreviousTasks=yes`). Under Inno Setup 7 the script sets `SetupArchitecture=x64`, so `{sys}` is the 64-bit System32 and the pin runs in 64-bit PowerShell, as with Inno Setup 6. `[InstallDelete]` removes an earlier desktop shortcut when an update unticks it. Windows has no supported pin API, so `installer/pin_taskbar.ps1` invokes the taskbar's own pin command through a temporary `HKCU\Software\Classes\*\shell\AutoClickerTaskbarPin` verb. It runs as the signed-in user (`ExecAsOriginalUser`), checks the `User Pinned\TaskBar` folder for the result, and the Finished page tells the user how to pin by hand if Windows refused. Newer Windows 11 builds refuse. Its exit codes (2 ignored, 3 no shortcut, 4 no answer, 5 error) go to Setup's log. The uninstaller runs it with `-Target <exe> -Unpin` through plain `Exec`, because `ExecAsOriginalUser` is Setup-only; for an all-users uninstall it unpins only for the account that approved the UAC prompt.
- Settings in `%APPDATA%\AutoClicker` are left on uninstall.

GitHub only shows logs to signed-in users. `.github/annotate_test_failures.py` posts failing tests as annotations, readable via `api.github.com/repos/mayarakwad/AutoClicker-Windows/check-runs/<job id>/annotations`. On Windows PowerShell 5.1, pass commit messages with `git commit -F <file>`, because double quotes inside `-m` get mangled.

## Architecture

Several threads; only the main thread touches tkinter:
- `ui.App` polls every 50 ms: it drains a queue of events from the hook threads and reads the engine's state.
- `platforms/windows.py` holds everything Windows-specific:
  - `Mouse`: clicks via pynput; clicks at X/Y as one SendInput batch (move, click, move back).
  - `PointPicker`: a pynput hook that swallows the pick click.
  - `MouseListener` (recording) and `KeySource` (hotkeys): keys are named by virtual-key code, and modifiers come from `GetAsyncKeyState`.
  - Also: DPI awareness, registry dark mode, DWM title bars, beeps, and the settings folder.
- `engine.ClickEngine` clicks on a background thread against `perf_counter` deadlines, sleeping at most 50 ms at a time so stop and the corner fail-safe react fast. Don't swap `time.sleep` for `Event.wait`, which has about 15.6 ms granularity. Waits under 2 ms (`SPIN_SECONDS`, intervals set with the nanoseconds box) spin on `perf_counter` instead. Real clicks top out around 3,500/s at the cursor and 1,500/s at a picked point on the dev PC.
- `hotkeys.HotkeyListener` holds the combo logic. `theme.py` uses `vista` for light and a styled `clam` for dark.

Tests use a fake mouse and must never send real input or write the real `%APPDATA%` file (`App(root, settings_path=...)`).
