"""Keyboard input module"""
import time
import pyautogui

try:
    from .utils import IS_WINDOWS, VK_SHIFT, VK_INSERT, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE, MAPVK_VK_TO_VSC
    from .clipboard import clipboard_get, clipboard_set
except ImportError:
    from utils import IS_WINDOWS, VK_SHIFT, VK_INSERT, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE, MAPVK_VK_TO_VSC
    from clipboard import clipboard_get, clipboard_set

if IS_WINDOWS:
    import ctypes


def ensure_insert_mode_reset():
    """Ensure insert mode is reset (not overwrite mode)"""
    if not IS_WINDOWS:
        return
    
    try:
        user32 = ctypes.windll.user32
        insert_state = user32.GetKeyState(VK_INSERT)
        
        # Low bit is 1 means overwrite mode is active
        if insert_state & 0x0001:
            insert_scan = user32.MapVirtualKeyW(VK_INSERT, MAPVK_VK_TO_VSC)
            # Press Insert once to switch back to insert mode
            user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.01)
            user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            print("Detected overwrite mode, reset to insert mode")
    except Exception as e:
        print(f"Check Insert state failed: {e}")


def send_shift_insert_windows():
    """Send Shift+Insert combo using Windows API (using scan codes, compatible with terminals)"""
    if not IS_WINDOWS:
        return False

    user32 = None
    shift_scan = None
    insert_scan = None
    shift_pressed = False
    insert_pressed = False

    try:
        user32 = ctypes.windll.user32

        # Get scan codes (must use scan codes for terminal apps like CMD/PowerShell)
        shift_scan = user32.MapVirtualKeyW(VK_SHIFT, MAPVK_VK_TO_VSC)
        insert_scan = user32.MapVirtualKeyW(VK_INSERT, MAPVK_VK_TO_VSC)

        # Press Shift (using scan code)
        user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE, 0)
        shift_pressed = True
        time.sleep(0.05)

        # Press Insert (using scan code + extended key flag)
        user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY, 0)
        insert_pressed = True
        time.sleep(0.02)

        # Release Insert (using scan code + extended key flag)
        user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        insert_pressed = False
        time.sleep(0.02)

        # Release Shift (using scan code)
        user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        shift_pressed = False

        return True
        
    except Exception as e:
        print(f"Windows API error: {e}")
        return False
        
    finally:
        # Use finally to ensure cleanup always executes
        if user32 and shift_scan is not None and insert_scan is not None:
            try:
                # Force release all possibly pressed keys
                if insert_pressed:
                    user32.keybd_event(VK_INSERT, insert_scan, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
                if shift_pressed:
                    user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
            except Exception as cleanup_error:
                print(f"Error during key cleanup: {cleanup_error}")


def send_ctrl_v_windows():
    """Send Ctrl+V combo using Windows API"""
    if not IS_WINDOWS:
        return False

    try:
        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11
        VK_V = 0x56
        
        ctrl_scan = user32.MapVirtualKeyW(VK_CONTROL, MAPVK_VK_TO_VSC)
        v_scan = user32.MapVirtualKeyW(VK_V, MAPVK_VK_TO_VSC)
        
        # Press Ctrl
        user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.05)
        
        # Press V
        user32.keybd_event(VK_V, v_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.02)
        
        # Release V
        user32.keybd_event(VK_V, v_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)
        
        # Release Ctrl
        user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        
        return True
    except Exception as e:
        print(f"Ctrl+V error: {e}")
        return False


