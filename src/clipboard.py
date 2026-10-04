"""Clipboard operations module, including safe Windows clipboard snapshots."""
from dataclasses import dataclass
import io
import platform
import struct
import time
try:
    import clipman
    CLIPMAN_AVAILABLE = True
except ImportError:
    CLIPMAN_AVAILABLE = False

import pyperclip


IS_WINDOWS = platform.system() == 'Windows'


@dataclass(frozen=True)
class ClipboardSnapshot:
    """A restorable clipboard snapshot.

    Only explicitly supported clipboard types are captured. Enumerating unknown
    Windows clipboard handles and treating all of them as HGLOBAL blocks can
    corrupt the native heap because bitmap/OLE formats use other handle types.
    """

    kind: str = 'text'
    payload: object = ''


def _open_windows_clipboard(owner=None, retries=8, delay=0.015):
    import ctypes

    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    for _ in range(retries):
        if user32.OpenClipboard(owner):
            return True
        time.sleep(delay)
    return False


def _create_clipboard_owner_window():
    """Create a tiny hidden HWND so EmptyClipboard/SetClipboardData are valid."""
    import ctypes

    user32 = ctypes.windll.user32
    user32.CreateWindowExW.argtypes = [
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    user32.CreateWindowExW.restype = ctypes.c_void_p
    user32.DestroyWindow.argtypes = [ctypes.c_void_p]
    user32.DestroyWindow.restype = ctypes.c_bool
    owner = user32.CreateWindowExW(
        0,
        'STATIC',
        'QAA-AirType Clipboard',
        0,
        0,
        0,
        0,
        0,
        None,
        None,
        None,
        None,
    )
    if not owner:
        raise RuntimeError('failed to create clipboard owner window')
    return owner


def _set_windows_clipboard_payload(format_id, payload):
    """Set one known HGLOBAL-backed clipboard format."""
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    GMEM_MOVEABLE = 0x0002

    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p

    owner = _create_clipboard_owner_window()
    try:
        if not _open_windows_clipboard(owner):
            raise RuntimeError('clipboard is busy')
        try:
            if not user32.EmptyClipboard():
                raise RuntimeError('failed to empty clipboard')
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, max(1, len(payload)))
            if not handle:
                raise RuntimeError('failed to allocate clipboard memory')
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                raise RuntimeError('failed to lock clipboard memory')
            try:
                if payload:
                    ctypes.memmove(pointer, payload, len(payload))
            finally:
                kernel32.GlobalUnlock(handle)
            # Ownership transfers to Windows after a successful call.
            if not user32.SetClipboardData(format_id, handle):
                kernel32.GlobalFree(handle)
                raise RuntimeError('failed to set clipboard data')
        finally:
            user32.CloseClipboard()
    finally:
        user32.DestroyWindow(owner)


def _image_to_dib(image):
    """Encode a Pillow image as CF_DIB bytes (BMP without its file header)."""
    output = io.BytesIO()
    image.convert('RGB').save(output, format='BMP')
    return output.getvalue()[14:]


def _files_to_hdrop(paths):
    """Encode copied file paths as a Unicode DROPFILES payload."""
    normalized = [str(path) for path in paths if path]
    names = ('\0'.join(normalized) + '\0\0').encode('utf-16le')
    dropfiles = struct.pack('<IiiII', 20, 0, 0, 0, 1)
    return dropfiles + names


def capture_clipboard_snapshot():
    """Capture the current clipboard without logging or exposing its contents."""
    if IS_WINDOWS:
        try:
            from PIL import Image, ImageGrab

            grabbed = ImageGrab.grabclipboard()
            if isinstance(grabbed, Image.Image):
                try:
                    grabbed.load()
                    return ClipboardSnapshot(kind='image', payload=_image_to_dib(grabbed))
                finally:
                    grabbed.close()
            if isinstance(grabbed, list):
                return ClipboardSnapshot(kind='files', payload=tuple(grabbed))
        except Exception as e:
            print(f"Image/file clipboard snapshot failed, falling back to text: {e}")
    return ClipboardSnapshot(kind='text', payload=clipboard_get())


def restore_clipboard_snapshot(snapshot):
    """Restore a snapshot captured by :func:`capture_clipboard_snapshot`."""
    if snapshot is None:
        return False
    if IS_WINDOWS and snapshot.kind == 'image':
        _set_windows_clipboard_payload(8, snapshot.payload)  # CF_DIB
        return True
    if IS_WINDOWS and snapshot.kind == 'files':
        _set_windows_clipboard_payload(15, _files_to_hdrop(snapshot.payload))  # CF_HDROP
        return True
    clipboard_set(snapshot.payload if snapshot.payload is not None else '')
    return True


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

