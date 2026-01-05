"""Keyboard input module"""
import time
import pyautogui
from .utils import IS_WINDOWS, VK_SHIFT, VK_INSERT, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE, MAPVK_VK_TO_VSC
from .clipboard import clipboard_get, clipboard_set

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
    
    # Choose paste method based on config
    if IS_WINDOWS:
        if use_ctrl_v:
            # Use Ctrl+V to paste
            send_ctrl_v_windows()
        else:
            # Use Shift+Insert to paste
            send_shift_insert_windows()
            # Check and reset Insert state
            ensure_insert_mode_reset()
    else:
        # Mac/Linux
        if use_ctrl_v:
            pyautogui.hotkey('ctrl', 'v')
        else:
            pyautogui.hotkey('shift', 'insert')
    
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

