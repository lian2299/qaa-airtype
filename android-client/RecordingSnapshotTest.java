package local.qaa.airtype;

public final class RecordingSnapshotTest {
    static String entry(boolean active, String pack, boolean silenced, int session) {
        return "riid 1; active? " + active + "\n  session:" + session + " -- pack:" + pack
            + " -- format client=x -- silenced:" + silenced + " -- effects client=\n";
    }
    static String dump(String current) {
        return "RecordActivityMonitor dump time: 12:00\n" + current
            + "Events log: recording activity received by AudioService\n"
            + entry(true, RecordingSnapshot.IME, false, 99);
    }
    static void check(boolean ok) { if (!ok) throw new AssertionError(); }
    public static void main(String[] args) {
        check(RecordingSnapshot.sessions(dump("")).isEmpty());
        check(RecordingSnapshot.sessions(dump(entry(false, RecordingSnapshot.IME, false, 1))).isEmpty());
        check(RecordingSnapshot.sessions(dump(entry(true, RecordingSnapshot.IME, true, 1))).isEmpty());
        check(RecordingSnapshot.sessions(dump(entry(true, "other.microphone", false, 1))).isEmpty());
        check(RecordingSnapshot.sessions(dump(entry(true, RecordingSnapshot.IME, false, 7))).contains(7));
        check(RecordingSnapshot.sessions(dump(entry(true, RecordingSnapshot.IME + ".other", false, 7))).isEmpty());
        check(RecordingSnapshot.sessions(dump(entry(true, RecordingSnapshot.IME, false, 7)
            + entry(false, RecordingSnapshot.IME, false, 8))).size() == 1);
        try { RecordingSnapshot.sessions("permission denied"); throw new AssertionError(); }
        catch (IllegalStateException expected) {}
        System.out.println("RecordingSnapshotTest: 8 checks passed");
    }
}
