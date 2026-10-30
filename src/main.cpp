#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <cstring>
#include <unistd.h>
#include <termios.h>
#include <sys/ioctl.h>

// ---------- ANSI цвета ----------
#define C_RESET   "\033[0m"
#define C_BOLD    "\033[1m"
#define C_YELLOW  "\033[38;5;220m"
#define C_PURPLE  "\033[38;5;141m"
#define C_PINK    "\033[38;5;211m"
#define C_BLUE    "\033[38;5;117m"
#define C_GREEN   "\033[38;5;82m"
#define C_RED     "\033[38;5;197m"
#define C_BLACK   "\033[30m"
#define C_BG_PURPLE "\033[48;5;141m"
#define C_BG_PINK   "\033[48;5;211m"
#define C_BG_YELLOW "\033[48;5;220m"

// ---------- Терминал ----------
struct Term {
    struct termios old;
    void raw() {
        tcgetattr(STDIN_FILENO, &old);
        struct termios n = old;
        n.c_lflag &= ~(ICANON | ECHO);
        tcsetattr(STDIN_FILENO, TCSANOW, &n);
    }
    void restore() { tcsetattr(STDIN_FILENO, TCSANOW, &old); }
} term;

int getch_ms(int ms) {
    struct timeval tv; tv.tv_sec = ms/1000; tv.tv_usec = (ms%1000)*1000;
    fd_set fds; FD_ZERO(&fds); FD_SET(STDIN_FILENO, &fds);
    int r = select(STDIN_FILENO+1, &fds, nullptr, nullptr, ms>0?&tv:nullptr);
    if (r <= 0) return -1;
    char c; read(STDIN_FILENO, &c, 1); return (unsigned char)c;
}

void clear() { std::cout << "\033[2J\033[H"; std::cout.flush(); }
void hide_cursor() { std::cout << "\033[?25l"; std::cout.flush(); }
void show_cursor() { std::cout << "\033[?25h"; std::cout.flush(); }
void gotoxy(int x, int y) { std::cout << "\033[" << (y+1) << ";" << (x+1) << "H"; }

// ---------- Размер терминала ----------
struct Winsz { int cols, rows; };
Winsz get_winsz() {
    Winsz w{80, 24};
    struct winsize ws;
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0) { w.cols = ws.ws_col; w.rows = ws.ws_row; }
    return w;
}

// ---------- Игра ----------
enum Screen { MENU, GAME, HOWTO, CREDITS, EXIT };

int selected = 0;
int day = 1;
int money = 500;
int gadgets_sold = 0;

const std::vector<std::string> menu_items = {
    "Continue",
    "New game",
    "Settings",
    "How to play",
    "Credits",
    "Exit"
};

void draw_banner(const std::string& text, int x, int y, const char* color) {
    gotoxy(x, y);
    std::cout << color << " ";
    for (size_t i = 0; i < text.size() + 2; i++) std::cout << " ";
    std::cout << C_RESET << "\n";
    gotoxy(x, y+1);
    std::cout << color << " " << text << " " << C_RESET << "\n";
    gotoxy(x, y+2);
    std::cout << color << " ";
    for (size_t i = 0; i < text.size() + 2; i++) std::cout << " ";
    std::cout << C_RESET << "\n";
}

