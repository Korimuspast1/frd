package ai.iskra.chat.data;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.pdf.PdfRenderer;
import android.media.ExifInterface;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.util.Xml;
import android.webkit.MimeTypeMap;

import ai.iskra.chat.model.AttachmentData;
import ai.iskra.chat.util.DebugLog;

import org.xmlpull.v1.XmlPullParser;

import java.io.BufferedInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Reads a user-selected document without broad storage permissions. */
public final class AttachmentReader {
    /** Public attachment ceiling: exactly 66 MiB. Processing remains bounded below this limit. */
    private static final long MAX_SOURCE_BYTES = 66L * 1024L * 1024L;
    private static final int MAX_TEXT_BYTES = 768 * 1024;
    private static final int MAX_TEXT_CHARS = 60_000;
    private static final int MAX_IMAGE_EDGE = 1_600;
    private static final int MAX_PDF_PAGES = 4;
    private static final String CACHE_PREFIX = "kvsai-attachment-";

    private final Context context;
    private final ContentResolver resolver;

    public AttachmentReader(Context context) {
        this.context = context.getApplicationContext();
        this.resolver = this.context.getContentResolver();
    }

    public AttachmentData read(Uri uri) throws Exception {
        if (uri == null) throw new IOException("Файл не выбран");
        Metadata supplied = metadata(uri);
        if (supplied.size > MAX_SOURCE_BYTES) {
            throw tooLarge();
        }

        // A content provider may omit or lie about SIZE. Materialising through a bounded stream
        // guarantees that an unknown-size URI can never bypass the 66 MiB ceiling, while keeping
        // large compressed documents and photos off the Java heap.
        File local = copyToBoundedCache(uri);
        Metadata metadata = new Metadata(supplied.name, supplied.mime, local.length());
        String lowerName = metadata.name.toLowerCase(Locale.US);
        DebugLog.log("FILE", "Reading attachment; nameChars=" + metadata.name.length() + ", type=" +
                metadata.mime + ", bytes=" + metadata.size);

        try {
            if (metadata.mime.startsWith("image/") || isImageName(lowerName)) {
                byte[] jpeg = prepareImage(local);
                return new AttachmentData(metadata.name, metadata.mime, metadata.size, "",
                        Collections.singletonList(jpeg), 1);
            }
            if ("application/pdf".equals(metadata.mime) || lowerName.endsWith(".pdf")) {
                return readPdf(local, metadata);
            }
            if (isOfficeArchive(lowerName, metadata.mime)) {
                String text = extractOfficeText(local, officeType(lowerName, metadata.mime));
                if (text.isEmpty()) throw new IOException("В этом документе не удалось найти читаемый текст");
                return new AttachmentData(metadata.name, metadata.mime, metadata.size,
                        trimText(text), Collections.emptyList(), 0);
            }
            if (isText(metadata.mime, lowerName)) {
                byte[] bytes = readPrefix(local, MAX_TEXT_BYTES);
                if (looksBinary(bytes)) throw new IOException("Файл выглядит как двоичный и не содержит обычного текста");
                String text = new String(bytes, StandardCharsets.UTF_8).replace("\u0000", "");
                if (local.length() > bytes.length) text += "\n\n[Показана начальная часть большого файла]";
                return new AttachmentData(metadata.name, metadata.mime, metadata.size,
                        trimText(text), Collections.emptyList(), 0);
            }
            throw new IOException("Этот формат пока нельзя прочитать. Выберите фото, PDF, DOCX, TXT, Markdown, JSON, CSV или файл с кодом");
        } finally {
            if (!local.delete()) local.deleteOnExit();
        }
    }

