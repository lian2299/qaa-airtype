"""Audio control module"""
import ctypes
import time
from .utils import IS_WINDOWS

# Audio control state (exported for web_routes)
auto_mute_enabled = False
original_mute_state = False
current_muted_by_app = False


def set_system_mute_windows(mute: bool) -> bool:
    """Control Windows system volume mute state (no OSD)"""
    if not IS_WINDOWS:
        return False
    
    try:
        # Use pycaw correctly: directly access EndpointVolume property
        from pycaw.pycaw import AudioUtilities
        
        # Get audio device
        speakers = AudioUtilities.GetSpeakers()
        
        # Correct way: directly access EndpointVolume property
        volume = speakers.EndpointVolume
        
        # Set mute state (no OSD)
        volume.SetMute(1 if mute else 0, None)
        print(f"[pycaw] {'Mute' if mute else 'Unmute'} successful (no OSD)")
        
        return True
        
    except ImportError as e:
        print(f"Warning: pycaw not installed: {e}")
        print("Please run: pip install pycaw comtypes")
        return False
    
    except Exception as e:
        print(f"pycaw mute failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Use fallback method (will show OSD)
        print(f"Using fallback method (will show OSD)...")
        try:
            user32 = ctypes.windll.user32
            VK_VOLUME_MUTE = 0xAD
            
            global current_muted_by_app
            
            # Only press key if need to toggle
            if (mute and not current_muted_by_app) or (not mute and current_muted_by_app):
                user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
                time.sleep(0.02)
                user32.keybd_event(VK_VOLUME_MUTE, 0, 0x0002, 0)
                print(f"[Fallback] {'Mute' if mute else 'Unmute'} (will show OSD)")
                return True
            
            return True
                
        except Exception as e2:
            print(f"Fallback mute failed: {e2}")
            return False

