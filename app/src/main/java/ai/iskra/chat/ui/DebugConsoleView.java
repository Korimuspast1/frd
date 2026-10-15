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
        setPadding(Ui.dp(context, 8), Ui.dp(context, 7), Ui.dp(context, 8), Ui.dp(context, 7));
        setBackground(Ui.glass(context, 20));
        setElevation(Ui.dp(context, 8));

        LinearLayout header = new LinearLayout(context);
        header.setOrientation(HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(context, 10), 0, Ui.dp(context, 5), 0);
        header.setBackground(Ui.glassBlue(context, 13));

        TextView title = Ui.text(context, "●  DEBUG CONSOLE • LIVE", 10, 0xFF73B7FF);
        title.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        header.addView(title, new LayoutParams(0, Ui.dp(context, 34), 1f));

        counter = consoleButton("0");
        counter.setTextColor(0xFFA5AAB4);
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
        scroll.setBackgroundColor(Color.TRANSPARENT);
        output = Ui.text(context, "", 9.5f, 0xFFC5DDF8);
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
        TextView button = Ui.text(getContext(), label, 9, 0xFF83BFFF);
        button.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        button.setGravity(Gravity.CENTER);
        button.setBackground(Ui.ripple(Ui.rounded(Color.TRANSPARENT, 7, getContext()), 0x334A9CFF));
        return button;
    }

    private void toggleCollapsed() {
        collapsed = !collapsed;
        scroll.setVisibility(collapsed ? GONE : VISIBLE);
        collapse.setText(collapsed ? "▲" : "▼");
        ViewGroup.LayoutParams params = getLayoutParams();
        if (params != null) {
            params.height = Ui.dp(getContext(), collapsed ? 48 : 180);
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
