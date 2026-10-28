"""Operating-system layer (Windows-only copy of AutoClicker).

The main project, github.com/mayarakwad/AutoClicker, also has a macOS
backend; this copy ships only platforms/windows.py.
"""
from platforms.windows import (
    EXAMPLE_COMBO, KEY_NAMES, MODIFIER_LABELS, NATIVE_DARK, NATIVE_THEME, OS_NAME, TYPING_MODIFIERS,
    KeySource, Mouse, MouseListener, PointPicker, is_own_window, on_screen, permission_problem,
    play_sound, prepare_process, request_permissions, set_app_icon, set_clicking, set_window_dark,
    settings_folder, system_uses_dark,
)
