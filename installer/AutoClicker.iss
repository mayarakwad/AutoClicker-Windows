; Inno Setup (6.3 or later) script for AutoClicker-Setup.exe. Build
; dist\AutoClicker.exe first (build.bat), then run build_installer.bat, which
; writes dist\AutoClicker-Setup.exe.
;
; The wizard asks whether to install for all users (Program Files, needs
; admin) or just the current user (no admin), lets the user pick the folder,
; and offers a desktop shortcut and a taskbar pin. Silent installs take the
; same choices on the command line:
;   AutoClicker-Setup.exe /VERYSILENT /CURRENTUSER /DIR="D:\Apps\AutoClicker" /TASKS="desktopicon,taskbarpin"
;   AutoClicker-Setup.exe /VERYSILENT /ALLUSERS /TASKS="desktopicon"
; Both tasks are ticked by default, so a silent install without /TASKS does both.

#define AppName "AutoClicker"
#define AppExe "AutoClicker.exe"
#define AppExePath AddBackslash(SourcePath) + "..\dist\" + AppExe

; x64compatible (ArchitecturesAllowed / ArchitecturesInstallIn64BitMode) needs 6.3.
#if Ver < 0x06030000
  #error Inno Setup 6.3 or later is required. Update it: winget upgrade JRSoftware.InnoSetup
#endif

#if !FileExists(AppExePath)
  #error dist\AutoClicker.exe is missing. Run build.bat first.
#endif

; The version comes from the exe (version_info.txt), so it's set in one place.
#define AppVersion GetStringFileInfo(AppExePath, "ProductVersion")
#if AppVersion == ""
  #error dist\AutoClicker.exe has no ProductVersion. Check version_info.txt.
#endif

[Setup]
; AppId identifies the app for upgrades and uninstall. Never change it.
AppId={{E6818349-7A33-412C-B8E2-1B567D7D4CAA}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=mayarakwad
AppPublisherURL=https://github.com/mayarakwad/AutoClicker-Windows
AppSupportURL=https://github.com/mayarakwad/AutoClicker-Windows/issues
AppUpdatesURL=https://github.com/mayarakwad/AutoClicker-Windows/releases
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
; "Install for all users" or "Install for me only". Defaults to just the
; current user, which needs no admin rights.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
; All users: C:\Program Files\AutoClicker. Just me: %LOCALAPPDATA%\Programs\AutoClicker.
DefaultDirName={autopf}\{#AppName}
; Asks for the folder on a first install. Updates reuse it, so they never leave
; an old copy behind; to move AutoClicker, uninstall it and install again.
DisableDirPage=auto
DisableProgramGroupPage=yes
DisableWelcomePage=no
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir=..\dist
OutputBaseFilename=AutoClicker-Setup
Compression=lzma2
SolidCompression=yes
; Closes a running AutoClicker before replacing it; Finish can start it again.
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "taskbarpin"; Description: "&Pin to taskbar"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
; Also used by the uninstaller to unpin.
Source: "pin_taskbar.ps1"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; An update with the desktop shortcut unticked removes the one made earlier.
Type: files; Name: "{autodesktop}\{#AppName}.lnk"; Tasks: not desktopicon

[Icons]
; All users: the shared Start menu and Public Desktop. Just me: this user's.
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  PinFailed: Boolean;

function PowerShellExe: String;
begin
  Result := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
end;

function PinScript: String;
begin
  Result := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
    ExpandConstant('{app}\pin_taskbar.ps1') + '"';
end;

{ Exit codes of pin_taskbar.ps1, for the log. }
function PinResult(Code: Integer): String;
begin
  case Code of
    0: Result := 'done';
    1: Result := 'PowerShell could not run pin_taskbar.ps1';
    2: Result := 'Windows ignored the taskbar command';
    3: Result := 'the shortcut is missing';
    4: Result := 'the taskbar command did not answer';
  else
    Result := Format('error %d', [Code]);
  end;
end;

{ The taskbar belongs to the signed-in user, so pin as that user even when
  Setup runs elevated for an all-users install. }
procedure PinToTaskbar;
var
  ResultCode: Integer;
begin
  if not ExecAsOriginalUser(PowerShellExe, PinScript + ' -Shortcut "' + ExpandConstant('{autoprograms}\{#AppName}.lnk') + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then begin
    PinFailed := True;
    Log('Could not pin AutoClicker to the taskbar: ' + SysErrorMessage(ResultCode));
  end else if ResultCode = 0 then
    Log('Pinned AutoClicker to the taskbar.')
  else begin
    PinFailed := True;
    Log('Could not pin AutoClicker to the taskbar: ' + PinResult(ResultCode) + '.');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('taskbarpin') then
    PinToTaskbar;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Delta: Integer;
begin
  if (CurPageID = wpFinished) and PinFailed then begin
    { The caption already ends with a line break, so one more leaves a blank line. }
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10 +
      'Windows didn''t let Setup pin AutoClicker to the taskbar. To pin it yourself, open Start, ' +
      'type AutoClicker, right-click it in the results and choose Pin to taskbar.';
    { Setup sized the label and placed the controls under it before this event,
      so grow the label to fit and move those controls down to match. }
    Delta := WizardForm.AdjustLabelHeight(WizardForm.FinishedLabel);
    WizardForm.IncTopDecHeight(WizardForm.RunList, Delta);
    WizardForm.YesRadio.Top := WizardForm.YesRadio.Top + Delta;
    WizardForm.NoRadio.Top := WizardForm.NoRadio.Top + Delta;
  end;
end;

{ Removes the taskbar pin, if there is one, before the exe it points to is
  deleted. The uninstaller can't run commands as the original user, so for an
  all-users uninstall this unpins for the account that approved the UAC prompt;
  a pin made by another account stays. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if (CurUninstallStep = usUninstall) and FileExists(ExpandConstant('{app}\pin_taskbar.ps1')) then begin
    if Exec(PowerShellExe, PinScript + ' -Target "' + ExpandConstant('{app}\{#AppExe}') + '" -Unpin',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
      Log('Removed any taskbar pin for this account.')
    else
      Log('Could not remove the taskbar pin: ' + PinResult(ResultCode) + '.');
  end;
end;
