package local.qaa.airtype;

import android.app.*;
import android.content.*;
import android.os.*;
import android.view.inputmethod.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.BooleanSupplier;
import org.json.JSONArray;

/** Real Shizuku attribution and IME microphone, with a simulated final text commit to an isolated sink. */
public final class ShizukuTest extends TransferTest {
    void progress(String message) { Bundle update = new Bundle(); update.putString("stream", message + "\n"); sendStatus(0, update); }
    void awaitTap(BooleanSupplier condition, String label) {
        long deadline = SystemClock.uptimeMillis() + 60000;
        while (SystemClock.uptimeMillis() < deadline) {
            AtomicBoolean ok = new AtomicBoolean(); runOnMainSync(() -> ok.set(condition.getAsBoolean()));
            if (ok.get()) return;
            SystemClock.sleep(50);
        }
        throw new AssertionError("Timed out: " + label);
    }
    @Override public void onStart() {
        SharedPreferences prefs = getTargetContext().getSharedPreferences("settings", 0);
        String oldUrl = prefs.getString("url", null), oldDraft = prefs.getString("draft", null);
        Bundle result = new Bundle();
        try {
            prefs.edit().putString("url", BASE).remove("draft").commit();
            getTargetContext().startActivity(new Intent(getTargetContext(), RemoteActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
            await(() -> RemoteActivity.instance != null && RemoteActivity.instance.resumed, "editor ready");
            runOnMainSync(() -> remote = RemoteActivity.instance);
            mode("ok"); prepare();
            await(() -> remote.shizukuVoice.ready, "Shizuku shell observer ready");
            check(ShizukuVoice.authorized(), "Shizuku is authorized");
            check(KeyService.instance == null, "AirType accessibility is disconnected");
            progress("READY_FOR_DIRECT_TAP");
            awaitTap(() -> remote.shizukuVoice.recording, "real Doubao recording start");
            check(remote.voiceArmed, "real Shizuku microphone observation armed automatic sending");
            runOnMainSync(() -> remote.editor.onCreateInputConnection(new EditorInfo()).setComposingText("录音中的未确认草稿", 1));
            SystemClock.sleep(250);
            check(types(events()) == 0, "composing draft is not sent during recording");
            progress("READY_FOR_DIRECT_STOP");
            awaitTap(() -> !remote.shizukuVoice.recording, "real Doubao recording stop");
            check(KeyService.instance == null && remote.voiceArmed, "Shizuku owns the finalization without accessibility");
            runOnMainSync(() -> {
                remote.editor.setText("");
                InputConnection input = remote.editor.onCreateInputConnection(new EditorInfo());
                input.commitText("Shizuku独立发送验证", 1); input.finishComposingText();
            });
            await(() -> !remote.sending && remote.editor.length() == 0, "Shizuku-armed final text sent");
            JSONArray captured = events();
            check(types(captured) == 1 && finalText(captured).equals("Shizuku独立发送验证 "), "one exact final text to the isolated sink");
            check(KeyService.instance == null, "accessibility stayed disconnected through sending");
            result.putString("stream", "ShizukuTest: " + checks + " checks passed (real microphone, simulated final InputConnection text)\n");
            result.putBoolean("passed", true);
        } catch (Throwable failure) {
            result.putString("stream", "ShizukuTest FAILED: " + failure + "\n"); result.putBoolean("passed", false);
        } finally {
            if (remote != null) runOnMainSync(() -> {
                remote.voiceArmed = false; remote.editor.setText(oldDraft == null ? "" : oldDraft); remote.finish();
            });
            SharedPreferences.Editor edit = prefs.edit();
            if (oldUrl == null) edit.remove("url"); else edit.putString("url", oldUrl);
            if (oldDraft == null) edit.remove("draft"); else edit.putString("draft", oldDraft);
            edit.commit();
        }
        finish(result.getBoolean("passed") ? Activity.RESULT_OK : Activity.RESULT_CANCELED, result);
    }
}
