using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
using TMPro;

/// <summary>
/// Main menu manager for Beepnook shop game.
/// Creates the main menu UI programmatically to match the reference style:
/// isometric shop background, title banner, and menu buttons.
/// Theme: Gadget / Tech Shop (NOT a repair shop).
/// </summary>
[RequireComponent(typeof(Canvas))]
[RequireComponent(typeof(GraphicRaycaster))]
public class MainMenuManager : MonoBehaviour
{
    [Header("Theme (change these to rebrand)")]
    [SerializeField] private string shopName = "BEEPNOOK";
    [SerializeField] private string shopSubtitle = "GADGET SHOP";
    [SerializeField] private Color titleColor = new Color(1f, 0.82f, 0.35f);   // yellow like reference
    [SerializeField] private Color subtitleBgColor = new Color(0.55f, 0.42f, 0.78f); // purple banner
    [SerializeField] private Color buttonColor = new Color(1f, 0.65f, 0.75f);   // pink continue button
    [SerializeField] private Color buttonTextColor = Color.black;

    [Header("Scene names")]
    [SerializeField] private string gameSceneName = "Game";

    private Canvas _canvas;
    private Camera _uiCamera;

    private void Awake()
    {
        _canvas = GetComponent<Canvas>();
        _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        _canvas.sortingOrder = 100;

        // Ensure an EventSystem exists for button input
        if (FindObjectOfType<UnityEngine.EventSystems.EventSystem>() == null)
        {
            var esGO = new GameObject("EventSystem");
            esGO.AddComponent<UnityEngine.EventSystems.EventSystem>();
            esGO.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
        }
    }

    private void Start()
    {
        BuildMenu();
    }