    private AttachmentData readPdf(File file, Metadata metadata) throws Exception {
        List<byte[]> pages = new ArrayList<>();
        try (ParcelFileDescriptor descriptor = ParcelFileDescriptor.open(
                file, ParcelFileDescriptor.MODE_READ_ONLY)) {
            try (PdfRenderer renderer = new PdfRenderer(descriptor)) {
                int pageCount = renderer.getPageCount();
                int limit = Math.min(pageCount, MAX_PDF_PAGES);
                for (int index = 0; index < limit; index++) {
                    try (PdfRenderer.Page page = renderer.openPage(index)) {
                        float scale = Math.min(2f, Math.min(
                                MAX_IMAGE_EDGE / (float) Math.max(1, page.getWidth()),
                                MAX_IMAGE_EDGE / (float) Math.max(1, page.getHeight())));
                        int width = Math.max(1, Math.round(page.getWidth() * scale));
                        int height = Math.max(1, Math.round(page.getHeight() * scale));
                        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
                        Canvas canvas = new Canvas(bitmap);
                        canvas.drawColor(Color.WHITE);
                        page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                        pages.add(toJpeg(bitmap, 80));
                        bitmap.recycle();
                    }
                }
                if (pages.isEmpty()) throw new IOException("В PDF нет страниц");
                return new AttachmentData(metadata.name, "application/pdf", metadata.size,
                        "", pages, pageCount);
            }
        }
    }

