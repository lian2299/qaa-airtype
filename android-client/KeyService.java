package local.qaa.airtype;

import android.accessibilityservice.*;
import android.app.*;
import android.content.*;
import android.graphics.*;
import android.hardware.input.InputManager;
import android.media.*;
import android.os.*;
import android.provider.Settings;
import android.util.Log;
import android.view.*;
import android.view.accessibility.*;
import android.widget.Toast;
import java.io.*;

public class KeyService extends AccessibilityService implements InputManager.InputDeviceListener {
    static KeyService instance;
    static final String IME = "com.bytedance.android.doubaoime", TAG = "AirTypeF9";
    KeySession session = new KeySession(1000);
    Handler main = new Handler(Looper.getMainLooper());
    HandlerThread inspectorThread;
    Handler inspector;
    volatile ImeFrame latestFrame;
    volatile boolean inspecting;
    volatile long generation;
    long frameAt, nextFrameAt;
    ToneGenerator tone;
    long deadline, lastFocusAt, sessionAt, stopFrameLoggedAt, activityLaunchAt, microphoneStoppedAt;
    boolean tapped, stopClicked;
    boolean pcRecording;
    String pcRecordingUrl;
    volatile boolean gesturePending;
    int oldKeyboardMode;
    final Runnable tick = this::advance;
    final BroadcastReceiver diagnostic = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (intent.hasExtra("hold_ms") && !session.pressed) {
                long hold = Math.max(0, Math.min(10000, intent.getLongExtra("hold_ms", 100)));
                long at = SystemClock.uptimeMillis();
                handleKey(KeyEvent.ACTION_DOWN, 0, at, -1, false);
                main.postDelayed(() -> handleKey(KeyEvent.ACTION_UP, 0, at + hold, -1, false), hold);
                main.postDelayed(() -> snapshot(), 600);
            } else snapshot();
        }
    };
    @Override protected void onServiceConnected() {
        instance = this;
        // Content events can synchronously refresh Android's node cache on the
        // UI thread while the IME waits for our InputConnection. We poll the
        // speech controls on the inspector thread instead.
        AccessibilityServiceInfo info = getServiceInfo();
        info.eventTypes &= ~AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED;
        setServiceInfo(info);
        if (Build.VERSION.SDK_INT >= 33) log("NODE_CACHE_DISABLED=" + (setCacheEnabled(false) && !isCacheEnabled()));
        inspectorThread = new HandlerThread("AirTypeImeInspector"); inspectorThread.start();
        inspector = new Handler(inspectorThread.getLooper());
        try { tone = new ToneGenerator(AudioManager.STREAM_MUSIC, 65); } catch (RuntimeException ignored) {}
        oldKeyboardMode = getSoftKeyboardController().getShowMode();
        getSystemService(InputManager.class).registerInputDeviceListener(this, main);
        NotificationChannel channel = new NotificationChannel("f9", "F9 语音状态", NotificationManager.IMPORTANCE_LOW);
        channel.setSound(null, null); getSystemService(NotificationManager.class).createNotificationChannel(channel);
        status("等待 F9 · 短按免手持，长按松开结束", false); log("CONNECTED");
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(diagnostic, new IntentFilter("local.qaa.airtype.SNAPSHOT"), "android.permission.DUMP", main, Context.RECEIVER_EXPORTED);
        else registerReceiver(diagnostic, new IntentFilter("local.qaa.airtype.SNAPSHOT"), "android.permission.DUMP", main);
        schedule(0);
    }
    @Override protected boolean onKeyEvent(KeyEvent event) {
        RemoteActivity remote = RemoteActivity.instance;
        if (remote != null && remote.handleRemoteKey(event)) return true;
        if (event.getKeyCode() != KeyEvent.KEYCODE_F9) return false;
        handleKey(event.getAction(), event.getRepeatCount(), event.getEventTime(), event.getDeviceId(), event.isCanceled());
        return true;
    }
    void handleKey(int action, int repeat, long time, int device, boolean canceled) {
        log("KEY action=" + action + " repeat=" + repeat + " device=" + device + " dispatch_ms=" + (SystemClock.uptimeMillis() - time));
        KeySession.Command command = KeySession.Command.NONE;
        if (action == KeyEvent.ACTION_DOWN && repeat == 0) command = session.down(time, device);
        else if (action == KeyEvent.ACTION_UP) {
            command = session.up(time, canceled);
            if (session.phase == KeySession.Phase.RECORDING && session.handsFree) status("正在收音 · 免手持，再按 F9 结束", true);
        }
        if (command == KeySession.Command.START) begin();
        else if (command == KeySession.Command.STOP) stopRecording();
    }
    void begin() {
        generation++;
        if (getSystemService(KeyguardManager.class).isKeyguardLocked()) { fail("请先解锁手机，再按 F9"); return; }
        String method = Settings.Secure.getString(getContentResolver(), Settings.Secure.DEFAULT_INPUT_METHOD);
        if (method == null || !method.startsWith(IME + "/")) { fail("请将豆包设为当前输入法"); return; }
        sessionAt = SystemClock.uptimeMillis(); deadline = sessionAt + 7000; activityLaunchAt = sessionAt;
        tapped = false; gesturePending = false; stopClicked = false; microphoneStoppedAt = 0; lastFocusAt = sessionAt;
        latestFrame = null; frameAt = 0; nextFrameAt = 0;
        getSoftKeyboardController().setShowMode(SHOW_MODE_IGNORE_HARD_KEYBOARD);
        status("启动中 · 等待成功提示后说话", false); log("START");
        RemoteActivity remote = RemoteActivity.instance;
        try {
            if (remote != null && remote.resumed && remote.hasWindowFocus()) {
                remote.probe(); if (!remote.editor.hasFocus()) remote.focusInput();
            } else startActivity(new Intent(this, RemoteActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
        }
        catch (RuntimeException error) { fail("无法打开远程输入窗口"); return; }
        schedule(0);
    }
    void schedule(long millis) { main.removeCallbacks(tick); main.postDelayed(tick, millis); }
    void wakeStartup() { if (session.phase == KeySession.Phase.STARTING || session.phase == KeySession.Phase.IDLE) schedule(0); }
    void advance() {
        long now = SystemClock.uptimeMillis(); RemoteActivity remote = RemoteActivity.instance;
        if (session.phase == KeySession.Phase.IDLE) {
            if (remote == null || !remote.resumed) return;
            requestFrame();
            ImeFrame frame = latestFrame;
            // Direct taps on Doubao's speech control need the same arming and
            // feedback as F9. Require both the IME panel and a live microphone.
            if (frame != null && frame.recording && now - frameAt < 800 && recordingCount() > 0 && !remote.sending) {
                generation++; session.phase = KeySession.Phase.RECORDING; session.handsFree = true;
                sessionAt = now; microphoneStoppedAt = 0; tapped = false;
                remote.main.removeCallbacks(remote.expireVoice); remote.voiceArmed = true; remote.keepAwake(true);
                log("MANUAL_READY mic=" + recordingCount()); signal(true);
                syncPcRecording(true);
                status("正在收音 · 点击豆包结束或按 F9 结束", true);
            }
            schedule(150); return;
        }
        if (session.phase == KeySession.Phase.STARTING) {
            if (now > deadline) { fail(tapped ? "豆包未确认进入语音状态，请重试" : "输入法面板未就绪，请重试"); return; }
            if (remote == null || !remote.resumed) {
                // Home transitions can briefly retain focus/resumed state at
                // key-down. Retry once the old page has actually paused.
                if (now - activityLaunchAt >= 500) {
                    activityLaunchAt = now; log("OPEN_REMOTE_RETRY");
                    try { startActivity(new Intent(this, RemoteActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)); }
                    catch (RuntimeException error) { fail("无法打开远程输入窗口"); return; }
                }
                schedule(80); return;
            }
            if ((remote.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) == 0) remote.keepAwake(true);
            if (!remote.error.isEmpty()) { fail(remote.error); return; }
            requestFrame();
            if (!remote.serverReady) { schedule(40); return; }
            ImeFrame frame = latestFrame;
            if (!tapped) {
                if (frame != null && frame.start != null && now - frameAt < 800 && !remote.sending && recordingCount() == 0) {
                    remote.main.removeCallbacks(remote.expireVoice); remote.voiceArmed = true; tapped = true; deadline = now + 2500;
                    log("START_BUTTON latency=" + (now - sessionAt)); click(frame.start);
                } else if (now - lastFocusAt > 350) {
                    lastFocusAt = now; remote.focusInput();
                    // A real click retries IMEs that ignore programmatic show requests.
                    if (remote.editor.isShown()) {
                        int[] xy = new int[2]; remote.editor.getLocationOnScreen(xy);
                        tap(xy[0] + remote.editor.getWidth() / 2, xy[1] + Math.min(remote.editor.getHeight() / 2, 90));
                    }
                }
            } else if (frame != null && frame.recording && recordingCount() > 0) {
                log("READY latency=" + (now - sessionAt) + " mic=" + recordingCount());
                syncPcRecording(true);
                if (session.ready() == KeySession.Command.STOP) { stopRecording(); return; }
                signal(true);
                log("SIGNAL latency=" + (SystemClock.uptimeMillis() - sessionAt) + " key_latency=" + (SystemClock.uptimeMillis() - session.downAt));
                status(session.handsFree ? "正在收音 · 免手持，再按 F9 结束" : "正在收音 · 松开 F9 结束", true);
            }
            schedule(session.phase == KeySession.Phase.STARTING ? 40 : 150);
        } else if (session.phase == KeySession.Phase.RECORDING) {
            ImeFrame frame = latestFrame; requestFrame();
            if (recordingCount() == 0) {
                if (microphoneStoppedAt == 0) microphoneStoppedAt = now;
                if ((frame != null && frame.start != null && now - frameAt < 800) || now - microphoneStoppedAt >= 250) { finish("语音已结束"); return; }
            } else microphoneStoppedAt = 0;
            if (remote == null || !remote.resumed) { fail("远程输入窗口已离开，请按 F9 重试"); return; }
            schedule(150);
        } else if (session.phase == KeySession.Phase.STOPPING) {
            ImeFrame frame = latestFrame; requestFrame();
            int microphones = recordingCount();
            if (microphones == 0) {
                if (microphoneStoppedAt == 0) microphoneStoppedAt = now;
            } else microphoneStoppedAt = 0;
            if (now - stopFrameLoggedAt >= 250) {
                stopFrameLoggedAt = now;
                log("STOP_FRAME mic=" + microphones + " start=" + (frame != null && frame.start != null)
                    + " recording=" + (frame != null && frame.recording) + " age=" + (now - frameAt));
            }
            if (microphones == 0 && frame != null && frame.start != null && now - frameAt < 800) { finish("语音已结束"); return; }
            // The IME may keep its recognition panel visible after releasing
            // the microphone. Final text still arrives through InputConnection.
            if (microphoneStoppedAt != 0 && now - microphoneStoppedAt >= 250) {
                log("STOP_MIC_CONFIRMED"); finish("语音已结束"); return;
            }
            if (now > deadline) { fail("结束语音未确认，请检查手机"); return; }
            if (!stopClicked && frame != null && !frame.stopBounds.isEmpty() && now - frameAt < 800) {
                // A real touch avoids the synchronous ACTION_CLICK/InputConnection
                // round trip that stalled the observed stop for five seconds.
                stopClicked = tap(frame.stopBounds.centerX(), frame.stopBounds.centerY());
                if (stopClicked) log("STOP_TAP");
            }
            else if (!stopClicked && remote != null && remote.resumed && frame != null && now - frameAt < 800) {
                stopClicked = true; log("STOP_BACK"); performGlobalAction(GLOBAL_ACTION_BACK);
            }
            schedule(80);
        }
    }
    void stopRecording() {
        session.phase = KeySession.Phase.STOPPING; stopClicked = false; microphoneStoppedAt = 0; deadline = SystemClock.uptimeMillis() + 2500;
        status("正在结束语音…", false); log("STOP_REQUEST"); schedule(0);
    }
    void finish(String message) {
        syncPcRecording(false);
        generation++;
        main.removeCallbacks(tick); session.reset(SystemClock.uptimeMillis());
        if (RemoteActivity.instance != null) {
            RemoteActivity.instance.keepAwake(false);
            RemoteActivity.instance.voiceEnded();
        }
        status(message, false); log("FINISHED");
        schedule(150);
    }
    void fail(String message) {
        syncPcRecording(false);
        generation++;
        main.removeCallbacks(tick);
        if (tapped && RemoteActivity.instance != null && RemoteActivity.instance.resumed && latestFrame != null) performGlobalAction(GLOBAL_ACTION_BACK);
        session.reset(SystemClock.uptimeMillis());
        if (RemoteActivity.instance != null) { RemoteActivity.instance.voiceArmed = false; RemoteActivity.instance.keepAwake(false); }
        status(message, false); signal(false); log("FAILED " + message); Toast.makeText(this, message, Toast.LENGTH_LONG).show();
        schedule(150);
    }
    void transferFailed() { signal(false); log("TRANSFER_UNCONFIRMED"); }
    void syncPcRecording(boolean active) {
        if (pcRecording == active) return;
        pcRecording = active;
        if (active) pcRecordingUrl = getSharedPreferences("settings", 0).getString("url", MainActivity.DEFAULT_URL);
        ServerClient.recording(pcRecordingUrl, active, ok -> log("PC_RECORDING active=" + active + " success=" + ok));
    }
    void signal(boolean ok) {
        if (tone != null) tone.startTone(ok ? ToneGenerator.TONE_PROP_ACK : ToneGenerator.TONE_PROP_NACK, ok ? 100 : 350);
        Vibrator vibrator = getSystemService(Vibrator.class);
        if (vibrator != null) vibrator.vibrate(VibrationEffect.createOneShot(ok ? 40 : 200, VibrationEffect.DEFAULT_AMPLITUDE));
    }
    void status(String value, boolean recording) {
        getSharedPreferences("settings", 0).edit().putString("status", value).apply();
        if (RemoteActivity.instance != null) RemoteActivity.instance.showStatus(value, recording);
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        getSystemService(NotificationManager.class).notify(9, new Notification.Builder(this, "f9")
            .setSmallIcon(getResources().getIdentifier("icon", "drawable", getPackageName()))
            .setContentTitle("F9 远程语音").setContentText(value).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true).build());
    }
    static class ImeFrame {
        AccessibilityNodeInfo start, stop; boolean recording; Rect bounds = new Rect(), stopBounds = new Rect();
    }
    ImeFrame readIme() {
        for (AccessibilityWindowInfo window : getWindows()) {
            if (window.getType() != AccessibilityWindowInfo.TYPE_INPUT_METHOD) continue;
            AccessibilityNodeInfo root = window.getRoot();
            if (root == null || !IME.contentEquals(root.getPackageName())) continue;
            ImeFrame frame = new ImeFrame(); window.getBoundsInScreen(frame.bounds); scan(root, frame, 0); return frame;
        }
        return null;
    }
    void requestFrame() {
        if (inspecting || inspector == null || SystemClock.uptimeMillis() < nextFrameAt) return;
        inspecting = true;
        nextFrameAt = SystemClock.uptimeMillis() + 40;
        long expected = generation;
        inspector.post(() -> {
            long queriedAt = SystemClock.uptimeMillis();
            ImeFrame frame = null;
            try { if (expected == generation) frame = readIme(); }
            catch (RuntimeException error) { log("IME_QUERY_FAILED " + error.getClass().getSimpleName()); }
            ImeFrame result = frame;
            main.post(() -> {
                inspecting = false;
                if (expected == generation) {
                    latestFrame = result; frameAt = queriedAt;
                    if (session.phase == KeySession.Phase.STARTING) {
                        log("IME_FRAME latency=" + (frameAt - sessionAt) + " query_ms=" + (SystemClock.uptimeMillis() - queriedAt)
                            + " start=" + (result != null && result.start != null) + " recording=" + (result != null && result.recording));
                    }
                    if (result != null && (session.phase == KeySession.Phase.STARTING || session.phase == KeySession.Phase.STOPPING)) schedule(0);
                }
            });
        });
    }
    void scan(AccessibilityNodeInfo node, ImeFrame frame, int depth) {
        if (node == null || depth > 30 || !node.isVisibleToUser()) return;
        String label = label(node);
        String id = node.getViewIdResourceName();
        if (label.contains("点击说话")) frame.start = node;
        if ((IME + ":id/asr_root_ll").equals(id) || label.contains("结束说话") || label.contains("点击结束") || label.contains("停止录音") || label.equals("完成") || label.equals("结束")) {
            frame.stop = node; node.getBoundsInScreen(frame.stopBounds);
        }
        if ((IME + ":id/asr_root_ll").equals(id) || label.contains("正在倾听") || label.contains("正在聆听") || label.contains("正在说话") || label.contains("说话中") || label.contains("请说话") || label.contains("点击结束")) frame.recording = true;
        // The speech control is above the keyboard. Its subtree is sufficient;
        // walking every letter adds IPC without contributing to readiness.
        for (int i = 0; i < node.getChildCount() && frame.start == null && !(frame.recording && frame.stop != null); i++) scan(node.getChild(i), frame, depth + 1);
    }
    String label(AccessibilityNodeInfo node) {
        String text = node.getText() == null ? "" : node.getText().toString();
        String desc = node.getContentDescription() == null ? "" : node.getContentDescription().toString(); return (text + " " + desc).trim();
    }
    void click(AccessibilityNodeInfo node) {
        // Some IME accessibility actions synchronously wait for the editor's
        // InputConnection. Keep that IPC away from this app's main/UI thread.
        long expected = generation;
        inspector.post(() -> {
            if (expected != generation) return;
            long at = SystemClock.uptimeMillis();
            try { clickNow(node, expected); }
            catch (RuntimeException error) { log("IME_CLICK_FAILED " + error.getClass().getSimpleName()); }
            main.post(() -> {
                if (expected == generation) {
                    log("IME_CLICK latency=" + (SystemClock.uptimeMillis() - sessionAt) + " action_ms=" + (SystemClock.uptimeMillis() - at));
                    nextFrameAt = 0; requestFrame(); wakeStartup();
                }
            });
        });
    }
    void clickNow(AccessibilityNodeInfo node, long expected) {
        AccessibilityNodeInfo candidate = node;
        for (int i = 0; i < 4 && candidate != null && expected == generation; i++, candidate = candidate.getParent()) {
            if (candidate.isClickable() && candidate.isEnabled() && candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return;
        }
        Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
        if (!bounds.isEmpty()) main.post(() -> { if (expected == generation) tap(bounds.centerX(), bounds.centerY()); });
    }
    boolean tap(int x, int y) {
        if (gesturePending) return false;
        long expected = generation;
        Path point = new Path(); point.moveTo(x, y); gesturePending = true;
        boolean queued = dispatchGesture(new GestureDescription.Builder().addStroke(new GestureDescription.StrokeDescription(point, 0, 35)).build(),
            new GestureResultCallback() {
                @Override public void onCompleted(GestureDescription gesture) {
                    if (expected != generation) return;
                    gesturePending = false;
                    if (session.phase == KeySession.Phase.STOPPING) { log("STOP_TAP_COMPLETED"); nextFrameAt = 0; requestFrame(); schedule(0); }
                }
                @Override public void onCancelled(GestureDescription gesture) {
                    if (expected != generation) return;
                    gesturePending = false; log("GESTURE_CANCELED");
                    if (session.phase == KeySession.Phase.STOPPING) { stopClicked = false; schedule(80); }
                }
            }, main);
        if (!queued) { gesturePending = false; log("GESTURE_REJECTED"); }
        return queued;
    }
    int recordingCount() {
        try {
            int count = 0; for (AudioRecordingConfiguration config : getSystemService(AudioManager.class).getActiveRecordingConfigurations()) if (!config.isClientSilenced()) count++;
            return count;
        } catch (RuntimeException ignored) { return -1; }
    }
    void snapshot() {
        log("SNAPSHOT phase=" + session.phase + " mic=" + recordingCount());
        inspector.post(this::snapshotWindows);
    }
    void snapshotWindows() {
        for (AccessibilityWindowInfo window : getWindows()) {
            AccessibilityNodeInfo root = window.getRoot(); log("WINDOW type=" + window.getType() + " pkg=" + (root == null ? "null" : root.getPackageName()));
            if (root != null && IME.contentEquals(root.getPackageName())) dumpNodes(root, 0);
        }
    }
    void dumpNodes(AccessibilityNodeInfo node, int depth) {
        if (node == null || depth > 30) return;
        Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
        log("IME_NODE id=" + node.getViewIdResourceName() + " label=" + label(node) + " click=" + node.isClickable() + " bounds=" + bounds);
        for (int i = 0; i < node.getChildCount(); i++) dumpNodes(node.getChild(i), depth + 1);
    }
    synchronized void log(String value) {
        Log.i(TAG, value);
        try {
            File file = new File(getFilesDir(), "events.log");
            if (file.length() > 96000) {
                File previous = new File(getFilesDir(), "events.previous.log"); if (previous.exists()) previous.delete(); file.renameTo(previous);
            }
            try (FileWriter writer = new FileWriter(file, true)) { writer.write(SystemClock.uptimeMillis() + " " + value + "\n"); }
        } catch (IOException ignored) {}
    }
    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        if (!main.hasCallbacks(tick) && (session.phase != KeySession.Phase.IDLE || (RemoteActivity.instance != null && RemoteActivity.instance.resumed))) schedule(0);
    }
    @Override public void onInterrupt() { if (session.phase != KeySession.Phase.IDLE) fail("无障碍服务中断"); }
    @Override public void onInputDeviceAdded(int id) {}
    @Override public void onInputDeviceChanged(int id) {}
    @Override public void onInputDeviceRemoved(int id) {
        if (session.pressed && id == session.deviceId && session.up(SystemClock.uptimeMillis(), true) == KeySession.Command.STOP) stopRecording();
    }
    @Override public void onDestroy() {
        syncPcRecording(false);
        generation++;
        unregisterReceiver(diagnostic);
        if (inspectorThread != null) inspectorThread.quitSafely();
        main.removeCallbacksAndMessages(null); getSystemService(InputManager.class).unregisterInputDeviceListener(this);
        getSoftKeyboardController().setShowMode(oldKeyboardMode); getSystemService(NotificationManager.class).cancel(9);
        if (tone != null) tone.release(); if (instance == this) instance = null; super.onDestroy();
    }
}
