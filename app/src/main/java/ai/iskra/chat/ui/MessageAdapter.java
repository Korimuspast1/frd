package ai.iskra.chat.ui;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import ai.iskra.chat.R;
import ai.iskra.chat.model.ChatMessage;
import ai.iskra.chat.model.SearchSource;
import ai.iskra.chat.util.DebugLog;
import ai.iskra.chat.util.MarkdownParser;
import ai.iskra.chat.util.SyntaxHighlighter;
import ai.iskra.chat.util.TextUtilsEx;
import ai.iskra.chat.util.Ui;

import java.util.ArrayList;
import java.util.List;

public final class MessageAdapter extends BaseAdapter {
    public interface Listener {
        void onRetry();
    }

    private final Context context;
    private final Listener listener;
    private List<ChatMessage> messages = new ArrayList<>();

    public MessageAdapter(Context context, Listener listener) {
        this.context = context;
        this.listener = listener;
    }

    public void setMessages(List<ChatMessage> values) {
        messages = values == null ? new ArrayList<>() : new ArrayList<>(values);
        notifyDataSetChanged();
    }

    public void add(ChatMessage message) {
        messages.add(message);
        notifyDataSetChanged();
    }

    public void replaceTransient(ChatMessage message) {
        for (int i = messages.size() - 1; i >= 0; i--) {
            if (messages.get(i).state != ChatMessage.State.READY) {
                messages.set(i, message);
                notifyDataSetChanged();
                return;
            }
        }
        messages.add(message);
        notifyDataSetChanged();
    }

    @Override public int getCount() { return messages.size(); }
    @Override public ChatMessage getItem(int position) { return messages.get(position); }
    @Override public long getItemId(int position) { return messages.get(position).id; }

    @Override
    public View getView(int position, View convertView, ViewGroup parent) {
        ChatMessage message = getItem(position);
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.VERTICAL);
        row.setGravity(message.isUser() ? Gravity.END : Gravity.START);
        row.setPadding(Ui.dp(context, 16), Ui.dp(context, 7),
                Ui.dp(context, 16), Ui.dp(context, 7));

        if (!message.isUser()) row.addView(assistantLabel(message));

        int availableWidth = context.getResources().getDisplayMetrics().widthPixels - Ui.dp(context, 62);
        int maxBubbleWidth = Math.min(availableWidth, Ui.dp(context, 560));
        LinearLayout bubble = new LinearLayout(context);
        bubble.setOrientation(LinearLayout.VERTICAL);
        bubble.setPadding(Ui.dp(context, 14), Ui.dp(context, 12),
                Ui.dp(context, 14), Ui.dp(context, 12));
        int bubbleColor = message.isUser() ? Ui.VIOLET_DARK
                : message.state == ChatMessage.State.ERROR ? 0xFF2B1B25 : Ui.CARD;
        int borderColor = message.isUser() ? Ui.VIOLET_DARK
                : message.state == ChatMessage.State.ERROR ? 0xFF65303F : 0xFF222E40;
        bubble.setBackground(Ui.roundedStroke(bubbleColor, borderColor, 18, context));
        bubble.setMinimumWidth(Ui.dp(context, 64));

        if (message.state == ChatMessage.State.PENDING) {
            addPending(bubble, message.content);
        } else {
            addFormattedContent(bubble, message.content, maxBubbleWidth - Ui.dp(context, 28));
            if (message.state == ChatMessage.State.ERROR) addRetryButton(bubble);
        }

        bubble.setLayoutParams(new LinearLayout.LayoutParams(maxBubbleWidth, ViewGroup.LayoutParams.WRAP_CONTENT));
        row.addView(bubble);

