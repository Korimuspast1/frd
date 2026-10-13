package ai.iskra.chat.net;

import ai.iskra.chat.model.ChatMessage;
import ai.iskra.chat.model.SearchSource;
import ai.iskra.chat.util.DebugLog;
import ai.iskra.chat.util.TextUtilsEx;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Client for OpenAI-compatible providers: OpenRouter, Ollama, LM Studio and others. */
public final class AiClient {
    public String complete(String endpoint, String model, String apiKey, String question,
                           List<ChatMessage> history, List<SearchSource> sources) throws Exception {
        URL url = new URL(completionsUrl(endpoint));
        HttpURLConnection connection = HttpUtils.configure((HttpURLConnection) url.openConnection());
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("Accept", "application/json");
        if (apiKey != null && !apiKey.trim().isEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer " + apiKey.trim());
        }
        connection.setRequestProperty("X-Title", "kvsai");

        JSONObject request = new JSONObject();
        request.put("model", model);
        request.put("temperature", 0.35);
        request.put("max_tokens", 1200);
        JSONArray messages = new JSONArray();
        messages.put(message("system", systemPrompt(sources)));

        int start = Math.max(0, history.size() - 12);
        for (int i = start; i < history.size(); i++) {
            ChatMessage item = history.get(i);
            if (item.state != ChatMessage.State.READY || item.content.trim().isEmpty()) continue;
            messages.put(message(item.isUser() ? "user" : "assistant",
                    TextUtilsEx.compact(item.content, 4500)));
        }
        if (history.isEmpty() || !history.get(history.size() - 1).isUser()
                || !history.get(history.size() - 1).content.equals(question)) {
            messages.put(message("user", question));
        }
        request.put("messages", messages);

        byte[] body = request.toString().getBytes(StandardCharsets.UTF_8);
        DebugLog.log("AI", "POST /chat/completions; model=" + model + ", messages=" +
                messages.length() + ", requestBytes=" + body.length + ", auth=" +
                (apiKey != null && !apiKey.trim().isEmpty()));
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(body);
        }

        String response;
        try {
            response = HttpUtils.readResponse(connection);
        } catch (HttpUtils.HttpException error) {
            throw friendlyProviderError(error);
        } finally {
            connection.disconnect();
        }
        String content = extractContent(new JSONObject(response));
        DebugLog.log("AI", "Provider response parsed; chars=" + content.length());
        return content;
    }

    private JSONObject message(String role, String content) throws Exception {
        JSONObject object = new JSONObject();
        object.put("role", role);
        object.put("content", content);
        return object;
    }

    private String systemPrompt(List<SearchSource> sources) {
        String date = new SimpleDateFormat("dd.MM.yyyy", new Locale("ru", "RU")).format(new Date());
        StringBuilder prompt = new StringBuilder(
                "Ты — kvsai, полезный русскоязычный ассистент. Отвечай ясно, по существу и честно. " +
                "Не выдумывай факты. Сегодня " + date + ". " +
                "Оформляй любой многострочный код только fenced-блоком Markdown: три обратные кавычки, " +
                "точное имя языка (python, kotlin, javascript, json и т. п.), перевод строки, код и закрывающие " +
                "три кавычки. Для обычного текста без синтаксиса используй язык plaintext. ");
        if (sources != null && !sources.isEmpty()) {
            prompt.append("Ниже результаты веб-поиска. Используй их как контекст, ставь ссылки на источники " +
                    "в формате [1], [2] после соответствующих утверждений. Если данных мало, прямо скажи об этом.\n\n");
            for (int i = 0; i < sources.size(); i++) {
                SearchSource source = sources.get(i);
                prompt.append('[').append(i + 1).append("] ")
                        .append(source.title).append("\nURL: ").append(source.url)
                        .append("\n").append(TextUtilsEx.compact(source.snippet, 900)).append("\n\n");
            }
        }
        return prompt.toString();
    }

    private String extractContent(JSONObject response) throws Exception {
        JSONArray choices = response.optJSONArray("choices");
        if (choices == null || choices.length() == 0) {
            throw new Exception("Провайдер не вернул вариант ответа");
        }
        JSONObject message = choices.getJSONObject(0).optJSONObject("message");
        if (message == null) throw new Exception("Некорректный ответ провайдера");
        Object content = message.opt("content");
        if (content instanceof String && !((String) content).trim().isEmpty()) {
            return ((String) content).trim();
        }
        if (content instanceof JSONArray) {
            StringBuilder text = new StringBuilder();
            JSONArray parts = (JSONArray) content;
            for (int i = 0; i < parts.length(); i++) {
                JSONObject part = parts.optJSONObject(i);
                if (part != null && "text".equals(part.optString("type"))) {
                    if (text.length() > 0) text.append('\n');
                    text.append(part.optString("text"));
                }
            }
            if (text.length() > 0) return text.toString().trim();
        }
        throw new Exception("Провайдер вернул пустой ответ");
    }

    private String completionsUrl(String endpoint) {
        String base = endpoint == null ? "" : endpoint.trim();
        while (base.endsWith("/")) base = base.substring(0, base.length() - 1);
        if (base.endsWith("/chat/completions")) return base;
        return base + "/chat/completions";
    }

    private Exception friendlyProviderError(HttpUtils.HttpException error) {
        String detail = "";
        try {
            JSONObject root = new JSONObject(error.responseBody);
            JSONObject object = root.optJSONObject("error");
            if (object != null) detail = object.optString("message", "");
        } catch (Exception ignored) {}
        if (error.statusCode == 401 || error.statusCode == 403) {
            return new Exception("Провайдер отклонил API-ключ. Проверьте ключ в настройках.");
        }
        if (error.statusCode == 429) {
            return new Exception("Лимит запросов исчерпан. Подождите немного или выберите другую модель.");
        }
        if (!detail.isEmpty()) return new Exception("Ошибка провайдера: " + TextUtilsEx.compact(detail, 240));
        return new Exception("Провайдер вернул HTTP " + error.statusCode);
    }
}
