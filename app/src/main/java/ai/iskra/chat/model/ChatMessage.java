package ai.iskra.chat.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class ChatMessage {
    public static final String ROLE_USER = "user";
    public static final String ROLE_ASSISTANT = "assistant";

    public enum State { READY, PENDING, ERROR }

    public final long id;
    public final long chatId;
    public final String role;
    public final String content;
    public final List<SearchSource> sources;
    public final long createdAt;
    public final State state;

    public ChatMessage(long id, long chatId, String role, String content,
                       List<SearchSource> sources, long createdAt, State state) {
        this.id = id;
        this.chatId = chatId;
        this.role = role;
        this.content = content == null ? "" : content;
        this.sources = sources == null
                ? Collections.emptyList()
                : Collections.unmodifiableList(new ArrayList<>(sources));
        this.createdAt = createdAt;
        this.state = state == null ? State.READY : state;
    }

    public boolean isUser() {
        return ROLE_USER.equals(role);
    }

    public static ChatMessage pending(long chatId) {
        return new ChatMessage(-1, chatId, ROLE_ASSISTANT, "Ищу информацию и готовлю ответ…",
                Collections.emptyList(), System.currentTimeMillis(), State.PENDING);
    }

    public static ChatMessage error(long chatId, String text) {
        return new ChatMessage(-2, chatId, ROLE_ASSISTANT, text,
                Collections.emptyList(), System.currentTimeMillis(), State.ERROR);
    }
}
