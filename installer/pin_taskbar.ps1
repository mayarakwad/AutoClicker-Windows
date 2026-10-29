# Pins a shortcut to the current user's taskbar, or with -Unpin removes the
# pin for the app it points to. Run by AutoClicker's installer and uninstaller.
#
# Windows has no supported way for an installer to pin apps. This invokes the
# taskbar's own "Pin to taskbar" shell command through a temporary
# context-menu verb. It works on Windows 10 and some Windows 11 builds; newer
# builds ignore it, and the installer then tells the user how to pin by hand.
#
# Pin:   pin_taskbar.ps1 -Shortcut <path to .lnk>
# Unpin: pin_taskbar.ps1 -Target <path to .exe> -Unpin
#
# Exit codes: 0 pinned (with -Unpin: no longer pinned); 2 Windows ignored the
# taskbar command; 3 the shortcut is missing or has no target; 4 the taskbar
# command didn't answer within 15 s; 5 any other error. 1 means PowerShell
# couldn't run this script at all (for example, blocked by policy).
param(
    [string] $Shortcut,
    [string] $Target,
    [switch] $Unpin
)

$ErrorActionPreference = 'Stop'
$VerbKey = 'Software\Classes\*\shell\AutoClickerTaskbarPin'
$TaskbarPinHandler = '{90AA3A4E-1CBA-4233-B8BB-535773D48449}'
$PinnedFolder = Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'

function Get-Target([string] $Lnk) {
    (New-Object -ComObject WScript.Shell).CreateShortcut($Lnk).TargetPath
}

# Shortcuts on the taskbar that start $Target.
function Get-Pinned([string] $Target) {
    if (-not (Test-Path -LiteralPath $PinnedFolder)) { return @() }
    @(Get-ChildItem -LiteralPath $PinnedFolder -Filter *.lnk |
        Where-Object { (Get-Target $_.FullName) -eq $Target } |
        ForEach-Object { $_.FullName })
}

# Runs the taskbar's pin/unpin command on a file. The same command pins an
# unpinned shortcut and unpins a pinned one. It runs on its own thread so a
# shell that never answers can't hang the installer.
function Invoke-TaskbarVerb([string] $File) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($VerbKey)
    $key.SetValue('ExplorerCommandHandler', $TaskbarPinHandler)
    $key.Close()
    try {
        $runspace = [RunspaceFactory]::CreateRunspace()
        $runspace.ApartmentState = 'STA'
        $runspace.Open()
        $ps = [PowerShell]::Create()
        $ps.Runspace = $runspace
        [void] $ps.AddScript({
            param($Folder, $Name)
            (New-Object -ComObject Shell.Application).Namespace($Folder).ParseName($Name).InvokeVerb('AutoClickerTaskbarPin')
        }).AddArgument((Split-Path -Parent $File)).AddArgument((Split-Path -Leaf $File))
        $call = $ps.BeginInvoke()
        if (-not $call.AsyncWaitHandle.WaitOne(15000)) { $script:code = 4; return }
        [void] $ps.EndInvoke($call)
    } finally {
        [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($VerbKey, $false)
    }
}

# The taskbar updates its folder a moment after the command returns.
function Wait-Until([scriptblock] $Condition) {
    for ($i = 0; $i -lt 20; $i++) {
        if (& $Condition) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return [bool] (& $Condition)
}

$code = 5
try {
    if (-not $Target) {
        if (-not $Shortcut -or -not (Test-Path -LiteralPath $Shortcut)) { $code = 3; throw "Shortcut not found: $Shortcut" }
        $Target = Get-Target $Shortcut
    }
    # Some pins (Store apps) have no target either; never match those.
    if (-not $Target) { $code = 3; throw "$Shortcut has no target." }
    $code = 2
    if ($Unpin) {
        foreach ($pinned in Get-Pinned $Target) { Invoke-TaskbarVerb $pinned }
        if (Wait-Until { (Get-Pinned $Target).Count -eq 0 }) { $code = 0 }
    } elseif ((Get-Pinned $Target).Count -gt 0) {
        $code = 0  # already pinned; running the command again would unpin it
    } elseif (-not $Shortcut) {
        $code = 3; throw 'Pinning needs -Shortcut.'
    } else {
        Invoke-TaskbarVerb $Shortcut
        if (Wait-Until { (Get-Pinned $Target).Count -gt 0 }) { $code = 0 }
    }
} catch {
    if ($code -lt 3) { $code = 5 }
    [Console]::Error.WriteLine("Taskbar pin failed: $_")
}
# Exit even if the shell call is still stuck on its thread.
[Environment]::Exit($code)
