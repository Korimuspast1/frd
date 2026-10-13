package ai.iskra.chat.util;

import ai.iskra.chat.model.SearchSource;

import org.json.JSONArray;
import org.json.JSONException;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class JsonUtils {
    private JsonUtils() {}

    public static String sourcesToJson(List<SearchSource> sources) {
        if (sources == null || sources.isEmpty()) return "[]";
        JSONArray array = new JSONArray();
        for (SearchSource source : sources) {
            try {
                array.put(source.toJson());
            } catch (JSONException ignored) {
                // All fields are strings, so this is only a defensive fallback.
            }
        }
        return array.toString();
    }

    public static List<SearchSource> sourcesFromJson(String json) {
        if (json == null || json.trim().isEmpty()) return Collections.emptyList();
        List<SearchSource> result = new ArrayList<>();
        try {
            JSONArray array = new JSONArray(json);
            for (int i = 0; i < array.length(); i++) {
                result.add(SearchSource.fromJson(array.getJSONObject(i)));
            }
        } catch (JSONException ignored) {
            return Collections.emptyList();
        }
        return result;
    }
}
