package ai.iskra.chat.net;

import ai.iskra.chat.model.AssistantReply;
import ai.iskra.chat.model.SearchSource;
import ai.iskra.chat.util.DebugLog;
import ai.iskra.chat.util.TextUtilsEx;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Collections;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Real key-free weather forecasts from Open-Meteo. */
public final class WeatherService {
    private static final Pattern CITY_AFTER_PREPOSITION = Pattern.compile(
            "(?iu)(?:^|\\s)(?:в|во|для)\\s+([а-яёa-z][а-яёa-z\\-]*(?:\\s+[а-яёa-z][а-яёa-z\\-]*){0,3})");

    public boolean isWeatherQuestion(String raw) {
        String value = raw == null ? "" : raw.toLowerCase(new Locale("ru", "RU"));
        return value.matches(".*(погод|температур|прогноз.*(дожд|снег|ветер)|будет ли (дожд|снег)).*");
    }

    public AssistantReply forecast(String question) throws Exception {
        Query parsed = parseQuery(question);
        if (parsed.city.isEmpty()) {
            DebugLog.log("WEATHER", "Weather intent found, but city is missing");
            return new AssistantReply(
                    "Для точного прогноза укажите город. Например: **«Какая погода завтра в Москве?»**",
                    Collections.emptyList());
        }
        DebugLog.log("WEATHER", "Forecast request: city=" + parsed.city + ", dayOffset=" + parsed.dayOffset);
        Location location = geocode(parsed.city);
        Forecast value = loadForecast(location, parsed.dayOffset);

        String dayLabel = parsed.dayOffset == 0 ? "сегодня"
                : parsed.dayOffset == 1 ? "завтра" : "послезавтра";
        StringBuilder answer = new StringBuilder();
        answer.append("**Погода в ").append(location.displayName).append(' ')
                .append(dayLabel).append(" — ").append(value.formattedDate).append("**\n\n");
        answer.append(weatherEmoji(value.code)).append(' ').append(description(value.code)).append(".\n\n");
        answer.append("- **Температура:** от ").append(round(value.minTemperature)).append("°C до ")
                .append(round(value.maxTemperature)).append("°C\n");
        if (!Double.isNaN(value.precipitationProbability)) {
            answer.append("- **Вероятность осадков:** ")
                    .append(round(value.precipitationProbability)).append("%\n");
        }
        if (!Double.isNaN(value.windSpeed)) {
            answer.append("- **Максимальный ветер:** ")
                    .append(round(value.windSpeed)).append(" км/ч\n");
        }
        answer.append("\nПрогноз получен в реальном времени от Open-Meteo. Погода может меняться — перед выходом лучше обновить запрос.");

        SearchSource source = new SearchSource(
                "Open-Meteo — прогноз для " + location.displayName,
                "https://open-meteo.com/",
                description(value.code) + ", " + round(value.minTemperature) + "…" +
                        round(value.maxTemperature) + " °C"
        );
        DebugLog.log("WEATHER", "Forecast loaded: code=" + value.code + ", min=" +
                value.minTemperature + ", max=" + value.maxTemperature);
        return new AssistantReply(answer.toString(), Collections.singletonList(source));
    }

    private Location geocode(String city) throws Exception {
        String encoded = URLEncoder.encode(city, StandardCharsets.UTF_8.name());
        URL url = new URL("https://geocoding-api.open-meteo.com/v1/search?name=" + encoded +
                "&count=5&language=ru&format=json");
        DebugLog.log("WEATHER", "Geocoding city via Open-Meteo: " + city);
        HttpURLConnection connection = HttpUtils.configure((HttpURLConnection) url.openConnection());
        connection.setRequestProperty("Accept", "application/json");
        String body;
        try {
            body = HttpUtils.readResponse(connection);
        } finally {
            connection.disconnect();
        }
        JSONArray results = new JSONObject(body).optJSONArray("results");
        if (results == null || results.length() == 0) {
            throw new Exception("Не удалось найти город «" + city + "». Проверьте написание.");
        }
        JSONObject result = results.getJSONObject(0);
        String name = result.optString("name", city);
        String admin = result.optString("admin1", "");
        String country = result.optString("country", "");
        StringBuilder display = new StringBuilder(name);
        if (!admin.isEmpty() && !admin.equalsIgnoreCase(name)) display.append(", ").append(admin);
        if (!country.isEmpty()) display.append(", ").append(country);
        return new Location(display.toString(), result.getDouble("latitude"), result.getDouble("longitude"));
    }