void draw_menu() {
    Winsz w = get_winsz();
    clear();

    // Фон: небо
    for (int y = 0; y < w.rows; y++) {
        gotoxy(0, y);
        std::cout << C_BLUE;
        for (int x = 0; x < w.cols; x++) std::cout << " ";
        std::cout << C_RESET;
    }

    // Дорога сверху
    int road_y = 2;
    gotoxy(0, road_y);
    std::cout << C_BOLD << "\033[38;5;238m";
    for (int x = 0; x < w.cols; x++) std::cout << "=";
    std::cout << C_RESET;

    // Заголовок "Beepnook"
    std::string title = "BEEPNOOK";
    int tx = (w.cols - (int)title.size()) / 2;
    if (tx < 0) tx = 0;
    gotoxy(tx, 4);
    std::cout << C_BOLD << C_YELLOW << title << C_RESET;

    // Баннер "GADGET SHOP" (не repair shop!)
    std::string banner = "GADGET SHOP";
    int bx = (w.cols - (int)banner.size()) / 2 - 2;
    if (bx < 0) bx = 0;
    draw_banner(banner, bx, 6, C_BG_PURPLE);

    // Изометрическая комната (ASCII)
    std::vector<std::string> room = {
        "        ___________",
        "       /  [WINDOW] /|",
        "      /___________/ |",
        "      |     |     | |",
        "      | [C] | [S] | |",
        "      |_____|_____|/ ",
        "         /     \\   ",
        "        / [DESK] \\  ",
        "       /___________\\ ",
        "            | |    ",
        "          [STOOL] "
    };
    int ry = 10;
    int rx = 2;
    for (const auto& line : room) {
        gotoxy(rx, ry++);
        std::cout << C_BOLD << "\033[38;5;130m" << line << C_RESET;
    }

    // Кнопка Continue (розшая, как на референсе)
    int by = ry + 1;
    std::string cont = "  Continue  ";
    int cx = (w.cols - (int)cont.size()) / 2;
    gotoxy(cx, by);
    std::cout << C_BG_PINK << C_BLACK << C_BOLD << cont << C_RESET;

    // Day 1
    std::string daytext = "Day " + std::to_string(day);
    int dx = (w.cols - (int)daytext.size()) / 2;
    gotoxy(dx, by + 2);
    std::cout << C_BOLD << C_GREEN << daytext << C_RESET;

    // Нижний ряд кнопок
    int sy = by + 4;
    std::string left = " New game ";
    std::string right = " Settings ";
    int lx = 4;
    int rx2 = w.cols - (int)right.size() - 4;
    if (rx2 < 0) rx2 = 0;

    // Подсветка выбранного
    if (selected == 0) { gotoxy(lx-2, sy); std::cout << ">"; }
    gotoxy(lx, sy);
    std::cout << (selected==0?C_BG_YELLOW:C_RESET) << C_BLACK << left << C_RESET;

    if (selected == 1) { gotoxy(rx2-2, sy); std::cout << ">"; }
    gotoxy(rx2, sy);
    std::cout << (selected==1?C_BG_YELLOW:C_RESET) << C_BLACK << right << C_RESET;

    // Footer
    int fy = sy + 2;
    std::string htp = "How to play";
    std::string cr = "Credits";
    int hx = (w.cols - (int)htp.size() - (int)cr.size() - 4) / 2;
    int cx2 = hx + (int)htp.size() + 4;
    gotoxy(hx, fy);
    std::cout << C_BOLD << C_BLUE << htp << C_RESET;
    gotoxy(cx2, fy);
    std::cout << C_BOLD << C_BLUE << cr << C_RESET;

    // Подсказка
    std::string hint = " arrows/wasd = choose   enter = select   q = quit ";
    int hix = (w.cols - (int)hint.size()) / 2;
    gotoxy(hix, w.rows - 1);
    std::cout << "\033[2m" << hint << C_RESET;

    std::cout.flush();
}

void draw_game() {
    clear();

    gotoxy(0, 0);
    std::cout << C_BOLD << C_YELLOW << "BEEPNOOK GADGET SHOP — DAY " << day << C_RESET << "\n\n";

    std::cout << C_GREEN << "Money: $" << money << C_RESET
              << "   Gadgets sold: " << gadgets_sold << "\n\n";

    std::cout << C_PURPLE << "Welcome to Beepnook!" C_RESET << "\n";
    std::cout << "This is a gadget shop, not a repair shop.\n";
    std::cout << "Sell smartphones, headphones, and smartwatches.\n\n";

    std::cout << "1. Restock inventory ($50 per item)\n";
    std::cout << "2. Open shop for the day\n";
    std::cout << "3. Return to menu\n\n";

    std::cout << C_BOLD << "Choose: " << C_RESET;
    std::cout.flush();
}

