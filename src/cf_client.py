"""Cloudflare client module"""
import asyncio
import threading
import time
import json
import hashlib
import base64

try:
    import websockets
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CF_AVAILABLE = True
except ImportError:
    CF_AVAILABLE = False


def derive_key_and_room(password: str) -> tuple:
    """Derive AES key and room ID from password"""
    password = password.strip() or 'noset'
    encoded = password.encode('utf-8')
    hash_bytes = hashlib.sha256(encoded).digest()
    room_id = hash_bytes.hex()
    return hash_bytes, room_id


def decrypt_message(key: bytes, iv_b64: str, data_b64: str) -> str:
    """AES-GCM decrypt message"""
    if not CF_AVAILABLE:
        raise ImportError("websockets and cryptography required for CF mode")
    
    iv = base64.b64decode(iv_b64)
    data = base64.b64decode(data_b64)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, data, None)
    return plaintext.decode('utf-8')


class CFChatClient:
    """CF mode WebSocket client"""
    def __init__(self, worker_url: str, password: str, on_message=None, on_status=None):
        if not CF_AVAILABLE:
            raise ImportError("websockets and cryptography required for CF mode")
        
        self.worker_url = worker_url.rstrip('/')
        self.password = password
        self.on_message = on_message
        self.on_status = on_status
        self.key, self.room_id = derive_key_and_room(password)
        self.ws = None
        self.running = False
        self._loop = None
        self._thread = None

    def _get_ws_url(self) -> str:
        """Build WebSocket URL"""
        url = self.worker_url
        if url.startswith('https://'):
            url = 'wss://' + url[8:]
        elif url.startswith('http://'):
            url = 'ws://' + url[7:]
        elif not url.startswith('ws'):
            url = 'wss://' + url
        return f"{url}/ws/{self.room_id}"

    async def _connect(self):
        """Connect and listen for messages"""
        ws_url = self._get_ws_url()
        if self.on_status:
            self.on_status('connecting', 'Connecting...')

        try:
            async with websockets.connect(ws_url) as ws:
                self.ws = ws
                if self.on_status:
                    self.on_status('connected', 'Connected to CF')

                while self.running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        self._handle_message(raw)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break

        except Exception as e:
            if self.on_status:
                self.on_status('error', f'Connection failed: {e}')

        finally:
            self.ws = None
            if self.on_status and self.running:
                self.on_status('disconnected', 'Disconnected, reconnecting...')

    def _handle_message(self, raw: str):
        """Handle received message"""
        try:
            payload = json.loads(raw)
            msg_type = payload.get('type', 'text').lower()

            if msg_type != 'text':
                return

            iv = payload.get('iv')
            data = payload.get('data')
            if not iv or not data:
                return

            text = decrypt_message(self.key, iv, data)
            if self.on_message:
                self.on_message(text)

        except Exception as e:
            print(f"Message handling error: {e}")

    def _run_loop(self):
        """Run event loop in separate thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        while self.running:
            try:
                self._loop.run_until_complete(self._connect())
            except Exception as e:
                print(f"Connection error: {e}")

            if self.running:
                time.sleep(2)

        self._loop.close()

    def start(self):
        """Start client"""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop client"""
        self.running = False
        if self.ws and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self.ws.close(), self._loop)
            except:
                pass