        if (message.state == ChatMessage.State.READY && !message.isUser()) {
            if (!message.sources.isEmpty()) row.addView(sourceList(message.sources, availableWidth));
            row.addView(actionRow(message));
        }
        return row;
    }

    private void addPending(LinearLayout bubble, String value) {
        LinearLayout progressRow = new LinearLayout(context);
        progressRow.setGravity(Gravity.CENTER_VERTICAL);
        ProgressBar progress = new ProgressBar(context, null, android.R.attr.progressBarStyleSmall);
        progress.setIndeterminateTintList(ColorStateList.valueOf(Ui.CYAN));
        progressRow.addView(progress, new LinearLayout.LayoutParams(Ui.dp(context, 22), Ui.dp(context, 22)));
        TextView status = Ui.text(context, value, 14, Ui.MUTED);
        LinearLayout.LayoutParams statusParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        statusParams.leftMargin = Ui.dp(context, 10);
        progressRow.addView(status, statusParams);
        bubble.addView(progressRow);
    }

    private void addFormattedContent(LinearLayout bubble, String markdown, int maxWidth) {
        List<MarkdownParser.Block> blocks = MarkdownParser.parse(markdown);
        for (int i = 0; i < blocks.size(); i++) {
            MarkdownParser.Block block = blocks.get(i);
            View child = block.code ? codeBlock(block, maxWidth) : textBlock(block.text, maxWidth);
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            if (i > 0) params.topMargin = Ui.dp(context, 9);
            bubble.addView(child, params);
        }
    }

    private View textBlock(String markdown, int maxWidth) {
        TextView content = Ui.text(context, "", 15, Ui.TEXT);
        content.setText(TextUtilsEx.renderMarkdown(markdown));
        content.setLineSpacing(0, 1.08f);
        content.setTextIsSelectable(true);
        content.setMaxWidth(maxWidth);
        return content;
    }

    private View codeBlock(MarkdownParser.Block block, int maxWidth) {
        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(Ui.roundedStroke(0xFF090E17, 0xFF2A3A4D, 12, context));
        card.setClipToOutline(true);

        LinearLayout header = new LinearLayout(context);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(context, 11), 0, Ui.dp(context, 5), 0);
        header.setBackgroundColor(0xFF101824);
        TextView language = Ui.text(context, block.language, 10, 0xFF8FA2B8);
        language.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        language.setLetterSpacing(0.08f);
        header.addView(language, new LinearLayout.LayoutParams(0, Ui.dp(context, 34), 1f));
        TextView copy = Ui.text(context, "КОПИРОВАТЬ", 9, Ui.CYAN);
        copy.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        copy.setGravity(Gravity.CENTER);
        copy.setPadding(Ui.dp(context, 9), 0, Ui.dp(context, 9), 0);
        copy.setBackground(Ui.ripple(Ui.rounded(Color.TRANSPARENT, 8, context), 0x3339D9C8));
        copy.setOnClickListener(v -> copyCode(block.text));
        header.addView(copy, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(context, 34)));
        card.addView(header, new LinearLayout.LayoutParams(maxWidth, Ui.dp(context, 34)));

        HorizontalScrollView horizontal = new HorizontalScrollView(context);
        horizontal.setFillViewport(false);
        horizontal.setHorizontalScrollBarEnabled(true);
        horizontal.setBackgroundColor(0xFF090E17);
        TextView code = Ui.text(context, "", 13, 0xFFD9E3F0);
        code.setTypeface(Typeface.MONOSPACE);
        code.setText(SyntaxHighlighter.highlight(block.text, block.language));
        code.setTextIsSelectable(true);
        code.setHorizontallyScrolling(true);
        code.setPadding(Ui.dp(context, 12), Ui.dp(context, 11),
                Ui.dp(context, 16), Ui.dp(context, 12));
        horizontal.addView(code, new HorizontalScrollView.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        card.addView(horizontal, new LinearLayout.LayoutParams(maxWidth, ViewGroup.LayoutParams.WRAP_CONTENT));
        return card;
    }

    private void addRetryButton(LinearLayout bubble) {
        Button retry = new Button(context);
        retry.setText("Повторить");
        retry.setTextColor(Ui.WARNING);
        retry.setTextSize(13);
        retry.setAllCaps(false);
        retry.setBackground(Ui.ripple(Ui.rounded(0x22FFA85C, 12, context), 0x33FFA85C));
        retry.setOnClickListener(v -> listener.onRetry());
        LinearLayout.LayoutParams retryParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(context, 42));
        retryParams.topMargin = Ui.dp(context, 10);
        bubble.addView(retry, retryParams);
    }

    private View assistantLabel(ChatMessage message) {
        LinearLayout label = new LinearLayout(context);
        label.setGravity(Gravity.CENTER_VERTICAL);
        label.setPadding(Ui.dp(context, 4), 0, 0, Ui.dp(context, 6));
        TextView spark = Ui.text(context, "✦", 14, Ui.CYAN);
        label.addView(spark);
        TextView name = Ui.text(context,
                message.state == ChatMessage.State.ERROR ? "Не удалось ответить" : "kvsai",
                12, message.state == ChatMessage.State.ERROR ? Ui.DANGER : Ui.MUTED);
        name.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.leftMargin = Ui.dp(context, 6);
        label.addView(name, params);
        return label;
    }

    private View sourceList(List<SearchSource> sources, int maxWidth) {
        LinearLayout container = new LinearLayout(context);
        container.setOrientation(LinearLayout.VERTICAL);
        container.setPadding(0, Ui.dp(context, 7), 0, 0);
        container.setMinimumWidth(Math.min(maxWidth, Ui.dp(context, 560)));

        TextView heading = Ui.text(context, "ИСТОЧНИКИ", 10, Ui.DIM);
        heading.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        heading.setLetterSpacing(0.12f);
        heading.setPadding(Ui.dp(context, 5), Ui.dp(context, 5), 0, Ui.dp(context, 5));
        container.addView(heading);

        int limit = Math.min(5, sources.size());
        for (int i = 0; i < limit; i++) {
            SearchSource source = sources.get(i);
            TextView item = Ui.text(context, (i + 1) + "  " + source.title + "  ↗", 12, Ui.CYAN);
            item.setMaxLines(2);
            item.setEllipsize(android.text.TextUtils.TruncateAt.END);
            item.setPadding(Ui.dp(context, 11), Ui.dp(context, 9),
                    Ui.dp(context, 11), Ui.dp(context, 9));
            item.setBackground(Ui.ripple(
                    Ui.roundedStroke(0xB20E131D, 0xFF20333A, 11, context), 0x2539D9C8));
            item.setOnClickListener(v -> openUrl(source.url));
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    Math.min(maxWidth, Ui.dp(context, 560)), ViewGroup.LayoutParams.WRAP_CONTENT);
            params.bottomMargin = Ui.dp(context, 5);
            container.addView(item, params);
        }
        return container;
    }

    private View actionRow(ChatMessage message) {
        LinearLayout actions = new LinearLayout(context);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        actions.setPadding(Ui.dp(context, 2), Ui.dp(context, 2), 0, 0);
        ImageButton copy = smallAction(R.drawable.ic_copy, "Копировать");
        copy.setOnClickListener(v -> copy(message.content));
        actions.addView(copy, new LinearLayout.LayoutParams(Ui.dp(context, 38), Ui.dp(context, 34)));
        ImageButton share = smallAction(R.drawable.ic_share, "Поделиться");
        share.setOnClickListener(v -> share(message.content));
        actions.addView(share, new LinearLayout.LayoutParams(Ui.dp(context, 38), Ui.dp(context, 34)));
        return actions;
    }

    private ImageButton smallAction(int icon, String description) {
        ImageButton button = new ImageButton(context);
        button.setImageResource(icon);
        button.setContentDescription(description);
        button.setPadding(Ui.dp(context, 8), Ui.dp(context, 7), Ui.dp(context, 8), Ui.dp(context, 7));
        button.setBackground(Ui.ripple(Ui.rounded(Color.TRANSPARENT, 10, context), 0x228B5CF6));
        return button;
    }

    private void copyCode(String text) {
        ClipboardManager manager = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
        if (manager != null) manager.setPrimaryClip(ClipData.newPlainText("Код", text));
        DebugLog.log("UI", "Code block copied, chars=" + text.length());
        Toast.makeText(context, "Код скопирован", Toast.LENGTH_SHORT).show();
    }

    private void copy(String text) {
        ClipboardManager manager = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
        if (manager != null) manager.setPrimaryClip(ClipData.newPlainText("Ответ kvsai", text));
        DebugLog.log("UI", "Assistant answer copied, chars=" + text.length());
        Toast.makeText(context, "Ответ скопирован", Toast.LENGTH_SHORT).show();
    }

    private void share(String text) {
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setType("text/plain");
        intent.putExtra(Intent.EXTRA_TEXT, text + "\n\n— kvsai");
        DebugLog.log("UI", "Share sheet opened for answer, chars=" + text.length());
        context.startActivity(Intent.createChooser(intent, "Поделиться ответом"));
    }

    private void openUrl(String url) {
        try {
            if (url == null || !(url.startsWith("https://") || url.startsWith("http://"))) return;
            DebugLog.log("UI", "Opening source: " + url);
            context.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception error) {
            DebugLog.error("UI", error);
            Toast.makeText(context, "Не удалось открыть ссылку", Toast.LENGTH_SHORT).show();
        }
    }
}
