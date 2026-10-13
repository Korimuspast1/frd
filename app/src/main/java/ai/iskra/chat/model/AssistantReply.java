package ai.iskra.chat.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class AssistantReply {
    public final String text;
    public final List<SearchSource> sources;

    public AssistantReply(String text, List<SearchSource> sources) {
        this.text = text == null ? "" : text.trim();
        this.sources = sources == null
                ? Collections.emptyList()
                : Collections.unmodifiableList(new ArrayList<>(sources));
    }
}
