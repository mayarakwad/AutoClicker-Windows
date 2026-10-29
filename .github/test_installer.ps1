# Installs and uninstalls AutoClicker-Setup.exe silently, for one user and for
# all users, and checks what each leaves behind. Run by the Windows build
# workflow (as admin, which the all-users install needs):
#   pwsh .github/test_installer.ps1 -Setup dist\AutoClicker-Setup.exe
# Failures are posted as annotations, which are readable without signing in.
param([Parameter(Mandatory)] [string] $Setup)

$ErrorActionPreference = 'Stop'
$Setup = (Resolve-Path $Setup).Path
$Exe = Join-Path (Split-Path -Parent $Setup) 'AutoClicker.exe'
$Version = (Get-Item $Exe).VersionInfo.ProductVersion
$AppId = '{E6818349-7A33-412C-B8E2-1B567D7D4CAA}_is1'
$UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $AppId
$PinnedFolder = Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'
$script:Failures = 0

function Check([bool] $Ok, [string] $What) {
    if ($Ok) {
        Write-Output "  ok: $What"
    } else {
        Write-Output "::error title=Installer check failed::$What"
        $script:Failures++
    }
}

function Get-Target([string] $Lnk) {
    (New-Object -ComObject WScript.Shell).CreateShortcut($Lnk).TargetPath
}

function Get-PinnedTo([string] $Target) {
    if (-not (Test-Path -LiteralPath $PinnedFolder)) { return @() }
    @(Get-ChildItem -LiteralPath $PinnedFolder -Filter *.lnk | Where-Object { (Get-Target $_.FullName) -eq $Target })
}

