"""Clipboard operations module"""
try:
    import clipman
    CLIPMAN_AVAILABLE = True
except ImportError:
    CLIPMAN_AVAILABLE = False

import pyperclip


def clipboard_get():
    """Get clipboard content (prefer clipman to avoid triggering Ditto)"""
    if CLIPMAN_AVAILABLE:
        try:
            clipman.init()
            return clipman.get()
        except Exception as e:
            print(f"clipman.get() failed: {e}, falling back to pyperclip")
    # Fallback to pyperclip
    return pyperclip.paste()


def clipboard_set(text):
    """Set clipboard content (prefer clipman to avoid triggering Ditto)"""
    if CLIPMAN_AVAILABLE:
        try:
            clipman.init()
            clipman.set(text)
            return
        except Exception as e:
            print(f"clipman.set() failed: {e}, falling back to pyperclip")
    # Fallback to pyperclip
    pyperclip.copy(text)

