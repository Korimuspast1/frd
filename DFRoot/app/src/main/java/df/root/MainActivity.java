package df.root;

import android.Manifest;
import android.app.ActionBar;
import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

public class MainActivity extends Activity implements IReporter {

    private static final String TAG = "dfroot";
    private static final String PREF_AUTO_SAVE_LOG = "auto_save_log";
    private static final String PREF_RETRY_COUNT = "retry_count";
    private static final String PREF_LAST_NOT_VULNERABLE = "last_not_vulnerable";
    private static final int MAX_LOG_CHARS = 256 * 1024;
    private static final long RUN_TIMEOUT_MS = 10 * 60 * 1000L;
    private static final long RETRY_DELAY_MS = 4000L;
    private static final int RESULT_NOTIFICATION_ID = 1001;
    private static final int REQ_POST_NOTIFICATIONS = 1;

    private Button btnRun;
    private Button btnSaveLog;
    private Button btnCopyLog;
    private ProgressBar progress;
    private TextView statusView;
    private ScrollView outputScroll;
    private TextView outputView;
    private Spinner spinnerSuManager;
    private Context mDeCtx;
    private final Handler mMain = new Handler(Looper.getMainLooper());
    private final Executor mExec = Executors.newSingleThreadExecutor();
    private int mValidSuManagerPos = 0;
    private final StringBuilder mLog = new StringBuilder();

    @Override
    public void report(String msg) {
        Log.i(TAG, msg.trim());
        mLog.append(msg);
        if (mLog.length() > MAX_LOG_CHARS) {
            mLog.delete(0, mLog.length() - MAX_LOG_CHARS);
        }
        mMain.post(() -> {
            outputView.append(msg);
            outputScroll.post(() -> outputScroll.fullScroll(View.FOCUS_DOWN));
        });
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mDeCtx = createDeviceProtectedStorageContext();
        setContentView(R.layout.activity_main);

        ActionBar ab = getActionBar();
        if (ab != null) {
            ab.setSubtitle(getString(R.string.subtitle, appVersion()));
        }

        btnRun = findViewById(R.id.btnRun);
        btnSaveLog = findViewById(R.id.btnSaveLog);
        btnCopyLog = findViewById(R.id.btnCopyLog);
        progress = findViewById(R.id.progress);
        statusView = findViewById(R.id.statusView);
        outputScroll = findViewById(R.id.outputScroll);
        outputView = findViewById(R.id.outputView);
        spinnerSuManager = findViewById(R.id.spinnerSuManager);

        PackageManager pm = getPackageManager();
        List<SuManagerEntry> entries = new ArrayList<>();
        for (ApplicationInfo ai : pm.getInstalledApplications(0)) {
            if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0) continue;
            if (!ExploitRunner.hasKsud(ai)) continue;
            entries.add(new SuManagerEntry(ai.packageName, pm.getApplicationLabel(ai), pm.getApplicationIcon(ai)));
        }
        entries.sort((a, b) -> a.label.toString().compareToIgnoreCase(b.label.toString()));
        entries.add(0, new SuManagerEntry(null, getString(R.string.select_su_manager), null));

        spinnerSuManager.setAdapter(new SuManagerAdapter(this, entries));

        SharedPreferences prefs = mDeCtx.getSharedPreferences(ExploitRunner.PREFS_NAME, Context.MODE_PRIVATE);
        String saved = prefs.getString(ExploitRunner.PREF_SU_MANAGER, null);
        boolean savedFound = false;
        for (int i = 1; i < entries.size(); i++) {
            if (entries.get(i).packageName.equals(saved)) {
                spinnerSuManager.setSelection(i);
                mValidSuManagerPos = i;
                savedFound = true;
                break;
            }
        }
        if (!savedFound && saved != null) { // Saved manager was uninstalled
            prefs.edit().remove(ExploitRunner.PREF_SU_MANAGER).apply();
        }

