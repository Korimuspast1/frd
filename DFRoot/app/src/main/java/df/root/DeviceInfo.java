package df.root;

import android.content.Context;
import android.os.Build;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Read-only device diagnostics. Everything here only reads information the app is
 * already allowed to read — nothing is executed and nothing is modified.
 */
public final class DeviceInfo {

    /** Must stay in sync with KO_FILES in app/src/main/jni/CMakeLists.txt. */
    private static final String[] BUNDLED_KMIS = {
            "android12-5.10",
            "android13-5.10",
            "android13-5.15",
            "android14-5.15",
            "android14-6.1",
            "android15-6.6",
            "android16-6.12",
            "android17-6.18",
    };

    private static final String FLAG_ROOT_ACTIVE = "/dev/df";

    private DeviceInfo() {
    }

    static String kernelRelease() {
        String v = System.getProperty("os.version");
        return (v == null || v.isEmpty()) ? "unknown" : v;
    }

    /** "6.1.75-android14-11-g..." -> "6.1" */
    static String kernelVersion() {
        String r = kernelRelease();
        StringBuilder sb = new StringBuilder();
        int dots = 0;
        for (int i = 0; i < r.length(); i++) {
            char c = r.charAt(i);
            if (c == '.') {
                dots++;
                if (dots == 2) break;
            }
            sb.append(c);
        }
        return sb.length() > 0 ? sb.toString() : "unknown";
    }

    static String abi() {
        String[] abis = Build.SUPPORTED_ABIS;
        return (abis != null && abis.length > 0) ? abis[0] : "unknown";
    }

    static boolean is64Bit() {
        return abi().contains("64");
    }

    static String selinux() {
        String[] paths = {"/sys/fs/selinux/enforce", "/selinux/enforce"};
        for (String p : paths) {
            try (BufferedReader r = new BufferedReader(new FileReader(p))) {
                String v = r.readLine();
                if (v == null) continue;
                v = v.trim();
                if (v.equals("1")) return "enforcing";
                if (v.equals("0")) return "permissive";
                if (!v.isEmpty()) return v;
            } catch (IOException | RuntimeException ignored) {
                /* not readable on this device */
            }
        }
        return "unknown";
    }

    static boolean rootActive() {
        try {
            return new File(FLAG_ROOT_ACTIVE).exists();
        } catch (SecurityException ignored) {
            return false;
        }
    }

    /** Bundled kernel modules whose version matches the running kernel. */
    static List<String> matchingKmis() {
        List<String> out = new ArrayList<>();
        String v = kernelVersion();
        for (String kmi : BUNDLED_KMIS) {
            if (kmi.endsWith("-" + v)) out.add(kmi);
        }
        return out;
    }

    /** Prints the whole diagnostics block into the on-screen log. */
    public static void report(Context ctx, IReporter reporter) {
        reporter.report(ctx.getString(R.string.di_header) + "\n");
        reporter.report("* " + ctx.getString(R.string.di_manufacturer) + ": " + Build.MANUFACTURER + "\n");
        reporter.report("* " + ctx.getString(R.string.di_model) + ": " + Build.MODEL + "\n");
        reporter.report("* " + ctx.getString(R.string.di_android) + ": " + Build.VERSION.RELEASE
                + " (API " + Build.VERSION.SDK_INT + ")\n");
        reporter.report("* " + ctx.getString(R.string.di_patch) + ": " + Build.VERSION.SECURITY_PATCH + "\n");
        reporter.report("* " + ctx.getString(R.string.di_kernel) + ": " + kernelRelease() + "\n");
        reporter.report("* " + ctx.getString(R.string.di_abi) + ": " + abi() + "\n");
        reporter.report("* " + ctx.getString(R.string.di_selinux) + ": " + selinux() + "\n");
        reporter.report("* " + ctx.getString(R.string.di_root) + ": "
                + (rootActive() ? ctx.getString(R.string.di_active)
                                : ctx.getString(R.string.di_inactive)) + "\n");

        String kv = kernelVersion();
        List<String> matches = matchingKmis();
        if (matches.isEmpty()) {
            reporter.report("* " + ctx.getString(R.string.warn_no_ko, kv) + "\n");
        } else {
            StringBuilder sb = new StringBuilder();
            for (String m : matches) {
                if (sb.length() > 0) sb.append(", ");
                sb.append(m);
            }
            reporter.report("* " + ctx.getString(R.string.di_kmi) + ": " + sb + "\n");
        }
        if (!is64Bit()) {
            reporter.report("* " + ctx.getString(R.string.warn_32bit) + "\n");
        }
        reporter.report("\n");
    }
}