def send_ctrl_z_windows():
    """Send Ctrl+Z using Windows API"""
    if not IS_WINDOWS:
        return False
    try:
        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11
        VK_Z = 0x5A
        ctrl_scan = user32.MapVirtualKeyW(VK_CONTROL, MAPVK_VK_TO_VSC)
        z_scan = user32.MapVirtualKeyW(VK_Z, MAPVK_VK_TO_VSC)
        
        # Press Ctrl
        user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.02)
        # Press Z
        user32.keybd_event(VK_Z, z_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.02)
        # Release Z
        user32.keybd_event(VK_Z, z_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)
        # Release Ctrl
        user32.keybd_event(VK_CONTROL, ctrl_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        print(f"Windows API error for Ctrl+Z: {e}")
        return False


def send_enter_windows():
    """Send Enter key using Windows API"""
    if not IS_WINDOWS:
        return False
    try:
        user32 = ctypes.windll.user32
        VK_RETURN = 0x0D
        return_scan = user32.MapVirtualKeyW(VK_RETURN, MAPVK_VK_TO_VSC)
        # Press Enter
        user32.keybd_event(VK_RETURN, return_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.02)
        # Release Enter
        user32.keybd_event(VK_RETURN, return_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        print(f"Windows API error for Enter: {e}")
        return False


def send_shift_enter_windows():
    """Send Shift+Enter combo using Windows API"""
    if not IS_WINDOWS:
        return False

    user32 = None
    shift_scan = None
    return_scan = None
    shift_pressed = False
    enter_pressed = False

    try:
        user32 = ctypes.windll.user32
        VK_RETURN = 0x0D
        shift_scan = user32.MapVirtualKeyW(VK_SHIFT, MAPVK_VK_TO_VSC)
        return_scan = user32.MapVirtualKeyW(VK_RETURN, MAPVK_VK_TO_VSC)

        user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE, 0)
        shift_pressed = True
        time.sleep(0.02)

        user32.keybd_event(VK_RETURN, return_scan, KEYEVENTF_SCANCODE, 0)
        enter_pressed = True
        time.sleep(0.02)

        user32.keybd_event(VK_RETURN, return_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        enter_pressed = False
        time.sleep(0.02)

        user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        shift_pressed = False
        return True
    except Exception as e:
        print(f"Windows API error for Shift+Enter: {e}")
        return False
    finally:
        if user32 and shift_scan is not None and return_scan is not None:
            try:
                if enter_pressed:
                    user32.keybd_event(VK_RETURN, return_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
                if shift_pressed:
                    user32.keybd_event(VK_SHIFT, shift_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
            except Exception as cleanup_error:
                print(f"Error during key cleanup: {cleanup_error}")


def send_backspace_windows():
    """Send Backspace key using Windows API"""
    if not IS_WINDOWS:
        return False
    try:
        user32 = ctypes.windll.user32
        VK_BACK = 0x08
        backspace_scan = user32.MapVirtualKeyW(VK_BACK, MAPVK_VK_TO_VSC)
        # Press Backspace
        user32.keybd_event(VK_BACK, backspace_scan, KEYEVENTF_SCANCODE, 0)
        time.sleep(0.02)
        # Release Backspace
        user32.keybd_event(VK_BACK, backspace_scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
        return True
    except Exception as e:
        print(f"Windows API error for Backspace: {e}")
        return False


def send_paste_hotkey(use_ctrl_v=False):
    """Send only the paste shortcut (Ctrl+V or Shift+Insert); does not touch clipboard."""
    if IS_WINDOWS:
        if use_ctrl_v:
            return bool(send_ctrl_v_windows())
        ok = send_shift_insert_windows()
        ensure_insert_mode_reset()
        return bool(ok)
    if use_ctrl_v:
        pyautogui.hotkey('ctrl', 'v')
    else:
        pyautogui.hotkey('shift', 'insert')
    return True


def paste_literal_fragment(text, use_ctrl_v=False):
    """Set clipboard to fragment, send paste hotkey. Caller restores staged clipboard after."""
    clipboard_set(text)
    time.sleep(0.1)
    send_paste_hotkey(use_ctrl_v=use_ctrl_v)


# Allowed token names for send_hotkey (lowercase after normalize)
HOTKEY_KEY_WHITELIST = frozenset({
    'ctrl', 'shift', 'alt', 'win',
    'enter', 'return', 'tab', 'backspace', 'insert', 'delete', 'escape', 'space',
    'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
    'v', 'c', 'x', 'z', 'a', 'b', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
    'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'w', 'y',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
})


def _normalize_hotkey_token(name):
    n = (name or '').strip().lower()
    if n == 'control':
        n = 'ctrl'
    return n


def _pyautogui_hotkey_names(keys):
    """Map whitelist tokens to pyautogui key names."""
    out = []
    for k in keys:
        if k == 'win':
            out.append('winleft')
        else:
            out.append(k)
    return out


def send_hotkey(keys):
    """
    Send a combo from a whitelist-validated list of key names (lowercase).
    Returns True on success, False if invalid or send failed.
    """
    if not keys:
        return False
    normalized = [_normalize_hotkey_token(k) for k in keys]
    for k in normalized:
        if k not in HOTKEY_KEY_WHITELIST:
            print(f"send_hotkey: disallowed key '{k}'")
            return False

    # Optimized Windows paths for common shortcuts
    if IS_WINDOWS and len(normalized) == 2:
        a, b = normalized[0], normalized[1]
        if a == 'ctrl' and b == 'v':
            return bool(send_ctrl_v_windows())
        if a == 'ctrl' and b == 'z':
            return bool(send_ctrl_z_windows())
        if a == 'shift' and b == 'insert':
            ok = send_shift_insert_windows()
            ensure_insert_mode_reset()
            return bool(ok)
        if a == 'shift' and b in ('enter', 'return'):
            return bool(send_shift_enter_windows())

    if IS_WINDOWS and len(normalized) == 1:
        k = normalized[0]
        if k in ('enter', 'return'):
            return bool(send_enter_windows())
        if k == 'backspace':
            return bool(send_backspace_windows())

    try:
        pg_keys = _pyautogui_hotkey_names(normalized)
        pyautogui.hotkey(*pg_keys)
        if IS_WINDOWS and 'insert' in normalized:
            ensure_insert_mode_reset()
        return True
    except Exception as e:
        print(f"send_hotkey failed: {e}")
        return False


def paste_text(text, use_ctrl_v=False, preserve_clipboard=False):
    """Copy to clipboard and paste"""
    # If clipboard protection enabled, save original content
    clipboard_saved = False
    original_clipboard = None
    if preserve_clipboard:
        try:
            original_clipboard = clipboard_get()
            clipboard_saved = True
            print(f"[Clipboard] Saved original content (length: {len(original_clipboard) if original_clipboard else 0})")
        except Exception as e:
            print(f"[Clipboard] Failed to save: {e}")
    
    # Copy text to clipboard
    clipboard_set(text)
    time.sleep(0.1)
    
    send_paste_hotkey(use_ctrl_v=use_ctrl_v)
    
    # If clipboard protection enabled, restore original content (increase wait time)
    if preserve_clipboard and clipboard_saved:
        time.sleep(0.15)  # Increase wait time to 150ms to ensure paste completes
        try:
            if original_clipboard is not None:
                clipboard_set(original_clipboard)
            else:
                # If original content is None, clear clipboard
                clipboard_set('')
            print(f"[Clipboard] Restored original content")
        except Exception as e:
            print(f"[Clipboard] Failed to restore: {e}")

