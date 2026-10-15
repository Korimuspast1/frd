package ai.iskra.chat.data;

import android.content.Context;
import android.content.SharedPreferences;

import ai.iskra.chat.security.SecureKeyStore;

public final class AppSettings {
    private static final String PREFS = "app_settings";
    private static final String DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1";
    private static final String DEFAULT_MODEL = "openrouter/free";

    private final SharedPreferences preferences;
    private final SecureKeyStore secureKeyStore;

    public AppSettings(Context context) {
        Context app = context.getApplicationContext();
        preferences = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        secureKeyStore = new SecureKeyStore(app);
    }

    public boolean isAiEnabled() {
        return preferences.getBoolean("ai_enabled", false);
    }

    public boolean isWebEnabled() {
        return preferences.getBoolean("web_enabled", true);
    }

    public boolean isDebugEnabled() {
        return preferences.getBoolean("debug_enabled", false);
    }

    public boolean isVoiceEnabled() {
        return preferences.getBoolean("voice_enabled", false);
    }

    public void setVoiceEnabled(boolean enabled) {
        preferences.edit().putBoolean("voice_enabled", enabled).apply();
    }

    public boolean isReasoningEnabled() {
        return preferences.getBoolean("reasoning_enabled", false);
    }

    public String getEndpoint() {
        return preferences.getString("endpoint", DEFAULT_ENDPOINT);
    }

    public String getModel() {
        return preferences.getString("model", DEFAULT_MODEL);
    }

    public String getApiKey() {
        return secureKeyStore.getKey();
    }

    public boolean hasApiKey() {
        return secureKeyStore.hasKey();
    }

    public void save(boolean aiEnabled, boolean webEnabled, boolean debugEnabled,
                     boolean reasoningEnabled, String endpoint, String model,
                     String newApiKey) throws Exception {
        String cleanEndpoint = endpoint == null ? "" : endpoint.trim();
        String cleanModel = model == null ? "" : model.trim();
        preferences.edit()
                .putBoolean("ai_enabled", aiEnabled)
                .putBoolean("web_enabled", webEnabled)
                .putBoolean("debug_enabled", debugEnabled)
                .putBoolean("reasoning_enabled", reasoningEnabled)
                .putString("endpoint", cleanEndpoint.isEmpty() ? DEFAULT_ENDPOINT : cleanEndpoint)
                .putString("model", cleanModel.isEmpty() ? DEFAULT_MODEL : cleanModel)
                .apply();
        if (newApiKey != null && !newApiKey.trim().isEmpty()) {
            secureKeyStore.saveKey(newApiKey);
        }
    }

    public void clearApiKey() {
        secureKeyStore.clearKey();
    }

    public Snapshot snapshot() {
        return new Snapshot(
                isAiEnabled(), isWebEnabled(), isReasoningEnabled(),
                getEndpoint(), getModel(), getApiKey()
        );
    }

    public static final class Snapshot {
        public final boolean aiEnabled;
        public final boolean webEnabled;
        public final boolean reasoningEnabled;
        public final String endpoint;
        public final String model;
        public final String apiKey;

        Snapshot(boolean aiEnabled, boolean webEnabled, boolean reasoningEnabled,
                 String endpoint, String model, String apiKey) {
            this.aiEnabled = aiEnabled;
            this.webEnabled = webEnabled;
            this.reasoningEnabled = reasoningEnabled;
            this.endpoint = endpoint;
            this.model = model;
            this.apiKey = apiKey;
        }

        public String modeLabel() {
            if (aiEnabled && reasoningEnabled && webEnabled) return "AI • думаю глубже • интернет";
            if (aiEnabled && reasoningEnabled) return "AI • думаю глубже";
            if (aiEnabled && webEnabled) return "AI + интернет";
            if (aiEnabled) return "AI";
            return "Веб-поиск • бесплатно";
        }
    }
}
