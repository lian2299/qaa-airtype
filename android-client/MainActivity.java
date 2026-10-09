package local.qaa.airtype;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.provider.Settings;
import android.widget.*;
import android.view.*;
import android.graphics.Insets;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.content.res.ColorStateList;

public class MainActivity extends Activity {
    static final String DEFAULT_URL = "http://192.168.31.8:15000/";
    TextView status;
    final Runnable refreshConnections = () -> refresh();
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (android.os.Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        WindowManager.LayoutParams attributes = getWindow().getAttributes();
        attributes.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        getWindow().setAttributes(attributes);
        SharedPreferences prefs = getSharedPreferences("settings", 0);
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true); scroll.setClipToPadding(false);
        scroll.setBackgroundColor(Color.rgb(244, 247, 245)); applyInsets(scroll, dp(18));
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setFocusableInTouchMode(true);
        LinearLayout header = new LinearLayout(this); header.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout title = new LinearLayout(this); title.setOrientation(LinearLayout.VERTICAL);
        title.addView(text("AirType", 23, RemoteActivity.INK, true));
        title.addView(text("连接与设置", 12, RemoteActivity.MUTED, false));
        header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button remote = button("返回输入", false);
        header.addView(remote, new LinearLayout.LayoutParams(dp(88), dp(44)));
        remote.setOnClickListener(v -> startActivity(new Intent(this, RemoteActivity.class)));
        addSection(layout, header, 16);

        LinearLayout stateCard = new LinearLayout(this); stateCard.setGravity(Gravity.CENTER_VERTICAL);
        stateCard.setPadding(dp(14), dp(12), dp(14), dp(12));
        stateCard.setBackground(surface(Color.rgb(228, 240, 234), Color.TRANSPARENT, 14));
        status = text("", 14, RemoteActivity.ACCENT, true); status.setLineSpacing(dp(4), 1);
        stateCard.addView(status, new LinearLayout.LayoutParams(0, -2, 1));
        Button snapshot = button("刷新", false);
        LinearLayout.LayoutParams refreshParams = new LinearLayout.LayoutParams(dp(60), dp(40)); refreshParams.leftMargin = dp(10);
        stateCard.addView(snapshot, refreshParams); snapshot.setOnClickListener(v -> refresh());
        addSection(layout, stateCard, 14);

        LinearLayout connection = card("电脑连接");
        TextView addressHelp = text("AirType 服务地址", 12, RemoteActivity.MUTED, false);
        addSection(connection, addressHelp, 8);
        EditText url = new EditText(this);
        url.setId(1101); url.setTextSize(15); url.setTextColor(RemoteActivity.INK);
        url.setPadding(dp(12), dp(12), dp(12), dp(12));
        url.setBackground(surface(Color.rgb(244, 247, 245), Color.rgb(223, 232, 226), 12));
        url.setSingleLine(true); url.setText(prefs.getString("url", DEFAULT_URL));
        url.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        addSection(connection, url, 12);
        Button save = button("保存服务地址", true); connection.addView(save, new LinearLayout.LayoutParams(-1, dp(48)));
        save.setOnClickListener(v -> {
            String value = url.getText().toString().trim();
            Uri parsed = Uri.parse(value);
            if (!("http".equals(parsed.getScheme()) || "https".equals(parsed.getScheme())) || parsed.getHost() == null) {
                url.setError("请输入完整的 http:// 或 https:// 地址"); return;
            }
            prefs.edit().putString("url", value).apply();
            Toast.makeText(this, "地址已保存", Toast.LENGTH_SHORT).show();
        });
        addSection(layout, connection, 14);

        LinearLayout accessibility = card("无障碍服务");
        TextView accessHelp = text("先关闭 Tasker 的两条 F9 配置，再开启本应用服务。", 13, RemoteActivity.MUTED, false);
        accessHelp.setLineSpacing(dp(3), 1); addSection(accessibility, accessHelp, 12);
        Button access = button("打开无障碍设置", false); accessibility.addView(access, new LinearLayout.LayoutParams(-1, dp(48)));
        access.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        Button shizuku = button("授权 Shizuku", false);
        LinearLayout.LayoutParams shizukuParams = new LinearLayout.LayoutParams(-1, dp(48)); shizukuParams.topMargin = dp(8);
        accessibility.addView(shizuku, shizukuParams);
        shizuku.setOnClickListener(v -> { ShizukuVoice.requestPermission(); refresh(); });
        addSection(layout, accessibility, 14);

