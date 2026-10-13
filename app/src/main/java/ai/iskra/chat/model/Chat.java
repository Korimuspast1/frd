package ai.iskra.chat.model;

public final class Chat {
    public final long id;
    public final String title;
    public final String preview;
    public final long createdAt;
    public final long updatedAt;
    public final int messageCount;

    public Chat(long id, String title, String preview, long createdAt, long updatedAt, int messageCount) {
        this.id = id;
        this.title = title == null || title.trim().isEmpty() ? "Новый чат" : title;
        this.preview = preview == null ? "" : preview;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        this.messageCount = messageCount;
    }
}
