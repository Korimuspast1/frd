package ai.iskra.chat.util;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Splits Markdown into normal text and fenced code blocks. */
public final class MarkdownParser {
    public static final class Block {
        public final boolean code;
        public final String text;
        public final String language;

        private Block(boolean code, String text, String language) {
            this.code = code;
            this.text = text;
            this.language = language;
        }

        public static Block text(String text) {
            return new Block(false, text, "");
        }

        public static Block code(String code, String language) {
            return new Block(true, code, normalizeLanguage(language));
        }
    }

    private MarkdownParser() {}

    public static List<Block> parse(String markdown) {
        String normalized = markdown == null ? "" : markdown.replace("\r\n", "\n").replace('\r', '\n');
        String[] lines = normalized.split("\n", -1);
        List<Block> blocks = new ArrayList<>();
        StringBuilder buffer = new StringBuilder();
        boolean inCode = false;
        String language = "plaintext";
        String fence = "```";

        for (String line : lines) {
            String trimmed = line.trim();
            boolean isFence = trimmed.startsWith("```") || trimmed.startsWith("~~~");
            if (isFence) {
                String marker = trimmed.startsWith("~~~") ? "~~~" : "```";
                if (!inCode) {
                    flushText(blocks, buffer);
                    inCode = true;
                    fence = marker;
                    language = trimmed.length() > 3 ? trimmed.substring(3).trim() : "plaintext";
                    if (language.startsWith("{")) language = language.replace("{", "").replace("}", "").replace(".", "");
                    if (language.isEmpty()) language = "plaintext";
                } else if (trimmed.startsWith(fence)) {
                    flushCode(blocks, buffer, language);
                    inCode = false;
                    language = "plaintext";
                } else {
                    appendLine(buffer, line);
                }
            } else {
                appendLine(buffer, line);
            }
        }

        if (inCode) flushCode(blocks, buffer, language);
        else flushText(blocks, buffer);
        if (blocks.isEmpty()) blocks.add(Block.text(normalized));
        return blocks;
    }

    private static void appendLine(StringBuilder buffer, String line) {
        if (buffer.length() > 0) buffer.append('\n');
        buffer.append(line);
    }

    private static void flushText(List<Block> blocks, StringBuilder buffer) {
        String text = trimBoundaryNewlines(buffer.toString());
        if (!text.isEmpty()) blocks.add(Block.text(text));
        buffer.setLength(0);
    }

    private static void flushCode(List<Block> blocks, StringBuilder buffer, String language) {
        String code = trimOneTrailingNewline(buffer.toString());
        blocks.add(Block.code(code, language));
        buffer.setLength(0);
    }

    private static String trimBoundaryNewlines(String value) {
        int start = 0;
        int end = value.length();
        while (start < end && value.charAt(start) == '\n') start++;
        while (end > start && value.charAt(end - 1) == '\n') end--;
        return value.substring(start, end);
    }

    private static String trimOneTrailingNewline(String value) {
        return value.endsWith("\n") ? value.substring(0, value.length() - 1) : value;
    }

    public static String normalizeLanguage(String raw) {
        String language = raw == null ? "" : raw.trim().toLowerCase(Locale.US);
        int space = language.indexOf(' ');
        if (space >= 0) language = language.substring(0, space);
        switch (language) {
            case "": case "text": case "txt": case "plain": return "plaintext";
            case "py": return "python";
            case "js": case "jsx": return "javascript";
            case "ts": case "tsx": return "typescript";
            case "kt": case "kts": return "kotlin";
            case "java": return "java";
            case "sh": case "shell": case "zsh": return "bash";
            case "cs": case "csharp": return "c#";
            case "cpp": case "cxx": case "cc": return "c++";
            case "yml": return "yaml";
            case "md": return "markdown";
            default: return language;
        }
    }
}
