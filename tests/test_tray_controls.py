import unittest

from src.remote_server import ServerApp


class _FakeRoot:
    def __init__(self):
        self.callbacks = []

    def after(self, delay, callback):
        self.callbacks.append((delay, callback))


class TrayServiceControlTests(unittest.TestCase):
    def make_app(self):
        app = ServerApp.__new__(ServerApp)
        app.root = _FakeRoot()
        app.is_running = False
        app.cf_mode = False
        app.lan_server = None
        return app

    def test_menu_state_follows_service_state(self):
        app = self.make_app()
        self.assertTrue(app._tray_can_start_service())
        self.assertFalse(app._tray_can_stop_service())
        self.assertFalse(app._tray_can_restart_service())

        app.is_running = True
        self.assertFalse(app._tray_can_start_service())
        self.assertTrue(app._tray_can_stop_service())
        self.assertFalse(app._tray_can_restart_service())

        app.lan_server = object()
        self.assertTrue(app._tray_can_restart_service())

    def test_tray_actions_are_dispatched_to_tk_thread(self):
        app = self.make_app()
        app._tray_start_service()
        self.assertEqual(app.root.callbacks, [(0, app._do_start_service_from_tray)])

        app.root.callbacks.clear()
        app.is_running = True
        app._tray_stop_service()
        self.assertEqual(app.root.callbacks, [(0, app._do_stop_service_from_tray)])

        app.root.callbacks.clear()
        app.lan_server = object()
        app._tray_restart_service()
        self.assertEqual(app.root.callbacks, [(0, app._do_restart_service_from_tray)])


if __name__ == '__main__':
    unittest.main()
