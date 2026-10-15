package ai.iskra.chat.ui;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;
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
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public final class ChatListAdapter extends BaseAdapter {
    public interface Listener {
        void onOpen(Chat chat);
        void onMenu(Chat chat, View card);
    }

    private final Context context;
    private final Listener listener;
    private final Set<Long> animated = new HashSet<>();
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
        outer.setPadding(Ui.dp(context, 12), Ui.dp(context, 5),
                Ui.dp(context, 12), Ui.dp(context, 5));

        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(Ui.dp(context, 12), Ui.dp(context, 11),
                Ui.dp(context, 6), Ui.dp(context, 11));
        card.setBackground(Ui.ripple(Ui.glassSoft(context, 21), 0x2AFFFFFF));
        card.setElevation(Ui.dp(context, 2));
        card.setClickable(true);
        card.setFocusable(true);
        card.setOnClickListener(v -> listener.onOpen(chat));
        card.setOnLongClickListener(v -> {
            listener.onMenu(chat, card);
            return true;
        });

        TextView icon = Ui.text(context, "✦", 18, Color.WHITE);
        icon.setGravity(Gravity.CENTER);
        icon.setBackground(Ui.glassBlue(context, 99));
        card.addView(icon, new LinearLayout.LayoutParams(Ui.dp(context, 45), Ui.dp(context, 45)));

        LinearLayout textColumn = new LinearLayout(context);
        textColumn.setOrientation(LinearLayout.VERTICAL);
        textColumn.setPadding(Ui.dp(context, 12), 0, Ui.dp(context, 7), 0);
        TextView title = Ui.text(context, chat.title, 15, Ui.TEXT);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        title.setMaxLines(1);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        textColumn.addView(title);

        String previewValue = chat.preview.isEmpty()
                ? "Новый диалог"
                : TextUtilsEx.compact(chat.preview, 66);
        TextView preview = Ui.text(context, previewValue, 12, 0xFF97999F);
        preview.setMaxLines(1);
        preview.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams previewParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        previewParams.topMargin = Ui.dp(context, 4);
        textColumn.addView(preview, previewParams);
        card.addView(textColumn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView time = Ui.text(context, formatTime(chat.updatedAt), 10, 0xFF7F8289);
        time.setGravity(Gravity.CENTER);
        card.addView(time, new LinearLayout.LayoutParams(Ui.dp(context, 45), Ui.dp(context, 36)));

        ImageButton more = new ImageButton(context);
        more.setImageResource(R.drawable.ic_more);
        more.setContentDescription("Действия с чатом");
        more.setPadding(Ui.dp(context, 9), Ui.dp(context, 9), Ui.dp(context, 9), Ui.dp(context, 9));
        more.setBackground(Ui.ripple(Ui.rounded(Color.TRANSPARENT, 99, context), 0x33FFFFFF));
        more.setOnClickListener(v -> listener.onMenu(chat, card));
        card.addView(more, new LinearLayout.LayoutParams(Ui.dp(context, 40), Ui.dp(context, 40)));

        outer.addView(card, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        if (animated.add(chat.id)) {
            outer.setAlpha(0f);
            outer.setTranslationX(-Ui.dp(context, 18));
            outer.animate().alpha(1f).translationX(0f).setDuration(320)
                    .setStartDelay(Math.min(position * 35L, 210L))
                    .setInterpolator(new DecelerateInterpolator()).start();
        }
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
