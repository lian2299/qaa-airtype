package local.qaa.airtype;

import android.os.Handler;
import android.os.Looper;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;

final class ServerClient {
    interface Reply { void done(boolean ok); }
    // Keep preview/clipboard capture and final text in their original order.
    static final ExecutorService network = Executors.newSingleThreadExecutor();
    static final Handler main = new Handler(Looper.getMainLooper());
    static URL endpoint(String base, String path) throws Exception {
        URI uri = new URI(base);
        String prefix = uri.getPath();
        if (prefix == null || prefix.isEmpty()) prefix = "/";
        if (!prefix.endsWith("/")) prefix += "/";
        String relative = path.startsWith("/") ? path.substring(1) : path;
        return new URI(uri.getScheme(), null, uri.getHost(), uri.getPort(), prefix + relative, null, null).toURL();
    }
    static void probe(String base, Reply reply) {
        network.execute(() -> {
            boolean ok = false; HttpURLConnection c = null;
            try {
                c = (HttpURLConnection) endpoint(base, "/last_text").openConnection();
                c.setConnectTimeout(1200); c.setReadTimeout(1500);
                c.setRequestMethod("HEAD"); c.setInstanceFollowRedirects(false);
                ok = c.getResponseCode() == 200;
            } catch (Exception ignored) {} finally { if (c != null) c.disconnect(); }
            final boolean result = ok; main.post(() -> reply.done(result));
        });
    }
    static boolean postNow(String base, String path, JSONObject data) {
        return postNow(base, path, data, null);
    }
    static boolean postNow(String base, String path, JSONObject data, Runnable submitted) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) endpoint(base, path).openConnection();
            c.setConnectTimeout(1200); c.setReadTimeout(3000); c.setInstanceFollowRedirects(false);
            c.setRequestMethod("POST"); c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            byte[] bytes = data.toString().getBytes(StandardCharsets.UTF_8);
            c.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream out = c.getOutputStream()) { out.write(bytes); }
            if (submitted != null) main.post(submitted);
            if (c.getResponseCode() != 200) return false;
            ByteArrayOutputStream body = new ByteArrayOutputStream();
            try (InputStream in = c.getInputStream()) {
                byte[] block = new byte[2048]; int n;
                while ((n = in.read(block)) != -1) {
                    if (body.size() + n > 65536) return false;
                    body.write(block, 0, n);
                }
            }
            return new JSONObject(body.toString("UTF-8")).optBoolean("success", false);
        } catch (Exception ignored) { return false; }
        finally { if (c != null) c.disconnect(); }
    }
    static JSONObject text(String value) {
        JSONObject data = new JSONObject();
        try { data.put("text", value); } catch (Exception ignored) {}
        return data;
    }
    static void preview(String base, String value, Reply reply) {
        network.execute(() -> {
            boolean ok = postNow(base, "/input_preview", text(value));
            if (reply != null) main.post(() -> reply.done(ok));
        });
    }
    static void send(String base, String draft, Runnable submitted, Reply reply) {
        network.execute(() -> {
            boolean ok = postNow(base, "/input_preview", text(draft)) && postNow(base, "/type", text(draft + " "), submitted);
            main.post(() -> reply.done(ok));
        });
    }
    static void key(String base, String key, Reply reply) {
        network.execute(() -> {
            JSONObject data = text("");
            try { data.put(key, true); } catch (Exception ignored) {}
            boolean ok = postNow(base, "/type", data); main.post(() -> reply.done(ok));
        });
    }
}
