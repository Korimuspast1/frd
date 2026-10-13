package ai.iskra.chat.ui;

import android.content.Context;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.TextView;

import ai.iskra.chat.R;
import ai.iskra.chat.model.Chat;
import ai.iskra.chat.util.TextUtilsEx;
import ai.iskra.chat.util.Ui;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public final class ChatListAdapter extends BaseAdapter {
    public interface Listener {
        void onOpen(Chat chat);
        void onMenu(Chat chat, View anchor);
    }

    private final Context context;
    private final Listener listener;
    private List<Chat> items = new ArrayList<>();

    public ChatListAdapter(Context context, Listener listener) {
        this.context = context;
        this.listener = listener;
    }

    public void setItems(List<Chat> chats) {
        items = chats == null ? new ArrayList<>() : new ArrayList<>(chats);
        notifyDataSetChanged();
    }

    @Override public int getCount() { return items.size(); }
    @Override public Chat getItem(int position) { return items.get(position); }
    @Override public long getItemId(int position) { return items.get(position).id; }

    @Override
    public View getView(int position, View convertView, ViewGroup parent) {
        Chat chat = getItem(position);
        FrameLayout outer = new FrameLayout(context);
        outer.setPadding(Ui.dp(context, 20), Ui.dp(context, 5),
                Ui.dp(context, 20), Ui.dp(context, 5));

        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(Ui.dp(context, 14), Ui.dp(context, 14),
                Ui.dp(context, 8), Ui.dp(context, 14));
        card.setBackground(Ui.ripple(
                Ui.roundedStroke(Ui.CARD, 0xFF202B3C, 20, context), 0x288B5CF6));
        card.setClickable(true);
        card.setFocusable(true);
        card.setOnClickListener(v -> listener.onOpen(chat));
        card.setOnLongClickListener(v -> {
            listener.onMenu(chat, v);
            return true;
        });

        FrameLayout icon = new FrameLayout(context);
        icon.setBackground(Ui.gradient(Ui.VIOLET, Ui.VIOLET_DARK, 15, context));
        TextView glyph = Ui.text(context, "✦", 20, Ui.TEXT);
        glyph.setGravity(Gravity.CENTER);
        icon.addView(glyph, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        card.addView(icon, new LinearLayout.LayoutParams(Ui.dp(context, 48), Ui.dp(context, 48)));

        LinearLayout textColumn = new LinearLayout(context);
        textColumn.setOrientation(LinearLayout.VERTICAL);
        textColumn.setPadding(Ui.dp(context, 13), 0, Ui.dp(context, 8), 0);
        TextView title = Ui.text(context, chat.title, 16, Ui.TEXT);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setMaxLines(1);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        textColumn.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        String previewText = chat.preview.isEmpty()
                ? "Пустой диалог • можно задать первый вопрос"
                : TextUtilsEx.compact(chat.preview, 88);
        TextView preview = Ui.text(context, previewText, 13, Ui.MUTED);
        preview.setMaxLines(1);
        preview.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams previewParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        previewParams.topMargin = Ui.dp(context, 5);
        textColumn.addView(preview, previewParams);
        card.addView(textColumn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        LinearLayout meta = new LinearLayout(context);
        meta.setOrientation(LinearLayout.VERTICAL);
        meta.setGravity(Gravity.END);
        TextView time = Ui.text(context, formatTime(chat.updatedAt), 11, Ui.DIM);
        time.setGravity(Gravity.END);
        meta.addView(time);
        TextView count = Ui.text(context, chat.messageCount == 0 ? "" : String.valueOf(chat.messageCount), 11, Ui.CYAN);
        count.setGravity(Gravity.CENTER);
        count.setMinWidth(Ui.dp(context, 24));
        count.setPadding(Ui.dp(context, 6), Ui.dp(context, 2), Ui.dp(context, 6), Ui.dp(context, 2));
        if (chat.messageCount > 0) count.setBackground(Ui.rounded(0x2239D9C8, 9, context));
        LinearLayout.LayoutParams countParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        countParams.gravity = Gravity.END;
        countParams.topMargin = Ui.dp(context, 8);
        meta.addView(count, countParams);
        card.addView(meta, new LinearLayout.LayoutParams(Ui.dp(context, 50), ViewGroup.LayoutParams.WRAP_CONTENT));

        ImageButton more = Ui.iconButton(context, R.drawable.ic_more, "Действия с чатом");
        more.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        more.setPadding(Ui.dp(context, 9), Ui.dp(context, 9), Ui.dp(context, 9), Ui.dp(context, 9));
        more.setOnClickListener(v -> listener.onMenu(chat, v));
        card.addView(more, new LinearLayout.LayoutParams(Ui.dp(context, 40), Ui.dp(context, 48)));

        outer.addView(card, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return outer;
    }

    private String formatTime(long timestamp) {
        Calendar now = Calendar.getInstance();
        Calendar date = Calendar.getInstance();
        date.setTimeInMillis(timestamp);
        if (sameDay(now, date)) {
            return new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date(timestamp));
        }
        now.add(Calendar.DAY_OF_YEAR, -1);
        if (sameDay(now, date)) return "вчера";
        return new SimpleDateFormat("d MMM", new Locale("ru", "RU")).format(new Date(timestamp));
    }

    private boolean sameDay(Calendar first, Calendar second) {
        return first.get(Calendar.ERA) == second.get(Calendar.ERA)
                && first.get(Calendar.YEAR) == second.get(Calendar.YEAR)
                && first.get(Calendar.DAY_OF_YEAR) == second.get(Calendar.DAY_OF_YEAR);
    }
}
