package ai.iskra.chat.data;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import ai.iskra.chat.model.Chat;
import ai.iskra.chat.model.ChatMessage;
import ai.iskra.chat.model.SearchSource;
import ai.iskra.chat.util.JsonUtils;

import java.util.ArrayList;
import java.util.List;

public final class ChatDatabase extends SQLiteOpenHelper {
    private static final String DATABASE_NAME = "iskra_chats.db";
    private static final int DATABASE_VERSION = 1;

    public ChatDatabase(Context context) {
        super(context.getApplicationContext(), DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onConfigure(SQLiteDatabase db) {
        super.onConfigure(db);
        db.setForeignKeyConstraintsEnabled(true);
        db.enableWriteAheadLogging();
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE chats (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "title TEXT NOT NULL," +
                "created_at INTEGER NOT NULL," +
                "updated_at INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE messages (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE," +
                "role TEXT NOT NULL," +
                "content TEXT NOT NULL," +
                "sources_json TEXT NOT NULL DEFAULT '[]'," +
                "created_at INTEGER NOT NULL)");
        db.execSQL("CREATE INDEX idx_messages_chat_time ON messages(chat_id, created_at, id)");
        db.execSQL("CREATE INDEX idx_chats_updated ON chats(updated_at DESC)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        // Version 1 is the initial schema. Future migrations belong here.
    }

    public long createChat() {
        long now = System.currentTimeMillis();
        ContentValues values = new ContentValues();
        values.put("title", "Новый чат");
        values.put("created_at", now);
        values.put("updated_at", now);
        return getWritableDatabase().insertOrThrow("chats", null, values);
    }

    public Chat getChat(long id) {
        String sql = "SELECT c.id,c.title,c.created_at,c.updated_at," +
                "COALESCE((SELECT content FROM messages m WHERE m.chat_id=c.id " +
                "ORDER BY m.created_at DESC,m.id DESC LIMIT 1),'')," +
                "(SELECT COUNT(*) FROM messages m WHERE m.chat_id=c.id) " +
                "FROM chats c WHERE c.id=?";
        try (Cursor cursor = getReadableDatabase().rawQuery(sql, new String[]{String.valueOf(id)})) {
            return cursor.moveToFirst() ? chatFromCursor(cursor) : null;
        }
    }

    public List<Chat> getChats(String search) {
        String query = search == null ? "" : search.trim();
        String sql = "SELECT c.id,c.title,c.created_at,c.updated_at," +
                "COALESCE((SELECT content FROM messages m WHERE m.chat_id=c.id " +
                "ORDER BY m.created_at DESC,m.id DESC LIMIT 1),'')," +
                "(SELECT COUNT(*) FROM messages m WHERE m.chat_id=c.id) " +
                "FROM chats c ";
        String[] args = null;
        if (!query.isEmpty()) {
            sql += "WHERE c.title LIKE ? ESCAPE '!' OR EXISTS(" +
                    "SELECT 1 FROM messages sm WHERE sm.chat_id=c.id AND sm.content LIKE ? ESCAPE '!') ";
            String pattern = "%" + escapeLike(query) + "%";
            args = new String[]{pattern, pattern};
        }
        sql += "ORDER BY c.updated_at DESC,c.id DESC";

        List<Chat> result = new ArrayList<>();
        try (Cursor cursor = getReadableDatabase().rawQuery(sql, args)) {
            while (cursor.moveToNext()) result.add(chatFromCursor(cursor));
        }
        return result;
    }

    private String escapeLike(String value) {
        return value.replace("!", "!!").replace("%", "!%").replace("_", "!_");
    }

    private Chat chatFromCursor(Cursor cursor) {
        return new Chat(
                cursor.getLong(0), cursor.getString(1), cursor.getString(4),
                cursor.getLong(2), cursor.getLong(3), cursor.getInt(5)
        );
    }

    public List<ChatMessage> getMessages(long chatId) {
        List<ChatMessage> result = new ArrayList<>();
        String sql = "SELECT id,chat_id,role,content,sources_json,created_at " +
                "FROM messages WHERE chat_id=? ORDER BY created_at ASC,id ASC";
        try (Cursor cursor = getReadableDatabase().rawQuery(sql, new String[]{String.valueOf(chatId)})) {
            while (cursor.moveToNext()) {
                result.add(new ChatMessage(
                        cursor.getLong(0), cursor.getLong(1), cursor.getString(2),
                        cursor.getString(3), JsonUtils.sourcesFromJson(cursor.getString(4)),
                        cursor.getLong(5), ChatMessage.State.READY
                ));
            }
        }
        return result;
    }

    public long addMessage(long chatId, String role, String content, List<SearchSource> sources) {
        SQLiteDatabase db = getWritableDatabase();
        long now = System.currentTimeMillis();
        db.beginTransaction();
        try {
            ContentValues message = new ContentValues();
            message.put("chat_id", chatId);
            message.put("role", role);
            message.put("content", content);
            message.put("sources_json", JsonUtils.sourcesToJson(sources));
            message.put("created_at", now);
            long id = db.insertOrThrow("messages", null, message);

            ContentValues chat = new ContentValues();
            chat.put("updated_at", now);
            db.update("chats", chat, "id=?", new String[]{String.valueOf(chatId)});
            db.setTransactionSuccessful();
            return id;
        } finally {
            db.endTransaction();
        }
    }

    public void renameChat(long chatId, String title) {
        String clean = title == null ? "" : title.trim();
        if (clean.isEmpty()) return;
        ContentValues values = new ContentValues();
        values.put("title", clean);
        values.put("updated_at", System.currentTimeMillis());
        getWritableDatabase().update("chats", values, "id=?", new String[]{String.valueOf(chatId)});
    }

    public void deleteChat(long chatId) {
        getWritableDatabase().delete("chats", "id=?", new String[]{String.valueOf(chatId)});
    }

    public void clearAll() {
        getWritableDatabase().delete("chats", null, null);
    }

    public int countChats() {
        try (Cursor cursor = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM chats", null)) {
            return cursor.moveToFirst() ? cursor.getInt(0) : 0;
        }
    }

    public int countMessages(long chatId) {
        try (Cursor cursor = getReadableDatabase().rawQuery(
                "SELECT COUNT(*) FROM messages WHERE chat_id=?",
                new String[]{String.valueOf(chatId)})) {
            return cursor.moveToFirst() ? cursor.getInt(0) : 0;
        }
    }
}
