package ai.iskra.chat.security;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;
import android.os.Debug;

import ai.iskra.chat.BuildConfig;
import ai.iskra.chat.util.DebugLog;

import java.io.File;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Release hardening. Android already verifies APK signatures at installation; this additionally
 * pins the expected signer and rejects an obviously repacked/debuggable package at runtime.
 */
public final class IntegrityGuard {
    private static final String EXPECTED_PACKAGE = "app.kvsai.chat";
    private static final String EXPECTED_SIGNER_SHA256 =
            "A40DA80A59D170CAA950CF15C18C454D47A39B26989D8B640ECD745BA71BF5DC";

    private IntegrityGuard() {}

    public static void verifyOrThrow(Context context) {
        if (BuildConfig.DEBUG) return;
        try {
            if (!EXPECTED_PACKAGE.equals(context.getPackageName())) fail("package identity");
            ApplicationInfo app = context.getApplicationInfo();
            if ((app.flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) fail("debuggable release");
            if (Debug.isDebuggerConnected() || Debug.waitingForDebugger()) fail("debugger attached");
            if (!hasExpectedSigner(context)) fail("signing certificate");
            verifyApkStructure(app.sourceDir);
        } catch (SecurityException error) {
            throw error;
        } catch (Throwable error) {
            throw new SecurityException("kvsai integrity verification failed", error);
        }
    }

    @SuppressWarnings("deprecation")
    private static boolean hasExpectedSigner(Context context) throws Exception {
        PackageManager manager = context.getPackageManager();
        Signature[] signatures;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            PackageInfo info = manager.getPackageInfo(context.getPackageName(),
                    PackageManager.GET_SIGNING_CERTIFICATES);
            if (info.signingInfo == null) return false;
            signatures = info.signingInfo.getApkContentsSigners();
        } else {
            PackageInfo info = manager.getPackageInfo(context.getPackageName(),
                    PackageManager.GET_SIGNATURES);
            signatures = info.signatures;
        }
        if (signatures == null || signatures.length == 0) return false;
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (Signature signature : signatures) {
            String fingerprint = hex(digest.digest(signature.toByteArray()));
            if (EXPECTED_SIGNER_SHA256.equals(fingerprint)) return true;
        }
        return false;
    }

    private static void verifyApkStructure(String sourcePath) throws Exception {
        if (sourcePath == null) fail("missing APK path");
        File apk = new File(sourcePath);
        // Do not use an arbitrary minimum APK size here: R8/resource shrinking can legitimately
        // produce a very small release. Required ZIP entries below are the structural check.
        if (!apk.isFile() || !apk.canRead()) fail("APK container");
        try (ZipFile zip = new ZipFile(apk)) {
            requireEntry(zip, "AndroidManifest.xml", 256L);
            requireEntry(zip, "classes.dex", 4_096L);
            requireEntry(zip, "resources.arsc", 1_024L);
        }
    }

    private static void requireEntry(ZipFile zip, String name, long minimumBytes) {
        ZipEntry entry = zip.getEntry(name);
        if (entry == null || entry.getSize() < minimumBytes || entry.getCrc() == 0L) {
            fail("APK entry " + name);
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder value = new StringBuilder(bytes.length * 2);
        for (byte item : bytes) value.append(String.format(Locale.US, "%02X", item & 0xFF));
        return value.toString();
    }

    private static void fail(String reason) {
        DebugLog.log("SECURITY", "Integrity rejection: " + reason);
        throw new SecurityException("kvsai integrity verification failed");
    }
}
