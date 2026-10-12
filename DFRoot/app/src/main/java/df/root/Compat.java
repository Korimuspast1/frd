package df.root;

import android.content.Context;

import java.util.ArrayList;
import java.util.List;

/**
 * Pre-run compatibility hints based on public information from the project FAQ.
 * These are heuristics for user messaging only — they never block a run, because
 * only the exploit itself can prove whether a device is vulnerable.
 */
public final class Compat {

    private Compat() {
    }

    static List<String> warnings(Context ctx) {
        List<String> out = new ArrayList<>();

        String kv = DeviceInfo.kernelVersion();
        if (DeviceInfo.matchingKmis().isEmpty()) {
            out.add(ctx.getString(R.string.warn_no_ko, kv));
        }
        // Documented in the project FAQ: kernel 6.1 often carries an accidental
        // mitigation, so patching fails on many 6.1 devices.
        if (kv.equals("6.1")) {
            out.add(ctx.getString(R.string.warn_kernel_61));
        }
        if (!DeviceInfo.is64Bit()) {
            out.add(ctx.getString(R.string.warn_32bit));
        }
        return out;
    }
}
