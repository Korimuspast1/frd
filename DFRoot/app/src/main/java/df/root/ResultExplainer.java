package df.root;

import android.content.Context;

/**
 * Turns the exit code and the raw exploit log into something a human can act on.
 * The strings the native side prints are stable enough to match on.
 */
public final class ResultExplainer {

    private static final String NOT_VULNERABLE = "DEVICE NOT VULNERABLE";
    private static final String VERIFY_FAILED  = "verification failed";

    private ResultExplainer() {
    }

    /** True when the exploit itself reported that the kernel cannot be patched. */
    static boolean isNotVulnerable(String log) {
        return log != null && (log.contains(NOT_VULNERABLE) || log.contains(VERIFY_FAILED));
    }

    static String title(Context ctx, int rc, String log) {
        if (rc == 0) return ctx.getString(R.string.result_success);
        if (isNotVulnerable(log)) return ctx.getString(R.string.result_not_vulnerable);
        if (rc == 1) return ctx.getString(R.string.result_ksud_exit);
        if (rc == 2) return ctx.getString(R.string.result_check_logs);
        return ctx.getString(R.string.result_patch_failed);
    }

    /** Detailed hint that gets appended to the log; never empty for a failed run. */
    static String hint(Context ctx, int rc, String log) {
        if (rc == 0) return ctx.getString(R.string.hint_success);
        if (isNotVulnerable(log)) return ctx.getString(R.string.hint_not_vulnerable);
        if (rc == 1) return ctx.getString(R.string.hint_ksud);
        if (rc == 2) return ctx.getString(R.string.hint_generic);
        return ctx.getString(R.string.hint_patch_failed);
    }
}
