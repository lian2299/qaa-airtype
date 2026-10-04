package local.qaa.airtype;

import android.app.*;
import android.content.*;
import android.os.*;
import android.view.*;
import android.view.inputmethod.*;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.BooleanSupplier;

/** Real Android InputConnection and HTTP checks against a loopback-only sink. */
public class TransferTest extends Instrumentation {
    static final String BASE = "http://127.0.0.1:15001/";
    RemoteActivity remote;
    int checks;
    @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }
    @Override public void onStart() {
        SharedPreferences prefs = getTargetContext().getSharedPreferences("settings", 0);
        String oldUrl = prefs.getString("url", null), oldDraft = prefs.getString("draft", null);
        Bundle result = new Bundle();
        try {
            check(ServerClient.endpoint("https://nps.store2299.cn/air-type/", "/last_text").toString().equals(
                "https://nps.store2299.cn/air-type/last_text"), "probe keeps service path");
            check(ServerClient.endpoint("https://nps.store2299.cn/air-type", "/input_preview").toString().equals(
                "https://nps.store2299.cn/air-type/input_preview"), "preview accepts missing trailing slash");
            check(ServerClient.endpoint("https://nps.store2299.cn/air-type/", "/type").toString().equals(
                "https://nps.store2299.cn/air-type/type"), "send keeps service path");
            check(ServerClient.endpoint("http://127.0.0.1:15001/", "/type").toString().equals(
                "http://127.0.0.1:15001/type"), "LAN root and port remain valid");
            prefs.edit().putString("url", BASE).remove("draft").commit();
            getTargetContext().startActivity(new Intent(getTargetContext(), RemoteActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
            await(() -> RemoteActivity.instance != null && RemoteActivity.instance.resumed, "native editor open");
            runOnMainSync(() -> remote = RemoteActivity.instance);
            mode("ok"); prepare(); compose("原生提交测试");
            await(() -> !remote.sending && remote.editor.length() == 0, "successful send");
            JSONArray events = events();
            check(types(events) == 1 && finalText(events).equals("原生提交测试 "), "one final text with trailing space");
            int finalIndex = -1;
            for (int i = 0; i < events.length(); i++) if (events.getJSONObject(i).getString("path").equals("/type")) finalIndex = i;
            check(finalIndex > 0 && events.getJSONObject(finalIndex - 1).getString("path").equals("/input_preview") &&
                events.getJSONObject(finalIndex - 1).getJSONObject("data").getString("text").equals("原生提交测试"), "preview before final send");

            mode("preview_error"); prepare(); long beforePreviewFailureSound = soundAt(); compose("预览失败应保留");
            await(() -> remote.transfer.getText().toString().contains("发送未确认"), "preview failure callback");
            check(types(events()) == 0 && draft().equals("预览失败应保留"), "failed preview blocks final send and keeps draft");
            check(soundAt() == beforePreviewFailureSound, "failed preview does not play a send sound");

            mode("type_error"); prepare(); compose("发送失败应保留");
            await(() -> remote.transfer.getText().toString().contains("发送未确认"), "send failure callback");
            SystemClock.sleep(350);
            check(types(events()) == 1 && draft().equals("发送失败应保留"), "failed final send keeps draft without retries");

            mode("ok"); prepare();
            runOnMainSync(() -> {
                remote.voiceArmed = false;
                remote.editor.onCreateInputConnection(new EditorInfo()).commitText("手动输入不自动发", 1);
            });
            SystemClock.sleep(350);
            check(types(events()) == 0 && draft().equals("手动输入不自动发"), "unarmed typing stays in editor");

            mode("ok"); prepare();
            runOnMainSync(() -> { remote.voiceArmed = true; remote.voiceEnded(); });
            SystemClock.sleep(200);
            check(remote.voiceArmed && types(events()) == 0, "empty voice stop waits for recognition without sending");
            runOnMainSync(() -> remote.editor.onCreateInputConnection(new EditorInfo()).commitText("停止后才到达的识别结果", 1));
            await(() -> !remote.sending && remote.editor.length() == 0, "late recognition sent");
            check(types(events()) == 1 && finalText(events()).equals("停止后才到达的识别结果 "), "late final text is sent exactly once");

            mode("delayed_type"); prepare(); long beforeDelayedSound = soundAt(); compose("上一条语音");
            await(() -> remote.sending, "send in progress");
            await(() -> remote.lastSentSoundAt > beforeDelayedSound && remote.sending, "sound plays before delayed PC confirmation");
            check(remote.sending, "send sound starts while PC response is still pending");
            long submittedSoundAt = soundAt();
            runOnMainSync(() -> remote.editor.setText("下一条草稿"));
            await(() -> !remote.sending, "delayed response");
            check(draft().equals("下一条草稿") && finalText(events()).equals("上一条语音 "), "later input survives previous response");
            check(soundAt() == submittedSoundAt, "successful response does not play the send sound twice");

            mode("ok"); prepare();
            runOnMainSync(() -> remote.editor.setText("回车不发送此草稿"));
            long beforeKeySound = soundAt();
            enter(KeyEvent.KEYCODE_ENTER);
            await(() -> remote.transfer.getText().toString().equals("✓ 已发送 enter"), "hardware Enter callback");
            check(types(events()) == 1 && enters(events()) == 1 && draft().equals("回车不发送此草稿"), "hardware Enter sends only one PC key and keeps draft");
            check(soundAt() == beforeKeySound, "key-only requests do not play the send sound");

            mode("ok"); prepare(); enter(KeyEvent.KEYCODE_NUMPAD_ENTER);
            await(() -> remote.transfer.getText().toString().equals("✓ 已发送 enter"), "keypad Enter callback");
            check(types(events()) == 1 && enters(events()) == 1 && draft().isEmpty(), "keypad Enter sends PC key without local newline");

            mode("ok"); prepare();
            runOnMainSync(() -> remote.editor.setText("保留手机草稿"));
            enter(KeyEvent.KEYCODE_F1);
            await(() -> remote.transfer.getText().toString().equals("✓ 已发送 shift_enter"), "F1 soft Enter callback");
            check(types(events()) == 1 && keys(events(), "shift_enter") == 1 && draft().equals("保留手机草稿"), "original F1 mapping sends Shift+Enter and preserves local draft");

            mode("ok"); prepare();
            runOnMainSync(() -> remote.editor.setText("保留手机草稿"));
            enter(KeyEvent.KEYCODE_F2);
            await(() -> remote.transfer.getText().toString().equals("✓ 已发送 backspace"), "F2 Backspace callback");
            check(types(events()) == 1 && keys(events(), "backspace") == 1 && draft().equals("保留手机草稿"), "original F2 mapping sends Backspace and preserves local draft");

            mode("ok"); prepare();
            runOnMainSync(() -> {
                long at = SystemClock.uptimeMillis();
                remote.dispatchKeyEvent(new KeyEvent(at, at, KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER, 1));
                remote.dispatchKeyEvent(new KeyEvent(at, at, KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER, 0));
                remote.dispatchKeyEvent(new KeyEvent(at, at, KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER, 0, 0, -1, 0, KeyEvent.FLAG_CANCELED));
                remote.editor.onCreateInputConnection(new EditorInfo()).sendKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_NUMPAD_ENTER));
                remote.editor.onCreateInputConnection(new EditorInfo()).sendKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_NUMPAD_ENTER));
            });
            await(() -> remote.transfer.getText().toString().equals("✓ 已发送 enter"), "input connection Enter callback");
            check(types(events()) == 1 && enters(events()) == 1, "IME forwarded Enter works; repeats, releases and canceled presses do not send");

            mode("ok"); prepare();
            runOnMainSync(() -> {
                remote.voiceArmed = true;
                remote.editor.onCreateInputConnection(new EditorInfo()).commitText("先文字后回车", 1);
                remote.handleRemoteKey(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER));
            });
            await(() -> remote.transfer.getText().toString().equals("✓ 已发送 enter"), "pending final followed by Enter");
            check(textThenEnter(events(), "先文字后回车 "), "Enter flushes pending finalized voice text before sending key");

            mode("delayed_type"); prepare(); compose("传输中的文字");
            await(() -> remote.sending, "voice request in progress before Enter");
            enter(KeyEvent.KEYCODE_NUMPAD_ENTER);
            await(() -> remote.transfer.getText().toString().equals("✓ 已发送 enter"), "queued Enter callback");
            check(textThenEnter(events(), "传输中的文字 "), "Enter during text transfer is queued after text instead of dropped");

            mode("ok"); prepare();
            runOnMainSync(() -> {
                remote.resumed = false;
                try {
                    check(!remote.handleRemoteKey(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER)) &&
                        !remote.handleRemoteKey(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_F1)) &&
                        !remote.handleRemoteKey(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_F2)), "remote keys outside remote page pass through");
                } finally { remote.resumed = true; }
            });
            result.putString("stream", "TransferTest: " + checks + " checks passed\n");
            result.putBoolean("passed", true);
        } catch (Throwable error) {
            android.util.Log.e("AirTypeTests", "Device transfer checks failed after " + checks + " checks", error);
            result.putString("stream", "TransferTest FAILED: " + error + "\n");
            result.putBoolean("passed", false);
        } finally {
            runOnMainSync(() -> {
                if (remote != null) {
                    remote.voiceArmed = false; remote.editor.setText(oldDraft == null ? "" : oldDraft); remote.finish();
                }
            });
            SharedPreferences.Editor edit = prefs.edit();
            if (oldUrl == null) edit.remove("url"); else edit.putString("url", oldUrl);
            if (oldDraft == null) edit.remove("draft"); else edit.putString("draft", oldDraft);
            edit.commit();
        }
        finish(result.getBoolean("passed") ? Activity.RESULT_OK : Activity.RESULT_CANCELED, result);
    }
    void prepare() {
        runOnMainSync(() -> {
            remote.voiceArmed = false; remote.editor.composing = false; remote.editor.setText("");
            remote.transfer.setText("测试中"); remote.error = ""; remote.serverReady = false;
            remote.probedAt = 0; remote.probe();
        });
        await(() -> remote.serverReady && !remote.probing, "test service ready");
    }
    void compose(String text) {
        runOnMainSync(() -> {
            remote.voiceArmed = true;
            InputConnection input = remote.editor.onCreateInputConnection(new EditorInfo());
            input.setComposingText(text, 1); input.commitText(text, 1); input.finishComposingText();
        });
    }
    void await(BooleanSupplier condition, String name) {
        long until = SystemClock.uptimeMillis() + 5000;
        while (SystemClock.uptimeMillis() < until) {
            AtomicBoolean ok = new AtomicBoolean(); runOnMainSync(() -> ok.set(condition.getAsBoolean()));
            if (ok.get()) return;
            SystemClock.sleep(25);
        }
        throw new AssertionError("Timed out: " + name);
    }
    String draft() {
        String[] value = new String[1]; runOnMainSync(() -> value[0] = remote.editor.getText().toString()); return value[0];
    }
    long soundAt() {
        long[] value = new long[1]; runOnMainSync(() -> value[0] = remote.lastSentSoundAt); return value[0];
    }
    void check(boolean ok, String name) { if (!ok) throw new AssertionError(name); checks++; }
    void enter(int code) {
        sendKeySync(new KeyEvent(KeyEvent.ACTION_DOWN, code));
        sendKeySync(new KeyEvent(KeyEvent.ACTION_UP, code));
    }
    int enters(JSONArray events) throws Exception {
        return keys(events, "enter");
    }
    int keys(JSONArray events, String key) throws Exception {
        int count = 0;
        for (int i = 0; i < events.length(); i++) {
            JSONObject event = events.getJSONObject(i), data = event.getJSONObject("data");
            if (event.getString("path").equals("/type") && data.optBoolean(key) && data.optString("text").isEmpty()) count++;
        }
        return count;
    }
    boolean textThenEnter(JSONArray events, String text) throws Exception {
        JSONObject first = null, second = null;
        for (int i = 0; i < events.length(); i++) {
            JSONObject event = events.getJSONObject(i);
            if (!event.getString("path").equals("/type")) continue;
            if (first == null) first = event.getJSONObject("data"); else if (second == null) second = event.getJSONObject("data"); else return false;
        }
        return first != null && second != null && first.optString("text").equals(text) && second.optBoolean("enter") && second.optString("text").isEmpty();
    }
    int types(JSONArray events) throws Exception {
        int count = 0; for (int i = 0; i < events.length(); i++) if (events.getJSONObject(i).getString("path").equals("/type")) count++; return count;
    }
    String finalText(JSONArray events) throws Exception {
        for (int i = events.length() - 1; i >= 0; i--) if (events.getJSONObject(i).getString("path").equals("/type")) return events.getJSONObject(i).getJSONObject("data").getString("text");
        return "";
    }
    void mode(String mode) throws Exception { request("mode", new JSONObject().put("mode", mode).toString()); }
    JSONArray events() throws Exception { return new JSONObject(request("events", null)).getJSONArray("events"); }
    String request(String path, String data) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(BASE + path).openConnection();
        connection.setConnectTimeout(1200); connection.setReadTimeout(3000);
        try {
            if (data != null) {
                connection.setRequestMethod("POST"); connection.setDoOutput(true);
                byte[] bytes = data.getBytes(StandardCharsets.UTF_8); connection.setFixedLengthStreamingMode(bytes.length);
                try (OutputStream out = connection.getOutputStream()) { out.write(bytes); }
            }
            ByteArrayOutputStream body = new ByteArrayOutputStream();
            try (InputStream in = connection.getInputStream()) {
                byte[] block = new byte[2048]; int n; while ((n = in.read(block)) != -1) body.write(block, 0, n);
            }
            return body.toString("UTF-8");
        } finally { connection.disconnect(); }
    }
}
