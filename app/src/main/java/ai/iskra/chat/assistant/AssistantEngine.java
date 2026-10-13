package ai.iskra.chat.assistant;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import ai.iskra.chat.data.AppSettings;
import ai.iskra.chat.model.AssistantReply;
import ai.iskra.chat.model.ChatMessage;
import ai.iskra.chat.model.SearchSource;
import ai.iskra.chat.net.AiClient;
import ai.iskra.chat.net.WeatherService;
import ai.iskra.chat.net.WebSearchService;
import ai.iskra.chat.util.DebugLog;
import ai.iskra.chat.util.TextUtilsEx;

import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class AssistantEngine {
    public interface Callback {
        void onSuccess(AssistantReply reply);
        void onError(String message);
    }

    private final ExecutorService executor = Executors.newFixedThreadPool(2);
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final WebSearchService webSearch = new WebSearchService();
    private final WeatherService weatherService = new WeatherService();
    private final AiClient aiClient = new AiClient();
    private final DeviceInfoProvider deviceInfo;

    public AssistantEngine(Context context) {
        deviceInfo = new DeviceInfoProvider(context);
    }

    public void ask(String question, List<ChatMessage> history,
                    AppSettings.Snapshot settings, Callback callback) {
        DebugLog.log("ASSISTANT", "Request queued: \"" + question + "\"; history=" + history.size() +
                ", ai=" + settings.aiEnabled + ", web=" + settings.webEnabled);
        executor.execute(() -> {
            long started = System.currentTimeMillis();
            try {
                AssistantReply deviceReply = deviceInfo.tryAnswer(question);
                if (deviceReply != null) {
                    DebugLog.log("ROUTER", "Matched local device/time intent");
                    postSuccess(callback, deviceReply, started, "device");
                    return;
                }

                if (weatherService.isWeatherQuestion(question)) {
                    DebugLog.log("ROUTER", "Matched live weather intent");
                    AssistantReply weather = weatherService.forecast(question);
                    postSuccess(callback, weather, started, "weather");
                    return;
                }

                AssistantReply local = localReply(question);
                if (local != null && !settings.aiEnabled) {
                    DebugLog.log("ROUTER", "Matched built-in local response");
                    postSuccess(callback, local, started, "local");
                    return;
                }

                List<SearchSource> sources = Collections.emptyList();
                Exception searchError = null;
                if (settings.webEnabled) {
                    try {
                        DebugLog.log("SEARCH", "Starting web research");
                        sources = webSearch.search(question);
                        DebugLog.log("SEARCH", "Web research completed; sources=" + sources.size());
                    } catch (Exception error) {
                        searchError = error;
                        DebugLog.error("SEARCH", error);
                    }
                }

                if (settings.aiEnabled) {
                    try {
                        DebugLog.log("AI", "Calling model=" + settings.model + ", endpoint=" + settings.endpoint +
                                ", contextSources=" + sources.size());
                        String answer = aiClient.complete(
                                settings.endpoint, settings.model, settings.apiKey,
                                question, history, sources);
                        postSuccess(callback, new AssistantReply(answer, sources), started, "ai");
                        return;
                    } catch (Exception providerError) {
                        DebugLog.error("AI", providerError);
                        if (!sources.isEmpty()) {
                            String fallback = buildSearchAnswer(sources) +
                                    "\n\n⚠️ ИИ-провайдер сейчас недоступен: " +
                                    safeError(providerError) + " Ответ составлен по результатам поиска.";
                            postSuccess(callback, new AssistantReply(fallback, sources), started, "search-fallback");
                            return;
                        }
                        throw providerError;
                    }
                }

                if (!sources.isEmpty()) {
                    postSuccess(callback, new AssistantReply(buildSearchAnswer(sources), sources), started, "search");
                } else if (local != null) {
                    postSuccess(callback, local, started, "local-fallback");
                } else if (!settings.webEnabled) {
                    postError(callback, "Веб-поиск выключен. Включите его в настройках или подключите AI-провайдера.", started);
                } else if (searchError != null) {
                    throw searchError;
                } else {
                    postError(callback, "По этому запросу ничего не нашлось. Попробуйте переформулировать вопрос.", started);
                }
            } catch (UnknownHostException error) {
                DebugLog.error("NETWORK", error);
                postError(callback, "Нет доступа к интернету. Проверьте подключение и повторите запрос.", started);
            } catch (SocketTimeoutException error) {
                DebugLog.error("NETWORK", error);
                postError(callback, "Сервис отвечает слишком долго. Попробуйте ещё раз через минуту.", started);
            } catch (Exception error) {
                DebugLog.error("ASSISTANT", error);
                postError(callback, safeError(error), started);
            }
        });
    }

    public void shutdown() {
        DebugLog.log("ASSISTANT", "Executor shutdown requested");
        executor.shutdownNow();
    }

    private AssistantReply localReply(String raw) {
        String question = raw == null ? "" : raw.trim().toLowerCase(new Locale("ru", "RU"));
        if (question.matches("^(привет|здравствуй|здравствуйте|добрый (день|вечер|утро))[!., ]*$")) {
            return new AssistantReply(
                    "Привет! Я **kvsai** ✦\n\nЗадайте вопрос — я найду информацию в интернете. " +
                            "Также я умею показывать реальные данные устройства и актуальную погоду.",
                    Collections.emptyList());
        }
        if (question.contains("что ты умеешь") || question.contains("кто ты")) {
            return new AssistantReply(
                    "Я **kvsai**. Умею:\n\n" +
                            "- искать актуальную информацию в интернете;\n" +
                            "- узнавать погоду на сегодня, завтра и послезавтра;\n" +
                            "- показывать время и характеристики этого Android-устройства;\n" +
                            "- красиво отображать Markdown и код с подсветкой;\n" +
                            "- сохранять чаты и показывать источники;\n" +
                            "- работать с OpenRouter, Ollama, LM Studio и другими OpenAI-совместимыми сервисами.",
                    Collections.emptyList());
        }
        return null;
    }

    private String buildSearchAnswer(List<SearchSource> sources) {
        StringBuilder answer = new StringBuilder("**Короткий ответ**\n\n");
        SearchSource first = sources.get(0);
        if (!first.snippet.isEmpty()) {
            answer.append(TextUtilsEx.compact(first.snippet, 750)).append(" [1]");
        } else {
            answer.append("Нашёл материал «").append(first.title).append("» [1].");
        }

        if (sources.size() > 1) {
            answer.append("\n\n**Дополнительно**\n\n");
            int limit = Math.min(4, sources.size());
            for (int i = 1; i < limit; i++) {
                SearchSource source = sources.get(i);
                answer.append("- **").append(source.title).append("** — ");
                answer.append(source.snippet.isEmpty()
                        ? "подробнее в источнике"
                        : TextUtilsEx.compact(source.snippet, 320));
                answer.append(" [").append(i + 1).append("]\n");
            }
        }
        answer.append("\nИсточники можно открыть под ответом.");
        return answer.toString().trim();
    }

    private String safeError(Exception error) {
        String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) {
            return "Не удалось получить ответ. Проверьте подключение и настройки.";
        }
        return TextUtilsEx.compact(message, 260);
    }

    private void postSuccess(Callback callback, AssistantReply reply, long started, String route) {
        DebugLog.log("ASSISTANT", "Reply ready via " + route + "; chars=" + reply.text.length() +
                ", sources=" + reply.sources.size() + ", elapsed=" +
                (System.currentTimeMillis() - started) + "ms");
        mainHandler.post(() -> callback.onSuccess(reply));
    }

    private void postError(Callback callback, String message, long started) {
        DebugLog.log("ASSISTANT", "Request failed after " +
                (System.currentTimeMillis() - started) + "ms: " + message);
        mainHandler.post(() -> callback.onError(message));
    }
}
