@echo off
rem Builds dist\AutoClicker.exe: one file, no console window.
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    py -3.12 -m venv .venv 2>nul || python -m venv .venv || goto :failed
)

echo Installing requirements...
.venv\Scripts\python -m pip install --disable-pip-version-check -q -r requirements.txt || goto :failed

echo Building...
.venv\Scripts\python -m PyInstaller --noconfirm --clean --log-level WARN ^
    --onefile --windowed --name AutoClicker ^
    --icon assets\app.ico --add-data "assets\app.ico;assets" ^
    --version-file version_info.txt --exclude-module platforms.macos ^
    main.py || goto :failed

echo.
echo Done: dist\AutoClicker.exe
exit /b 0

:failed
echo.
echo Build failed.
exit /b 1
