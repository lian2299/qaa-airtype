package local.qaa.airtype;

import java.util.HashSet;
import java.util.Set;
import java.util.regex.*;

/** Only current, unsilenced Doubao sessions count; historical log entries never do. */
final class RecordingSnapshot {
    static final String IME = "com.bytedance.android.doubaoime";
    static Set<Integer> sessions(String dump) {
        int start = dump.indexOf("RecordActivityMonitor dump time:");
        int end = dump.indexOf("Events log:", start);
        if (start < 0 || end < start) throw new IllegalStateException("Unsupported recording monitor");
        Set<Integer> result = new HashSet<>();
        String current = dump.substring(start, end);
        for (String entry : current.split("(?m)^\\s*riid ")) {
            if (!entry.contains("active? true") || !entry.contains("-- pack:" + IME + " --")
                    || !entry.contains("-- silenced:false")) continue;
            Matcher session = Pattern.compile("session:(\\d+)").matcher(entry);
            if (!session.find()) throw new IllegalStateException("Missing recording session");
            result.add(Integer.parseInt(session.group(1)));
        }
        return result;
    }
}
