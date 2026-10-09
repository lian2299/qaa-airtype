package local.qaa.airtype;

import android.content.*;
import android.content.pm.PackageManager;
import android.media.*;
import android.os.*;
import android.provider.Settings;
import android.util.Log;
import java.util.concurrent.*;
import rikka.shizuku.Shizuku;

/** Foreground voice monitoring is independent of the accessibility service. */
final class ShizukuVoice {
    static final int PERMISSION = 73;
    final RemoteActivity remote;
    final Handler main = new Handler(Looper.getMainLooper());
    final ExecutorService worker = Executors.newSingleThreadExecutor();
    final IBinder lifetime = new Binder();
    final Shizuku.UserServiceArgs args;
    IBinder helper;
    boolean resumed, binding, ready, recording, busy, requesting;
    long generation, stoppedAt, bindAt, retryAt, queryAt;
    String lastFailure = "";
    ToneGenerator tone;
    final Runnable tick = this::poll;
    final Shizuku.OnBinderReceivedListener received = () -> main.post(this::wake);
    final Shizuku.OnBinderDeadListener died = () -> main.post(() -> failed("Shizuku disconnected"));
    final Shizuku.OnRequestPermissionResultListener permission = (code, result) -> {
        if (code == PERMISSION) main.post(() -> { requesting = false; wake(); });
    };
    final ServiceConnection connection = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            main.post(() -> {
                if (!resumed) { helper = binder; unbind(); return; }
                if (!binding) return;
                binding = false; helper = binder; wake();
            });
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            main.post(() -> { if (resumed && (helper != null || binding)) failed("Voice helper disconnected"); });
        }
    };
    ShizukuVoice(RemoteActivity activity) {
        remote = activity;
        args = new Shizuku.UserServiceArgs(new ComponentName(activity, VoiceUserService.class))
            .daemon(false).tag("airtype-voice").processNameSuffix("voice").version(1);
        Shizuku.addBinderReceivedListener(received);
        Shizuku.addBinderDeadListener(died);
        Shizuku.addRequestPermissionResultListener(permission);
    }
    static boolean authorized() {
        try { return Shizuku.pingBinder() && Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED; }
        catch (RuntimeException ignored) { return false; }
    }
    static String permissionStatus() {
        try {
            if (!Shizuku.pingBinder()) return "Shizuku 未运行";
            return authorized() ? "Shizuku 已授权" : "Shizuku 未授权";
        } catch (RuntimeException ignored) { return "Shizuku 未连接"; }
    }
    static String connectionStatus() {
        try {
            if (!Shizuku.pingBinder()) return "Shizuku：未连接";
            if (!authorized()) return "Shizuku：未授权";
            RemoteActivity remote = RemoteActivity.instance;
            if (remote != null && remote.resumed && remote.shizukuVoice != null && !remote.shizukuVoice.ready) {
                return "Shizuku：" + (remote.shizukuVoice.retryAt > SystemClock.uptimeMillis() ? "未连接" : "连接中");
            }
            return "Shizuku：已连接";
        } catch (RuntimeException ignored) { return "Shizuku：未连接"; }
    }
    static void requestPermission() {
        try {
            if (Shizuku.pingBinder() && !authorized()) Shizuku.requestPermission(PERMISSION);
        } catch (RuntimeException failure) { Log.w("AirTypeShizuku", "Request permission", failure); }
    }
    void resume() { resumed = true; retryAt = 0; wake(); }
    void pause() {
        resumed = false; generation++; ready = false; main.removeCallbacks(tick);
        if (recording) {
            ServerClient.recording(remote.url(), false, null);
            remote.voiceArmed = false; remote.keepAwake(false);
        }
        recording = false; stoppedAt = 0; unbind();
        ConnectionStatus.refresh();
    }
    void destroy() {
        pause(); worker.shutdown();
        Shizuku.removeBinderReceivedListener(received); Shizuku.removeBinderDeadListener(died);
        Shizuku.removeRequestPermissionResultListener(permission);
        if (tone != null) { tone.release(); tone = null; }
    }
    void wake() { if (resumed) { main.removeCallbacks(tick); main.post(tick); } }
    void schedule(long delay) { main.removeCallbacks(tick); if (resumed) main.postDelayed(tick, delay); }
    void unbind() {
        boolean attached = helper != null || binding;
        helper = null; binding = false;
        try { if (attached && Shizuku.pingBinder()) Shizuku.unbindUserService(args, connection, true); }
        catch (RuntimeException ignored) {}
    }
    void failed(String message) {
        generation++; ready = false; unbind(); retryAt = SystemClock.uptimeMillis() + 5000;
        if (!message.equals(lastFailure)) { lastFailure = message; Log.w("AirTypeShizuku", "FALLBACK " + message); }
        if (recording) {
            recording = false; stoppedAt = 0;
            ServerClient.recording(remote.url(), false, null);
            // A lost observer does not prove recording ended. Preserve the draft;
            // accessibility can re-arm it after confirming the live microphone.
            remote.voiceArmed = false; remote.keepAwake(false);
            remote.showStatus("语音连接已断开，文字已保留", false);
        }
        if (KeyService.instance != null) KeyService.instance.wakeStartup();
        ConnectionStatus.refresh();
        schedule(1000);
    }
    void poll() {
        if (!resumed) return;
        if (!authorized()) {
            if (ready || helper != null || binding) { failed("Shizuku unavailable or unauthorized"); return; }
            if (!requesting && !remote.getSharedPreferences("settings", 0).getBoolean("shizukuAsked", false)) {
                try {
                    if (Shizuku.pingBinder()) {
                        requesting = true;
                        remote.getSharedPreferences("settings", 0).edit().putBoolean("shizukuAsked", true).apply();
                        requestPermission();
                    }
                } catch (RuntimeException ignored) {}
            }
            schedule(1000); return;
        }
        if (busy) {
            if (helper != null && SystemClock.uptimeMillis() - queryAt > 2500) { failed("Voice observer timeout"); return; }
            schedule(150); return;
        }
        if (SystemClock.uptimeMillis() < retryAt) { schedule(150); return; }
        if (helper == null) {
            if (!binding) {
                binding = true; bindAt = SystemClock.uptimeMillis();
                try { Shizuku.bindUserService(args, connection); }
                catch (RuntimeException failure) { failed(failure.toString()); return; }
            } else if (SystemClock.uptimeMillis() - bindAt > 5000) { failed("Voice helper timeout"); return; }
            schedule(150); return;
        }
        IBinder binder = helper; long expected = generation; busy = true; queryAt = SystemClock.uptimeMillis();
        worker.execute(() -> {
            int state = -1, uid = -1; String error = "";
            Parcel request = Parcel.obtain(), reply = Parcel.obtain();
            try {
                request.writeInterfaceToken(VoiceUserService.DESCRIPTOR); request.writeStrongBinder(lifetime);
                if (!binder.transact(VoiceUserService.OBSERVE, request, reply, 0)) throw new IllegalStateException("Missing observe method");
                reply.readException(); state = reply.readInt(); error = reply.readString(); uid = reply.readInt();
            } catch (Exception failure) { error = failure.toString(); }
            finally { request.recycle(); reply.recycle(); }
            int observed = state, shellUid = uid; String failure = error;
            main.post(() -> {
                busy = false;
                if (!resumed || expected != generation) { schedule(150); return; }
                if (observed < 0) { failed(failure); return; }
                if (!ready) {
                    ready = true; lastFailure = "";
                    ConnectionStatus.refresh();
                    Log.i("AirTypeShizuku", "READY uid=" + shellUid);
                    if (!remote.voiceArmed) remote.showStatus("等待语音 · Shizuku", false);
                }
                observed(observed == 1); schedule(150);
            });
        });
        schedule(150);
    }
    void observed(boolean active) {
        long now = SystemClock.uptimeMillis();
        if (active) {
            stoppedAt = 0;
            KeyService keys = KeyService.instance;
            // Existing F9 sessions keep their start/stop controls and one set of feedback.
            if (!recording && keys != null && keys.session.phase != KeySession.Phase.IDLE) return;
            String ime = Settings.Secure.getString(remote.getContentResolver(), Settings.Secure.DEFAULT_INPUT_METHOD);
            if (!recording && remote.editor.hasFocus() && ime != null && ime.startsWith(RecordingSnapshot.IME + "/") && !remote.sending) {
                recording = true; remote.main.removeCallbacks(remote.expireVoice); remote.voiceArmed = true;
                remote.keepAwake(true); remote.showStatus("正在收音 · 点击豆包结束", true);
                try {
                    if (tone == null) tone = new ToneGenerator(AudioManager.STREAM_MUSIC, 65);
                    tone.startTone(ToneGenerator.TONE_PROP_ACK, 100);
                } catch (RuntimeException ignored) {}
                Vibrator vibrator = remote.getSystemService(Vibrator.class);
                if (vibrator != null) vibrator.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE));
                ServerClient.recording(remote.url(), true, null);
                Log.i("AirTypeShizuku", "MANUAL_READY");
            }
        } else if (recording) {
            if (stoppedAt == 0) stoppedAt = now;
            if (now - stoppedAt >= 250) {
                recording = false; stoppedAt = 0;
                ServerClient.recording(remote.url(), false, null);
                remote.keepAwake(false); remote.voiceEnded(); remote.showStatus("语音已结束 · Shizuku", false);
                Log.i("AirTypeShizuku", "FINISHED");
            }
        }
    }
}