function Wait-Until([scriptblock] $Condition, [int] $Seconds = 60) {
    for ($i = 0; $i -lt $Seconds * 4; $i++) {
        if (& $Condition) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return [bool] (& $Condition)
}

function Test-Install {
    param(
        [string] $Name, [string] $Mode, [string] $Tasks, [string] $Dir, [string] $ExpectedDir,
        [string] $Registry, [string] $Programs, [string] $Desktop
    )
    Write-Output "== $Name"
    $log = Join-Path $env:RUNNER_TEMP ('setup-' + ($Name -replace '\W+', '-') + '.log')
    $arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/$Mode", "/TASKS=""$Tasks""", "/LOG=""$log""")
    if ($Dir) { $arguments += "/DIR=""$Dir""" }

    # Twice: the second run checks that installing over an existing copy works.
    foreach ($run in 1, 2) {
        $setupProcess = Start-Process -FilePath $Setup -ArgumentList $arguments -Wait -PassThru
        Check ($setupProcess.ExitCode -eq 0) "$Name setup run $run exits with 0 (got $($setupProcess.ExitCode))"
    }

    $installed = Join-Path $ExpectedDir 'AutoClicker.exe'
    $programsLnk = Join-Path $Programs 'AutoClicker.lnk'
    $desktopLnk = Join-Path $Desktop 'AutoClicker.lnk'
    $key = "${Registry}:\$UninstallKey"

    Check (Test-Path -LiteralPath $installed) "$Name installs $installed"
    if (Test-Path -LiteralPath $installed) {
        Check ((Get-FileHash $installed).Hash -eq (Get-FileHash $Exe).Hash) "$Name installs the built exe unchanged"
    }
    Check ((Test-Path -LiteralPath $programsLnk) -and ((Get-Target $programsLnk) -eq $installed)) "$Name Start menu shortcut $programsLnk opens $installed"
    if ($Tasks -match 'desktopicon') {
        Check ((Test-Path -LiteralPath $desktopLnk) -and ((Get-Target $desktopLnk) -eq $installed)) "$Name desktop shortcut $desktopLnk opens $installed"
    } else {
        Check (-not (Test-Path -LiteralPath $desktopLnk)) "$Name makes no desktop shortcut when the task is off"
    }
    Check (Test-Path -LiteralPath $key) "$Name registers the uninstaller under $key"
    $uninstaller = $null
    if (Test-Path -LiteralPath $key) {
        $entry = Get-ItemProperty -LiteralPath $key
        Check ($entry.DisplayVersion -eq $Version) "$Name lists version $Version in Apps (got $($entry.DisplayVersion))"
        Check ($entry.InstallLocation.TrimEnd('\') -eq $ExpectedDir) "$Name lists the install folder $ExpectedDir (got $($entry.InstallLocation))"
        $uninstaller = $entry.UninstallString.Trim('"')
    }
    Check (-not (Test-Path -LiteralPath 'HKCU:\Software\Classes\*\shell\AutoClickerTaskbarPin')) "$Name removes the temporary taskbar-pin verb"

    $pinned = (Get-PinnedTo $installed).Count -gt 0
    if ($Tasks -match 'taskbarpin') {
        # Windows may refuse to pin, especially on a build server; Setup then says how to pin by hand.
        $setupLog = Get-Content -LiteralPath $log -Raw
        $outcome = if ($setupLog -match 'Pinned AutoClicker') { 'pinned' } elseif ($setupLog -match 'Could not pin') { 'not pinned (Windows refused)' } else { 'not attempted' }
        Write-Output "::notice title=Taskbar pin::$Name taskbar pin: $outcome"
        Check ($outcome -ne 'not attempted') "$Name tries to pin to the taskbar"
        Check ($pinned -eq ($outcome -eq 'pinned')) "$Name pin result matches the taskbar"
    }

    if ($uninstaller) {
        Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait
        # The uninstaller hands over to a copy of itself in %TEMP%, so wait for its work to show.
        Check (Wait-Until { -not (Test-Path -LiteralPath $key) -and -not (Test-Path -LiteralPath $installed) }) "$Name uninstall removes the exe and the Apps entry"
        Check (-not (Test-Path -LiteralPath $programsLnk)) "$Name uninstall removes the Start menu shortcut"
        Check (-not (Test-Path -LiteralPath $desktopLnk)) "$Name uninstall removes the desktop shortcut"
        if ($pinned) { Check ((Get-PinnedTo $installed).Count -eq 0) "$Name uninstall unpins it from the taskbar" }
    }
}

# Just me, in a chosen folder with a space in its path, with both shortcuts.
$customDir = Join-Path $env:RUNNER_TEMP 'Chosen Folder\AutoClicker'
Test-Install -Name 'Just-me install' -Mode CURRENTUSER -Tasks 'desktopicon,taskbarpin' `
    -Dir $customDir -ExpectedDir $customDir -Registry HKCU `
    -Programs ([Environment]::GetFolderPath('Programs')) -Desktop ([Environment]::GetFolderPath('Desktop'))

# All users, in the default folder, with no extra shortcuts.
Test-Install -Name 'All-users install' -Mode ALLUSERS -Tasks '' `
    -ExpectedDir (Join-Path $env:ProgramFiles 'AutoClicker') -Registry HKLM `
    -Programs ([Environment]::GetFolderPath('CommonPrograms')) -Desktop ([Environment]::GetFolderPath('CommonDesktopDirectory'))

# All users with a desktop shortcut, which goes on the Public desktop.
Test-Install -Name 'All-users install with desktop shortcut' -Mode ALLUSERS -Tasks 'desktopicon' `
    -ExpectedDir (Join-Path $env:ProgramFiles 'AutoClicker') -Registry HKLM `
    -Programs ([Environment]::GetFolderPath('CommonPrograms')) -Desktop ([Environment]::GetFolderPath('CommonDesktopDirectory'))

if ($script:Failures) {
    Write-Output "$script:Failures installer check(s) failed. Setup logs:"
    Get-ChildItem -Path $env:RUNNER_TEMP -Filter 'setup-*.log' | ForEach-Object { Write-Output "--- $($_.Name)"; Get-Content $_.FullName }
    exit 1
}
Write-Output 'All installer checks passed.'