    private Forecast loadForecast(Location location, int dayOffset) throws Exception {
        String endpoint = "https://api.open-meteo.com/v1/forecast?latitude=" + location.latitude +
                "&longitude=" + location.longitude +
                "&daily=weather_code,temperature_2m_max,temperature_2m_min," +
                "precipitation_probability_max,wind_speed_10m_max" +
                "&timezone=auto&forecast_days=4";
        DebugLog.log("WEATHER", "Loading daily forecast lat=" + location.latitude + ", lon=" + location.longitude);
        HttpURLConnection connection = HttpUtils.configure((HttpURLConnection) new URL(endpoint).openConnection());
        connection.setRequestProperty("Accept", "application/json");
        String body;
        try {
            body = HttpUtils.readResponse(connection);
        } finally {
            connection.disconnect();
        }
        JSONObject daily = new JSONObject(body).getJSONObject("daily");
        JSONArray dates = daily.getJSONArray("time");
        if (dayOffset >= dates.length()) throw new Exception("Прогноз на выбранный день пока недоступен.");
        String isoDate = dates.getString(dayOffset);
        String formattedDate = LocalDate.parse(isoDate)
                .format(DateTimeFormatter.ofPattern("d MMMM", new Locale("ru", "RU")));
        return new Forecast(
                daily.getJSONArray("weather_code").getInt(dayOffset),
                daily.getJSONArray("temperature_2m_min").getDouble(dayOffset),
                daily.getJSONArray("temperature_2m_max").getDouble(dayOffset),
                optionalDouble(daily.optJSONArray("precipitation_probability_max"), dayOffset),
                optionalDouble(daily.optJSONArray("wind_speed_10m_max"), dayOffset),
                formattedDate
        );
    }

    private Query parseQuery(String raw) {
        String lower = raw == null ? "" : raw.toLowerCase(new Locale("ru", "RU"))
                .replace('?', ' ').replace('!', ' ').replace(',', ' ').replace('.', ' ')
                .replaceAll("\\s+", " ").trim();
        int offset = lower.contains("послезавтра") ? 2 : lower.contains("завтра") ? 1 : 0;
        String city = "";
        Matcher matcher = CITY_AFTER_PREPOSITION.matcher(lower);
        while (matcher.find()) city = matcher.group(1);
        city = city.replaceAll("(?iu)(?:^|\\s)(сегодня|завтра|послезавтра|сейчас|например|" +
                        "пожалуйста|будет|ожидается|реально)(?:\\s.*)?$", "")
                .trim();
        if (city.isEmpty()) {
            Matcher simple = Pattern.compile("(?iu)погод[ауы]?\\s+(?:на\\s+)?(?:сегодня|завтра|послезавтра)?\\s*([а-яёa-z][а-яёa-z\\-]+)")
                    .matcher(lower);
            if (simple.find()) city = simple.group(1);
        }
        return new Query(normalizeCity(city), offset);
    }

    private String normalizeCity(String city) {
        String value = city.trim().toLowerCase(new Locale("ru", "RU"));
        switch (value) {
            case "москве": case "москвы": case "москву": return "Москва";
            case "санкт петербурге": case "санкт-петербурге": case "питере": return "Санкт-Петербург";
            case "риге": return "Рига";
            case "владивостоке": return "Владивосток";
            case "казани": return "Казань";
            case "сочи": return "Сочи";
            case "минске": return "Минск";
            case "киеве": return "Киев";
            case "лондоне": return "Лондон";
            case "берлине": return "Берлин";
            case "париже": return "Париж";
            default:
                if (value.isEmpty()) return "";
                return value.substring(0, 1).toUpperCase(new Locale("ru", "RU")) + value.substring(1);
        }
    }

    private double optionalDouble(JSONArray array, int index) {
        if (array == null || index >= array.length() || array.isNull(index)) return Double.NaN;
        return array.optDouble(index, Double.NaN);
    }

    private int round(double value) {
        return (int) Math.round(value);
    }

    private String weatherEmoji(int code) {
        if (code == 0) return "☀️";
        if (code <= 3) return "⛅";
        if (code <= 48) return "🌫️";
        if (code <= 57) return "🌦️";
        if (code <= 67) return "🌧️";
        if (code <= 77) return "🌨️";
        if (code <= 82) return "🌦️";
        if (code <= 86) return "❄️";
        return "⛈️";
    }

    private String description(int code) {
        switch (code) {
            case 0: return "Ясно";
            case 1: return "Преимущественно ясно";
            case 2: return "Переменная облачность";
            case 3: return "Пасмурно";
            case 45: case 48: return "Туман";
            case 51: case 53: case 55: return "Морось";
            case 56: case 57: return "Ледяная морось";
            case 61: case 63: case 65: return "Дождь";
            case 66: case 67: return "Ледяной дождь";
            case 71: case 73: case 75: case 77: return "Снег";
            case 80: case 81: case 82: return "Ливень";
            case 85: case 86: return "Снегопад";
            case 95: return "Гроза";
            case 96: case 99: return "Гроза с градом";
            default: return "Смешанные погодные условия";
        }
    }

    private static final class Query {
        final String city;
        final int dayOffset;
        Query(String city, int dayOffset) { this.city = city; this.dayOffset = dayOffset; }
    }

    private static final class Location {
        final String displayName;
        final double latitude;
        final double longitude;
        Location(String displayName, double latitude, double longitude) {
            this.displayName = displayName;
            this.latitude = latitude;
            this.longitude = longitude;
        }
    }

    private static final class Forecast {
        final int code;
        final double minTemperature;
        final double maxTemperature;
        final double precipitationProbability;
        final double windSpeed;
        final String formattedDate;
        Forecast(int code, double minTemperature, double maxTemperature,
                 double precipitationProbability, double windSpeed, String formattedDate) {
            this.code = code;
            this.minTemperature = minTemperature;
            this.maxTemperature = maxTemperature;
            this.precipitationProbability = precipitationProbability;
            this.windSpeed = windSpeed;
            this.formattedDate = formattedDate;
        }
    }
}
