"""Writes the winget manifests for a released AutoClicker-Setup.exe.

winget installs AutoClicker as the package mayarakwad.AutoClicker from
microsoft/winget-pkgs. Each release needs a new set of manifests there, with
the installer's download URL and SHA-256. The winget workflow
(.github/workflows/winget.yml) runs this, checks the result, and submits it.

    python winget/make_manifests.py --tag v1.0.2 --installer AutoClicker-Setup.exe --out manifests

--installer must be the exact file attached to the release, since its hash
goes into the manifest.
"""
import argparse
import hashlib
import re
from pathlib import Path

PACKAGE_ID = "mayarakwad.AutoClicker"
REPO = "https://github.com/mayarakwad/AutoClicker-Windows"
# installer/AutoClicker.iss AppId: how Windows lists the installed app.
PRODUCT_CODE = "{E6818349-7A33-412C-B8E2-1B567D7D4CAA}_is1"
MANIFEST_VERSION = "1.10.0"
# winget installs make a Start menu and desktop shortcut but don't pin to the taskbar.
TASKS = '/TASKS="desktopicon"'


def header(kind):
    return f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{kind}.{MANIFEST_VERSION}.schema.json\n\n"


def manifests(version, url, sha256):
    """{file name: contents} for one version."""
    common = f"PackageIdentifier: {PACKAGE_ID}\nPackageVersion: {version}\n"
    installers = "".join(
        f"- Architecture: x64\n"
        f"  Scope: {scope}\n"
        f"  InstallerUrl: {url}\n"
        f"  InstallerSha256: {sha256}\n"
        f"  InstallerSwitches:\n"
        f"    Custom: {switch} {TASKS}\n"
        for scope, switch in (("user", "/CURRENTUSER"), ("machine", "/ALLUSERS")))
    return {
        f"{PACKAGE_ID}.yaml": header("version") + common + (
            "DefaultLocale: en-US\n"
            "ManifestType: version\n"
            f"ManifestVersion: {MANIFEST_VERSION}\n"),
        f"{PACKAGE_ID}.installer.yaml": header("installer") + common + (
            "InstallerLocale: en-US\n"
            "MinimumOSVersion: 10.0.0.0\n"
            "InstallerType: inno\n"
            "UpgradeBehavior: install\n"
            f"ProductCode: '{PRODUCT_CODE}'\n"
            "Installers:\n"
            f"{installers}"
            "ManifestType: installer\n"
            f"ManifestVersion: {MANIFEST_VERSION}\n"),
        f"{PACKAGE_ID}.locale.en-US.yaml": header("defaultLocale") + common + (
            "PackageLocale: en-US\n"
            "Publisher: mayarakwad\n"
            "PublisherUrl: https://github.com/mayarakwad\n"
            f"PublisherSupportUrl: {REPO}/issues\n"
            "PackageName: AutoClicker\n"
            f"PackageUrl: {REPO}\n"
            "License: Freeware\n"
            "ShortDescription: A lightweight auto clicker for Windows 10 and 11, modeled on OP Auto Clicker.\n"
            "Description: |-\n"
            "  Clicks the mouse for you at a set interval, at the cursor or at a picked spot on screen.\n"
            "  Start and stop it with a global hotkey (F6 by default). Esc or moving the mouse into the\n"
            "  top-left corner stops it. It can also record a sequence of clicks and play it back.\n"
            "Tags:\n"
            "- autoclicker\n"
            "- clicker\n"
            "- mouse\n"
            "- automation\n"
            "- macro\n"
            f"ReleaseNotesUrl: {REPO}/releases/tag/v{version}\n"
            "ManifestType: defaultLocale\n"
            f"ManifestVersion: {MANIFEST_VERSION}\n"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="release tag, e.g. v1.0.2")
    parser.add_argument("--installer", required=True, type=Path, help="the release's AutoClicker-Setup.exe")
    parser.add_argument("--out", required=True, type=Path, help="folder to write the manifests to")
    args = parser.parse_args()
    if not re.fullmatch(r"v\d+(\.\d+){1,3}", args.tag):
        parser.error(f"{args.tag} isn't a release tag like v1.0.2")
    version = args.tag[1:]
    url = f"{REPO}/releases/download/{args.tag}/AutoClicker-Setup.exe"
    sha256 = hashlib.sha256(args.installer.read_bytes()).hexdigest().upper()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in manifests(version, url, sha256).items():
        (args.out / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {args.out / name}")


if __name__ == "__main__":
    main()