void run_game() {
    while (true) {
        draw_game();
        int c = getch_ms(0);
        if (c == '1') {
            // Restock
            if (money >= 50) {
                money -= 50;
                std::cout << "\nRestocked! New gadgets arrived.\n";
            } else {
                std::cout << "\nNot enough money!\n";
            }
            std::cout << "Press enter...";
            while (getch_ms(0) != '\n' && getch_ms(0) != '\r' && getch_ms(0) != -1) {}
            getch_ms(0);
        } else if (c == '2') {
            // Open shop
            int sales = 1 + (rand() % 5);
            int earn = sales * 40;
            money += earn;
            gadgets_sold += sales;
            std::cout << "\nShop opened! Sold " << sales << " gadget(s), earned $" << earn << "\n";
            std::cout << "Press enter...";
            while (getch_ms(0) != '\n' && getch_ms(0) != '\r' && getch_ms(0) != -1) {}
            getch_ms(0);
        } else if (c == '3' || c == 27) { // 3 or esc
            return;
        } else if (c == 'q' || c == 'Q') {
            // quit to menu handled by return too
            return;
        }
    }
}

void show_howto() {
    clear();
    gotoxy(0, 0);
    std::cout << C_BOLD << C_YELLOW << "HOW TO PLAY" << C_RESET << "\n\n";
    std::cout << "Beepnook Gadget Shop — not a repair shop.\n";
    std::cout << "Each day, restock inventory and open the shop.\n";
    std::cout << "Sell gadgets to earn money. Survive as many days as you can!\n\n";
    std::cout << "Press any key to return...";
    std::cout.flush();
    getch_ms(0);
}

void show_credits() {
    clear();
    gotoxy(0, 0);
    std::cout << C_BOLD << C_YELLOW << "CREDITS" << C_RESET << "\n\n";
    std::cout << "Beepnook — Gadget Shop\n";
    std::cout << "Inspired by the reference art (isometric shop).\n";
    std::cout << "Theme changed: gadget shop, not repair shop.\n\n";
    std::cout << "© Korimuspast1\n\n";
    std::cout << "Press any key to return...";
    std::cout.flush();
    getch_ms(0);
}

int main() {
    srand((unsigned)time(nullptr));
    term.raw();
    hide_cursor();

    Screen sc = MENU;
    while (sc != EXIT) {
        switch (sc) {
            case MENU:
                draw_menu();
                {
                    int c = getch_ms(0);
                    if (c == -1) continue;
                    if (c == 'q' || c == 'Q') { sc = EXIT; break; }
                    if (c == 'w' || c == 'W' || c == 'A' || c == 'a' || c == 'k' || c == 'K' || c == '\033') {
                        // '\033' start of arrow sequence; handle below after reading more
                    }
                    // Handle arrow keys
                    if (c == '\033') {
                        int c2 = getch_ms(50);
                        int c3 = getch_ms(50);
                        if (c2 == '[') {
                            if (c3 == 'A') { selected = (selected + menu_items.size() - 1) % menu_items.size(); }
                            if (c3 == 'B') { selected = (selected + 1) % menu_items.size(); }
                        }
                    } else if (c == 's' || c == 'S' || c == 'd' || c == 'D' || c == 'j' || c == 'J') {
                        selected = (selected + 1) % menu_items.size();
                    } else if (c == '\n' || c == '\r') {
                        if (selected == 0) { sc = GAME; }
                        else if (selected == 1) { day = 1; money = 500; gadgets_sold = 0; sc = GAME; }
                        else if (selected == 2) { /* settings placeholder */ }
                        else if (selected == 3) { sc = HOWTO; }
                        else if (selected == 4) { sc = CREDITS; }
                        else if (selected == 5) { sc = EXIT; }
                    }
                }
                break;
            case GAME:
                run_game();
                sc = MENU;
                break;
            case HOWTO:
                show_howto();
                sc = MENU;
                break;
            case CREDITS:
                show_credits();
                sc = MENU;
                break;
            default:
                sc = EXIT;
        }
    }

    show_cursor();
    term.restore();
    clear();
    std::cout << C_BOLD << C_YELLOW << "Thanks for visiting Beepnook Gadget Shop!" << C_RESET << "\n";
    return 0;
}
