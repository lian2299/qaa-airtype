package local.qaa.airtype;

import android.content.Context;
import android.media.AudioRecordingConfiguration;
import android.os.Binder;
import android.os.IBinder;
import android.os.Parcel;
import android.os.Process;
import android.os.RemoteException;
import android.os.SystemClock;
import java.io.*;
import java.lang.reflect.Method;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Shizuku shell helper. Only exposes attributed recording state, never arbitrary commands. */
public final class VoiceUserService extends Binder {
    static final String DESCRIPTOR = "local.qaa.airtype.VoiceMonitor";
    static final int OBSERVE = 1;
    private final int appUid;
    private final Object audio;
    private final Method configurations;
    private IBinder owner;
    private Set<Integer> lastSessions = null, doubaoSessions = new HashSet<>();
    private long attributedAt;

    public VoiceUserService(Context context) throws Exception {
        appUid = context.getPackageManager().getApplicationInfo("local.qaa.airtype", 0).uid;
        IBinder binder = (IBinder) Class.forName("android.os.ServiceManager")
            .getMethod("getService", String.class).invoke(null, "audio");
        audio = Class.forName("android.media.IAudioService$Stub")
            .getMethod("asInterface", IBinder.class).invoke(null, binder);
        configurations = Class.forName("android.media.IAudioService").getMethod("getActiveRecordingConfigurations");
    }
    @Override protected synchronized boolean onTransact(int code, Parcel data, Parcel reply, int flags)
            throws RemoteException {
        int caller = getCallingUid();
        if (code == 16777115 && (caller == 2000 || caller == 0 || caller == appUid)) {
            Process.killProcess(Process.myPid()); return true;
        }
        if (code != OBSERVE) return super.onTransact(code, data, reply, flags);
        data.enforceInterface(DESCRIPTOR);
        if (caller != appUid) throw new SecurityException("Only AirType may observe recording");
        IBinder lifetime = data.readStrongBinder();
        if (lifetime == null) throw new SecurityException("Missing owner lifetime");
        if (owner == null) {
            owner = lifetime; owner.linkToDeath(() -> Process.killProcess(Process.myPid()), 0);
        }
        int state = -1; String error = "";
        try { state = recording() ? 1 : 0; }
        catch (Exception failure) { error = failure.toString(); lastSessions = null; }
        reply.writeNoException(); reply.writeInt(state); reply.writeString(error); reply.writeInt(Process.myUid());
        return true;
    }
    @SuppressWarnings("unchecked") private boolean recording() throws Exception {
        List<AudioRecordingConfiguration> configs = (List<AudioRecordingConfiguration>) configurations.invoke(audio);
        Set<Integer> active = new HashSet<>();
        for (AudioRecordingConfiguration config : configs) {
            if (!config.isClientSilenced()) active.add(config.getClientAudioSessionId());
        }
        // Shell's public audio API may anonymize package names but preserves session ids.
        // Attribute new sessions once through DUMP, then use cheap Binder reads for start/stop.
        if (!active.equals(lastSessions) || (!active.isEmpty() && Collections.disjoint(active, doubaoSessions)
                && SystemClock.uptimeMillis() - attributedAt > 1000)) {
            doubaoSessions = active.isEmpty() ? new HashSet<>() : RecordingSnapshot.sessions(audioDump());
            lastSessions = active; attributedAt = SystemClock.uptimeMillis();
        }
        for (int session : active) if (doubaoSessions.contains(session)) return true;
        return false;
    }
    private String audioDump() throws Exception {
        java.lang.Process process = new ProcessBuilder("/system/bin/dumpsys", "-t", "1", "audio")
            .redirectErrorStream(true).start();
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream input = process.getInputStream()) {
                byte[] block = new byte[8192]; int count;
                while ((count = input.read(block)) != -1) {
                    if (bytes.size() + count > 1024 * 1024) throw new IOException("Audio dump too large");
                    bytes.write(block, 0, count);
                }
            }
            if (!process.waitFor(500, TimeUnit.MILLISECONDS) || process.exitValue() != 0)
                throw new IOException("Audio dump failed");
            return bytes.toString("UTF-8");
        } finally { process.destroy(); }
    }
}