        LinearLayout shortcuts = card("按键说明");
        shortcut(shortcuts, "F9", "短按开始，再按结束\n按住满 1 秒，松开结束");
        shortcut(shortcuts, "Enter", "回车 / 发送");
        shortcut(shortcuts, "F1", "软回车 · Shift+Enter");
        shortcut(shortcuts, "F2", "删除 · Backspace");
        TextView help = text("听到成功提示音、看到绿色状态后开始说话。", 12, RemoteActivity.MUTED, false);
        help.setPadding(0, dp(10), 0, 0); shortcuts.addView(help);
        addSection(layout, shortcuts, 0);
        scroll.addView(layout, new ScrollView.LayoutParams(-1, -2));
        setContentView(scroll); layout.requestFocus(); scroll.requestApplyInsets(); enterFullscreen();
        refresh();
        if ("snapshot".equals(getIntent().getStringExtra("command")) && KeyService.instance != null) {
            new android.os.Handler(getMainLooper()).postDelayed(() -> {
                if (KeyService.instance != null) KeyService.instance.snapshot();
            }, 1000);
            if (getIntent().getBooleanExtra("return_remote", false)) startActivity(new Intent(this, RemoteActivity.class));
        }
    }
    int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    TextView text(String value, int size, int color, boolean bold) {
        TextView text = new TextView(this); text.setText(value); text.setTextSize(size); text.setTextColor(color);
        if (bold) text.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return text;
    }
    GradientDrawable surface(int fill, int border, int radius) {
        GradientDrawable background = new GradientDrawable(); background.setColor(fill); background.setCornerRadius(dp(radius));
        if (border != Color.TRANSPARENT) background.setStroke(dp(1), border);
        return background;
    }
    Button button(String label, boolean primary) {
        Button button = new Button(this); button.setText(label); button.setAllCaps(false); button.setFocusable(false);
        button.setTextSize(14); button.setTypeface(Typeface.DEFAULT, Typeface.BOLD); button.setSingleLine(true);
        button.setTextColor(primary ? Color.WHITE : RemoteActivity.INK); button.setMinWidth(0); button.setMinimumWidth(0);
        button.setMinHeight(0); button.setMinimumHeight(0); button.setPadding(dp(4), 0, dp(4), 0); button.setStateListAnimator(null);
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(primary ? 0x33FFFFFF : 0x18207059),
            surface(primary ? RemoteActivity.ACCENT : Color.WHITE, primary ? Color.TRANSPARENT : Color.rgb(220, 229, 224), 12), null));
        return button;
    }
    void addSection(LinearLayout parent, View child, int gap) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2); params.bottomMargin = dp(gap);
        parent.addView(child, params);
    }
    LinearLayout card(String title) {
        LinearLayout card = new LinearLayout(this); card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(14), dp(16), dp(16)); card.setBackground(surface(Color.WHITE, Color.rgb(223, 232, 226), 18));
        addSection(card, text(title, 16, RemoteActivity.INK, true), 12);
        return card;
    }
    void shortcut(LinearLayout parent, String key, String description) {
        LinearLayout row = new LinearLayout(this); row.setGravity(Gravity.CENTER_VERTICAL);
        TextView label = text(key, 12, RemoteActivity.ACCENT, true); label.setGravity(Gravity.CENTER);
        label.setPadding(0, dp(8), 0, dp(8)); label.setBackground(surface(Color.rgb(228, 240, 234), Color.TRANSPARENT, 8));
        row.addView(label, new LinearLayout.LayoutParams(dp(60), -2));
        TextView detail = text(description, 13, RemoteActivity.INK, false); detail.setLineSpacing(dp(3), 1);
        LinearLayout.LayoutParams detailParams = new LinearLayout.LayoutParams(0, -2, 1); detailParams.leftMargin = dp(12);
        row.addView(detail, detailParams); addSection(parent, row, 8);
    }
    static void applyInsets(View view, int padding) {
        view.setPadding(padding, padding, padding, padding);
        view.setOnApplyWindowInsetsListener((target, windowInsets) -> {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                Insets safe = windowInsets.getInsets(WindowInsets.Type.displayCutout());
                int keyboard = windowInsets.getInsets(WindowInsets.Type.ime()).bottom;
                target.setPadding(padding + safe.left, padding + safe.top, padding + safe.right, padding + Math.max(safe.bottom, keyboard));
                return WindowInsets.CONSUMED;
            } else {
                target.setPadding(padding + windowInsets.getSystemWindowInsetLeft(), padding + windowInsets.getSystemWindowInsetTop(),
                    padding + windowInsets.getSystemWindowInsetRight(), padding + windowInsets.getSystemWindowInsetBottom());
            }
            return windowInsets;
        });
    }
    void enterFullscreen() {
        if (android.os.Build.VERSION.SDK_INT >= 30) {
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
    void refresh() {
        boolean connected = KeyService.instance != null;
        status.setText(ConnectionStatus.summary() + "\n" +
            getSharedPreferences("settings", 0).getString("status", "等待 F9"));
        status.setTextColor(connected ? RemoteActivity.ACCENT : RemoteActivity.MUTED);
    }
    @Override public void onWindowFocusChanged(boolean focused) { super.onWindowFocusChanged(focused); if (focused) enterFullscreen(); }
    @Override public void onResume() { super.onResume(); ConnectionStatus.watch(this, refreshConnections); }
    @Override public void onPause() { ConnectionStatus.unwatch(refreshConnections); super.onPause(); }
    @Override public void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent);
        if ("snapshot".equals(intent.getStringExtra("command")) && KeyService.instance != null) {
            new android.os.Handler(getMainLooper()).postDelayed(() -> {
                if (KeyService.instance != null) KeyService.instance.snapshot();
            }, 1000);
            if (intent.getBooleanExtra("return_remote", false)) startActivity(new Intent(this, RemoteActivity.class));
        }
    }
}
