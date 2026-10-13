package ai.iskra.chat;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.text.TextWatcher;
import android.text.Editable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.PopupMenu;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import ai.iskra.chat.assistant.AssistantEngine;
import ai.iskra.chat.data.AppSettings;
import ai.iskra.chat.data.ChatDatabase;
import ai.iskra.chat.model.AssistantReply;
import ai.iskra.chat.model.Chat;
import ai.iskra.chat.model.ChatMessage;
import ai.iskra.chat.ui.ChatListAdapter;
import ai.iskra.chat.ui.MessageAdapter;
import ai.iskra.chat.util.TextUtilsEx;
import ai.iskra.chat.util.Ui;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class MainActivity extends Activity {
    private enum Screen { HOME, CHAT, SETTINGS }

    private ChatDatabase database;
    private AppSettings settings;
    private AssistantEngine assistant;
    private FrameLayout host;
    private Screen screen = Screen.HOME;
    private Screen settingsReturnScreen = Screen.HOME;
    private long settingsReturnChatId = -1;
    private long currentChatId = -1;

    private ChatListAdapter chatListAdapter;
    private EditText chatSearch;
    private TextView chatCount;

    private MessageAdapter messageAdapter;
    private ListView messageList;
    private EditText composer;
    private ImageButton sendButton;
    private TextView currentChatTitle;
    private TextView currentMode;

    private boolean requestRunning;
    private long requestChatId = -1;
    private String lastQuestion = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureWindow();
        database = new ChatDatabase(this);
        settings = new AppSettings(this);
        assistant = new AssistantEngine();

        host = new FrameLayout(this);
        host.setBackgroundColor(Ui.BG);
        setContentView(host);
        applyAndroid15Insets();
        showHome();
    }

    private void configureWindow() {
        Window window = getWindow();
        window.setStatusBarColor(Ui.BG);
        window.setNavigationBarColor(Ui.BG);
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.setStatusBarContrastEnforced(false);
            window.setNavigationBarContrastEnforced(false);
        }
        window.getDecorView().setSystemUiVisibility(0);
    }

    private void applyAndroid15Insets() {
        if (Build.VERSION.SDK_INT >= 35) {
            host.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(0, bars.top, 0, bars.bottom);
                return insets;
            });
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (screen == Screen.HOME && chatListAdapter != null) refreshChats();
        if (screen == Screen.CHAT && currentMode != null) {
            currentMode.setText(settings.snapshot().modeLabel());
        }
    }

    @Override
    protected void onDestroy() {
        assistant.shutdown();
        database.close();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (screen == Screen.SETTINGS) {
            if (settingsReturnScreen == Screen.CHAT && database.getChat(settingsReturnChatId) != null) {
                showChat(settingsReturnChatId);
            } else {
                showHome();
            }
        } else if (screen == Screen.CHAT) {
            hideKeyboard();
            showHome();
        } else {
            super.onBackPressed();
        }
    }

    private void showHome() {
        screen = Screen.HOME;
        currentChatId = -1;
        host.removeAllViews();

        LinearLayout root = vertical();
        root.setBackgroundColor(Ui.BG);
        host.addView(root, match());
        root.addView(buildHomeHeader());
        root.addView(buildHero());

        LinearLayout sectionTitle = horizontal(Gravity.CENTER_VERTICAL);
        sectionTitle.setPadding(Ui.dp(this, 20), Ui.dp(this, 19), Ui.dp(this, 20), Ui.dp(this, 8));
        TextView title = text("Ваши чаты", 20, Ui.TEXT, true);
        sectionTitle.addView(title, new LinearLayout.LayoutParams(0, wrap(), 1f));
        chatCount = text("0", 12, Ui.CYAN, true);
        chatCount.setGravity(Gravity.CENTER);
        chatCount.setBackground(Ui.rounded(0x2239D9C8, 11, this));
        chatCount.setMinWidth(Ui.dp(this, 34));
        Ui.setPadding(chatCount, 10, 5);
        sectionTitle.addView(chatCount);
        root.addView(sectionTitle);

        root.addView(buildChatSearch());

        FrameLayout listFrame = new FrameLayout(this);
        root.addView(listFrame, new LinearLayout.LayoutParams(matchValue(), 0, 1f));
        ListView list = new ListView(this);
        list.setDivider(null);
        list.setSelector(android.R.color.transparent);
        list.setClipToPadding(false);
        list.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 18));
        list.setVerticalScrollBarEnabled(false);
        chatListAdapter = new ChatListAdapter(this, new ChatListAdapter.Listener() {
            @Override public void onOpen(Chat chat) { showChat(chat.id); }
            @Override public void onMenu(Chat chat, View anchor) { showChatMenu(chat, anchor); }
        });
        list.setAdapter(chatListAdapter);
        listFrame.addView(list, match());

        View empty = buildEmptyChats();
        listFrame.addView(empty, match());
        list.setEmptyView(empty);
        refreshChats();
    }

    private View buildHomeHeader() {
        LinearLayout header = horizontal(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(this, 20), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 8));

        TextView logo = text("✦", 22, Ui.TEXT, false);
        logo.setGravity(Gravity.CENTER);
        logo.setBackground(Ui.gradient(Ui.VIOLET, Ui.VIOLET_DARK, 15, this));
        header.addView(logo, new LinearLayout.LayoutParams(Ui.dp(this, 46), Ui.dp(this, 46)));

        LinearLayout names = vertical();
        names.setPadding(Ui.dp(this, 12), 0, 0, 0);
        names.addView(text("Искра AI", 20, Ui.TEXT, true));
        names.addView(text("умный поиск без лишнего", 12, Ui.MUTED, false));
        header.addView(names, new LinearLayout.LayoutParams(0, wrap(), 1f));

        ImageButton settingsButton = Ui.iconButton(this, R.drawable.ic_settings, "Настройки");
        settingsButton.setOnClickListener(v -> openSettings());
        header.addView(settingsButton, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));
        return header;
    }

    private View buildHero() {
        FrameLayout outer = new FrameLayout(this);
        outer.setPadding(Ui.dp(this, 20), Ui.dp(this, 10), Ui.dp(this, 20), 0);

        LinearLayout card = vertical();
        card.setPadding(Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 18), Ui.dp(this, 18));
        card.setBackground(Ui.gradient(0xFF6034CE, 0xFF263F8D, 25, this));

        LinearLayout top = horizontal(Gravity.TOP);
        LinearLayout copy = vertical();
        TextView eyebrow = text("✦  ИНТЕРНЕТ + AI", 11, 0xFFD8CCFF, true);
        eyebrow.setLetterSpacing(0.12f);
        copy.addView(eyebrow);
        TextView heading = text("Спроси что угодно", 25, Ui.TEXT, true);
        LinearLayout.LayoutParams headingParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        headingParams.topMargin = Ui.dp(this, 7);
        copy.addView(heading, headingParams);
        TextView subtitle = text("Найду информацию, покажу источники и сохраню диалог.", 14, 0xFFD9DEF0, false);
        subtitle.setLineSpacing(0, 1.1f);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        subtitleParams.topMargin = Ui.dp(this, 5);
        copy.addView(subtitle, subtitleParams);
        top.addView(copy, new LinearLayout.LayoutParams(0, wrap(), 1f));

        TextView sparkle = text("✦", 38, 0x6639D9C8, false);
        sparkle.setGravity(Gravity.CENTER);
        top.addView(sparkle, new LinearLayout.LayoutParams(Ui.dp(this, 54), Ui.dp(this, 54)));
        card.addView(top);

        Button create = primaryButton("＋  Новый чат");
        create.setOnClickListener(v -> createChat());
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(wrap(), Ui.dp(this, 46));
        buttonParams.topMargin = Ui.dp(this, 15);
        card.addView(create, buttonParams);
        outer.addView(card, matchWidthWrap());
        return outer;
    }

    private View buildChatSearch() {
        FrameLayout outer = new FrameLayout(this);
        outer.setPadding(Ui.dp(this, 20), Ui.dp(this, 3), Ui.dp(this, 20), Ui.dp(this, 4));
        LinearLayout box = horizontal(Gravity.CENTER_VERTICAL);
        box.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 12), 0);
        box.setBackground(Ui.roundedStroke(Ui.SURFACE, 0xFF202A39, 16, this));
        ImageView icon = new ImageView(this);
        icon.setImageResource(R.drawable.ic_search);
        box.addView(icon, new LinearLayout.LayoutParams(Ui.dp(this, 22), Ui.dp(this, 22)));
        chatSearch = new EditText(this);
        chatSearch.setHint("Поиск по чатам");
        chatSearch.setHintTextColor(Ui.DIM);
        chatSearch.setTextColor(Ui.TEXT);
        chatSearch.setTextSize(14);
        chatSearch.setSingleLine(true);
        chatSearch.setBackgroundColor(Color.TRANSPARENT);
        chatSearch.setPadding(Ui.dp(this, 10), 0, 0, 0);
        chatSearch.addTextChangedListener(new SimpleTextWatcher() {
            @Override public void afterTextChanged(Editable editable) { refreshChats(); }
        });
        box.addView(chatSearch, new LinearLayout.LayoutParams(0, Ui.dp(this, 50), 1f));
        outer.addView(box, new FrameLayout.LayoutParams(matchValue(), Ui.dp(this, 50)));
        return outer;
    }

    private View buildEmptyChats() {
        LinearLayout empty = vertical();
        empty.setGravity(Gravity.CENTER);
        empty.setPadding(Ui.dp(this, 36), Ui.dp(this, 20), Ui.dp(this, 36), Ui.dp(this, 34));
        TextView icon = text("✦", 38, Ui.VIOLET, false);
        icon.setGravity(Gravity.CENTER);
        icon.setBackground(Ui.rounded(0x228B5CF6, 29, this));
        empty.addView(icon, new LinearLayout.LayoutParams(Ui.dp(this, 72), Ui.dp(this, 72)));
        TextView title = text("Здесь появятся ваши чаты", 18, Ui.TEXT, true);
        title.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(wrap(), wrap());
        titleParams.topMargin = Ui.dp(this, 15);
        empty.addView(title, titleParams);
        TextView hint = text("Создайте диалог и задайте первый вопрос", 14, Ui.MUTED, false);
        hint.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams hintParams = new LinearLayout.LayoutParams(wrap(), wrap());
        hintParams.topMargin = Ui.dp(this, 6);
        empty.addView(hint, hintParams);
        Button button = secondaryButton("Создать чат");
        button.setOnClickListener(v -> createChat());
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(wrap(), Ui.dp(this, 44));
        buttonParams.topMargin = Ui.dp(this, 16);
        empty.addView(button, buttonParams);
        return empty;
    }

    private void refreshChats() {
        if (chatListAdapter == null) return;
        String query = chatSearch == null ? "" : chatSearch.getText().toString();
        List<Chat> chats = database.getChats(query);
        chatListAdapter.setItems(chats);
        if (chatCount != null) chatCount.setText(String.valueOf(database.countChats()));
    }

    private void createChat() {
        long id = database.createChat();
        showChat(id);
    }

    private void showChatMenu(Chat chat, View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add("Переименовать");
        menu.getMenu().add("Удалить");
        menu.setOnMenuItemClickListener(item -> {
            if ("Переименовать".contentEquals(item.getTitle())) renameDialog(chat);
            else deleteDialog(chat);
            return true;
        });
        menu.show();
    }

    private void renameDialog(Chat chat) {
        EditText input = dialogInput(chat.title, "Название чата");
        new AlertDialog.Builder(this)
                .setTitle("Переименовать чат")
                .setView(wrapDialogInput(input))
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Сохранить", (dialog, which) -> {
                    database.renameChat(chat.id, input.getText().toString());
                    if (screen == Screen.CHAT && currentChatId == chat.id) showChat(chat.id);
                    else refreshChats();
                })
                .show();
        input.selectAll();
    }

    private void deleteDialog(Chat chat) {
        if (requestRunning && requestChatId == chat.id) {
            Toast.makeText(this, "Дождитесь ответа перед удалением этого чата", Toast.LENGTH_SHORT).show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Удалить чат?")
                .setMessage("История «" + chat.title + "» будет удалена без возможности восстановления.")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Удалить", (dialog, which) -> {
                    database.deleteChat(chat.id);
                    if (screen == Screen.CHAT && currentChatId == chat.id) showHome();
                    else refreshChats();
                })
                .show();
    }

    private void showChat(long chatId) {
        Chat chat = database.getChat(chatId);
        if (chat == null) {
            showHome();
            return;
        }
        screen = Screen.CHAT;
        currentChatId = chatId;
        host.removeAllViews();

        LinearLayout root = vertical();
        root.setBackgroundColor(Ui.BG);
        host.addView(root, match());
        root.addView(buildChatHeader(chat));

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(matchValue(), 0, 1f));
        messageList = new ListView(this);
        messageList.setDivider(null);
        messageList.setSelector(android.R.color.transparent);
        messageList.setClipToPadding(false);
        messageList.setPadding(0, Ui.dp(this, 10), 0, Ui.dp(this, 12));
        messageList.setTranscriptMode(ListView.TRANSCRIPT_MODE_ALWAYS_SCROLL);
        messageList.setStackFromBottom(false);
        messageAdapter = new MessageAdapter(this, this::retryLastQuestion);
        List<ChatMessage> messages = database.getMessages(chatId);
        if (requestRunning && requestChatId == chatId) messages.add(ChatMessage.pending(chatId));
        messageAdapter.setMessages(messages);
        messageList.setAdapter(messageAdapter);
        content.addView(messageList, match());

        View empty = buildEmptyConversation();
        content.addView(empty, match());
        messageList.setEmptyView(empty);
        root.addView(buildComposer());
        scrollMessagesToEnd();
        updateSendState();
    }

    private View buildChatHeader(Chat chat) {
        LinearLayout header = horizontal(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(this, 10), Ui.dp(this, 9), Ui.dp(this, 10), Ui.dp(this, 9));
        header.setBackgroundColor(Ui.SURFACE);

        ImageButton back = Ui.iconButton(this, R.drawable.ic_back, "Назад к чатам");
        back.setBackgroundColor(Color.TRANSPARENT);
        back.setOnClickListener(v -> onBackPressed());
        header.addView(back, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));

        LinearLayout titleBox = vertical();
        titleBox.setPadding(Ui.dp(this, 5), 0, Ui.dp(this, 6), 0);
        currentChatTitle = text(chat.title, 16, Ui.TEXT, true);
        currentChatTitle.setMaxLines(1);
        currentChatTitle.setEllipsize(android.text.TextUtils.TruncateAt.END);
        titleBox.addView(currentChatTitle);
        currentMode = text(settings.snapshot().modeLabel(), 11,
                settings.isAiEnabled() ? Ui.CYAN : 0xFFC9B8FF, false);
        LinearLayout.LayoutParams modeParams = new LinearLayout.LayoutParams(wrap(), wrap());
        modeParams.topMargin = Ui.dp(this, 2);
        titleBox.addView(currentMode, modeParams);
        titleBox.setOnClickListener(v -> renameDialog(database.getChat(currentChatId)));
        header.addView(titleBox, new LinearLayout.LayoutParams(0, wrap(), 1f));

        ImageButton settingsButton = Ui.iconButton(this, R.drawable.ic_settings, "Настройки");
        settingsButton.setBackgroundColor(Color.TRANSPARENT);
        settingsButton.setOnClickListener(v -> openSettings());
        header.addView(settingsButton, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));
        return header;
    }

    private View buildEmptyConversation() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout empty = vertical();
        empty.setGravity(Gravity.CENTER_HORIZONTAL);
        empty.setPadding(Ui.dp(this, 24), Ui.dp(this, 34), Ui.dp(this, 24), Ui.dp(this, 24));
        scroll.addView(empty, matchWidthWrap());

        TextView spark = text("✦", 34, Ui.TEXT, false);
        spark.setGravity(Gravity.CENTER);
        spark.setBackground(Ui.gradient(Ui.VIOLET, Ui.VIOLET_DARK, 25, this));
        empty.addView(spark, new LinearLayout.LayoutParams(Ui.dp(this, 66), Ui.dp(this, 66)));
        TextView title = text("Чем помочь?", 24, Ui.TEXT, true);
        title.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(wrap(), wrap());
        titleParams.topMargin = Ui.dp(this, 17);
        empty.addView(title, titleParams);
        TextView subtitle = text("Напишите вопрос или выберите пример", 14, Ui.MUTED, false);
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(wrap(), wrap());
        subtitleParams.topMargin = Ui.dp(this, 5);
        subtitleParams.bottomMargin = Ui.dp(this, 19);
        empty.addView(subtitle, subtitleParams);

        addSuggestion(empty, "Объясни простыми словами, как работает искусственный интеллект");
        addSuggestion(empty, "Найди свежую информацию про Android");
        addSuggestion(empty, "Помоги составить план обучения программированию");
        return scroll;
    }

    private void addSuggestion(LinearLayout parent, String value) {
        TextView chip = text(value + "  →", 14, Ui.TEXT, false);
        chip.setGravity(Gravity.CENTER_VERTICAL);
        chip.setPadding(Ui.dp(this, 15), Ui.dp(this, 12), Ui.dp(this, 15), Ui.dp(this, 12));
        chip.setBackground(Ui.ripple(
                Ui.roundedStroke(Ui.CARD, 0xFF273448, 15, this), 0x258B5CF6));
        chip.setOnClickListener(v -> sendQuestion(value));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(matchValue(), wrap());
        params.bottomMargin = Ui.dp(this, 9);
        parent.addView(chip, params);
    }

    private View buildComposer() {
        LinearLayout area = vertical();
        area.setPadding(Ui.dp(this, 12), Ui.dp(this, 7), Ui.dp(this, 12), Ui.dp(this, 10));
        area.setBackgroundColor(Ui.SURFACE);

        LinearLayout status = horizontal(Gravity.CENTER_VERTICAL);
        ImageView globe = new ImageView(this);
        globe.setImageResource(R.drawable.ic_globe);
        status.addView(globe, new LinearLayout.LayoutParams(Ui.dp(this, 16), Ui.dp(this, 16)));
        TextView statusText = text(settings.isWebEnabled()
                ? "Веб-поиск включён • ответы содержат источники"
                : "Веб-поиск выключен", 10, Ui.DIM, false);
        statusText.setPadding(Ui.dp(this, 6), 0, 0, 0);
        status.addView(statusText);
        area.addView(status);

        LinearLayout box = horizontal(Gravity.BOTTOM);
        box.setPadding(Ui.dp(this, 13), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));
        box.setBackground(Ui.roundedStroke(Ui.CARD, 0xFF29364A, 20, this));
        composer = new EditText(this);
        composer.setHint("Напишите сообщение…");
        composer.setHintTextColor(Ui.DIM);
        composer.setTextColor(Ui.TEXT);
        composer.setTextSize(15);
        composer.setBackgroundColor(Color.TRANSPARENT);
        composer.setPadding(0, Ui.dp(this, 7), Ui.dp(this, 7), Ui.dp(this, 7));
        composer.setMinLines(1);
        composer.setMaxLines(5);
        composer.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        composer.setImeOptions(EditorInfo.IME_ACTION_SEND);
        composer.addTextChangedListener(new SimpleTextWatcher() {
            @Override public void afterTextChanged(Editable editable) { updateSendState(); }
        });
        composer.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                submitComposer();
                return true;
            }
            return false;
        });
        box.addView(composer, new LinearLayout.LayoutParams(0, wrap(), 1f));

        sendButton = Ui.iconButton(this, R.drawable.ic_send, "Отправить");
        sendButton.setBackground(Ui.ripple(Ui.gradient(Ui.VIOLET, Ui.VIOLET_DARK, 17, this), 0x55FFFFFF));
        sendButton.setOnClickListener(v -> submitComposer());
        LinearLayout.LayoutParams sendParams = new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48));
        box.addView(sendButton, sendParams);
        LinearLayout.LayoutParams boxParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        boxParams.topMargin = Ui.dp(this, 6);
        area.addView(box, boxParams);
        return area;
    }

    private void submitComposer() {
        if (composer == null) return;
        String question = composer.getText().toString().trim();
        if (question.isEmpty()) return;
        composer.setText("");
        sendQuestion(question);
    }

    private void sendQuestion(String question) {
        if (requestRunning) {
            Toast.makeText(this, "Дождитесь текущего ответа", Toast.LENGTH_SHORT).show();
            return;
        }
        if (currentChatId < 0 || database.getChat(currentChatId) == null) return;
        askAssistant(currentChatId, question.trim(), true);
    }

    private void askAssistant(long chatId, String question, boolean addUserMessage) {
        if (question.isEmpty() || requestRunning) return;
        if (addUserMessage) {
            int oldCount = database.countMessages(chatId);
            database.addMessage(chatId, ChatMessage.ROLE_USER, question, Collections.emptyList());
            if (oldCount == 0) {
                database.renameChat(chatId, TextUtilsEx.chatTitle(question));
                Chat renamed = database.getChat(chatId);
                if (renamed != null && currentChatTitle != null) currentChatTitle.setText(renamed.title);
            }
        }

        requestRunning = true;
        requestChatId = chatId;
        lastQuestion = question;
        if (screen == Screen.CHAT && currentChatId == chatId && messageAdapter != null) {
            List<ChatMessage> saved = database.getMessages(chatId);
            saved.add(ChatMessage.pending(chatId));
            messageAdapter.setMessages(saved);
            scrollMessagesToEnd();
        }
        updateSendState();

        List<ChatMessage> history = database.getMessages(chatId);
        AppSettings.Snapshot snapshot = settings.snapshot();
        assistant.ask(question, history, snapshot, new AssistantEngine.Callback() {
            @Override
            public void onSuccess(AssistantReply reply) {
                if (database.getChat(chatId) != null) {
                    database.addMessage(chatId, ChatMessage.ROLE_ASSISTANT, reply.text, reply.sources);
                }
                requestRunning = false;
                requestChatId = -1;
                if (screen == Screen.CHAT && currentChatId == chatId && messageAdapter != null) {
                    messageAdapter.setMessages(database.getMessages(chatId));
                    scrollMessagesToEnd();
                    updateSendState();
                } else if (screen == Screen.HOME) {
                    refreshChats();
                }
            }

            @Override
            public void onError(String error) {
                requestRunning = false;
                requestChatId = -1;
                if (screen == Screen.CHAT && currentChatId == chatId && messageAdapter != null) {
                    messageAdapter.replaceTransient(ChatMessage.error(chatId, error));
                    scrollMessagesToEnd();
                    updateSendState();
                } else if (screen == Screen.HOME) {
                    refreshChats();
                    Toast.makeText(MainActivity.this, error, Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(MainActivity.this, error, Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    private void retryLastQuestion() {
        if (requestRunning || currentChatId < 0 || lastQuestion.isEmpty()) return;
        askAssistant(currentChatId, lastQuestion, false);
    }

    private void updateSendState() {
        if (sendButton == null) return;
        boolean hasText = composer != null && !composer.getText().toString().trim().isEmpty();
        boolean enabled = hasText && !requestRunning;
        sendButton.setEnabled(enabled);
        sendButton.setAlpha(enabled ? 1f : 0.42f);
        if (composer != null) composer.setEnabled(!requestRunning);
    }

    private void scrollMessagesToEnd() {
        if (messageList == null || messageAdapter == null || messageAdapter.getCount() == 0) return;
        messageList.post(() -> messageList.setSelection(messageAdapter.getCount() - 1));
    }

    private void openSettings() {
        settingsReturnScreen = screen;
        settingsReturnChatId = currentChatId;
        showSettings();
    }

    @SuppressWarnings("deprecation")
    private void showSettings() {
        screen = Screen.SETTINGS;
        host.removeAllViews();
        LinearLayout root = vertical();
        root.setBackgroundColor(Ui.BG);
        host.addView(root, match());

        LinearLayout header = horizontal(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(this, 10), Ui.dp(this, 9), Ui.dp(this, 16), Ui.dp(this, 9));
        header.setBackgroundColor(Ui.SURFACE);
        ImageButton back = Ui.iconButton(this, R.drawable.ic_back, "Назад");
        back.setBackgroundColor(Color.TRANSPARENT);
        back.setOnClickListener(v -> onBackPressed());
        header.addView(back, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));
        TextView title = text("Настройки", 20, Ui.TEXT, true);
        title.setPadding(Ui.dp(this, 5), 0, 0, 0);
        header.addView(title, new LinearLayout.LayoutParams(0, wrap(), 1f));
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout content = vertical();
        content.setPadding(Ui.dp(this, 20), Ui.dp(this, 20), Ui.dp(this, 20), Ui.dp(this, 36));
        scroll.addView(content, matchWidthWrap());
        root.addView(scroll, new LinearLayout.LayoutParams(matchValue(), 0, 1f));

        content.addView(sectionLabel("ОТВЕТЫ"));
        LinearLayout webCard = settingsCard();
        Switch webSwitch = new Switch(this);
        webSwitch.setText("Искать в интернете");
        webSwitch.setTextColor(Ui.TEXT);
        webSwitch.setTextSize(16);
        webSwitch.setChecked(settings.isWebEnabled());
        webSwitch.setButtonTintList(ColorStateList.valueOf(Ui.VIOLET));
        webCard.addView(webSwitch, matchWidthWrap());
        TextView webHint = text("Бесплатно и без API-ключа. Искра найдёт материалы и покажет ссылки на источники.",
                13, Ui.MUTED, false);
        webHint.setLineSpacing(0, 1.08f);
        LinearLayout.LayoutParams webHintParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        webHintParams.topMargin = Ui.dp(this, 7);
        webCard.addView(webHint, webHintParams);
        content.addView(webCard, cardParams());

        content.addView(sectionLabel("AI-ПРОВАЙДЕР"));
        LinearLayout aiCard = settingsCard();
        Switch aiSwitch = new Switch(this);
        aiSwitch.setText("Использовать нейросеть");
        aiSwitch.setTextColor(Ui.TEXT);
        aiSwitch.setTextSize(16);
        aiSwitch.setChecked(settings.isAiEnabled());
        aiCard.addView(aiSwitch, matchWidthWrap());
        TextView aiHint = text("Поддерживаются OpenRouter, Ollama, LM Studio и любой OpenAI-совместимый API.",
                13, Ui.MUTED, false);
        aiHint.setLineSpacing(0, 1.08f);
        LinearLayout.LayoutParams aiHintParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        aiHintParams.topMargin = Ui.dp(this, 7);
        aiHintParams.bottomMargin = Ui.dp(this, 13);
        aiCard.addView(aiHint, aiHintParams);

        EditText endpoint = formField(aiCard, "Адрес API", settings.getEndpoint(),
                "https://openrouter.ai/api/v1", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        EditText model = formField(aiCard, "Модель", settings.getModel(),
                "openrouter/free", InputType.TYPE_CLASS_TEXT);
        EditText apiKey = formField(aiCard, "API-ключ", "",
                settings.hasApiKey() ? "Ключ сохранён и зашифрован ••••" : "Необязательно для локального API",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);

        LinearLayout keyActions = horizontal(Gravity.CENTER_VERTICAL);
        Button getKey = inlineButton("Получить ключ OpenRouter");
        getKey.setOnClickListener(v -> openUrl("https://openrouter.ai/keys"));
        keyActions.addView(getKey, new LinearLayout.LayoutParams(0, Ui.dp(this, 42), 1f));
        if (settings.hasApiKey()) {
            Button removeKey = inlineButton("Удалить ключ");
            removeKey.setTextColor(Ui.DANGER);
            removeKey.setOnClickListener(v -> {
                settings.clearApiKey();
                apiKey.setHint("Ключ удалён");
                Toast.makeText(this, "API-ключ удалён", Toast.LENGTH_SHORT).show();
            });
            LinearLayout.LayoutParams removeParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 42), 1f);
            removeParams.leftMargin = Ui.dp(this, 7);
            keyActions.addView(removeKey, removeParams);
        }
        LinearLayout.LayoutParams actionsParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        actionsParams.topMargin = Ui.dp(this, 4);
        aiCard.addView(keyActions, actionsParams);
        content.addView(aiCard, cardParams());

        TextView localTip = text("💡 Для полностью локальной модели запустите Ollama или LM Studio на компьютере, " +
                "укажите его адрес в локальной сети (например, http://192.168.1.2:11434/v1) и включите нейросеть.",
                13, 0xFFD8CCFF, false);
        localTip.setLineSpacing(0, 1.12f);
        localTip.setPadding(Ui.dp(this, 15), Ui.dp(this, 13), Ui.dp(this, 15), Ui.dp(this, 13));
        localTip.setBackground(Ui.roundedStroke(0x221E123C, 0xFF392862, 15, this));
        LinearLayout.LayoutParams tipParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        tipParams.bottomMargin = Ui.dp(this, 18);
        content.addView(localTip, tipParams);

        Button save = primaryButton("Сохранить настройки");
        save.setOnClickListener(v -> {
            String endpointValue = endpoint.getText().toString().trim();
            String modelValue = model.getText().toString().trim();
            if (aiSwitch.isChecked() && !(endpointValue.startsWith("https://") || endpointValue.startsWith("http://"))) {
                endpoint.setError("Адрес должен начинаться с http:// или https://");
                endpoint.requestFocus();
                return;
            }
            if (aiSwitch.isChecked() && modelValue.isEmpty()) {
                model.setError("Укажите модель");
                model.requestFocus();
                return;
            }
            try {
                settings.save(aiSwitch.isChecked(), webSwitch.isChecked(),
                        endpointValue, modelValue, apiKey.getText().toString());
                Toast.makeText(this, "Настройки сохранены", Toast.LENGTH_SHORT).show();
                onBackPressed();
            } catch (Exception error) {
                Toast.makeText(this, "Не удалось зашифровать ключ", Toast.LENGTH_LONG).show();
            }
        });
        content.addView(save, new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 52)));

        content.addView(sectionLabel("ДАННЫЕ"));
        LinearLayout dataCard = settingsCard();
        TextView dataTitle = text("История хранится только на устройстве", 15, Ui.TEXT, true);
        dataCard.addView(dataTitle);
        TextView dataHint = text("Чаты сохраняются в локальной базе. API-ключ защищён Android Keystore.",
                13, Ui.MUTED, false);
        LinearLayout.LayoutParams dataHintParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        dataHintParams.topMargin = Ui.dp(this, 6);
        dataHintParams.bottomMargin = Ui.dp(this, 11);
        dataCard.addView(dataHint, dataHintParams);
        Button clear = inlineButton("Удалить все чаты");
        clear.setTextColor(Ui.DANGER);
        clear.setOnClickListener(v -> clearAllDialog());
        dataCard.addView(clear, new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 44)));
        content.addView(dataCard, cardParams());

        TextView version = text("Искра AI 1.0.0  •  Сделано для Android", 12, Ui.DIM, false);
        version.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams versionParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        versionParams.topMargin = Ui.dp(this, 8);
        content.addView(version, versionParams);
    }

    private void clearAllDialog() {
        if (requestRunning) {
            Toast.makeText(this, "Дождитесь текущего ответа перед очисткой истории", Toast.LENGTH_SHORT).show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Удалить все чаты?")
                .setMessage("Все диалоги и ответы будут удалены с устройства.")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Удалить всё", (dialog, which) -> {
                    database.clearAll();
                    Toast.makeText(this, "История удалена", Toast.LENGTH_SHORT).show();
                })
                .show();
    }

    private EditText formField(LinearLayout parent, String label, String value,
                               String hint, int inputType) {
        TextView labelView = text(label, 11, Ui.MUTED, true);
        labelView.setLetterSpacing(0.08f);
        LinearLayout.LayoutParams labelParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        labelParams.topMargin = Ui.dp(this, 7);
        labelParams.bottomMargin = Ui.dp(this, 5);
        parent.addView(labelView, labelParams);

        EditText input = new EditText(this);
        input.setText(value);
        input.setHint(hint);
        input.setHintTextColor(Ui.DIM);
        input.setTextColor(Ui.TEXT);
        input.setTextSize(14);
        input.setSingleLine(true);
        input.setInputType(inputType);
        input.setPadding(Ui.dp(this, 13), 0, Ui.dp(this, 13), 0);
        input.setBackground(Ui.roundedStroke(Ui.BG, 0xFF29364A, 12, this));
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 50));
        inputParams.bottomMargin = Ui.dp(this, 8);
        parent.addView(input, inputParams);
        return input;
    }

    private LinearLayout settingsCard() {
        LinearLayout card = vertical();
        card.setPadding(Ui.dp(this, 16), Ui.dp(this, 15), Ui.dp(this, 16), Ui.dp(this, 15));
        card.setBackground(Ui.roundedStroke(Ui.CARD, 0xFF222E40, 18, this));
        return card;
    }

    private LinearLayout.LayoutParams cardParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(matchValue(), wrap());
        params.bottomMargin = Ui.dp(this, 17);
        return params;
    }

    private TextView sectionLabel(String value) {
        TextView label = text(value, 11, Ui.DIM, true);
        label.setLetterSpacing(0.12f);
        label.setPadding(Ui.dp(this, 3), Ui.dp(this, 9), 0, Ui.dp(this, 8));
        return label;
    }

    private Button primaryButton(String value) {
        Button button = new Button(this);
        button.setText(value);
        button.setTextColor(Ui.TEXT);
        button.setTextSize(14);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        button.setAllCaps(false);
        button.setGravity(Gravity.CENTER);
        button.setPadding(Ui.dp(this, 17), 0, Ui.dp(this, 17), 0);
        button.setBackground(Ui.ripple(Ui.gradient(Ui.VIOLET, Ui.VIOLET_DARK, 15, this), 0x55FFFFFF));
        return button;
    }

    private Button secondaryButton(String value) {
        Button button = new Button(this);
        button.setText(value);
        button.setTextColor(0xFFD8CCFF);
        button.setTextSize(14);
        button.setAllCaps(false);
        button.setPadding(Ui.dp(this, 16), 0, Ui.dp(this, 16), 0);
        button.setBackground(Ui.ripple(
                Ui.roundedStroke(0x228B5CF6, 0xFF59408C, 14, this), 0x338B5CF6));
        return button;
    }

    private Button inlineButton(String value) {
        Button button = new Button(this);
        button.setText(value);
        button.setTextColor(Ui.CYAN);
        button.setTextSize(12);
        button.setAllCaps(false);
        button.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 8), 0);
        button.setBackground(Ui.ripple(
                Ui.roundedStroke(Color.TRANSPARENT, 0xFF273448, 11, this), 0x2239D9C8));
        return button;
    }

    private TextView text(String value, float size, int color, boolean bold) {
        TextView view = Ui.text(this, value, size, color);
        if (bold) view.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return view;
    }

    private LinearLayout vertical() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private LinearLayout horizontal(int gravity) {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setGravity(gravity);
        return layout;
    }

    private FrameLayout.LayoutParams match() {
        return new FrameLayout.LayoutParams(matchValue(), matchValue());
    }

    private FrameLayout.LayoutParams matchWidthWrap() {
        return new FrameLayout.LayoutParams(matchValue(), wrap());
    }

    private int matchValue() { return ViewGroup.LayoutParams.MATCH_PARENT; }
    private int wrap() { return ViewGroup.LayoutParams.WRAP_CONTENT; }

    private EditText dialogInput(String value, String hint) {
        EditText input = new EditText(this);
        input.setText(value);
        input.setHint(hint);
        input.setTextColor(Ui.TEXT);
        input.setHintTextColor(Ui.DIM);
        input.setSingleLine(true);
        input.setBackground(Ui.roundedStroke(Ui.CARD, 0xFF334158, 12, this));
        input.setPadding(Ui.dp(this, 13), 0, Ui.dp(this, 13), 0);
        return input;
    }

    private View wrapDialogInput(EditText input) {
        FrameLayout wrapper = new FrameLayout(this);
        wrapper.setPadding(Ui.dp(this, 22), Ui.dp(this, 8), Ui.dp(this, 22), 0);
        wrapper.addView(input, new FrameLayout.LayoutParams(matchValue(), Ui.dp(this, 52)));
        return wrapper;
    }

    private void openUrl(String value) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(value)));
        } catch (Exception error) {
            Toast.makeText(this, "Не удалось открыть ссылку", Toast.LENGTH_SHORT).show();
        }
    }

    private void hideKeyboard() {
        View focus = getCurrentFocus();
        if (focus != null) {
            InputMethodManager manager = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            if (manager != null) manager.hideSoftInputFromWindow(focus.getWindowToken(), 0);
        }
    }

    private abstract static class SimpleTextWatcher implements TextWatcher {
        @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
        @Override public void onTextChanged(CharSequence s, int start, int before, int count) {}
    }
}
