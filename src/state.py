"""Runtime state management module"""
import threading
import time

try:
    from .clipboard import capture_clipboard_snapshot
except ImportError:
    from clipboard import capture_clipboard_snapshot

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
_paste_occurrences = []
_paste_snapshots = []


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


def sync_paste_occurrences(occurrences, capture_fn=None):
    """Capture the clipboard once when each new paste keyword appears.

    ``occurrences`` is the ordered list of paste-keyword signatures in the
    current frontend text. A stable prefix keeps its existing bindings; removed
    or replaced trailing occurrences are discarded.
    """
    global _paste_occurrences, _paste_snapshots

    current = list(occurrences or [])
    capture = capture_fn or capture_clipboard_snapshot
    with _input_preview_lock:
        common = 0
        limit = min(len(_paste_occurrences), len(current))
        while common < limit and _paste_occurrences[common] == current[common]:
            common += 1

        if common < len(_paste_occurrences):
            _paste_occurrences = _paste_occurrences[:common]
            _paste_snapshots = _paste_snapshots[:common]

        for signature in current[common:]:
            try:
                snapshot = capture()
            except Exception as e:
                print(f"Clipboard placeholder capture failed: {e}")
                snapshot = None
            _paste_occurrences.append(signature)
            _paste_snapshots.append(snapshot)

        return list(_paste_snapshots[:len(current)])


def get_paste_snapshots(occurrences, capture_missing=True, capture_fn=None):
    """Return snapshots aligned with the current paste occurrences."""
    current = list(occurrences or [])
    if capture_missing:
        sync_paste_occurrences(current, capture_fn=capture_fn)
    with _input_preview_lock:
        if _paste_occurrences[:len(current)] != current:
            return []
        return list(_paste_snapshots[:len(current)])


def clear_input_preview():
    """Clear frontend preview text and all per-message clipboard bindings."""
    global input_preview_text, input_preview_updated_at, _paste_occurrences, _paste_snapshots
    with _input_preview_lock:
        input_preview_text = ''
        input_preview_updated_at = time.time()
        _paste_occurrences = []
        _paste_snapshots = []
