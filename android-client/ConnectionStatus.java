package local.qaa.airtype;

import android.app.*;
import android.content.*;
import android.os.*;
import java.util.*;
import rikka.shizuku.Shizuku;

/** One live connection summary for the input page, settings and notification. */
final class ConnectionStatus {
    static final Handler main = new Handler(Looper.getMainLooper());
    static final Set<Runnable> observers = new HashSet<>();
    static Context app;
    static String notified = "";
    static final Runnable tick = () -> refresh();

    static void start(Context context) {
        if (app == null) {
            app = context.getApplicationContext();
            NotificationChannel channel = new NotificationChannel("f9", "F9 语音状态", NotificationManager.IMPORTANCE_LOW);
            channel.setSound(null, null);
            app.getSystemService(NotificationManager.class).createNotificationChannel(channel);
            Shizuku.addBinderReceivedListener(() -> main.post(tick));
            Shizuku.addBinderDeadListener(() -> main.post(tick));
            Shizuku.addRequestPermissionResultListener((code, result) -> main.post(tick));
        }
        refresh();
    }
    static String summary() {
        return "无障碍：" + (KeyService.instance != null ? "已连接" : "未连接") + " · " + ShizukuVoice.connectionStatus();
    }
    static void watch(Context context, Runnable observer) { observers.add(observer); start(context); }
    static void unwatch(Runnable observer) { observers.remove(observer); refresh(); }
    static void status(Context context, String value) {
        context.getSharedPreferences("settings", 0).edit().putString("status", value).apply();
        start(context);
    }
    static void refresh() {
        if (app == null) return;
        main.removeCallbacks(tick);
        for (Runnable observer : new ArrayList<>(observers)) observer.run();
        String line = summary();
        String activity = app.getSharedPreferences("settings", 0).getString("status", "等待语音");
        String content = line + "\n" + activity;
        if (!content.equals(notified)) {
            PendingIntent open = PendingIntent.getActivity(app, 0, new Intent(app, RemoteActivity.class),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            app.getSystemService(NotificationManager.class).notify(9, new Notification.Builder(app, "f9")
                .setSmallIcon(app.getResources().getIdentifier("icon", "drawable", app.getPackageName()))
                .setContentTitle("F9 远程语音").setContentText(line)
                .setStyle(new Notification.BigTextStyle().bigText(content))
                .setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true).build());
            notified = content;
        }
        // No background polling when both the UI and accessibility are inactive.
        if (!observers.isEmpty() || KeyService.instance != null) main.postDelayed(tick, 1000);
    }
}
