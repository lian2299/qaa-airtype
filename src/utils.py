"""Utility functions and constants"""
import platform
import sys
import os
import socket


IS_MAC = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'
PASTE_KEY = 'command' if IS_MAC else 'ctrl'

# Windows API constants
if IS_WINDOWS:
    VK_SHIFT = 0x10
    VK_INSERT = 0x2D
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0


def get_icon_path():
    """Get icon path, support dev and packaged environments"""
    # If packaged by PyInstaller
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
        if os.path.exists(icon_path):
            return icon_path

    # Dev environment or current directory
    if os.path.exists('icon.ico'):
        return 'icon.ico'

    return None


def get_host_ip():
    """Get host IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_all_ips():
    """Get all IP addresses"""
    ips = []
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        ips.append(local_ip)
    except Exception:
        pass

    try:
        for interface in socket.getaddrinfo(socket.gethostname(), None):
            ip = interface[4][0]
            if ip not in ips and not ip.startswith('127.'):
                ips.append(ip)
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.append(ip)
    except Exception:
        pass

    ips.insert(0, '0.0.0.0 (All interfaces)')
    return ips

