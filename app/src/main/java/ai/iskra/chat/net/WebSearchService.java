package ai.iskra.chat.net;

import android.text.Html;

import ai.iskra.chat.model.SearchSource;
import ai.iskra.chat.util.TextUtilsEx;

import org.json.JSONArray;
import org.json.JSONObject;
import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlPullParserFactory;

import java.io.StringReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Key-free metasearch using Bing RSS plus Wikipedia's public API. */
public final class WebSearchService {
    private static final int MAX_RESULTS = 6;

    public List<SearchSource> search(String query) throws Exception {
        List<SearchSource> results = new ArrayList<>();
        Exception firstError = null;

        try {
            results.addAll(searchBingRss(query));
        } catch (Exception error) {
            firstError = error;
        }

        try {
            mergeUnique(results, searchWikipedia(query));
        } catch (Exception error) {
            if (firstError == null) firstError = error;
        }

        if (results.isEmpty() && firstError != null) throw firstError;
        if (results.size() > MAX_RESULTS) return new ArrayList<>(results.subList(0, MAX_RESULTS));
        return results;
    }

    private List<SearchSource> searchBingRss(String query) throws Exception {
        String encoded = URLEncoder.encode(query, StandardCharsets.UTF_8.name());
        URL url = new URL("https://www.bing.com/search?format=rss&setlang=ru&q=" + encoded);
        HttpURLConnection connection = HttpUtils.configure((HttpURLConnection) url.openConnection());
        connection.setRequestProperty("Accept", "application/rss+xml, application/xml, text/xml");
        String xml;
        try {
            xml = HttpUtils.readResponse(connection);
        } finally {
            connection.disconnect();
        }

        List<SearchSource> results = new ArrayList<>();
        XmlPullParser parser = XmlPullParserFactory.newInstance().newPullParser();
        parser.setInput(new StringReader(xml));
        String title = "";
        String link = "";
        String description = "";
        boolean inItem = false;
        int event = parser.getEventType();
        while (event != XmlPullParser.END_DOCUMENT && results.size() < 5) {
            if (event == XmlPullParser.START_TAG) {
                String name = parser.getName();
                if ("item".equalsIgnoreCase(name)) {
                    inItem = true;
                    title = link = description = "";
                } else if (inItem && "title".equalsIgnoreCase(name)) {
                    title = parser.nextText();
                } else if (inItem && "link".equalsIgnoreCase(name)) {
                    link = parser.nextText();
                } else if (inItem && "description".equalsIgnoreCase(name)) {
                    description = parser.nextText();
                }
            } else if (event == XmlPullParser.END_TAG && "item".equalsIgnoreCase(parser.getName())) {
                inItem = false;
                String cleanTitle = stripHtml(title);
                String cleanDescription = TextUtilsEx.compact(stripHtml(description), 460);
                if (!cleanTitle.isEmpty() && link.startsWith("http")) {
                    results.add(new SearchSource(cleanTitle, link, cleanDescription));
                }
            }
            event = parser.next();
        }
        return results;
    }

    private List<SearchSource> searchWikipedia(String query) throws Exception {
        String language = containsCyrillic(query) ? "ru" : "en";
        String encoded = URLEncoder.encode(query, StandardCharsets.UTF_8.name());
        String endpoint = "https://" + language + ".wikipedia.org/w/api.php" +
                "?action=query&generator=search&gsrsearch=" + encoded +
                "&gsrlimit=3&prop=extracts%7Cinfo&exintro=1&explaintext=1" +
                "&exsentences=4&inprop=url&format=json&formatversion=2&origin=*";
        HttpURLConnection connection = HttpUtils.configure((HttpURLConnection) new URL(endpoint).openConnection());
        connection.setRequestProperty("Accept", "application/json");
        String body;
        try {
            body = HttpUtils.readResponse(connection);
        } finally {
            connection.disconnect();
        }

        List<SearchSource> results = new ArrayList<>();
        JSONObject root = new JSONObject(body);
        JSONArray pages = root.optJSONObject("query") == null
                ? null : root.optJSONObject("query").optJSONArray("pages");
        if (pages == null) return results;
        for (int i = 0; i < pages.length(); i++) {
            JSONObject page = pages.optJSONObject(i);
            if (page == null) continue;
            String title = page.optString("title", "Wikipedia");
            String extract = TextUtilsEx.compact(page.optString("extract", ""), 700);
            String url = page.optString("fullurl", "");
            if (url.isEmpty()) {
                url = "https://" + language + ".wikipedia.org/wiki/" +
                        URLEncoder.encode(title.replace(' ', '_'), StandardCharsets.UTF_8.name());
            }
            if (!extract.isEmpty()) results.add(new SearchSource(title + " — Википедия", url, extract));
        }
        return results;
    }

    private void mergeUnique(List<SearchSource> destination, List<SearchSource> additions) {
        Set<String> seen = new HashSet<>();
        for (SearchSource source : destination) seen.add(source.url);
        for (SearchSource source : additions) {
            if (seen.add(source.url)) destination.add(source);
        }
    }

    private boolean containsCyrillic(String value) {
        return value != null && value.matches(".*[А-Яа-яЁё].*");
    }

    private String stripHtml(String value) {
        if (value == null || value.isEmpty()) return "";
        return Html.fromHtml(value, Html.FROM_HTML_MODE_LEGACY).toString()
                .replace('\u00a0', ' ').trim();
    }
}
