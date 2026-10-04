"""Tests for safe clipboard snapshot serialization (no real clipboard writes)."""
import struct
import unittest
from unittest.mock import patch

from PIL import Image

from src.clipboard import (
    ClipboardSnapshot,
    _files_to_hdrop,
    _image_to_dib,
    restore_clipboard_snapshot,
)


class ClipboardSnapshotTests(unittest.TestCase):
    def test_image_is_encoded_as_dib_without_bmp_file_header(self):
        image = Image.new('RGB', (2, 3), color='red')

        dib = _image_to_dib(image)

        self.assertEqual(struct.unpack_from('<I', dib)[0], 40)
        self.assertNotEqual(dib[:2], b'BM')

    def test_file_list_is_encoded_as_unicode_hdrop(self):
        payload = _files_to_hdrop([r'C:\one.png', r'D:\two.txt'])

        offset, _, _, _, wide = struct.unpack_from('<IiiII', payload)
        self.assertEqual(offset, 20)
        self.assertEqual(wide, 1)
        self.assertEqual(
            payload[offset:].decode('utf-16le'),
            'C:\\one.png\0D:\\two.txt\0\0',
        )

    def test_image_restore_uses_only_known_cf_dib_format(self):
        snapshot = ClipboardSnapshot(kind='image', payload=b'dib-data')

        with patch('src.clipboard.IS_WINDOWS', True), \
                patch('src.clipboard._set_windows_clipboard_payload') as setter:
            self.assertTrue(restore_clipboard_snapshot(snapshot))

        setter.assert_called_once_with(8, b'dib-data')

    def test_file_restore_uses_only_known_cf_hdrop_format(self):
        snapshot = ClipboardSnapshot(kind='files', payload=(r'C:\one.png',))

        with patch('src.clipboard.IS_WINDOWS', True), \
                patch('src.clipboard._set_windows_clipboard_payload') as setter:
            self.assertTrue(restore_clipboard_snapshot(snapshot))

        self.assertEqual(setter.call_args.args[0], 15)


if __name__ == '__main__':
    unittest.main()