    private byte[] prepareImage(File file) throws Exception {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), bounds);
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
            throw new IOException("Не удалось распознать изображение");
        }
        if (bounds.outWidth > 16_000 || bounds.outHeight > 16_000
                || (long) bounds.outWidth * bounds.outHeight > 120_000_000L) {
            throw new IOException("Слишком большое разрешение изображения");
        }
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        options.inSampleSize = 1;
        while (bounds.outWidth / options.inSampleSize > MAX_IMAGE_EDGE
                || bounds.outHeight / options.inSampleSize > MAX_IMAGE_EDGE) {
            options.inSampleSize *= 2;
        }
        Bitmap decoded = BitmapFactory.decodeFile(file.getAbsolutePath(), options);
        if (decoded == null) throw new IOException("Не удалось декодировать изображение");
        int rotation = imageRotation(file);
        if (rotation != 0) {
            Matrix matrix = new Matrix();
            matrix.postRotate(rotation);
            Bitmap rotated = Bitmap.createBitmap(decoded, 0, 0,
                    decoded.getWidth(), decoded.getHeight(), matrix, true);
            if (rotated != decoded) decoded.recycle();
            decoded = rotated;
        }
        float scale = Math.min(1f, MAX_IMAGE_EDGE /
                (float) Math.max(decoded.getWidth(), decoded.getHeight()));
        Bitmap prepared = decoded;
        if (scale < 1f) {
            prepared = Bitmap.createScaledBitmap(decoded,
                    Math.max(1, Math.round(decoded.getWidth() * scale)),
                    Math.max(1, Math.round(decoded.getHeight() * scale)), true);
            if (prepared != decoded) decoded.recycle();
        }
        byte[] jpeg = toJpeg(prepared, 84);
        prepared.recycle();
        return jpeg;
    }

    private int imageRotation(File file) {
        try {
            ExifInterface exif = new ExifInterface(file.getAbsolutePath());
            int orientation = exif.getAttributeInt(ExifInterface.TAG_ORIENTATION,
                    ExifInterface.ORIENTATION_NORMAL);
            if (orientation == ExifInterface.ORIENTATION_ROTATE_90) return 90;
            if (orientation == ExifInterface.ORIENTATION_ROTATE_180) return 180;
            if (orientation == ExifInterface.ORIENTATION_ROTATE_270) return 270;
        } catch (Exception ignored) {
            // PNG, screenshots and some providers do not include EXIF metadata.
        }
        return 0;
    }

    private byte[] toJpeg(Bitmap source, int quality) throws IOException {
        Bitmap opaque = Bitmap.createBitmap(source.getWidth(), source.getHeight(), Bitmap.Config.RGB_565);
        Canvas canvas = new Canvas(opaque);
        canvas.drawColor(Color.WHITE);
        canvas.drawBitmap(source, 0, 0, null);
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        if (!opaque.compress(Bitmap.CompressFormat.JPEG, quality, output)) {
            opaque.recycle();
            throw new IOException("Не удалось подготовить изображение");
        }
        opaque.recycle();
        return output.toByteArray();
    }

    private Metadata metadata(Uri uri) {
        String name = "Вложение";
        long size = -1;
        try (Cursor cursor = resolver.query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE},
                null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                int sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE);
                if (nameIndex >= 0 && cursor.getString(nameIndex) != null) name = cursor.getString(nameIndex);
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) size = cursor.getLong(sizeIndex);
            }
        } catch (Exception error) {
            DebugLog.error("FILE", error);
        }
        String mime = resolver.getType(uri);
        if (mime == null || mime.trim().isEmpty()) {
            String extension = MimeTypeMap.getFileExtensionFromUrl(name);
            mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension.toLowerCase(Locale.US));
        }
        if (mime == null) mime = "application/octet-stream";
        return new Metadata(name, mime, size);
    }

    private void removeStaleCacheFiles(File cacheDirectory) {
        if (cacheDirectory == null) return;
        try {
            File[] files = cacheDirectory.listFiles((directory, name) ->
                    name != null && name.startsWith(CACHE_PREFIX));
            if (files == null) return;
            for (File file : files) {
                if (file != null && file.isFile()) file.delete();
            }
        } catch (RuntimeException ignored) {
            // Cache housekeeping is optional and must not block a user-selected attachment.
        }
    }

    private File copyToBoundedCache(Uri uri) throws IOException {
        File cacheDirectory = context.getCacheDir();
        if (cacheDirectory == null) throw new IOException("Временное хранилище недоступно");
        removeStaleCacheFiles(cacheDirectory);
        File outputFile = File.createTempFile(CACHE_PREFIX, ".bin", cacheDirectory);
        boolean complete = false;
        try (InputStream raw = resolver.openInputStream(uri)) {
            if (raw == null) throw new IOException("Не удалось открыть файл");
            try (BufferedInputStream input = new BufferedInputStream(raw);
                 FileOutputStream output = new FileOutputStream(outputFile)) {
                byte[] buffer = new byte[16 * 1024];
                long total = 0L;
                int count;
                while ((count = input.read(buffer)) != -1) {
                    total += count;
                    if (total > MAX_SOURCE_BYTES) throw tooLarge();
                    output.write(buffer, 0, count);
                }
                output.getFD().sync();
                complete = true;
                return outputFile;
            }
        } finally {
            if (!complete && !outputFile.delete()) outputFile.deleteOnExit();
        }
    }

    private byte[] readPrefix(File file, int maxBytes) throws IOException {
        int capacity = (int) Math.min(file.length(), maxBytes);
        try (BufferedInputStream input = new BufferedInputStream(new FileInputStream(file));
             ByteArrayOutputStream output = new ByteArrayOutputStream(Math.max(32, capacity))) {
            byte[] buffer = new byte[8192];
            int remaining = maxBytes;
            while (remaining > 0) {
                int count = input.read(buffer, 0, Math.min(buffer.length, remaining));
                if (count == -1) break;
                output.write(buffer, 0, count);
                remaining -= count;
            }
            return output.toByteArray();
        }
    }

    private IOException tooLarge() {
        return new IOException("Файл слишком большой. Максимальный размер — 66 МБ");
    }

    private String extractOfficeText(File archive, String lowerName) throws Exception {
        StringBuilder result = new StringBuilder();
        try (ZipInputStream zip = new ZipInputStream(
                new BufferedInputStream(new FileInputStream(archive)))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null && result.length() < MAX_TEXT_CHARS) {
                String path = entry.getName().toLowerCase(Locale.US);
                boolean wanted = (lowerName.endsWith(".docx") && path.equals("word/document.xml"))
                        || (lowerName.endsWith(".odt") && path.equals("content.xml"))
                        || (lowerName.endsWith(".pptx") && path.startsWith("ppt/slides/slide") && path.endsWith(".xml"))
                        || (lowerName.endsWith(".xlsx") && (path.equals("xl/sharedstrings.xml")
                        || path.startsWith("xl/worksheets/sheet")) && path.endsWith(".xml"));
                if (!wanted || entry.isDirectory()) continue;
                byte[] xml = readZipEntry(zip, 3 * 1024 * 1024);
                String text = xmlText(xml);
                if (!text.isEmpty()) {
                    if (result.length() > 0) result.append("\n\n");
                    result.append(text);
                }
            }
        }
        return result.toString();
    }

    private byte[] readZipEntry(ZipInputStream zip, int limit) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int total = 0;
        int count;
        while ((count = zip.read(buffer)) != -1) {
            total += count;
            if (total > limit) throw new IOException("Документ содержит слишком большой XML-раздел");
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }

    private String xmlText(byte[] xml) throws Exception {
        XmlPullParser parser = Xml.newPullParser();
        parser.setInput(new ByteArrayInputStream(xml), StandardCharsets.UTF_8.name());
        StringBuilder result = new StringBuilder();
        int event;
        while ((event = parser.next()) != XmlPullParser.END_DOCUMENT && result.length() < MAX_TEXT_CHARS) {
            if (event == XmlPullParser.TEXT) {
                String text = parser.getText();
                if (text != null && !text.trim().isEmpty()) {
                    if (result.length() > 0 && !Character.isWhitespace(result.charAt(result.length() - 1))) {
                        result.append(' ');
                    }
                    result.append(text.trim());
                }
            } else if (event == XmlPullParser.END_TAG) {
                String name = parser.getName();
                if ("p".equals(name) || "tr".equals(name) || "row".equals(name)) result.append('\n');
            }
        }
        return result.toString().replaceAll("[ \\t]+", " ")
                .replaceAll("\\n{3,}", "\n\n").trim();
    }

    private String trimText(String value) {
        String clean = value == null ? "" : value.replace("\r\n", "\n").trim();
        if (clean.length() <= MAX_TEXT_CHARS) return clean;
        return clean.substring(0, MAX_TEXT_CHARS) + "\n\n[Файл сокращён до первых " + MAX_TEXT_CHARS + " символов]";
    }

    private boolean looksBinary(byte[] bytes) {
        int checked = Math.min(bytes.length, 4096);
        int controls = 0;
        for (int i = 0; i < checked; i++) {
            int value = bytes[i] & 0xFF;
            if (value == 0) return true;
            if (value < 8 || (value > 13 && value < 32)) controls++;
        }
        return checked > 0 && controls > checked / 20;
    }

    private boolean isText(String mime, String name) {
        if (mime.startsWith("text/")) return true;
        if (mime.contains("json") || mime.contains("xml") || mime.contains("javascript")
                || mime.contains("yaml") || mime.contains("csv")) return true;
        String[] extensions = {".txt", ".md", ".markdown", ".json", ".xml", ".csv", ".tsv",
                ".yaml", ".yml", ".java", ".kt", ".kts", ".py", ".js", ".ts", ".html",
                ".css", ".sql", ".sh", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs",
                ".gradle", ".properties", ".log", ".ini", ".toml"};
        for (String extension : extensions) if (name.endsWith(extension)) return true;
        return false;
    }

    private boolean isImageName(String name) {
        return name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".png")
                || name.endsWith(".webp") || name.endsWith(".gif") || name.endsWith(".bmp");
    }

    private String officeType(String name, String mime) {
        if (name.endsWith(".docx") || name.endsWith(".pptx")
                || name.endsWith(".xlsx") || name.endsWith(".odt")) return name;
        if (mime.contains("wordprocessingml")) return name + ".docx";
        if (mime.contains("presentationml")) return name + ".pptx";
        if (mime.contains("spreadsheetml")) return name + ".xlsx";
        if (mime.contains("opendocument.text")) return name + ".odt";
        return name;
    }

    private boolean isOfficeArchive(String name, String mime) {
        return name.endsWith(".docx") || name.endsWith(".pptx") || name.endsWith(".xlsx")
                || name.endsWith(".odt") || mime.contains("openxmlformats")
                || "application/vnd.oasis.opendocument.text".equals(mime);
    }

    private static final class Metadata {
        final String name;
        final String mime;
        final long size;

        Metadata(String name, String mime, long size) {
            this.name = name;
            this.mime = mime;
            this.size = size;
        }
    }
}
