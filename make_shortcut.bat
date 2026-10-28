@echo off
rem Creates a Desktop shortcut that runs AutoClicker from source through the
rem venv's pythonw.exe (signed by the Python Software Foundation, no console).
rem Use it where Smart App Control blocks the unsigned dist\AutoClicker.exe.
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\pythonw.exe (
    echo No virtual environment yet: run build.bat first.
    exit /b 1
)

powershell -NoProfile -Command ^
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'AutoClicker.lnk'));" ^
    "$s.TargetPath = '%~dp0.venv\Scripts\pythonw.exe';" ^
    "$s.Arguments = '\"%~dp0main.py\"';" ^
    "$s.WorkingDirectory = '%~dp0';" ^
    "$s.IconLocation = '%~dp0assets\app.ico,0';" ^
    "$s.Description = 'AutoClicker';" ^
    "$s.Save(); Write-Host ('Created ' + $s.FullName)" || goto :failed
exit /b 0

:failed
echo Could not create the shortcut.
exit /b 1
