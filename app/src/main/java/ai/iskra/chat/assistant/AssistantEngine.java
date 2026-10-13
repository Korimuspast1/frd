package ai.iskra.chat.assistant;

import android.os.Handler;
import android.os.Looper;

import ai.iskra.chat.data.AppSettings;
import ai.iskra.chat.model.AssistantReply;
import ai.iskra.chat.model.ChatMessage;
import ai.iskra.chat.model.SearchSource;
import ai.iskra.chat.net.AiClient;
import ai.iskra.chat.net.WebSearchService;
import ai.iskra.chat.util.TextUtilsEx;

import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.text.SimpleDateFormat;
import java.util.Collections;
import java.util.Date;
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
    private final AiClient aiClient = new AiClient();

    public void ask(String question, List<ChatMessage> history,
                    AppSettings.Snapshot settings, Callback callback) {
        executor.execute(() -> {
            try {
                AssistantReply local = localReply(question);
                if (local != null && !settings.aiEnabled) {
                    postSuccess(callback, local);
                    return;
                }

                List<SearchSource> sources = Collections.emptyList();
                Exception searchError = null;
                if (settings.webEnabled) {
                    try {
                        sources = webSearch.search(question);
                    } catch (Exception error) {
                        searchError = error;
                    }
                }

                if (settings.aiEnabled) {
                    try {
                        String answer = aiClient.complete(
                                settings.endpoint, settings.model, settings.apiKey,
                                question, history, sources);
                        postSuccess(callback, new AssistantReply(answer, sources));
                        return;
                    } catch (Exception providerError) {
                        if (!sources.isEmpty()) {
                            String fallback = buildSearchAnswer(sources) +
                                    "\n\n⚠️ ИИ-провайдер сейчас недоступен: " +
                                    safeError(providerError) + " Ответ составлен по результатам поиска.";
                            postSuccess(callback, new AssistantReply(fallback, sources));
                            return;
                        }
                        throw providerError;
                    }
                }

                if (!sources.isEmpty()) {
                    postSuccess(callback, new AssistantReply(buildSearchAnswer(sources), sources));
                } else if (local != null) {
                    postSuccess(callback, local);
                } else if (!settings.webEnabled) {
                    postError(callback, "Веб-поиск выключен. Включите его в настройках или подключите AI-провайдера.");
                } else if (searchError != null) {
                    throw searchError;
                } else {
                    postError(callback, "По этому запросу ничего не нашлось. Попробуйте переформулировать вопрос.");
                }
            } catch (UnknownHostException error) {
                postError(callback, "Нет доступа к интернету. Проверьте подключение и повторите запрос.");
            } catch (SocketTimeoutException error) {
                postError(callback, "Сервис отвечает слишком долго. Попробуйте ещё раз через минуту.");
            } catch (Exception error) {
                postError(callback, safeError(error));
            }
        });
    }

    public void shutdown() {
        executor.shutdownNow();
    }

    private AssistantReply localReply(String raw) {
        String question = raw == null ? "" : raw.trim().toLowerCase(new Locale("ru", "RU"));
        if (question.matches("^(привет|здравствуй|здравствуйте|добрый (день|вечер|утро))[!., ]*$")) {
            return new AssistantReply(
                    "Привет! Я Искра ✦\n\nЗадайте вопрос — я найду информацию в интернете. " +
                            "А если подключить AI в настройках, смогу анализировать источники и давать более связные ответы.",
                    Collections.emptyList());
        }
        if (question.contains("что ты умеешь") || question.contains("кто ты")) {
            return new AssistantReply(
                    "Я **Искра AI**. Умею:\n\n" +
                            "- искать актуальную информацию в интернете;\n" +
                            "- сохранять отдельные чаты и историю;\n" +
                            "- показывать источники ответа;\n" +
                            "- работать с OpenRouter, Ollama, LM Studio и другими OpenAI-совместимыми сервисами.\n\n" +
                            "Веб-поиск работает бесплатно и без ключа.",
                    Collections.emptyList());
        }
        if (question.matches(".*(какая сегодня дата|какое сегодня число).*")) {
            String date = new SimpleDateFormat("d MMMM yyyy 'года'", new Locale("ru", "RU"))
                    .format(new Date());
            return new AssistantReply("Сегодня **" + date + "**.", Collections.emptyList());
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
                if (source.snippet.isEmpty()) {
                    answer.append("подробнее в источнике");
                } else {
                    answer.append(TextUtilsEx.compact(source.snippet, 320));
                }
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

    private void postSuccess(Callback callback, AssistantReply reply) {
        mainHandler.post(() -> callback.onSuccess(reply));
    }

    private void postError(Callback callback, String message) {
        mainHandler.post(() -> callback.onError(message));
    }
}