    private void BuildMenu()
    {
        // Background panel (full screen, light blue like reference)
        var bg = CreatePanel("BG", Color.clear, anchorMin: Vector2.zero, anchorMax: Vector2.one, offsetMin: Vector2.zero, offsetMax: Vector2.zero);
        var bgImage = bg.AddComponent<Image>();
        bgImage.color = new Color(0.86f, 0.93f, 1f); // light sky blue

        // Center container for title + buttons
        var container = CreatePanel("Container", Color.clear,
            anchorMin: new Vector2(0.5f, 0.5f), anchorMax: new Vector2(0.5f, 0.5f),
            offsetMin: new Vector2(-420, -520), offsetMax: new Vector2(420, 520),
            parent: bg.transform);

        // --- Title text ---
        var title = CreateText("Title", shopName,
            fontSize: 64, color: titleColor,
            anchorMin: new Vector2(0.5f, 1f), anchorMax: new Vector2(0.5f, 1f),
            offsetMin: new Vector2(-300, -420), offsetMax: new Vector2(300, -280),
            parent: container.transform, alignment: TextAlignmentOptions.Center);
        // Outline effect for bubbly look
        var outline = title.gameObject.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(3, 3);

        // --- Subtitle banner ---
        var banner = CreatePanel("Banner", subtitleBgColor,
            anchorMin: new Vector2(0.5f, 1f), anchorMax: new Vector2(0.5f, 1f),
            offsetMin: new Vector2(-160, -260), offsetMax: new Vector2(160, -210),
            parent: container.transform);
        var bannerText = CreateText("BannerText", shopSubtitle,
            fontSize: 24, color: Color.white,
            anchorMin: Vector2.zero, anchorMax: Vector2.one,
            offsetMin: Vector2.zero, offsetMax: Vector2.zero,
            parent: banner.transform, alignment: TextAlignmentOptions.Center);
        var bannerOutline = bannerText.gameObject.AddComponent<Outline>();
        bannerOutline.effectColor = Color.black;
        bannerOutline.effectDistance = new Vector2(2, 2);

        // --- Continue button (pink, large, like reference) ---
        var continueBtn = CreateButton("BtnContinue", "▶  Continue",
            buttonColor, buttonTextColor,
            fontSize: 32,
            anchorMin: new Vector2(0.5f, 1f), anchorMax: new Vector2(0.5f, 1f),
            offsetMin: new Vector2(-260, -150), offsetMax: new Vector2(260, -70),
            parent: container.transform);
        continueBtn.GetComponentInChildren<Button>().onClick.AddListener(OnContinue);

        // --- Day label ---
        var dayLabel = CreateText("DayLabel", "Day 1",
            fontSize: 24, color: new Color(0.4f, 0.4f, 0.4f),
            anchorMin: new Vector2(0.5f, 1f), anchorMax: new Vector2(0.5f, 1f),
            offsetMin: new Vector2(-100, -50), offsetMax: new Vector2(100, -20),
            parent: container.transform, alignment: TextAlignmentOptions.Center);

        // --- Bottom row: New game + Settings ---
        var bottomRow = CreatePanel("BottomRow", Color.clear,
            anchorMin: new Vector2(0.5f, 0f), anchorMax: new Vector2(0.5f, 0f),
            offsetMin: new Vector2(-300, 40), offsetMax: new Vector2(300, 160),
            parent: container.transform);

        var newGameBtn = CreateButton("BtnNewGame", "New game",
            Color.white, Color.black, fontSize: 24,
            anchorMin: new Vector2(0f, 0.5f), anchorMax: new Vector2(0f, 0.5f),
            offsetMin: new Vector2(0, -40), offsetMax: new Vector2(260, 40),
            parent: bottomRow.transform);
        AddButtonOutline(newGameBtn);
        newGameBtn.GetComponentInChildren<Button>().onClick.AddListener(OnNewGame);

        var settingsBtn = CreateButton("BtnSettings", "⚙  Settings",
            Color.white, Color.black, fontSize: 24,
            anchorMin: new Vector2(1f, 0.5f), anchorMax: new Vector2(1f, 0.5f),
            offsetMin: new Vector2(-260, -40), offsetMax: new Vector2(0, 40),
            parent: bottomRow.transform);
        AddButtonOutline(settingsBtn);
        settingsBtn.GetComponentInChildren<Button>().onClick.AddListener(OnSettings);

        // --- Footer links: How to play + Credits ---
        var footer = CreatePanel("Footer", Color.clear,
            anchorMin: new Vector2(0.5f, 0f), anchorMax: new Vector2(0.5f, 0f),
            offsetMin: new Vector2(-300, -20), offsetMax: new Vector2(300, 40),
            parent: container.transform);

        var howToPlay = CreateTextLink("TxtHowToPlay", "How to play",
            anchorMin: new Vector2(0f, 0.5f), anchorMax: new Vector2(0f, 0.5f),
            offsetMin: new Vector2(0, -14), offsetMax: new Vector2(200, 14),
            parent: footer.transform);
        howToPlay.GetComponent<Button>().onClick.AddListener(OnHowToPlay);

        var credits = CreateTextLink("TxtCredits", "Credits",
            anchorMin: new Vector2(1f, 0.5f), anchorMax: new Vector2(1f, 0.5f),
            offsetMin: new Vector2(-200, -14), offsetMax: new Vector2(0, 14),
            parent: footer.transform);
        credits.GetComponent<Button>().onClick.AddListener(OnCredits);
    }

    // ---------- helpers ----------

