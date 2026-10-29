@echo off
rem Builds dist\AutoClicker-Setup.exe from dist\AutoClicker.exe with Inno Setup 6.3
rem or later (installer\AutoClicker.iss). Runs build.bat first if the exe isn't built.
rem Get Inno Setup from https://jrsoftware.org/isdl.php or: winget install JRSoftware.InnoSetup
setlocal
cd /d "%~dp0"

if not exist dist\AutoClicker.exe (
    call build.bat || goto :failed
)

set "ISCC="
for %%I in (ISCC.exe) do set "ISCC=%%~$PATH:I"
rem These stay outside ( ) blocks: the ")" in %ProgramFiles(x86)% would end one.
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo Inno Setup 6.3 or later not found. Install it with: winget install JRSoftware.InnoSetup
    goto :failed
)

echo Building the installer...
"%ISCC%" /Q installer\AutoClicker.iss || goto :failed

echo.
echo Done: dist\AutoClicker-Setup.exe
exit /b 0

:failed
echo.
echo Installer build failed.
exit /b 1
