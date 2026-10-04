package local.qaa.airtype;

import android.app.Activity;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.media.AudioAttributes;
import android.media.SoundPool;
import android.os.*;
import android.text.*;
import android.view.*;
import android.view.inputmethod.*;
import android.widget.*;
import android.util.Log;

/** Native editor uses Doubao IME and AirType's existing HTTP endpoints. */
public class RemoteActivity extends Activity {
    static final int INK = Color.rgb(29, 46, 43), MUTED = Color.rgb(103, 119, 114), ACCENT = Color.rgb(24, 112, 91);
    static RemoteActivity instance;
    VoiceEditor editor;
    TextView banner, transfer;
    boolean resumed, serverReady, probing, sending, voiceArmed;
    long probedAt;
    String error = "", lastPreview = "", probedUrl = "";
    SoundPool sendSounds;
    int sentSound;
    boolean sentSoundReady, sentSoundPending;
    long lastSentSoundAt;
    Handler main = new Handler(Looper.getMainLooper());
    Runnable sendFinal = () -> {
        if (voiceArmed && !editor.composing && BaseInputConnection.getComposingSpanStart(editor.getText()) < 0) sendDraft();
    };
    @Override public void onCreate(Bundle state) {
        super.onCreate(state); instance = this; setTurnScreenOn(true);
        loadSentSound();
        if (Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        WindowManager.LayoutParams attributes = getWindow().getAttributes();
        attributes.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        getWindow().setAttributes(attributes);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.rgb(244, 247, 245));
        int pad = dp(18); applyFullscreenInsets(layout, pad);
        LinearLayout header = new LinearLayout(this); header.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout title = new LinearLayout(this); title.setOrientation(LinearLayout.VERTICAL);
        TextView name = new TextView(this); name.setText("AirType"); name.setTextSize(23); name.setTextColor(INK);
        name.setTypeface(Typeface.DEFAULT, Typeface.BOLD); title.addView(name);
        TextView subtitle = new TextView(this); subtitle.setText("远程语音输入"); subtitle.setTextSize(12); subtitle.setTextColor(MUTED); title.addView(subtitle);
        header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button settings = button("设置", false); header.addView(settings, new LinearLayout.LayoutParams(dp(64), dp(44)));
        settings.setOnClickListener(v -> startActivity(new Intent(this, MainActivity.class)));
        LinearLayout.LayoutParams headerParams = new LinearLayout.LayoutParams(-1, -2); headerParams.bottomMargin = dp(16);
        layout.addView(header, headerParams);
        banner = new TextView(this); banner.setTextSize(15); banner.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        banner.setGravity(Gravity.CENTER_VERTICAL); banner.setPadding(dp(14), dp(12), dp(14), dp(12)); layout.addView(banner);
        transfer = new TextView(this); transfer.setTextSize(12); transfer.setTextColor(MUTED);
        transfer.setPadding(dp(2), dp(8), dp(2), dp(12)); transfer.setText("短按 F9 开始 · 再按结束 · 长按松开结束"); layout.addView(transfer);
        LinearLayout input = new LinearLayout(this); input.setOrientation(LinearLayout.VERTICAL);
        input.setPadding(dp(16), dp(14), dp(16), dp(12)); input.setBackground(surface(Color.WHITE, Color.rgb(223, 232, 226), 18));
        TextView inputLabel = new TextView(this); inputLabel.setText("输入内容"); inputLabel.setTextSize(12); inputLabel.setTextColor(MUTED);
        input.addView(inputLabel);
        editor = new VoiceEditor(); editor.setId(1001); editor.setHint("开始说话，或在这里输入…");
        editor.setTextSize(20); editor.setTextColor(INK); editor.setHintTextColor(Color.rgb(149, 161, 156));
        editor.setGravity(Gravity.TOP | Gravity.START); editor.setBackgroundColor(Color.TRANSPARENT);
        editor.setPadding(0, dp(10), 0, 0); editor.setMinHeight(0);
        editor.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        editor.setImeOptions(EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        input.addView(editor, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(-1, 0, 1); inputParams.bottomMargin = dp(12);
        layout.addView(input, inputParams);
        editor.setText(getSharedPreferences("settings", 0).getString("draft", "")); editor.setSelection(editor.length());
        editor.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence text, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence text, int start, int before, int count) {}
            @Override public void afterTextChanged(Editable text) { syncPreview(); }
        });
        LinearLayout row = new LinearLayout(this);
        addButton(row, "发送到电脑", true, 2, () -> sendDraft());
        addButton(row, "清空", false, 1, () -> { voiceArmed = false; editor.setText(""); focusInput(); });
        LinearLayout.LayoutParams rowParams = new LinearLayout.LayoutParams(-1, -2); rowParams.bottomMargin = dp(8);
        layout.addView(row, rowParams);
        LinearLayout keys = new LinearLayout(this);
        addButton(keys, "回车", false, 1, () -> sendKey("enter")); addButton(keys, "软回车", false, 1, () -> sendKey("shift_enter"));
        addButton(keys, "删除", false, 1, () -> sendKey("backspace"));
        addButton(keys, "撤销", false, 1, () -> sendKey("undo")); layout.addView(keys);
        // Keep the controls and an editable area available in short windows or landscape with an IME.
        layout.addOnLayoutChangeListener((v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) -> {
            boolean compact = bottom - top - layout.getPaddingTop() - layout.getPaddingBottom() < dp(360);
            int visibility = compact ? View.GONE : View.VISIBLE;
            if (header.getVisibility() != visibility) {
                header.setVisibility(visibility); inputLabel.setVisibility(visibility);
                banner.setPadding(dp(14), dp(compact ? 6 : 12), dp(14), dp(compact ? 6 : 12));
                transfer.setPadding(dp(2), dp(6), dp(2), dp(compact ? 6 : 12));
            }
        });
        setContentView(layout); layout.requestApplyInsets(); enterFullscreen(); showStatus("等待 F9", false); probe();
    }
    int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    GradientDrawable surface(int fill, int border, int radius) {
        GradientDrawable background = new GradientDrawable(); background.setColor(fill); background.setCornerRadius(dp(radius));
        if (border != Color.TRANSPARENT) background.setStroke(dp(1), border);
        return background;
    }
    Button button(String label, boolean primary) {
        Button button = new Button(this); button.setText(label); button.setAllCaps(false); button.setFocusable(false);
        button.setTextSize(14); button.setTypeface(Typeface.DEFAULT, Typeface.BOLD); button.setSingleLine(true);
        button.setTextColor(primary ? Color.WHITE : INK); button.setMinWidth(0); button.setMinimumWidth(0);
        button.setMinHeight(0); button.setMinimumHeight(0); button.setPadding(dp(4), 0, dp(4), 0);
        button.setStateListAnimator(null);
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(primary ? 0x33FFFFFF : 0x18207059),
            surface(primary ? ACCENT : Color.WHITE, primary ? Color.TRANSPARENT : Color.rgb(220, 229, 224), 12), null));
        return button;
    }
    void addButton(LinearLayout row, String label, boolean primary, int weight, Runnable action) {
        Button button = button(label, primary);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(48), weight);
        if (row.getChildCount() > 0) params.leftMargin = dp(8);
        row.addView(button, params); button.setOnClickListener(v -> action.run());
    }
    void applyFullscreenInsets(View view, int padding) {
        view.setPadding(padding, padding, padding, padding);
        view.setOnApplyWindowInsetsListener((target, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                Insets safe = insets.getInsets(WindowInsets.Type.displayCutout());
                int keyboard = insets.getInsets(WindowInsets.Type.ime()).bottom;
                target.setPadding(padding + safe.left, padding + safe.top, padding + safe.right, padding + Math.max(safe.bottom, keyboard));
                return WindowInsets.CONSUMED;
            }
            target.setPadding(padding + insets.getSystemWindowInsetLeft(), padding + insets.getSystemWindowInsetTop(),
                padding + insets.getSystemWindowInsetRight(), padding + insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
    }
    void enterFullscreen() {
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                controller.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                controller.hide(WindowInsets.Type.systemBars());
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN |
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }
    }
    String url() { return getSharedPreferences("settings", 0).getString("url", MainActivity.DEFAULT_URL); }
    void probe() {
        String address = url();
        if (probing || (serverReady && address.equals(probedUrl) && SystemClock.uptimeMillis() - probedAt < 5000)) return;
        probing = true; error = ""; serverReady = false;
        ServerClient.probe(address, ok -> {
            probing = false; probedAt = SystemClock.uptimeMillis(); probedUrl = address;
            serverReady = ok; error = ok ? "" : "无法连接 PC 的 AirType 服务";
            if (!ok) transfer.setText(error + "；已输入的文字会保留");
            if (KeyService.instance != null) KeyService.instance.wakeStartup();
        });
    }
    void focusInput() {
        if (!resumed) return;
        editor.requestFocus(); editor.post(() -> {
            if (resumed) getSystemService(InputMethodManager.class).showSoftInput(editor, InputMethodManager.SHOW_IMPLICIT);
        });
    }
    void syncPreview() {
        String text = editor.getText().toString(); if (text.equals(lastPreview)) return;
        lastPreview = text;
        if (!serverReady) return;
        ServerClient.preview(url(), text, ok -> {
            if (!ok) {
                serverReady = false;
                transfer.setText("文字预览同步失败；内容仍保留在手机");
            }
        });
    }
    void compositionFinished() { main.removeCallbacks(sendFinal); main.postDelayed(sendFinal, 80); }
    void sendDraft() {
        String draft = editor.getText().toString().trim();
        if (sending || draft.isEmpty() || editor.composing || BaseInputConnection.getComposingSpanStart(editor.getText()) >= 0) return;
        sending = true; voiceArmed = false; transfer.setText("正在发送到 PC…");
        ServerClient.send(url(), draft, this::playSentSound, ok -> {
            sending = false;
            if (ok) {
                transfer.setText("✓ 已发送到 PC");
                // Keep any later input that arrived while the previous request was pending.
                if (editor.getText().toString().trim().equals(draft) && !editor.composing) {
                    editor.setText(""); getSharedPreferences("settings", 0).edit().remove("draft").apply();
                }
            } else {
                transfer.setText("发送未确认，文字已保留；请核对 PC 后手动重发");
                getSharedPreferences("settings", 0).edit().putString("draft", editor.getText().toString()).apply();
                if (KeyService.instance != null) KeyService.instance.transferFailed();
            }
        });
    }
    void loadSentSound() {
        try {
            sendSounds = new SoundPool.Builder().setMaxStreams(1).setAudioAttributes(new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()).build();
            sendSounds.setOnLoadCompleteListener((pool, id, status) -> {
                if (pool != sendSounds || id != sentSound) return;
                sentSoundReady = status == 0;
                if (sentSoundPending && sentSoundReady) { sentSoundPending = false; playSentSound(); }
            });
            sentSound = sendSounds.load(this, getResources().getIdentifier("message_sent", "raw", getPackageName()), 1);
        } catch (RuntimeException error) { Log.w("AirTypeSound", "Unable to load send sound", error); }
    }
    void playSentSound() {
        if (sendSounds == null || sentSound == 0) return;
        if (!sentSoundReady) { sentSoundPending = true; return; }
        try {
            int stream = sendSounds.play(sentSound, 0.65f, 0.65f, 1, 0, 1f);
            if (stream != 0) lastSentSoundAt = SystemClock.uptimeMillis();
            Log.i("AirTypeSound", stream != 0 ? "SENT_SOUND_PLAYED" : "SENT_SOUND_UNAVAILABLE");
        } catch (RuntimeException error) { Log.w("AirTypeSound", "Unable to play send sound", error); }
    }
    void sendKey(String key) {
        if (sending && "undo".equals(key)) return;
        // Flush a finalized voice draft before queuing a key, including the
        // short interval before sendFinal runs. The network queue preserves order.
        if (!"undo".equals(key) && voiceArmed && !editor.composing && BaseInputConnection.getComposingSpanStart(editor.getText()) < 0) {
            main.removeCallbacks(sendFinal); sendDraft();
        }
        ServerClient.key(url(), key, ok -> transfer.setText(ok ? "✓ 已发送 " + key : "快捷键发送未确认"));
    }
    boolean handleRemoteKey(KeyEvent event) {
        int code = event.getKeyCode();
        if (!resumed) return false;
        String key;
        if (code == KeyEvent.KEYCODE_ENTER || code == KeyEvent.KEYCODE_NUMPAD_ENTER) key = "enter";
        else if (code == KeyEvent.KEYCODE_F1) key = "shift_enter";
        else if (code == KeyEvent.KEYCODE_F2) key = "backspace";
        else return false;
        if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0 && !event.isCanceled()) {
            if (KeyService.instance != null) KeyService.instance.log("REMOTE_KEY key=" + key + " code=" + code + " device=" + event.getDeviceId());
            sendKey(key);
        }
        return true;
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        return handleRemoteKey(event) || super.dispatchKeyEvent(event);
    }
    void showStatus(String text, boolean recording) {
        banner.setText((recording ? "●  " : "○  ") + text);
        banner.setTextColor(recording ? Color.WHITE : ACCENT);
        banner.setBackground(surface(recording ? ACCENT : Color.rgb(228, 240, 234), Color.TRANSPARENT, 14));
    }
    void keepAwake(boolean keep) {
        if (keep) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
    @Override public void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); probe(); focusInput(); }
    @Override public void onResume() {
        super.onResume(); resumed = true; instance = this; probe(); focusInput();
        if (KeyService.instance != null) KeyService.instance.wakeStartup();
    }
    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) { enterFullscreen(); focusInput(); if (KeyService.instance != null) KeyService.instance.wakeStartup(); }
    }
    @Override public void onPause() {
        resumed = false; getSharedPreferences("settings", 0).edit().putString("draft", editor.getText().toString()).apply(); super.onPause();
    }
    @Override public void onDestroy() {
        if (instance == this) instance = null; main.removeCallbacks(sendFinal);
        if (sendSounds != null) { sendSounds.release(); sendSounds = null; }
        sentSoundPending = false; super.onDestroy();
    }
    class VoiceEditor extends EditText {
        boolean composing;
        VoiceEditor() { super(RemoteActivity.this); }
        @Override public InputConnection onCreateInputConnection(EditorInfo info) {
            InputConnection target = super.onCreateInputConnection(info); if (target == null) return null;
            return new InputConnectionWrapper(target, false) {
                @Override public boolean sendKeyEvent(KeyEvent event) {
                    return handleRemoteKey(event) || super.sendKeyEvent(event);
                }
                @Override public boolean setComposingText(CharSequence text, int cursor) {
                    composing = true; main.removeCallbacks(sendFinal); return super.setComposingText(text, cursor);
                }
                @Override public boolean setComposingText(CharSequence text, int cursor, TextAttribute attribute) {
                    composing = true; main.removeCallbacks(sendFinal); return super.setComposingText(text, cursor, attribute);
                }
                @Override public boolean commitText(CharSequence text, int cursor) {
                    boolean result = super.commitText(text, cursor); composing = false; compositionFinished(); return result;
                }
                @Override public boolean commitText(CharSequence text, int cursor, TextAttribute attribute) {
                    boolean result = super.commitText(text, cursor, attribute); composing = false; compositionFinished(); return result;
                }
                @Override public boolean finishComposingText() {
                    boolean result = super.finishComposingText(); composing = false; compositionFinished(); return result;
                }
            };
        }
    }
}
