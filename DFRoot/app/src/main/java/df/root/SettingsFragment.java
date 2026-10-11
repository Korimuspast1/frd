package df.root;

import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.preference.Preference;
import android.preference.PreferenceFragment;
import android.preference.SwitchPreference;

public class SettingsFragment extends PreferenceFragment {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        addPreferencesFromResource(R.xml.preferences);

        Context ctx = getActivity();
        SharedPreferences dePrefs = ctx.createDeviceProtectedStorageContext()
                .getSharedPreferences(ExploitRunner.PREFS_NAME, Context.MODE_PRIVATE);

        ComponentName bootReceiver = new ComponentName(ctx, BootReceiver.class);
        SwitchPreference bootPref = (SwitchPreference) findPreference("boot_start");
        bootPref.setPersistent(false);
        int state = ctx.getPackageManager().getComponentEnabledSetting(bootReceiver);
        bootPref.setChecked(state == PackageManager.COMPONENT_ENABLED_STATE_ENABLED);
        bootPref.setOnPreferenceChangeListener((pref, value) -> {
            ctx.getPackageManager().setComponentEnabledSetting(bootReceiver,
                    (Boolean) value ? PackageManager.COMPONENT_ENABLED_STATE_ENABLED
                                    : PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
                    PackageManager.DONT_KILL_APP);
            return true;
        });

        bindDeSwitch(dePrefs, "soft_reboot");
        bindDeSwitch(dePrefs, "disable_modules");
        bindDeSwitch(dePrefs, "auto_save_log");

        Preference versionPref = findPreference("version");
        try {
            versionPref.setSummary(ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName);
        } catch (PackageManager.NameNotFoundException ignored) {
            versionPref.setSummary("?");
        }
    }

    /** These switches are read by the native bootstrap, so they live in DE storage. */
    private void bindDeSwitch(SharedPreferences dePrefs, String key) {
        SwitchPreference pref = (SwitchPreference) findPreference(key);
        pref.setPersistent(false);
        pref.setChecked(dePrefs.getBoolean(key, false));
        pref.setOnPreferenceChangeListener((p, value) -> {
            dePrefs.edit().putBoolean(key, (Boolean) value).apply();
            return true;
        });
    }
}
