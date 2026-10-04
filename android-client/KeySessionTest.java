package local.qaa.airtype;

public class KeySessionTest {
    static int checks;
    static void check(boolean value, String name) {
        checks++;
        if (!value) throw new AssertionError(name);
    }
    public static void main(String[] args) {
        KeySession s = new KeySession(1000);
        check(s.down(0, 1) == KeySession.Command.START, "first down starts immediately");
        check(s.down(300, 1) == KeySession.Command.NONE, "key repeat does not click again");
        check(s.up(200, false) == KeySession.Command.NONE && s.handsFree, "short release before ready is latched");
        check(s.ready() == KeySession.Command.NONE && s.phase == KeySession.Phase.RECORDING, "slow startup keeps short tap recording");
        check(s.down(2500, 1) == KeySession.Command.STOP, "next press ends hands-free");
        s.up(2700, false); s.reset();
        s.down(3000, 1);
        check(s.up(4000, false) == KeySession.Command.NONE && s.stopRequested, "boundary long release is queued");
        check(s.ready() == KeySession.Command.STOP, "queued long release ends after startup");
        s.reset(); s.down(5000, 1); s.ready();
        check(s.up(6200, false) == KeySession.Command.STOP, "long hold ends on release");
        s.reset(); s.down(7000, 1); s.up(7100, false);
        s.down(7200, 1);
        check(s.ready() == KeySession.Command.STOP, "second tap during startup cancels after ready");
        s.up(7300, false); s.reset(); s.down(8000, 1); s.ready();
        check(s.up(8050, true) == KeySession.Command.STOP && !s.handsFree, "canceled or disconnected key never latches");
        s.reset(); s.down(9000, 1); s.reset();
        check(s.down(9500, 1) == KeySession.Command.NONE, "failed startup ignores a still-held key");
        s.up(9600, false);
        check(s.down(10000, 1) == KeySession.Command.START, "fresh press recovers after failure");
        s.up(11600, false); s.ready(); s.reset(15000);
        check(s.down(12400, 1) == KeySession.Command.NONE, "tap queued during a stalled stop cannot restart after timeout");
        check(s.up(12460, false) == KeySession.Command.NONE && s.phase == KeySession.Phase.IDLE, "queued release cannot latch hands-free recording");
        check(s.down(15100, 1) == KeySession.Command.START, "new physical press after timeout still starts");
        check(s.up(12460, false) == KeySession.Command.NONE && s.pressed, "older release cannot release a newer physical press");
        s.ready();
        check(s.up(16400, false) == KeySession.Command.STOP, "fresh long hold still stops on release");
        s.reset(17000);
        check(s.down(16900, 1) == KeySession.Command.NONE, "queued tap after a successful stop is also ignored");
        check(s.down(17100, 1) == KeySession.Command.START, "fresh press after a successful stop starts normally");
        System.out.println("KeySession: " + checks + " checks passed");
    }
}
