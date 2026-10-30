using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Placeholder game scene manager.
/// Replace this with your actual shop gameplay logic.
/// </summary>
public class GameManager : MonoBehaviour
{
    private void Start()
    {
        Debug.Log("[Game] Welcome to Beepnook Gadget Shop!");
    }

    private void Update()
    {
        // Press Escape to return to main menu (useful for testing in editor)
        if (Input.GetKeyDown(KeyCode.Escape))
        {
            SceneManager.LoadScene("MainMenu");
        }
    }
}
