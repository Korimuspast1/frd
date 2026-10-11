package df.root;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Log;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Saves / copies the run log so it can be attached to a bug report. */
public final class LogSaver {

    private static final String TAG = "dfroot";

    private LogSaver() {
    }

    static String fileName() {
        String ts = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
        return "dfroot-log-" + ts + ".txt";
    }

    /**
     * Writes the log into Downloads through MediaStore. Works on API 29+ without
     * any storage permission and without adding a dependency on androidx.
     */
    static boolean save(Context ctx, String name, String text) {
        ContentValues cv = new ContentValues();
        cv.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        cv.put(MediaStore.MediaColumns.MIME_TYPE, "text/plain");
        cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
        try {
            Uri uri = ctx.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
            if (uri == null) return false;
            try (OutputStream os = ctx.getContentResolver().openOutputStream(uri)) {
                if (os == null) return false;
                os.write(text.getBytes(StandardCharsets.UTF_8));
                return true;
            }
        } catch (Exception e) {
            Log.e(TAG, "save log failed", e);
            return false;
        }
    }

    static boolean copy(Context ctx, String text) {
        try {
            ClipboardManager cm = (ClipboardManager) ctx.getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm == null) return false;
            cm.setPrimaryClip(ClipData.newPlainText("dfroot-log", text));
            return true;
        } catch (Exception e) {
            Log.e(TAG, "copy log failed", e);
            return false;
        }
    }
}
