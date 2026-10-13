package ai.iskra.chat.util;

import android.os.Handler;
import android.os.Looper;

import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.regex.Pattern;

/** In-memory application trace used by the optional on-screen debug console. */
public final class DebugLog {
    public interface Listener {
        void onDebugLogChanged();
    }

    private static final int MAX_LINES = 600;
    private static final int MAX_MESSAGE = 1_500;
    private static final Object LOCK = new Object();
    private static final ArrayDeque<String> LINES = new ArrayDeque<>();
    private static final CopyOnWriteArrayList<Listener> LISTENERS = new CopyOnWriteArrayList<>();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final Pattern BEARER = Pattern.compile("(?i)Bearer\\s+[A-Za-z0-9._~+\\-/]+=*");
    private static final Pattern SECRET_FIELD = Pattern.compile(
            "(?i)(api[_ -]?key|authorization|token|password|secret)(\\s*[=:]\\s*)([^\\s&,;]+)");
    private static final Pattern OPENAI_KEY = Pattern.compile("\\b(sk|pk)-[A-Za-z0-9_-]{8,}\\b");

    private static volatile boolean enabled;

    private DebugLog() {}

    public static void initialize(boolean value) {
        enabled = value;
        if (value) append("SYSTEM", "Debug mode restored; in-memory trace started");
    }

    public static void setEnabled(boolean value) {
        if (value == enabled) return;
        enabled = value;
        if (value) {
            append("SYSTEM", "Debug mode enabled");
        } else {
            // Keep the existing buffer available if debug is enabled again in this process.
            notifyListeners();
        }
    }

    public static boolean isEnabled() {
        return enabled;
    }

    public static void log(String category, String message) {
        if (!enabled) return;
        append(category, message);
    }

    public static void error(String category, Throwable error) {
        if (!enabled) return;
        String detail = error == null ? "unknown error"
                : error.getClass().getSimpleName() + ": " + String.valueOf(error.getMessage());
        append(category, "ERROR " + detail);
    }

    public static void register(Listener listener) {
        if (listener != null && !LISTENERS.contains(listener)) LISTENERS.add(listener);
    }

    public static void unregister(Listener listener) {
        LISTENERS.remove(listener);
    }

    public static void clear() {
        synchronized (LOCK) {
            LINES.clear();
        }
        if (enabled) append("SYSTEM", "Console cleared");
        else notifyListeners();
    }

    public static int size() {
        synchronized (LOCK) {
            return LINES.size();
        }
    }

    public static String snapshot() {
        List<String> copy;
        synchronized (LOCK) {
            copy = new ArrayList<>(LINES);
        }
        StringBuilder output = new StringBuilder();
        for (String line : copy) {
            if (output.length() > 0) output.append('\n');
            output.append(line);
        }
        return output.toString();
    }

    private static void append(String category, String rawMessage) {
        String timestamp = new SimpleDateFormat("HH:mm:ss.SSS", Locale.US).format(new Date());
        String thread = Thread.currentThread().getName();
        String cleanCategory = category == null ? "APP" : category.trim().toUpperCase(Locale.US);
        String message = redact(rawMessage == null ? "null" : rawMessage);
        if (message.length() > MAX_MESSAGE) message = message.substring(0, MAX_MESSAGE) + "…";
        String[] parts = message.replace("\r", "").split("\n", -1);
        synchronized (LOCK) {
            for (int i = 0; i < parts.length; i++) {
                String prefix = i == 0
                        ? timestamp + " [" + cleanCategory + "/" + thread + "] "
                        : timestamp + " [" + cleanCategory + "] ↳ ";
                LINES.addLast(prefix + parts[i]);
                while (LINES.size() > MAX_LINES) LINES.removeFirst();
            }
        }
        notifyListeners();
    }

    private static String redact(String value) {
        String redacted = BEARER.matcher(value).replaceAll("Bearer <redacted>");
        redacted = SECRET_FIELD.matcher(redacted).replaceAll("$1$2<redacted>");
        return OPENAI_KEY.matcher(redacted).replaceAll("$1-<redacted>");
    }

    private static void notifyListeners() {
        MAIN.post(() -> {
            for (Listener listener : LISTENERS) listener.onDebugLogChanged();
        });
    }
}
