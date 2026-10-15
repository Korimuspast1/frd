package ai.iskra.chat.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/** A short-lived, privacy-conscious attachment prepared for one assistant request. */
public final class AttachmentData {
    public final String displayName;
    public final String mimeType;
    public final long sourceBytes;
    public final String extractedText;
    public final List<byte[]> visualPages;
    public final int pageCount;

    public AttachmentData(String displayName, String mimeType, long sourceBytes,
                          String extractedText, List<byte[]> visualPages, int pageCount) {
        this.displayName = clean(displayName, "Вложение");
        this.mimeType = clean(mimeType, "application/octet-stream");
        this.sourceBytes = Math.max(0L, sourceBytes);
        this.extractedText = extractedText == null ? "" : extractedText.trim();
        List<byte[]> pages = new ArrayList<>();
        if (visualPages != null) {
            for (byte[] page : visualPages) {
                if (page != null && page.length > 0) pages.add(page);
            }
        }
        this.visualPages = Collections.unmodifiableList(pages);
        this.pageCount = Math.max(pageCount, pages.size());
    }

    public boolean hasText() {
        return !extractedText.isEmpty();
    }

    public boolean hasVisualContent() {
        return !visualPages.isEmpty();
    }

    public boolean isImage() {
        return mimeType.toLowerCase(Locale.US).startsWith("image/");
    }

    public boolean isPdf() {
        return "application/pdf".equalsIgnoreCase(mimeType)
                || displayName.toLowerCase(Locale.US).endsWith(".pdf");
    }

    public String historyLabel() {
        StringBuilder value = new StringBuilder("📎 ").append(displayName);
        if (isPdf() && pageCount > 0) value.append(" • ").append(pageCount).append(" стр.");
        else if (isImage()) value.append(" • изображение");
        else if (hasText()) value.append(" • текстовый файл");
        return value.toString();
    }

    public String requestContext() {
        StringBuilder value = new StringBuilder();
        value.append("Пользователь приложил файл «").append(displayName).append("»")
                .append(" (тип ").append(mimeType).append(", размер ")
                .append(humanSize(sourceBytes)).append(").");
        if (isPdf() && pageCount > visualPages.size()) {
            value.append(" Для визуального анализа переданы первые ")
                    .append(visualPages.size()).append(" из ").append(pageCount).append(" страниц.");
        }
        if (hasText()) {
            value.append("\n\nСодержимое файла:\n---\n")
                    .append(extractedText)
                    .append("\n---");
        }
        return value.toString();
    }

    public String compactDescription() {
        if (isImage()) return "Фото • " + humanSize(sourceBytes);
        if (isPdf()) return "PDF • " + pageCount + " стр. • " + humanSize(sourceBytes);
        return (hasText() ? "Текст • " : "Файл • ") + humanSize(sourceBytes);
    }

    private static String clean(String value, String fallback) {
        if (value == null || value.trim().isEmpty()) return fallback;
        return value.trim();
    }

    private static String humanSize(long bytes) {
        if (bytes < 1024) return bytes + " Б";
        if (bytes < 1024L * 1024L) return String.format(Locale.US, "%.1f КБ", bytes / 1024f);
        return String.format(Locale.US, "%.1f МБ", bytes / (1024f * 1024f));
    }
}
