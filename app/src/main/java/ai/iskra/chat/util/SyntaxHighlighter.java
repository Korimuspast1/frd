package ai.iskra.chat.util;

import android.graphics.Color;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.text.style.StyleSpan;
import android.graphics.Typeface;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Lightweight, dependency-free highlighting for fenced code in common languages. */
public final class SyntaxHighlighter {
    private static final int COLOR_COMMENT = Color.rgb(112, 132, 154);
    private static final int COLOR_STRING = Color.rgb(244, 184, 126);
    private static final int COLOR_KEYWORD = Color.rgb(196, 155, 255);
    private static final int COLOR_NUMBER = Color.rgb(91, 211, 224);
    private static final int COLOR_FUNCTION = Color.rgb(102, 208, 255);
    private static final int COLOR_LITERAL = Color.rgb(255, 127, 159);
    private static final int COLOR_TAG = Color.rgb(255, 139, 122);

    private SyntaxHighlighter() {}

    public static CharSequence highlight(String code, String rawLanguage) {
        String source = code == null ? "" : code;
        String language = MarkdownParser.normalizeLanguage(rawLanguage);
        SpannableString output = new SpannableString(source);
        if (source.isEmpty() || "plaintext".equals(language)) return output;

        boolean[] protectedChars = new boolean[source.length()];
        applyComments(output, source, language, protectedChars);
        applyStrings(output, source, language, protectedChars);

        String keywords = keywords(language);
        if (!keywords.isEmpty()) {
            int flags = ("sql".equals(language) ? Pattern.CASE_INSENSITIVE : 0) | Pattern.MULTILINE;
            apply(output, Pattern.compile("\\b(?:" + keywords + ")\\b", flags),
                    COLOR_KEYWORD, protectedChars, false, true);
        }
        apply(output, Pattern.compile("\\b(?:true|false|null|none|nil|undefined|nan|inf)\\b",
                        Pattern.CASE_INSENSITIVE), COLOR_LITERAL, protectedChars, false, true);
        apply(output, Pattern.compile("(?<![\\w.])(?:0x[0-9a-fA-F]+|0b[01]+|\\d+(?:\\.\\d+)?)(?![\\w.])"),
                COLOR_NUMBER, protectedChars, false, false);
        apply(output, Pattern.compile("\\b[A-Za-z_$][A-Za-z0-9_$]*(?=\\s*\\()"),
                COLOR_FUNCTION, protectedChars, false, false);

        if (isMarkup(language)) {
            apply(output, Pattern.compile("</?[A-Za-z][A-Za-z0-9:_-]*"),
                    COLOR_TAG, protectedChars, false, false);
        }
        return output;
    }

    private static void applyComments(SpannableString output, String source, String language,
                                      boolean[] protectedChars) {
        apply(output, Pattern.compile("/\\*.*?\\*/", Pattern.DOTALL),
                COLOR_COMMENT, protectedChars, true, false);
        if (isMarkup(language)) {
            apply(output, Pattern.compile("<!--.*?-->", Pattern.DOTALL),
                    COLOR_COMMENT, protectedChars, true, false);
        }
        if ("python".equals(language) || "bash".equals(language) || "ruby".equals(language)
                || "yaml".equals(language) || "r".equals(language)) {
            apply(output, Pattern.compile("(?m)#.*$"), COLOR_COMMENT, protectedChars, true, false);
        } else if ("sql".equals(language) || "lua".equals(language)) {
            apply(output, Pattern.compile("(?m)--.*$"), COLOR_COMMENT, protectedChars, true, false);
        } else if (!"json".equals(language) && !isMarkup(language) && !"css".equals(language)) {
            apply(output, Pattern.compile("(?m)//.*$"), COLOR_COMMENT, protectedChars, true, false);
        }
    }

    private static void applyStrings(SpannableString output, String source, String language,
                                     boolean[] protectedChars) {
        if ("python".equals(language)) {
            apply(output, Pattern.compile("(?:'''|\\\"\\\"\\\").*?(?:'''|\\\"\\\"\\\")", Pattern.DOTALL),
                    COLOR_STRING, protectedChars, true, false);
        }
        apply(output, Pattern.compile("\\\"(?:\\\\.|[^\\\"\\\\])*\\\""),
                COLOR_STRING, protectedChars, true, false);
        apply(output, Pattern.compile("'(?:\\\\.|[^'\\\\])*'"),
                COLOR_STRING, protectedChars, true, false);
        if ("javascript".equals(language) || "typescript".equals(language)) {
            apply(output, Pattern.compile("`(?:\\\\.|[^`\\\\])*`", Pattern.DOTALL),
                    COLOR_STRING, protectedChars, true, false);
        }
    }

