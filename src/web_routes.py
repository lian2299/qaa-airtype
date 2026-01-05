"""Flask web routes module"""
import time
import pyautogui
from flask import request, render_template_string
from .utils import IS_WINDOWS
from .audio import set_system_mute_windows
from .keyboard import (
    paste_text, send_ctrl_z_windows, send_enter_windows, send_backspace_windows
)
from .state import use_ctrl_v, preserve_clipboard

# Import audio state variables
from . import audio


def register_routes(app, html_template):
    """Register Flask routes"""
    
    @app.route('/')
    def index():
        return render_template_string(html_template)

    @app.route('/mute', methods=['POST'])
    def toggle_mute():
        """Toggle auto mute feature"""
        try:
            data = request.get_json()
            enabled = data.get('enabled', False)
            audio.auto_mute_enabled = enabled
            return {'success': True, 'enabled': audio.auto_mute_enabled}
        except Exception as e:
            print(f"Error in toggle_mute: {e}")
            return {'success': False}

    @app.route('/mute_immediate', methods=['POST'])
    def mute_immediate():
        """Immediately mute or unmute (for voice input)"""
        try:
            data = request.get_json()
            mute = data.get('mute', False)
            
            if IS_WINDOWS:
                if mute:
                    # If currently not muted by app, switch to mute
                    if not audio.current_muted_by_app:
                        success = set_system_mute_windows(True)
                        if success:
                            audio.current_muted_by_app = True
                        print(f"Mute on voice input start: {success}")
                    else:
                        success = True
                        print("Already muted")
                else:
                    # If currently muted by app, switch back
                    if audio.current_muted_by_app:
                        success = set_system_mute_windows(False)
                        if success:
                            audio.current_muted_by_app = False
                        print(f"Unmute on voice input end: {success}")
                    else:
                        success = True
                        print("Not muted by app, no need to restore")
                
                return {'success': success}
            else:
                return {'success': False, 'message': 'Only supported on Windows'}
        except Exception as e:
            print(f"Error in mute_immediate: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    @app.route('/type', methods=['POST'])
    def type_text():
        try:
            data = request.get_json()
            enter = data.get('enter', False)
            backspace = data.get('backspace', False)
            undo = data.get('undo', False)
            
            # If just sending Undo key (Ctrl+Z)
            if undo:
                if IS_WINDOWS:
                    try:
                        send_ctrl_z_windows()
                    except Exception as e:
                        print(f"Windows API error for Ctrl+Z: {e}")
                        pyautogui.hotkey('ctrl', 'z')
                else:
                    # Mac/Linux: use pyautogui
                    pyautogui.hotkey('ctrl', 'z')
                
                return {'success': True}
            
            # If just sending Enter key
            if enter:
                if IS_WINDOWS:
                    try:
                        send_enter_windows()
                    except Exception as e:
                        print(f"Windows API error for Enter: {e}")
                        pyautogui.press('enter')
                else:
                    # Mac/Linux: use pyautogui
                    pyautogui.press('enter')
                
                return {'success': True}
            
            # If just sending Backspace key
            if backspace:
                if IS_WINDOWS:
                    try:
                        send_backspace_windows()
                    except Exception as e:
                        print(f"Windows API error for Backspace: {e}")
                        pyautogui.press('backspace')
                else:
                    # Mac/Linux: use pyautogui
                    pyautogui.press('backspace')
                
                return {'success': True}
            
            # Send text
            text = data.get('text', '')
            if text:
                # Use paste_text function from keyboard module
                paste_text(text, use_ctrl_v=use_ctrl_v, preserve_clipboard=preserve_clipboard)
                return {'success': True}
        except Exception as e:
            print(f"Error in type_text: {e}")
            pass
        return {'success': False}

