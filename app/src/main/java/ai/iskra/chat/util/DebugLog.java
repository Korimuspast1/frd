package ai.iskra.chat.util;

/**
 * Compile-time-compatible diagnostics facade.
 *
 * The former in-app developer console and its memory buffer have been removed. Calls remain
 * intentionally inert so release builds neither retain a hidden console nor collect a private
 * transcript of user activity.
 */
public final class DebugLog {
    private DebugLog() {}

    public static void log(String category, String message) {
        // Intentionally disabled in the consumer application.
    }

    public static void error(String category, Throwable error) {
        // Intentionally disabled in the consumer application.
    }
}
