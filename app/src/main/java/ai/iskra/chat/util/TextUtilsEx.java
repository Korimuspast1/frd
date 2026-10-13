package ai.iskra.chat.util;

import android.text.Html;
import android.text.Spanned;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class TextUtilsEx {
    private static final Pattern BOLD = Pattern.compile("\\*\\*(.+?)\\*\\*");
    private static final Pattern CODE = Pattern.compile("`([^`]+)`");

    private TextUtilsEx() {}

    public static Spanned renderMarkdown(String input) {
        if (input == null) input = "";
        String safe = input.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;");
        safe = replace(BOLD, safe, "<b>$1</b>");
        safe = replace(CODE, safe, "<tt>$1</tt>");

        StringBuilder out = new StringBuilder();
        String[] lines = safe.split("\\r?\\n", -1);
        for (String line : lines) {
            if (line.startsWith("### ")) {
                out.append("<b>").append(line.substring(4)).append("</b>");
            } else if (line.startsWith("## ")) {
                out.append("<b><big>").append(line.substring(3)).append("</big></b>");
            } else if (line.startsWith("# ")) {
                out.append("<b><big>").append(line.substring(2)).append("</big></b>");
            } else if (line.startsWith("- ") || line.startsWith("* ")) {
                out.append("• ").append(line.substring(2));
            } else {
                out.append(line);
            }
            out.append("<br>");
        }
        return Html.fromHtml(out.toString(), Html.FROM_HTML_MODE_LEGACY);
    }

    private static String replace(Pattern pattern, String source, String replacement) {
        Matcher matcher = pattern.matcher(source);
        StringBuffer buffer = new StringBuffer();
        while (matcher.find()) {
            matcher.appendReplacement(buffer, Matcher.quoteReplacement(replacement)
                    .replace("\\$1", Matcher.quoteReplacement(matcher.group(1))));
        }
        matcher.appendTail(buffer);
        return buffer.toString();
    }

    public static String compact(String text, int maxLength) {
        if (text == null) return "";
        String compact = text.replaceAll("\\s+", " ").trim();
        if (compact.length() <= maxLength) return compact;
        int end = compact.lastIndexOf(' ', maxLength - 1);
        if (end < maxLength / 2) end = maxLength - 1;
        return compact.substring(0, end).trim() + "…";
    }

    public static String chatTitle(String question) {
        String clean = compact(question, 48)
                .replaceAll("[?!.]+$", "")
                .trim();
        if (clean.isEmpty()) return "Новый чат";
        return clean.substring(0, 1).toUpperCase(Locale.getDefault()) + clean.substring(1);
    }
}
