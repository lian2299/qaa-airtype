import unittest
from unittest.mock import Mock, patch

from src import remote_server, state
from src.remote_server import ServerApp


class InputPreviewTests(unittest.TestCase):
    def setUp(self):
        state.clear_input_preview()
        state.set_input_recording(False)
        self.client = remote_server.app.test_client()
        self.gui = ServerApp.__new__(ServerApp)
        self.gui.root = Mock()
        self.gui.root.after.side_effect = lambda delay, callback: callback()
        self.gui.input_preview_window = Mock()
        self.gui.input_preview_text_label = Mock()
        self.gui._ensure_input_preview_window = Mock()
        self.gui._position_input_preview_window = Mock()
        self.gui._apply_input_preview_window_styles = Mock()
        self.handler = patch.object(remote_server, 'input_preview_update_handler', self.gui.schedule_input_preview_update)
        self.handler.start()
        self.addCleanup(self.handler.stop)
        self.addCleanup(state.clear_input_preview)
        self.addCleanup(state.set_input_recording, False)

    def post(self, payload):
        response = self.client.post('/input_preview', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])

    def test_recording_opens_panel_before_first_text_and_empty_updates_keep_it_open(self):
        self.post({'recording': True})
        self.gui.input_preview_window.deiconify.assert_called_once()
        self.gui.input_preview_text_label.config.assert_called_with(text='正在录音，等待识别文字…')
        self.post({'text': ''})
        self.gui.input_preview_window.withdraw.assert_not_called()
        self.post({'text': '识别中的文字'})
        self.gui.input_preview_text_label.config.assert_called_with(text='识别中的文字')

    def test_empty_recording_end_hides_panel(self):
        self.post({'recording': True})
        self.post({'recording': False})
        self.gui.input_preview_window.withdraw.assert_called_once()

    def test_recording_end_preserves_text_and_clipboard_bindings(self):
        state.set_input_preview('保留草稿')
        snapshot = object()
        state.sync_paste_occurrences(['paste'], capture_fn=lambda: snapshot)
        with patch.object(state, 'sync_paste_occurrences') as capture:
            self.post({'recording': True})
            self.post({'recording': False})
        capture.assert_not_called()
        self.assertEqual(state.get_input_preview()[0], '保留草稿')
        self.assertEqual(state.get_paste_snapshots(['paste'], capture_missing=False), [snapshot])
        self.gui.input_preview_window.withdraw.assert_not_called()

    def test_clearing_sent_text_waits_while_recording_then_hides(self):
        self.post({'recording': True, 'text': '将要发送'})
        state.clear_input_preview()
        self.gui.schedule_input_preview_update('')
        self.gui.input_preview_window.withdraw.assert_not_called()
        self.post({'recording': False})
        self.gui.input_preview_window.withdraw.assert_called_once()

    def test_text_only_clients_still_show_and_hide(self):
        self.post({'text': '网页版文字'})
        self.gui.input_preview_window.deiconify.assert_called_once()
        self.post({'text': ''})
        self.gui.input_preview_window.withdraw.assert_called_once()

    def test_invalid_recording_does_not_change_text_or_state(self):
        state.set_input_preview('保留草稿')
        response = self.client.post('/input_preview', json={'recording': 'false', 'text': ''})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(state.get_input_recording())
        self.assertEqual(state.get_input_preview()[0], '保留草稿')


if __name__ == '__main__':
    unittest.main()
