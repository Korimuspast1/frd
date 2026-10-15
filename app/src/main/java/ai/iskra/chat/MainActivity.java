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
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.text.InputType;
import android.text.TextWatcher;
import android.text.Editable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.animation.DecelerateInterpolator;
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
import ai.iskra.chat.ui.AmbientBackgroundView;
import ai.iskra.chat.ui.AssistantOrbView;
import ai.iskra.chat.ui.ChatListAdapter;
import ai.iskra.chat.ui.DebugConsoleView;
import ai.iskra.chat.ui.MessageAdapter;
import ai.iskra.chat.ui.ShatterOverlay;
import ai.iskra.chat.util.DebugLog;
import ai.iskra.chat.util.TextUtilsEx;
import ai.iskra.chat.util.Ui;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

public final class MainActivity extends Activity {
    private static final int VOICE_REQUEST_CODE = 4281;
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
    private FrameLayout drawerOverlay;
    private EditText homeComposer;
    private ImageButton homeActionButton;
    private ImageButton currentVoiceButton;

    private MessageAdapter messageAdapter;
    private ListView messageList;
    private EditText composer;
    private ImageButton sendButton;
    private TextView currentChatTitle;
    private TextView currentMode;

    private boolean requestRunning;
    private long requestChatId = -1;
    private String lastQuestion = "";
    private TextToSpeech textToSpeech;
    private boolean textToSpeechReady;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureWindow();
        settings = new AppSettings(this);
        DebugLog.initialize(settings.isDebugEnabled());
        DebugLog.log("APP", "kvsai 1.2.0 starting; Android=" + Build.VERSION.RELEASE +
                ", sdk=" + Build.VERSION.SDK_INT + ", device=" + Build.MANUFACTURER + " " + Build.MODEL);
        database = new ChatDatabase(this);
        assistant = new AssistantEngine(this);
        if (settings.isVoiceEnabled()) initializeSpeech();

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
        DebugLog.log("LIFECYCLE", "onResume screen=" + screen);
        if (screen == Screen.HOME && chatListAdapter != null) refreshChats();
    }

    @Override
    protected void onDestroy() {
        DebugLog.log("LIFECYCLE", "onDestroy; finishing=" + isFinishing());
        assistant.shutdown();
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }
        database.close();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (drawerOverlay != null) {
            closeDrawer(null);
            return;
        }
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
        drawerOverlay = null;

        DebugLog.log("NAV", "Open HOME screen");
        LinearLayout root = vertical();
        root.setBackgroundColor(Color.TRANSPARENT);
        mountScreen(root);
        root.addView(buildFloatingTopBar(null));
        root.addView(buildHomeCenter(), new LinearLayout.LayoutParams(matchValue(), 0, 1f));
        root.addView(buildHomeComposer());
        animateScreenIn(root);
    }

    private View buildFloatingTopBar(String chatTitle) {
        LinearLayout bar = horizontal(Gravity.CENTER_VERTICAL);
        bar.setPadding(Ui.dp(this, 24), Ui.dp(this, 11), Ui.dp(this, 24), Ui.dp(this, 8));

        ImageButton menu = Ui.iconButton(this, R.drawable.ic_menu, "Открыть меню и чаты");
        menu.setOnClickListener(v -> showDrawer());
        bar.addView(menu, new LinearLayout.LayoutParams(Ui.dp(this, 58), Ui.dp(this, 58)));

        LinearLayout pill = horizontal(Gravity.CENTER_VERTICAL);
        pill.setPadding(Ui.dp(this, 18), 0, Ui.dp(this, 18), 0);
        pill.setBackground(Ui.ripple(Ui.glass(this, 99), 0x2AFFFFFF));
        pill.setElevation(Ui.dp(this, 5));
        pill.setContentDescription(chatTitle == null ? "Режим kvsai и настройки" : "Название чата — нажмите, чтобы изменить");
        TextView primary = text(chatTitle == null ? "kvsai" : TextUtilsEx.compact(chatTitle, 22),
                17, Ui.TEXT, true);
        primary.setMaxLines(1);
        primary.setEllipsize(android.text.TextUtils.TruncateAt.END);
        pill.addView(primary, new LinearLayout.LayoutParams(0, wrap(), 1f));
        String modeLabel = settings.isAiEnabled() ? "AI" : "Web";
        TextView secondary = text("  " + modeLabel, 14, 0xFF9D9EA3, false);
        secondary.setMaxLines(1);
        pill.addView(secondary);
        if (chatTitle != null) {
            currentChatTitle = primary;
            currentMode = secondary;
        } else {
            currentChatTitle = null;
            currentMode = null;
        }
        pill.setOnClickListener(v -> {
            if (chatTitle != null) renameDialog(database.getChat(currentChatId));
            else openSettings();
        });
        LinearLayout.LayoutParams pillParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 54), 1f);
        pillParams.leftMargin = Ui.dp(this, 16);
        pillParams.rightMargin = Ui.dp(this, 16);
        bar.addView(pill, pillParams);

        currentVoiceButton = Ui.iconButton(this,
                settings.isVoiceEnabled() ? R.drawable.ic_volume_on : R.drawable.ic_volume_off,
                "Автоозвучка ответов");
        currentVoiceButton.setOnClickListener(v -> toggleVoice());
        bar.addView(currentVoiceButton, new LinearLayout.LayoutParams(Ui.dp(this, 58), Ui.dp(this, 58)));
        return bar;
    }

    private View buildHomeCenter() {
        LinearLayout center = vertical();
        center.setGravity(Gravity.CENTER);
        center.setPadding(Ui.dp(this, 28), 0, Ui.dp(this, 28), Ui.dp(this, 24));
        AssistantOrbView orb = new AssistantOrbView(this);
        orb.setOnClickListener(v -> createChat());
        center.addView(orb, new LinearLayout.LayoutParams(Ui.dp(this, 150), Ui.dp(this, 150)));

        TextView greeting = text("Привет,", 27, 0xFFE7E7E9, false);
        greeting.setTypeface(Typeface.create("sans-serif-light", Typeface.NORMAL));
        greeting.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams greetingParams = new LinearLayout.LayoutParams(wrap(), wrap());
        greetingParams.topMargin = Ui.dp(this, 17);
        center.addView(greeting, greetingParams);

        TextView subtitle = text("давайте создадим что-нибудь", 25, 0xFFD6D6D9, false);
        subtitle.setTypeface(Typeface.create("sans-serif-light", Typeface.NORMAL));
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(wrap(), wrap());
        subtitleParams.topMargin = Ui.dp(this, 8);
        center.addView(subtitle, subtitleParams);
        return center;
    }

    private View buildHomeComposer() {
        FrameLayout outer = new FrameLayout(this);
        outer.setPadding(Ui.dp(this, 24), Ui.dp(this, 8), Ui.dp(this, 24), Ui.dp(this, 20));
        LinearLayout box = horizontal(Gravity.CENTER_VERTICAL);
        box.setPadding(Ui.dp(this, 10), Ui.dp(this, 7), Ui.dp(this, 9), Ui.dp(this, 7));
        box.setBackground(Ui.glass(this, 36));
        box.setElevation(Ui.dp(this, 7));

        TextView add = text("＋", 28, 0xFFE8E8EA, false);
        add.setGravity(Gravity.CENTER);
        add.setBackground(Ui.ripple(Ui.glassSoft(this, 99), 0x32FFFFFF));
        add.setContentDescription("Создать пустой чат");
        add.setOnClickListener(v -> createChat());
        box.addView(add, new LinearLayout.LayoutParams(Ui.dp(this, 56), Ui.dp(this, 56)));

        homeComposer = new EditText(this);
        homeComposer.setHint("Спросите. Поручите.");
        homeComposer.setHintTextColor(0xFF8F9095);
        homeComposer.setTextColor(Ui.TEXT);
        homeComposer.setTextSize(18);
        homeComposer.setSingleLine(true);
        homeComposer.setBackgroundColor(Color.TRANSPARENT);
        homeComposer.setPadding(Ui.dp(this, 18), 0, Ui.dp(this, 8), 0);
        homeComposer.setImeOptions(EditorInfo.IME_ACTION_SEND);
        homeComposer.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                submitHomeComposer();
                return true;
            }
            return false;
        });
        homeComposer.addTextChangedListener(new SimpleTextWatcher() {
            @Override public void afterTextChanged(Editable value) {
                boolean hasText = !value.toString().trim().isEmpty();
                homeActionButton.setImageResource(hasText ? R.drawable.ic_send : R.drawable.ic_waveform);
                homeActionButton.setAlpha(hasText ? 1f : 0.82f);
            }
        });
        box.addView(homeComposer, new LinearLayout.LayoutParams(0, Ui.dp(this, 58), 1f));

        homeActionButton = new ImageButton(this);
        homeActionButton.setImageResource(R.drawable.ic_waveform);
        homeActionButton.setContentDescription("Отправить или продиктовать");
        homeActionButton.setPadding(Ui.dp(this, 15), Ui.dp(this, 15), Ui.dp(this, 15), Ui.dp(this, 15));
        homeActionButton.setBackground(Ui.ripple(Ui.glassSoft(this, 99), 0x32FFFFFF));
        homeActionButton.setOnClickListener(v -> {
            if (homeComposer.getText().toString().trim().isEmpty()) startVoiceInput();
            else submitHomeComposer();
        });
        box.addView(homeActionButton, new LinearLayout.LayoutParams(Ui.dp(this, 56), Ui.dp(this, 56)));
        outer.addView(box, new FrameLayout.LayoutParams(matchValue(), Ui.dp(this, 72)));
        return outer;
    }

    private void submitHomeComposer() {
        if (homeComposer == null) return;
        String question = homeComposer.getText().toString().trim();
        if (question.isEmpty()) return;
        long chatId = database.createChat();
        DebugLog.log("UI", "Home prompt created chat=" + chatId);
        showChat(chatId);
        askAssistant(chatId, question, true);
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
        names.addView(text("kvsai", 20, Ui.TEXT, true));
        names.addView(text("AI, интернет и данные устройства", 12, Ui.MUTED, false));
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

    private void showDrawer() {
        if (drawerOverlay != null) return;
        hideKeyboard();
        DebugLog.log("NAV", "Open glass navigation drawer");
        drawerOverlay = new FrameLayout(this);

        View dim = new View(this);
        dim.setBackgroundColor(0xA6000000);
        dim.setAlpha(0f);
        dim.setOnClickListener(v -> closeDrawer(null));
        drawerOverlay.addView(dim, match());

        LinearLayout panel = vertical();
        panel.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 16));
        panel.setBackground(Ui.glass(this, 0));
        panel.setElevation(Ui.dp(this, 18));

        LinearLayout drawerHeader = horizontal(Gravity.CENTER_VERTICAL);
        TextView brand = text("kvsai", 24, Ui.TEXT, true);
        brand.setPadding(Ui.dp(this, 8), 0, 0, 0);
        drawerHeader.addView(brand, new LinearLayout.LayoutParams(0, Ui.dp(this, 54), 1f));
        ImageButton close = Ui.iconButton(this, R.drawable.ic_close, "Закрыть меню");
        close.setOnClickListener(v -> closeDrawer(null));
        drawerHeader.addView(close, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));
        panel.addView(drawerHeader);

        TextView status = text(settings.snapshot().modeLabel() + "  •  online", 12, 0xFF9EA3AC, false);
        status.setPadding(Ui.dp(this, 9), 0, 0, Ui.dp(this, 12));
        panel.addView(status);

        TextView home = drawerAction("Главная", R.drawable.ic_home);
        home.setOnClickListener(v -> closeDrawer(this::showHome));
        panel.addView(home, new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 50)));

        TextView newChat = drawerAction("Новый чат", R.drawable.ic_add);
        newChat.setOnClickListener(v -> closeDrawer(this::createChat));
        LinearLayout.LayoutParams newChatParams = new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 50));
        newChatParams.topMargin = Ui.dp(this, 7);
        panel.addView(newChat, newChatParams);

        TextView label = text("ДИАЛОГИ", 10, 0xFF858991, true);
        label.setLetterSpacing(0.13f);
        label.setPadding(Ui.dp(this, 9), Ui.dp(this, 19), 0, Ui.dp(this, 7));
        panel.addView(label);

        LinearLayout searchBox = horizontal(Gravity.CENTER_VERTICAL);
        searchBox.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 10), 0);
        searchBox.setBackground(Ui.glassSoft(this, 18));
        ImageView searchIcon = new ImageView(this);
        searchIcon.setImageResource(R.drawable.ic_search);
        searchBox.addView(searchIcon, new LinearLayout.LayoutParams(Ui.dp(this, 20), Ui.dp(this, 20)));
        chatSearch = new EditText(this);
        chatSearch.setHint("Найти чат");
        chatSearch.setHintTextColor(0xFF7F8289);
        chatSearch.setTextColor(Ui.TEXT);
        chatSearch.setTextSize(14);
        chatSearch.setSingleLine(true);
        chatSearch.setBackgroundColor(Color.TRANSPARENT);
        chatSearch.setPadding(Ui.dp(this, 9), 0, 0, 0);
        chatSearch.addTextChangedListener(new SimpleTextWatcher() {
            @Override public void afterTextChanged(Editable editable) { refreshChats(); }
        });
        searchBox.addView(chatSearch, new LinearLayout.LayoutParams(0, Ui.dp(this, 46), 1f));
        panel.addView(searchBox, new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 46)));

        FrameLayout listFrame = new FrameLayout(this);
        ListView list = new ListView(this);
        list.setDivider(null);
        list.setSelector(android.R.color.transparent);
        list.setVerticalScrollBarEnabled(false);
        list.setClipToPadding(false);
        list.setPadding(0, Ui.dp(this, 5), 0, Ui.dp(this, 8));
        chatListAdapter = new ChatListAdapter(this, new ChatListAdapter.Listener() {
            @Override public void onOpen(Chat chat) { closeDrawer(() -> showChat(chat.id)); }
            @Override public void onMenu(Chat chat, View card) { showChatMenu(chat, card); }
        });
        list.setAdapter(chatListAdapter);
        listFrame.addView(list, match());
        LinearLayout empty = vertical();
        empty.setGravity(Gravity.CENTER);
        TextView emptyIcon = text("✦", 28, 0xFF6C8FEF, false);
        emptyIcon.setGravity(Gravity.CENTER);
        empty.addView(emptyIcon, new LinearLayout.LayoutParams(Ui.dp(this, 56), Ui.dp(this, 56)));
        TextView emptyText = text("Диалогов пока нет", 13, 0xFF8B8E95, false);
        emptyText.setGravity(Gravity.CENTER);
        empty.addView(emptyText);
        listFrame.addView(empty, match());
        list.setEmptyView(empty);
        panel.addView(listFrame, new LinearLayout.LayoutParams(matchValue(), 0, 1f));

        TextView settingsRow = drawerAction("Настройки", R.drawable.ic_settings);
        settingsRow.setOnClickListener(v -> closeDrawer(this::openSettings));
        panel.addView(settingsRow, new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 52)));

        int panelWidth = Math.min((int) (getResources().getDisplayMetrics().widthPixels * 0.87f), Ui.dp(this, 390));
        FrameLayout.LayoutParams panelParams = new FrameLayout.LayoutParams(panelWidth, matchValue());
        panelParams.gravity = Gravity.START;
        drawerOverlay.addView(panel, panelParams);
        host.addView(drawerOverlay, match());
        refreshChats();

        panel.setTranslationX(-panelWidth - Ui.dp(this, 20));
        panel.setAlpha(0.72f);
        panel.animate().translationX(0).alpha(1f).setDuration(360)
                .setInterpolator(new DecelerateInterpolator()).start();
        dim.animate().alpha(1f).setDuration(300).start();
    }

    private TextView drawerAction(String label, int icon) {
        TextView item = text("     " + label, 15, Ui.TEXT, false);
        item.setGravity(Gravity.CENTER_VERTICAL);
        item.setCompoundDrawablesWithIntrinsicBounds(icon, 0, 0, 0);
        item.setCompoundDrawablePadding(Ui.dp(this, 12));
        item.setPadding(Ui.dp(this, 15), 0, Ui.dp(this, 15), 0);
        item.setBackground(Ui.ripple(Ui.glassSoft(this, 17), 0x2AFFFFFF));
        return item;
    }

    private void closeDrawer(Runnable after) {
        if (drawerOverlay == null) {
            if (after != null) after.run();
            return;
        }
        FrameLayout closing = drawerOverlay;
        drawerOverlay = null;
        View panel = closing.getChildAt(1);
        View dim = closing.getChildAt(0);
        panel.animate().translationX(-panel.getWidth() - Ui.dp(this, 20)).alpha(0.65f)
                .setDuration(280).setInterpolator(new DecelerateInterpolator()).start();
        dim.animate().alpha(0f).setDuration(260).withEndAction(() -> {
            host.removeView(closing);
            if (after != null) after.run();
        }).start();
    }

    private void createChat() {
        long id = database.createChat();
        DebugLog.log("UI", "New chat button; created id=" + id);
        showChat(id);
    }

    private void showChatMenu(Chat chat, View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add("Переименовать");
        menu.getMenu().add("Удалить");
        menu.setOnMenuItemClickListener(item -> {
            if ("Переименовать".contentEquals(item.getTitle())) renameDialog(chat);
            else deleteDialog(chat, anchor);
            return true;
        });
        menu.show();
    }

    private void renameDialog(Chat chat) {
        if (chat == null) return;
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

    private void deleteDialog(Chat chat, View card) {
        if (requestRunning && requestChatId == chat.id) {
            Toast.makeText(this, "Дождитесь ответа перед удалением этого чата", Toast.LENGTH_SHORT).show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Разбить и удалить чат?")
                .setMessage("Диалог «" + chat.title + "» рассыплется и будет удалён без возможности восстановления.")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Удалить", (dialog, which) ->
                        ShatterOverlay.shatter(this, card, () -> {
                            database.deleteChat(chat.id);
                            if (screen == Screen.CHAT && currentChatId == chat.id) {
                                closeDrawer(this::showHome);
                            } else {
                                refreshChats();
                            }
                        }))
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

        DebugLog.log("NAV", "Open CHAT screen id=" + chatId + ", title=\"" + chat.title + "\"");
        LinearLayout root = vertical();
        root.setBackgroundColor(Color.TRANSPARENT);
        mountScreen(root);
        root.addView(buildFloatingTopBar(chat.title));

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
        animateScreenIn(root);
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

        AssistantOrbView spark = new AssistantOrbView(this);
        empty.addView(spark, new LinearLayout.LayoutParams(Ui.dp(this, 102), Ui.dp(this, 102)));
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

        addSuggestion(empty, "Какая погода завтра в Москве?");
        addSuggestion(empty, "Покажи характеристики моего телефона");
        addSuggestion(empty, "Напиши пример кода на Python с пояснениями");
        return scroll;
    }

    private void addSuggestion(LinearLayout parent, String value) {
        TextView chip = text(value + "  →", 14, Ui.TEXT, false);
        chip.setGravity(Gravity.CENTER_VERTICAL);
        chip.setPadding(Ui.dp(this, 15), Ui.dp(this, 12), Ui.dp(this, 15), Ui.dp(this, 12));
        chip.setBackground(Ui.ripple(Ui.glassSoft(this, 18), 0x2AFFFFFF));
        chip.setElevation(Ui.dp(this, 2));
        chip.setOnClickListener(v -> sendQuestion(value));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(matchValue(), wrap());
        params.bottomMargin = Ui.dp(this, 9);
        parent.addView(chip, params);
    }

    private View buildComposer() {
        FrameLayout area = new FrameLayout(this);
        area.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 16));

        LinearLayout box = horizontal(Gravity.CENTER_VERTICAL);
        box.setPadding(Ui.dp(this, 8), Ui.dp(this, 7), Ui.dp(this, 8), Ui.dp(this, 7));
        box.setBackground(Ui.glass(this, 34));
        box.setElevation(Ui.dp(this, 7));

        TextView add = text("＋", 25, 0xFFE6E6E8, false);
        add.setGravity(Gravity.CENTER);
        add.setContentDescription("Новый чат");
        add.setBackground(Ui.ripple(Ui.glassSoft(this, 99), 0x32FFFFFF));
        add.setOnClickListener(v -> createChat());
        box.addView(add, new LinearLayout.LayoutParams(Ui.dp(this, 50), Ui.dp(this, 50)));

        composer = new EditText(this);
        composer.setHint("Спросите меня…");
        composer.setHintTextColor(0xFF8E9096);
        composer.setTextColor(Ui.TEXT);
        composer.setTextSize(16);
        composer.setBackgroundColor(Color.TRANSPARENT);
        composer.setPadding(Ui.dp(this, 14), Ui.dp(this, 7), Ui.dp(this, 8), Ui.dp(this, 7));
        composer.setMinLines(1);
        composer.setMaxLines(4);
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

        sendButton = new ImageButton(this);
        sendButton.setImageResource(R.drawable.ic_waveform);
        sendButton.setContentDescription("Отправить или продиктовать");
        sendButton.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
        sendButton.setBackground(Ui.ripple(Ui.glassBlue(this, 99), 0x55FFFFFF));
        sendButton.setOnClickListener(v -> {
            if (composer.getText().toString().trim().isEmpty()) startVoiceInput();
            else submitComposer();
        });
        box.addView(sendButton, new LinearLayout.LayoutParams(Ui.dp(this, 52), Ui.dp(this, 52)));
        area.addView(box, new FrameLayout.LayoutParams(matchValue(), wrap()));
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
        DebugLog.log("CHAT", (addUserMessage ? "Send" : "Retry") + " chat=" + chatId +
                ", chars=" + question.length() + ", text=\"" + question + "\"");
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
                DebugLog.log("CHAT", "Assistant callback success chat=" + chatId +
                        ", chars=" + reply.text.length() + ", sources=" + reply.sources.size());
                if (database.getChat(chatId) != null) {
                    database.addMessage(chatId, ChatMessage.ROLE_ASSISTANT, reply.text, reply.sources);
                }
                speakReply(reply.text);
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
                DebugLog.log("CHAT", "Assistant callback error chat=" + chatId + ": " + error);
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
        boolean enabled = !requestRunning;
        sendButton.setImageResource(hasText ? R.drawable.ic_send : R.drawable.ic_waveform);
        sendButton.setEnabled(enabled);
        sendButton.setAlpha(enabled ? 1f : 0.42f);
        if (composer != null) composer.setEnabled(!requestRunning);
    }

    private void scrollMessagesToEnd() {
        if (messageList == null || messageAdapter == null || messageAdapter.getCount() == 0) return;
        messageList.post(() -> messageList.setSelection(messageAdapter.getCount() - 1));
    }

    private void openSettings() {
        DebugLog.log("UI", "Settings button from " + screen);
        settingsReturnScreen = screen;
        settingsReturnChatId = currentChatId;
        showSettings();
    }

    @SuppressWarnings("deprecation")
    private void showSettings() {
        screen = Screen.SETTINGS;
        host.removeAllViews();
        DebugLog.log("NAV", "Open SETTINGS screen; return=" + settingsReturnScreen);
        LinearLayout root = vertical();
        root.setBackgroundColor(Color.TRANSPARENT);
        mountScreen(root);

        LinearLayout header = horizontal(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(this, 24), Ui.dp(this, 11), Ui.dp(this, 24), Ui.dp(this, 8));
        ImageButton back = Ui.iconButton(this, R.drawable.ic_back, "Назад");
        back.setOnClickListener(v -> onBackPressed());
        header.addView(back, new LinearLayout.LayoutParams(Ui.dp(this, 58), Ui.dp(this, 58)));
        TextView title = text("Настройки", 18, Ui.TEXT, true);
        title.setGravity(Gravity.CENTER);
        title.setBackground(Ui.glass(this, 99));
        title.setElevation(Ui.dp(this, 5));
        LinearLayout.LayoutParams settingsTitleParams = new LinearLayout.LayoutParams(0, Ui.dp(this, 54), 1f);
        settingsTitleParams.leftMargin = Ui.dp(this, 16);
        header.addView(title, settingsTitleParams);
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
        TextView webHint = text("Бесплатно и без API-ключа. kvsai найдёт материалы и покажет ссылки на источники.",
                13, Ui.MUTED, false);
        webHint.setLineSpacing(0, 1.08f);
        LinearLayout.LayoutParams webHintParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        webHintParams.topMargin = Ui.dp(this, 7);
        webCard.addView(webHint, webHintParams);
        content.addView(webCard, cardParams());

        LinearLayout voiceCard = settingsCard();
        Switch voiceSwitch = new Switch(this);
        voiceSwitch.setText("Автоозвучка ответов");
        voiceSwitch.setTextColor(Ui.TEXT);
        voiceSwitch.setTextSize(16);
        voiceSwitch.setChecked(settings.isVoiceEnabled());
        voiceCard.addView(voiceSwitch, matchWidthWrap());
        TextView voiceHint = text("После ответа kvsai прочитает текст системным русским голосом. " +
                "Микрофон в поле ввода работает независимо.", 13, Ui.MUTED, false);
        voiceHint.setLineSpacing(0, 1.08f);
        LinearLayout.LayoutParams voiceHintParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        voiceHintParams.topMargin = Ui.dp(this, 7);
        voiceCard.addView(voiceHint, voiceHintParams);
        voiceSwitch.setOnCheckedChangeListener((button, checked) -> {
            settings.setVoiceEnabled(checked);
            if (checked) initializeSpeech();
            else if (textToSpeech != null) textToSpeech.stop();
            DebugLog.log("VOICE", "Auto speech from settings=" + checked);
        });
        content.addView(voiceCard, cardParams());

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
                13, 0xFFD4E7FF, false);
        localTip.setLineSpacing(0, 1.12f);
        localTip.setPadding(Ui.dp(this, 15), Ui.dp(this, 13), Ui.dp(this, 15), Ui.dp(this, 13));
        localTip.setBackground(Ui.glassBlue(this, 17));
        LinearLayout.LayoutParams tipParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        tipParams.bottomMargin = Ui.dp(this, 18);
        content.addView(localTip, tipParams);

        content.addView(sectionLabel("РАЗРАБОТКА"));
        LinearLayout debugCard = settingsCard();
        Switch debugSwitch = new Switch(this);
        debugSwitch.setText("Debug mode");
        debugSwitch.setTextColor(Ui.TEXT);
        debugSwitch.setTextSize(16);
        debugSwitch.setChecked(settings.isDebugEnabled());
        debugCard.addView(debugSwitch, matchWidthWrap());
        TextView debugHint = text("Показывает снизу живую консоль: навигацию, запросы, маршрутизацию, " +
                "операции базы, HTTP-статусы, время выполнения и ошибки. API-ключи всегда скрываются.",
                13, Ui.MUTED, false);
        debugHint.setLineSpacing(0, 1.08f);
        LinearLayout.LayoutParams debugHintParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        debugHintParams.topMargin = Ui.dp(this, 7);
        debugCard.addView(debugHint, debugHintParams);
        Button clearDebug = inlineButton("Очистить debug-консоль");
        clearDebug.setOnClickListener(v -> DebugLog.clear());
        LinearLayout.LayoutParams clearDebugParams = new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 42));
        clearDebugParams.topMargin = Ui.dp(this, 10);
        debugCard.addView(clearDebug, clearDebugParams);
        content.addView(debugCard, cardParams());

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
                settings.save(aiSwitch.isChecked(), webSwitch.isChecked(), debugSwitch.isChecked(),
                        endpointValue, modelValue, apiKey.getText().toString());
                DebugLog.setEnabled(debugSwitch.isChecked());
                DebugLog.log("SETTINGS", "Saved: ai=" + aiSwitch.isChecked() +
                        ", web=" + webSwitch.isChecked() + ", debug=" + debugSwitch.isChecked() +
                        ", model=" + modelValue + ", endpoint=" + endpointValue +
                        ", newApiKeyProvided=" + !apiKey.getText().toString().isEmpty());
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

        TextView version = text("kvsai 1.2.0  •  Android 8.0+", 12, Ui.DIM, false);
        version.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams versionParams = new LinearLayout.LayoutParams(matchValue(), wrap());
        versionParams.topMargin = Ui.dp(this, 8);
        content.addView(version, versionParams);
        animateScreenIn(root);
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
        input.setBackground(Ui.glassSoft(this, 14));
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 50));
        inputParams.bottomMargin = Ui.dp(this, 8);
        parent.addView(input, inputParams);
        return input;
    }

    private LinearLayout settingsCard() {
        LinearLayout card = vertical();
        card.setPadding(Ui.dp(this, 16), Ui.dp(this, 15), Ui.dp(this, 16), Ui.dp(this, 15));
        card.setBackground(Ui.glassSoft(this, 22));
        card.setElevation(Ui.dp(this, 3));
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
        button.setBackground(Ui.ripple(Ui.glassBlue(this, 18), 0x55FFFFFF));
        button.setElevation(Ui.dp(this, 4));
        return button;
    }

    private Button secondaryButton(String value) {
        Button button = new Button(this);
        button.setText(value);
        button.setTextColor(0xFFD7E8FF);
        button.setTextSize(14);
        button.setAllCaps(false);
        button.setPadding(Ui.dp(this, 16), 0, Ui.dp(this, 16), 0);
        button.setBackground(Ui.ripple(Ui.glassBlue(this, 16), 0x334A9CFF));
        return button;
    }

    private Button inlineButton(String value) {
        Button button = new Button(this);
        button.setText(value);
        button.setTextColor(Ui.CYAN);
        button.setTextSize(12);
        button.setAllCaps(false);
        button.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 8), 0);
        button.setBackground(Ui.ripple(Ui.glassSoft(this, 12), 0x224A9CFF));
        return button;
    }

    private TextView text(String value, float size, int color, boolean bold) {
        TextView view = Ui.text(this, value, size, color);
        if (bold) view.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return view;
    }

    private void mountScreen(View screenView) {
        LinearLayout shell = new LinearLayout(this);
        shell.setOrientation(LinearLayout.VERTICAL);
        shell.setBackgroundColor(0xFF0B0C0E);
        FrameLayout stage = new FrameLayout(this);
        stage.addView(new AmbientBackgroundView(this), match());
        stage.addView(screenView, match());
        shell.addView(stage, new LinearLayout.LayoutParams(matchValue(), 0, 1f));
        if (settings.isDebugEnabled()) {
            DebugConsoleView console = new DebugConsoleView(this);
            shell.addView(console, new LinearLayout.LayoutParams(matchValue(), Ui.dp(this, 180)));
        }
        host.addView(shell, match());
    }

    private void animateScreenIn(View screenView) {
        screenView.setAlpha(0f);
        screenView.setTranslationY(Ui.dp(this, 12));
        screenView.animate().alpha(1f).translationY(0f).setDuration(380)
                .setInterpolator(new DecelerateInterpolator()).start();
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
        input.setBackground(Ui.glassSoft(this, 14));
        input.setPadding(Ui.dp(this, 13), 0, Ui.dp(this, 13), 0);
        return input;
    }

    private View wrapDialogInput(EditText input) {
        FrameLayout wrapper = new FrameLayout(this);
        wrapper.setPadding(Ui.dp(this, 22), Ui.dp(this, 8), Ui.dp(this, 22), 0);
        wrapper.addView(input, new FrameLayout.LayoutParams(matchValue(), Ui.dp(this, 52)));
        return wrapper;
    }

    private void initializeSpeech() {
        if (textToSpeech != null) return;
        textToSpeech = new TextToSpeech(getApplicationContext(), status -> {
            textToSpeechReady = status == TextToSpeech.SUCCESS;
            if (textToSpeechReady) {
                int language = textToSpeech.setLanguage(new Locale("ru", "RU"));
                textToSpeechReady = language != TextToSpeech.LANG_MISSING_DATA
                        && language != TextToSpeech.LANG_NOT_SUPPORTED;
                textToSpeech.setSpeechRate(1.02f);
                textToSpeech.setPitch(1.0f);
            }
            DebugLog.log("VOICE", "TTS initialized; ready=" + textToSpeechReady);
        });
    }

    private void toggleVoice() {
        boolean enabled = !settings.isVoiceEnabled();
        settings.setVoiceEnabled(enabled);
        if (enabled) initializeSpeech();
        else if (textToSpeech != null) textToSpeech.stop();
        if (currentVoiceButton != null) {
            currentVoiceButton.setImageResource(enabled ? R.drawable.ic_volume_on : R.drawable.ic_volume_off);
        }
        DebugLog.log("VOICE", "Auto speech=" + enabled);
        Toast.makeText(this, enabled ? "Автоозвучка включена" : "Автоозвучка выключена", Toast.LENGTH_SHORT).show();
    }

    private void speakReply(String markdown) {
        if (!settings.isVoiceEnabled()) return;
        if (textToSpeech == null) initializeSpeech();
        if (!textToSpeechReady || textToSpeech == null) return;
        String spoken = markdown.replaceAll("(?s)```.*?```", " Блок кода. ")
                .replaceAll("[*_#`]", "")
                .replaceAll("\\[(\\d+)]", "источник $1")
                .replaceAll("\\s+", " ").trim();
        if (spoken.length() > 3800) spoken = spoken.substring(0, 3800);
        textToSpeech.speak(spoken, TextToSpeech.QUEUE_FLUSH, null, "kvsai-reply");
        DebugLog.log("VOICE", "Speaking assistant reply; chars=" + spoken.length());
    }

    private void startVoiceInput() {
        try {
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU");
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Скажите запрос для kvsai");
            startActivityForResult(intent, VOICE_REQUEST_CODE);
            DebugLog.log("VOICE", "System speech recognizer opened");
        } catch (Exception error) {
            DebugLog.error("VOICE", error);
            Toast.makeText(this, "На устройстве нет голосового ввода", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != VOICE_REQUEST_CODE || resultCode != RESULT_OK || data == null) return;
        ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
        if (results == null || results.isEmpty()) return;
        String value = results.get(0).trim();
        DebugLog.log("VOICE", "Recognized input chars=" + value.length());
        if (screen == Screen.HOME && homeComposer != null) {
            homeComposer.setText(value);
            homeComposer.setSelection(value.length());
            submitHomeComposer();
        } else if (screen == Screen.CHAT && composer != null) {
            composer.setText(value);
            composer.setSelection(value.length());
            submitComposer();
        }
    }

    private void openUrl(String value) {
        try {
            DebugLog.log("UI", "Open external URL: " + value);
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(value)));
        } catch (Exception error) {
            DebugLog.error("UI", error);
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