        spinnerSuManager.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int pos, long id) {
                SuManagerEntry e = entries.get(pos);
                if (e.packageName == null) return;
                mValidSuManagerPos = pos;
                prefs.edit().putString(ExploitRunner.PREF_SU_MANAGER, e.packageName).apply();
                updateRunButton();
            }
            @Override
            public void onNothingSelected(AdapterView<?> parent) {}
        });

        updateRunButton();
        updateStatus();

        btnRun.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= 33
                    && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                       != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},
                        REQ_POST_NOTIFICATIONS);
            }
            btnRun.setEnabled(false);
            btnSaveLog.setEnabled(false);
            btnCopyLog.setEnabled(false);
            progress.setVisibility(View.VISIBLE);
            outputView.setText("");
            mLog.setLength(0);
            mExec.execute(this::runExploit);
        });

        btnSaveLog.setOnClickListener(v -> saveLog());
        btnCopyLog.setOnClickListener(v -> copyLog());

        // Print device diagnostics right away, before anything is launched.
        mExec.execute(() -> {
            DeviceInfo.report(this, this);
            List<String> warnings = Compat.warnings(this);
            if (!warnings.isEmpty()) {
                report("\n" + getString(R.string.compat_warnings) + "\n");
                for (String w : warnings) report("* " + w + "\n");
            }
            if (prefs.getBoolean(PREF_LAST_NOT_VULNERABLE, false)) {
                report("\n" + getString(R.string.compat_last_not_vulnerable) + "\n");
            }
            report("\n");
        });
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.main_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.action_settings) {
            startActivity(new Intent(this, SettingsActivity.class));
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateStatus();
    }

    private String appVersion() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (PackageManager.NameNotFoundException e) {
            return "?";
        }
    }

    private void updateRunButton() {
        btnRun.setEnabled(mValidSuManagerPos >= 1 && !DeviceInfo.rootActive());
    }

    private void updateStatus() {
        boolean active = DeviceInfo.rootActive();
        statusView.setText(active ? R.string.status_active : R.string.status_inactive);
    }

    private int retryCount() {
        try {
            return Integer.parseInt(mDeCtx.getSharedPreferences(ExploitRunner.PREFS_NAME,
                    Context.MODE_PRIVATE).getString(PREF_RETRY_COUNT, "0"));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    /** Posts the run result as a notification. Skipped silently without permission. */
    private void notifyResult(String title, String text) {
        try {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;
            if (Build.VERSION.SDK_INT >= 33
                    && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                       != PackageManager.PERMISSION_GRANTED) {
                return;
            }
            final String channelId = "dfroot_result";
            if (nm.getNotificationChannel(channelId) == null) {
                nm.createNotificationChannel(new NotificationChannel(channelId,
                        getString(R.string.notif_channel), NotificationManager.IMPORTANCE_DEFAULT));
            }
            Notification n = new Notification.Builder(this, channelId)
                    .setSmallIcon(R.drawable.ic_launcher_monochrome)
                    .setContentTitle(title)
                    .setContentText(text)
                    .setStyle(new Notification.BigTextStyle().bigText(text))
                    .setAutoCancel(true)
                    .build();
            nm.notify(RESULT_NOTIFICATION_ID, n);
        } catch (Exception e) {
            Log.w(TAG, "notification failed", e);
        }
    }

    private boolean autoSaveEnabled() {
        return mDeCtx.getSharedPreferences(ExploitRunner.PREFS_NAME, Context.MODE_PRIVATE)
                .getBoolean(PREF_AUTO_SAVE_LOG, false);
    }

    private void saveLog() {
        final String text = mLog.toString();
        if (text.trim().isEmpty()) {
            Toast.makeText(this, R.string.log_empty, Toast.LENGTH_SHORT).show();
            return;
        }
        final String name = LogSaver.fileName();
        mExec.execute(() -> {
            boolean ok = LogSaver.save(getApplicationContext(), name, text);
            mMain.post(() -> Toast.makeText(this,
                    ok ? getString(R.string.log_saved, name) : getString(R.string.log_save_failed),
                    Toast.LENGTH_LONG).show());
        });
    }

    private void copyLog() {
        final String text = mLog.toString();
        if (text.trim().isEmpty()) {
            Toast.makeText(this, R.string.log_empty, Toast.LENGTH_SHORT).show();
            return;
        }
        boolean ok = LogSaver.copy(this, text);
        Toast.makeText(this, ok ? R.string.log_copied : R.string.log_copy_failed, Toast.LENGTH_SHORT).show();
    }

    private void runExploit() {
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        PowerManager.WakeLock wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "dfroot:run");
        wl.acquire(RUN_TIMEOUT_MS); // keep the CPU awake while the exploit runs
        try {
            final int attempts = 1 + Math.max(0, Math.min(2, retryCount()));
            int rc = -1;
            for (int i = 1; i <= attempts; i++) {
                if (i > 1) {
                    final String attemptLine = getString(R.string.retry_attempt, i, attempts);
                    report("\n" + attemptLine + "\n");
                    mMain.post(() -> Toast.makeText(this, attemptLine, Toast.LENGTH_SHORT).show());
                    try {
                        Thread.sleep(RETRY_DELAY_MS);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
                rc = ExploitRunner.run(mDeCtx, this);
                if (rc == 0) break;
                if (ResultExplainer.isNotVulnerable(mLog.toString())) {
                    report("\n" + getString(R.string.retry_skipped) + "\n");
                    break; // retrying a device that cannot be patched is pointless
                }
            }

            final String log = mLog.toString();
            final String title = ResultExplainer.title(this, rc, log);
            final String hint = ResultExplainer.hint(this, rc, log);
            report("\n" + hint + "\n");

            mDeCtx.getSharedPreferences(ExploitRunner.PREFS_NAME, Context.MODE_PRIVATE).edit()
                    .putBoolean(PREF_LAST_NOT_VULNERABLE, rc != 0 && ResultExplainer.isNotVulnerable(log))
                    .apply();

            mMain.post(() -> Toast.makeText(this, title, Toast.LENGTH_LONG).show());
            notifyResult(title, hint);

            if (autoSaveEnabled()) {
                final String text = mLog.toString();
                final String name = LogSaver.fileName();
                mExec.execute(() -> LogSaver.save(getApplicationContext(), name, text));
            }
        } catch (Exception e) {
            Log.e(TAG, "exploit exception", e);
            report("\n" + getString(R.string.err_generic, e) + "\n");
        } finally {
            mMain.post(() -> {
                progress.setVisibility(View.GONE);
                btnSaveLog.setEnabled(true);
                btnCopyLog.setEnabled(true);
                updateRunButton();
                updateStatus();
            });
            if (wl.isHeld()) wl.release();
        }
    }

    private static class SuManagerEntry {
        final String packageName;
        final CharSequence label;
        final Drawable icon;

        SuManagerEntry(String pkg, CharSequence label, Drawable icon) {
            this.packageName = pkg;
            this.label = label;
            this.icon = icon;
        }
    }

    private static class SuManagerAdapter extends ArrayAdapter<SuManagerEntry> {
        SuManagerAdapter(Context ctx, List<SuManagerEntry> items) {
            super(ctx, R.layout.item_su_manager, items);
        }

        @Override
        public View getView(int pos, View v, ViewGroup parent) {
            if (v == null || v.getTag() != Boolean.FALSE)
                v = LayoutInflater.from(getContext()).inflate(R.layout.item_su_manager_closed, parent, false);
            v.setTag(Boolean.FALSE);
            return bindClosedView(pos, v);
        }

        @Override
        public View getDropDownView(int pos, View v, ViewGroup parent) {
            if (v == null || v.getTag() != Boolean.TRUE)
                v = LayoutInflater.from(getContext()).inflate(R.layout.item_su_manager, parent, false);
            v.setTag(Boolean.TRUE);
            return bindView(pos, v);
        }

        @Override
        public boolean isEnabled(int pos) {
            return getItem(pos).packageName != null;
        }

        private View bindClosedView(int pos, View v) {
            SuManagerEntry e = getItem(pos);
            ImageView icon = v.findViewById(R.id.iconApp);
            TextView label = v.findViewById(R.id.labelApp);
            if (e.packageName == null) {
                icon.setVisibility(View.GONE);
                label.setVisibility(View.VISIBLE);
                label.setText(e.label);
            } else {
                icon.setVisibility(View.VISIBLE);
                label.setVisibility(View.GONE);
                icon.setImageDrawable(e.icon);
            }
            return v;
        }

        private View bindView(int pos, View v) {
            SuManagerEntry e = getItem(pos);
            ((ImageView) v.findViewById(R.id.iconApp)).setImageDrawable(e.icon);
            ((TextView)  v.findViewById(R.id.labelApp)).setText(e.label);
            return v;
        }
    }
}
