package ai.iskra.chat.model;

import org.json.JSONException;
import org.json.JSONObject;

public final class SearchSource {
    public final String title;
    public final String url;
    public final String snippet;

    public SearchSource(String title, String url, String snippet) {
        this.title = title == null ? "Источник" : title.trim();
        this.url = url == null ? "" : url.trim();
        this.snippet = snippet == null ? "" : snippet.trim();
    }

    public JSONObject toJson() throws JSONException {
        JSONObject object = new JSONObject();
        object.put("title", title);
        object.put("url", url);
        object.put("snippet", snippet);
        return object;
    }

    public static SearchSource fromJson(JSONObject object) {
        return new SearchSource(
                object.optString("title", "Источник"),
                object.optString("url", ""),
                object.optString("snippet", "")
        );
    }
}