    private static void apply(SpannableString output, Pattern pattern, int color,
                              boolean[] occupied, boolean protect, boolean bold) {
        Matcher matcher = pattern.matcher(output.toString());
        while (matcher.find()) {
            int start = matcher.start();
            int end = matcher.end();
            if (start == end || overlaps(occupied, start, end)) continue;
            output.setSpan(new ForegroundColorSpan(color), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            if (bold) output.setSpan(new StyleSpan(Typeface.BOLD), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            if (protect) {
                for (int i = Math.max(0, start); i < Math.min(occupied.length, end); i++) occupied[i] = true;
            }
        }
    }

    private static boolean overlaps(boolean[] occupied, int start, int end) {
        for (int i = Math.max(0, start); i < Math.min(occupied.length, end); i++) {
            if (occupied[i]) return true;
        }
        return false;
    }

    private static boolean isMarkup(String language) {
        return "html".equals(language) || "xml".equals(language) || "svg".equals(language)
                || "vue".equals(language) || "svelte".equals(language);
    }

    private static String keywords(String language) {
        switch (language.toLowerCase(Locale.US)) {
            case "python":
                return "and|as|assert|async|await|break|case|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|match|nonlocal|not|or|pass|raise|return|try|while|with|yield";
            case "java": case "kotlin": case "c": case "c++": case "c#": case "dart": case "swift":
                return "abstract|actual|as|async|await|base|bool|break|by|case|catch|char|class|const|constructor|continue|data|decimal|default|delegate|do|double|dynamic|else|enum|event|expect|extends|extern|false|final|finally|fixed|float|for|fun|func|get|goto|if|implements|import|in|init|inline|int|interface|internal|is|let|lock|long|namespace|native|new|null|object|operator|out|override|package|params|private|protected|protocol|public|readonly|record|ref|return|sealed|set|short|sizeof|static|string|struct|super|suspend|switch|synchronized|this|throw|throws|transient|true|try|typealias|typeof|uint|ulong|unchecked|unsafe|ushort|using|val|var|virtual|void|volatile|when|where|while|with|yield";
            case "javascript": case "typescript":
                return "as|async|await|break|case|catch|class|const|continue|debugger|declare|default|delete|do|else|enum|export|extends|finally|for|from|function|get|if|implements|import|in|instanceof|interface|keyof|let|new|of|private|protected|public|readonly|return|set|static|super|switch|this|throw|try|type|typeof|var|void|while|with|yield";
            case "go":
                return "break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|interface|map|package|range|return|select|struct|switch|type|var";
            case "rust":
                return "as|async|await|break|const|continue|crate|dyn|else|enum|extern|false|fn|for|if|impl|in|let|loop|match|mod|move|mut|pub|ref|return|self|static|struct|super|trait|true|type|unsafe|use|where|while";
            case "sql":
                return "add|all|alter|and|any|as|asc|between|by|case|check|column|constraint|create|database|default|delete|desc|distinct|drop|else|end|exists|foreign|from|full|group|having|in|index|inner|insert|into|is|join|key|left|like|limit|not|null|on|or|order|outer|primary|references|right|row|select|set|table|then|union|unique|update|values|view|when|where|with";
            case "bash":
                return "case|do|done|elif|else|esac|export|fi|for|function|if|in|local|readonly|return|select|then|time|until|while";
            case "php":
                return "abstract|and|array|as|break|callable|case|catch|class|clone|const|continue|declare|default|do|echo|else|elseif|empty|enddeclare|endfor|endforeach|endif|endswitch|endwhile|enum|eval|exit|extends|final|finally|fn|for|foreach|function|global|goto|if|implements|include|instanceof|insteadof|interface|isset|list|match|namespace|new|or|print|private|protected|public|readonly|require|return|static|switch|throw|trait|try|unset|use|var|while|xor|yield";
            case "css":
                return "important|inherit|initial|revert|unset|var";
            default:
                return "break|case|catch|class|const|continue|def|do|else|enum|export|extends|false|final|for|function|if|import|in|interface|let|new|null|private|protected|public|return|static|struct|switch|this|throw|true|try|type|var|void|while";
        }
    }
}
