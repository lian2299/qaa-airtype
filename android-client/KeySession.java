package local.qaa.airtype;

/** Timing and queued releases are independent of page/IME startup latency. */
final class KeySession {
    enum Phase { IDLE, STARTING, RECORDING, STOPPING }
    enum Command { NONE, START, STOP }
    Phase phase = Phase.IDLE;
    boolean pressed, handsFree, stopRequested;
    long downAt;
    long ignoreThrough = -1;
    int deviceId = -1;
    final long tapMillis;

    KeySession(long tapMillis) { this.tapMillis = tapMillis; }
    Command down(long time, int device) {
        if (time <= ignoreThrough) return Command.NONE;
        if (pressed) return Command.NONE;
        pressed = true;
        downAt = time;
        deviceId = device;
        if (phase == Phase.IDLE) {
            phase = Phase.STARTING;
            handsFree = false;
            stopRequested = false;
            return Command.START;
        }
        if (phase == Phase.STARTING) { stopRequested = true; return Command.NONE; }
        if (phase == Phase.RECORDING) {
            phase = Phase.STOPPING;
            return Command.STOP;
        }
        return Command.NONE;
    }
    Command up(long time, boolean canceled) {
        if (!pressed || time < downAt) return Command.NONE;
        pressed = false;
        if (time <= ignoreThrough) return Command.NONE;
        if (phase != Phase.STARTING && phase != Phase.RECORDING) return Command.NONE;
        if (!canceled && time - downAt < tapMillis && !stopRequested) {
            handsFree = true;
            return Command.NONE;
        }
        stopRequested = true;
        if (phase == Phase.RECORDING) {
            phase = Phase.STOPPING;
            return Command.STOP;
        }
        return Command.NONE;
    }
    Command ready() {
        if (phase != Phase.STARTING) return Command.NONE;
        if (stopRequested) { phase = Phase.STOPPING; return Command.STOP; }
        phase = Phase.RECORDING;
        return Command.NONE;
    }
    void reset() {
        phase = Phase.IDLE;
        handsFree = false;
        stopRequested = false;
        // Preserve a still-held key so repeats cannot restart a failed session.
    }
    void reset(long time) {
        reset();
        // A delayed tap from the session that just ended must not reopen the IME.
        ignoreThrough = Math.max(ignoreThrough, time);
    }
}
