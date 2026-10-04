"""Flask web routes module"""
import pyautogui
from flask import request, render_template_string
from .utils import IS_WINDOWS
from .audio import set_system_mute_windows
from .keyboard import (
    send_ctrl_z_windows, send_enter_windows, send_shift_enter_windows, send_backspace_windows
)
from .config import load_config
from .keyword_pipeline import execute_typed_text, get_paste_keywords, get_paste_occurrences, validate_keyword_actions
from . import state

# Import audio state variables
from . import audio


def register_routes(app, html_template):
    """Register Flask routes"""
    
    @app.route('/')
    def index():
        rules = validate_keyword_actions(load_config().get('keyword_actions', []))
        paste_keywords = get_paste_keywords(rules)
        return render_template_string(html_template, paste_keywords=paste_keywords)

    @app.route('/input_preview', methods=['POST'])
    def update_input_preview():
        """Update frontend input preview state without sending text."""
        try:
            data = request.get_json(silent=True) or {}
            raw_text = data.get('text', '')
            if not isinstance(raw_text, str):
                raw_text = '' if raw_text is None else str(raw_text)
            text = state.set_input_preview(raw_text)
            rules = validate_keyword_actions(load_config().get('keyword_actions', []))
            state.sync_paste_occurrences(get_paste_occurrences(raw_text, rules))
            return {'success': True, 'length': len(raw_text)}
        except Exception as e:
            print(f"Error in update_input_preview: {e}")
            return {'success': False}

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
            shift_enter = data.get('shift_enter', False)
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

            # If just sending Shift+Enter combo
            if shift_enter:
                if IS_WINDOWS:
                    try:
                        send_shift_enter_windows()
                    except Exception as e:
                        print(f"Windows API error for Shift+Enter: {e}")
                        pyautogui.hotkey('shift', 'enter')
                else:
                    # Mac/Linux: use pyautogui
                    pyautogui.hotkey('shift', 'enter')

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
                state.last_sent_text = text
                rules = validate_keyword_actions(load_config().get('keyword_actions', []))
                occurrences = get_paste_occurrences(text, rules)
                snapshots = state.get_paste_snapshots(occurrences, capture_missing=True)
                ok = execute_typed_text(text, clipboard_snapshots=snapshots)
                if ok:
                    state.clear_input_preview()
                    return {'success': True}
                return {'success': False, 'error': 'Paste failed'}
        except Exception as e:
            print(f"Error in type_text: {e}")
            pass
        return {'success': False}

