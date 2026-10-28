"""AutoClicker entry point."""
import sys
import tkinter as tk
from pathlib import Path

import platforms
from ui import App

# Bundled files live next to this script, or in PyInstaller's unpack folder.
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets"


def main():
    platforms.prepare_process()  # before any window: DPI awareness on Windows
    root = tk.Tk()
    platforms.set_app_icon(root, ASSETS)
    App(root)  # loads settings from platforms.settings_folder()
    root.mainloop()


if __name__ == "__main__":
    main()
