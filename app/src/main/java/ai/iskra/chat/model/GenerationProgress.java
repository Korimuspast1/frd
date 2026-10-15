package ai.iskra.chat.model;

/** Live usage information while an AI provider is generating a response. */
public final class GenerationProgress {
    public final int promptTokens;
    public final int completionTokens;
    public final int generatedCharacters;
    public final boolean exact;

    public GenerationProgress(int promptTokens, int completionTokens,
                              int generatedCharacters, boolean exact) {
        this.promptTokens = Math.max(0, promptTokens);
        this.completionTokens = Math.max(0, completionTokens);
        this.generatedCharacters = Math.max(0, generatedCharacters);
        this.exact = exact;
    }

    public int totalTokens() {
        long total = (long) promptTokens + completionTokens;
        return total > Integer.MAX_VALUE ? Integer.MAX_VALUE : (int) total;
    }

    public boolean exact() {
        return exact;
    }

    public String label() {
        if (exact) {
            String input = promptTokens > 0 ? " • вход: " + promptTokens : "";
            return completionTokens + " токенов" + input + " • точно";
        }
        if (generatedCharacters == 0) return "ожидаю первый токен…";
        return "≈ " + completionTokens + " токенов • " + generatedCharacters + " симв.";
    }
}
