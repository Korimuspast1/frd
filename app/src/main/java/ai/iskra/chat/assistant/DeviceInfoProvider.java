package ai.iskra.chat.assistant;

import android.app.ActivityManager;
import android.content.Context;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Environment;
import android.os.StatFs;
import android.text.TextUtils;
import android.util.DisplayMetrics;

import ai.iskra.chat.model.AssistantReply;
import ai.iskra.chat.util.DebugLog;

import java.text.SimpleDateFormat;
import java.util.Collections;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/** Answers explicit questions using non-sensitive values exposed by Android. */
public final class DeviceInfoProvider {
    private final Context context;

    public DeviceInfoProvider(Context context) {
        this.context = context.getApplicationContext();
    }

    public AssistantReply tryAnswer(String rawQuestion) {
        String question = normalize(rawQuestion);
        if (isTimeQuestion(question)) {
            String value = currentTimeAnswer();
            DebugLog.log("DEVICE", "Answered device date/time request");
            return reply(value);
        }
        if (isDeviceQuestion(question)) {
            String value = deviceAnswer(question);
            DebugLog.log("DEVICE", "Answered hardware request for " + Build.MANUFACTURER + " " + Build.MODEL);
            return reply(value);
        }
        return null;
    }

    private boolean isTimeQuestion(String question) {
        return question.matches(".*(который час|сколько( сейчас)? врем|текущее время|время на (мо[её]м )?устройстве|" +
                "время на телефон|какая сегодня дата|какое сегодня число|сегодняшняя дата).*" );
    }

    private boolean isDeviceQuestion(String question) {
        return question.matches(".*(характеристик.*(телефон|устройств|смартфон)|информация об устройстве|" +
                "какой у меня (телефон|смартфон|андроид)|что у меня за (телефон|устройство)|" +
                "модель (моего )?(телефона|устройства)|моя модель телефона|что (это )?за модель( телефона)?|" +
                "версия (android|андроид)|оперативн(ая|ой) памят|сколько (озу|памяти)|" +
                "процессор телефона|характеристики устройства|уровень заряда|сколько заряд|" +
                "разрешение экрана).*" );
    }

    private String currentTimeAnswer() {
        Date now = new Date();
        Locale locale = new Locale("ru", "RU");
        String time = new SimpleDateFormat("HH:mm:ss", locale).format(now);
        String date = new SimpleDateFormat("d MMMM yyyy, EEEE", locale).format(now);
        TimeZone zone = TimeZone.getDefault();
        return "На устройстве сейчас **" + time + "**.\n\n" +
                "Дата: **" + date + "**  \n" +
                "Часовой пояс: **" + zone.getID() + " (UTC" + offset(zone, now) + ")**";
    }

    private String deviceAnswer(String question) {
        if (question.contains("заряд")) {
            int battery = batteryPercent();
            return battery >= 0 ? "Текущий заряд устройства: **" + battery + "%**."
                    : "Android не предоставил значение заряда батареи.";
        }

        ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
        ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
        if (manager != null) manager.getMemoryInfo(memory);

        StatFs storage = new StatFs(Environment.getDataDirectory().getAbsolutePath());
        long totalStorage = storage.getTotalBytes();
        long freeStorage = storage.getAvailableBytes();
        DisplayMetrics display = context.getResources().getDisplayMetrics();
        int battery = batteryPercent();

        String soc;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            String maker = emptyFallback(Build.SOC_MANUFACTURER, "");
            String model = emptyFallback(Build.SOC_MODEL, Build.HARDWARE);
            soc = (maker + " " + model).trim();
        } else {
            soc = Build.HARDWARE;
        }

        StringBuilder answer = new StringBuilder("**Характеристики этого устройства**\n\n");
        answer.append("- **Модель:** ").append(pretty(Build.MANUFACTURER)).append(' ').append(Build.MODEL).append('\n');
        answer.append("- **Android:** ").append(Build.VERSION.RELEASE)
                .append(" (API ").append(Build.VERSION.SDK_INT).append(")\n");
        if (Build.VERSION.SECURITY_PATCH != null && !Build.VERSION.SECURITY_PATCH.isEmpty()) {
            answer.append("- **Патч безопасности:** ").append(Build.VERSION.SECURITY_PATCH).append('\n');
        }
        answer.append("- **Процессор / платформа:** ").append(emptyFallback(soc, "не определено")).append('\n');
        answer.append("- **Ядра CPU:** ").append(Runtime.getRuntime().availableProcessors()).append('\n');
        answer.append("- **Архитектура:** ").append(TextUtils.join(", ", Build.SUPPORTED_ABIS)).append('\n');
        if (memory.totalMem > 0) {
            answer.append("- **ОЗУ:** ").append(formatBytes(memory.totalMem))
                    .append(" (доступно сейчас ").append(formatBytes(memory.availMem)).append(")\n");
        }
        answer.append("- **Хранилище:** ").append(formatBytes(totalStorage))
                .append(" (свободно ").append(formatBytes(freeStorage)).append(")\n");
        answer.append("- **Экран приложения:** ").append(display.widthPixels).append('×').append(display.heightPixels)
                .append(", ").append(display.densityDpi).append(" dpi\n");
        if (battery >= 0) answer.append("- **Заряд:** ").append(battery).append("%\n");
        answer.append("- **Часовой пояс:** ").append(TimeZone.getDefault().getID()).append('\n');
        answer.append("- **Локаль:** ").append(Locale.getDefault().toLanguageTag());
        answer.append("\n\nСерийный номер, IMEI и другие закрытые идентификаторы приложение не считывает.");
        return answer.toString();
    }

    private int batteryPercent() {
        BatteryManager battery = (BatteryManager) context.getSystemService(Context.BATTERY_SERVICE);
        if (battery == null) return -1;
        int value = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
        return value >= 0 && value <= 100 ? value : -1;
    }

    private String formatBytes(long bytes) {
        if (bytes <= 0) return "0 Б";
        double value = bytes;
        String[] units = {"Б", "КБ", "МБ", "ГБ", "ТБ"};
        int unit = 0;
        while (value >= 1024 && unit < units.length - 1) {
            value /= 1024;
            unit++;
        }
        return String.format(new Locale("ru", "RU"), value >= 10 ? "%.0f %s" : "%.1f %s", value, units[unit]);
    }

    private String offset(TimeZone zone, Date date) {
        int totalMinutes = zone.getOffset(date.getTime()) / 60_000;
        int hours = Math.abs(totalMinutes / 60);
        int minutes = Math.abs(totalMinutes % 60);
        return String.format(Locale.US, "%s%02d:%02d", totalMinutes >= 0 ? "+" : "-", hours, minutes);
    }

    private String pretty(String value) {
        if (value == null || value.isEmpty()) return "";
        return value.substring(0, 1).toUpperCase(Locale.getDefault()) + value.substring(1);
    }

    private String emptyFallback(String value, String fallback) {
        return value == null || value.trim().isEmpty() || "unknown".equalsIgnoreCase(value)
                ? fallback : value.trim();
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(new Locale("ru", "RU"));
    }

    private AssistantReply reply(String text) {
        return new AssistantReply(text, Collections.emptyList());
    }
}
