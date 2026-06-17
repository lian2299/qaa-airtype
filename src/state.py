"""Runtime state management module"""
import threading
import time

# Paste and clipboard configuration
use_ctrl_v = False  # False: use Shift+Insert, True: use Ctrl+V
preserve_clipboard = False  # Whether to protect clipboard (don't overwrite)
auto_minimize = False  # Auto-minimize on startup

# Last payload sent via /type or CF (used by /last_text and tray UI)
last_sent_text = ''

# Current frontend input contents used only for the desktop input indicator.
input_preview_text = ''
input_preview_updated_at = 0.0
_input_preview_lock = threading.Lock()
MAX_INPUT_PREVIEW_CHARS = 2000


def set_input_preview(text):
    """Store the latest frontend input contents without affecting send logic."""
    global input_preview_text, input_preview_updated_at

    if text is None:
        text = ''
    elif not isinstance(text, str):
        text = str(text)

    if len(text) > MAX_INPUT_PREVIEW_CHARS:
        text = text[-MAX_INPUT_PREVIEW_CHARS:]

    with _input_preview_lock:
        input_preview_text = text
        input_preview_updated_at = time.time()
        return input_preview_text


def get_input_preview():
    """Return the current frontend input preview text and update timestamp."""
    with _input_preview_lock:
        return input_preview_text, input_preview_updated_at