    private GameObject CreatePanel(string name, Color color,
        Vector2 anchorMin, Vector2 anchorMax,
        Vector2 offsetMin, Vector2 offsetMax, Transform parent = null)
    {
        var go = new GameObject(name);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, anchorMin, anchorMax, offsetMin, offsetMax, parent);
        var img = go.AddComponent<Image>();
        img.color = color;
        return go;
    }

    private TextMeshProUGUI CreateText(string name, string text, int fontSize, Color color,
        Vector2 anchorMin, Vector2 anchorMax,
        Vector2 offsetMin, Vector2 offsetMax, Transform parent = null,
        TextAlignmentOptions alignment = TextAlignmentOptions.Center)
    {
        var go = new GameObject(name);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, anchorMin, anchorMax, offsetMin, offsetMax, parent);
        var tmp = go.AddComponent<TextMeshProUGUI>();
        tmp.text = text;
        tmp.fontSize = fontSize;
        tmp.color = color;
        tmp.alignment = alignment;
        tmp.enableAutoSizing = false;
        return tmp;
    }

    private GameObject CreateButton(string name, string label, Color bgColor, Color textColor,
        int fontSize, Vector2 anchorMin, Vector2 anchorMax,
        Vector2 offsetMin, Vector2 offsetMax, Transform parent = null)
    {
        var go = new GameObject(name);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, anchorMin, anchorMax, offsetMin, offsetMax, parent);

        var img = go.AddComponent<Image>();
        img.color = bgColor;
        img.sprite = null; // solid color
        var btn = go.AddComponent<Button>();
        btn.targetGraphic = img;

        // rounded corners via a simple visual (no sprite needed)
        var textGo = new GameObject("Label");
        textGo.transform.SetParent(go.transform, false);
        var textRt = textGo.AddComponent<RectTransform>();
        textRt.anchorMin = Vector2.zero;
        textRt.anchorMax = Vector2.one;
        textRt.offsetMin = Vector2.zero;
        textRt.offsetMax = Vector2.zero;
        var tmp = textGo.AddComponent<TextMeshProUGUI>();
        tmp.text = label;
        tmp.fontSize = fontSize;
        tmp.color = textColor;
        tmp.alignment = TextAlignmentOptions.Center;

        return go;
    }

    private TextMeshProUGUI CreateTextLink(string name, string label,
        Vector2 anchorMin, Vector2 anchorMax,
        Vector2 offsetMin, Vector2 offsetMax, Transform parent = null)
    {
        var go = new GameObject(name);
        var rt = go.AddComponent<RectTransform>();
        SetAnchors(rt, anchorMin, anchorMax, offsetMin, offsetMax, parent);
        var btn = go.AddComponent<Button>();
        var tmp = go.AddComponent<TextMeshProUGUI>();
        tmp.text = label;
        tmp.fontSize = 20;
        tmp.color = new Color(0.3f, 0.3f, 0.3f);
        tmp.alignment = TextAlignmentOptions.Center;
        btn.targetGraphic = tmp;
        return tmp;
    }

    private void SetAnchors(RectTransform rt, Vector2 anchorMin, Vector2 anchorMax,
        Vector2 offsetMin, Vector2 offsetMax, Transform parent = null)
    {
        if (parent != null) rt.SetParent(parent, false);
        rt.anchorMin = anchorMin;
        rt.anchorMax = anchorMax;
        rt.offsetMin = offsetMin;
        rt.offsetMax = offsetMax;
    }

    private void AddButtonOutline(GameObject btnGo)
    {
        var outline = btnGo.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(2, 2);
    }

    // ---------- button callbacks ----------

    private void OnContinue()
    {
        Debug.Log("[MainMenu] Continue pressed");
        LoadScene(gameSceneName);
    }

    private void OnNewGame()
    {
        Debug.Log("[MainMenu] New game pressed");
        LoadScene(gameSceneName);
    }

    private void OnSettings()
    {
        Debug.Log("[MainMenu] Settings pressed");
        // TODO: open settings panel
    }

    private void OnHowToPlay()
    {
        Debug.Log("[MainMenu] How to play pressed");
        // TODO: show how-to-play
    }

    private void OnCredits()
    {
        Debug.Log("[MainMenu] Credits pressed");
        // TODO: show credits
    }

    private void LoadScene(string sceneName)
    {
        if (string.IsNullOrEmpty(sceneName))
        {
            Debug.LogWarning("[MainMenu] No game scene name set.");
            return;
        }
        SceneManager.LoadScene(sceneName);
    }
}
