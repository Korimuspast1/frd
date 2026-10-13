package ai.iskra.chat.ui;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import ai.iskra.chat.util.DebugLog;
import ai.iskra.chat.util.Ui;

public final class DebugConsoleView extends LinearLayout implements DebugLog.Listener {
    private final TextView output;
    private final TextView counter;
    private final ScrollView scroll;
    private final TextView collapse;
    private boolean registered;
    private boolean collapsed;

    public DebugConsoleView(Context context) {
        super(context);
        setOrientation(VERTICAL);
        setBackground(Ui.roundedStroke(0xFF05080D, 0xFF244138, 0, context));

        LinearLayout header = new LinearLayout(context);
        header.setOrientation(HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(context, 10), 0, Ui.dp(context, 5), 0);
        header.setBackgroundColor(0xFF09120F);

        TextView title = Ui.text(context, "●  DEBUG CONSOLE • LIVE", 10, 0xFF58E6AE);
        title.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        header.addView(title, new LayoutParams(0, Ui.dp(context, 34), 1f));

        counter = consoleButton("0");
        counter.setTextColor(0xFF86A69A);
        header.addView(counter, new LayoutParams(Ui.dp(context, 42), Ui.dp(context, 34)));

        TextView copy = consoleButton("COPY");
        copy.setOnClickListener(v -> copyLog());
        header.addView(copy, new LayoutParams(Ui.dp(context, 50), Ui.dp(context, 34)));

        TextView clear = consoleButton("CLEAR");
        clear.setOnClickListener(v -> DebugLog.clear());
        header.addView(clear, new LayoutParams(Ui.dp(context, 54), Ui.dp(context, 34)));

        collapse = consoleButton("▼");
        collapse.setOnClickListener(v -> toggleCollapsed());
        header.addView(collapse, new LayoutParams(Ui.dp(context, 38), Ui.dp(context, 34)));
        addView(header, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(context, 34)));

        scroll = new ScrollView(context);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(0xFF05080D);
        output = Ui.text(context, "", 9.5f, 0xFFB2F5D8);
        output.setTypeface(Typeface.MONOSPACE);
        output.setTextIsSelectable(true);
        output.setLineSpacing(0, 1.05f);
        output.setPadding(Ui.dp(context, 9), Ui.dp(context, 6), Ui.dp(context, 9), Ui.dp(context, 8));
        scroll.addView(output, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addView(scroll, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        refresh();
    }

    private TextView consoleButton(String label) {
        TextView button = Ui.text(getContext(), label, 9, 0xFF58E6AE);
        button.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        button.setGravity(Gravity.CENTER);
        button.setBackground(Ui.ripple(Ui.rounded(Color.TRANSPARENT, 5, getContext()), 0x3358E6AE));
        return button;
    }

    private void toggleCollapsed() {
        collapsed = !collapsed;
        scroll.setVisibility(collapsed ? GONE : VISIBLE);
        collapse.setText(collapsed ? "▲" : "▼");
        ViewGroup.LayoutParams params = getLayoutParams();
        if (params != null) {
            params.height = Ui.dp(getContext(), collapsed ? 34 : 180);
            setLayoutParams(params);
        }
        DebugLog.log("UI", collapsed ? "Debug console collapsed" : "Debug console expanded");
    }

    private void copyLog() {
        ClipboardManager clipboard = (ClipboardManager) getContext().getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText("kvsai debug log", DebugLog.snapshot()));
            Toast.makeText(getContext(), "Debug-лог скопирован", Toast.LENGTH_SHORT).show();
        }
    }

    private void refresh() {
        output.setText(DebugLog.snapshot());
        counter.setText(String.valueOf(DebugLog.size()));
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (!registered) {
            registered = true;
            DebugLog.register(this);
        }
        refresh();
    }

    @Override protected void onDetachedFromWindow() {
        DebugLog.unregister(this);
        registered = false;
        super.onDetachedFromWindow();
    }

    @Override public void onDebugLogChanged() {
        if (isAttachedToWindow()) refresh();
    }
}
