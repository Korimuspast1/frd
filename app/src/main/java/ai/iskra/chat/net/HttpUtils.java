package ai.iskra.chat.net;

import ai.iskra.chat.util.DebugLog;

import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.nio.charset.StandardCharsets;

final class HttpUtils {
    private static final int MAX_RESPONSE_BYTES = 2 * 1024 * 1024;

    private HttpUtils() {}

    static HttpURLConnection configure(HttpURLConnection connection) {
        DebugLog.log("HTTP", "OPEN " + connection.getURL());
        connection.setConnectTimeout(12_000);
        connection.setReadTimeout(20_000);
        connection.setUseCaches(false);
        connection.setRequestProperty("User-Agent", "kvsai/1.3 (Android; multimodal assistant)");
        connection.setRequestProperty("Accept-Language", "ru,en;q=0.7");
        return connection;
    }

    static String readResponse(HttpURLConnection connection) throws IOException {
        int code = connection.getResponseCode();
        InputStream stream = code >= 200 && code < 400
                ? connection.getInputStream()
                : connection.getErrorStream();
        String body = stream == null ? "" : readUtf8(stream);
        DebugLog.log("HTTP", connection.getRequestMethod() + " " + connection.getURL().getHost() +
                connection.getURL().getPath() + " → " + code + "; responseChars=" + body.length());
        if (code < 200 || code >= 300) {
            DebugLog.log("HTTP", "Non-success response " + code + "; bodyChars=" + body.length());
            throw new HttpException(code, body);
        }
        return body;
    }

    static String readUtf8(InputStream input) throws IOException {
        try (BufferedInputStream stream = new BufferedInputStream(input);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int total = 0;
            int count;
            while ((count = stream.read(buffer)) != -1) {
                total += count;
                if (total > MAX_RESPONSE_BYTES) throw new IOException("Ответ сервера слишком большой");
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    static final class HttpException extends IOException {
        final int statusCode;
        final String responseBody;

        HttpException(int statusCode, String responseBody) {
            super("HTTP " + statusCode);
            this.statusCode = statusCode;
            this.responseBody = responseBody == null ? "" : responseBody;
        }
    }
}
