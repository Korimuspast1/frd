"""exteraGram plugin: a strictly local, visual profile showcase.

Nothing in this module changes Telegram account data or sends Telegram requests.
The Stars, Premium label and gifts below are stored as plugin settings on this
installation and are rendered only in a clearly marked local badge/dialog.
"""

import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from base_plugin import BasePlugin, MenuItemData, MenuItemType
from android_utils import OnClickListener, R as RunnableProxy
from hook_utils import find_class, get_private_field
from client_utils import get_last_fragment
from org.telegram.messenger import AndroidUtilities, UserConfig
from android.graphics import Color
from android.graphics.drawable import GradientDrawable
from android.view import Gravity
from android.widget import FrameLayout, LinearLayout, TextView
from ui.alert import AlertDialogBuilder
from ui.bulletin import BulletinHelper
from ui.settings import Header, Input, Switch, Text
from java.lang.ref import WeakReference


__id__ = "local_visual_profile"
__name__ = "Локальная витрина профиля"
__description__ = (
    "Локальный визуальный макет: Stars, метка Premium и подарки видны только "
    "в этом клиенте и не меняют данные Telegram."
)
__author__ = "Arena"
__version__ = "1.0.0"
__icon__ = "exteraPlugins/1"
__app_version__ = ">=12.5.1"
__sdk_version__ = ">=1.4.4.3"


_PROFILE_BADGE_TAG = "arena.local_visual_profile.badge"
_MAX_LOCAL_GIFTS = 500
_MARKET_MENU_LABEL = "🎁 Добавить в мою локальную витрину"


def _digits_only(value: Any) -> str:
    """Return a non-negative decimal string without imposing a numeric limit."""
    digits = re.sub(r"[^0-9]", "", str(value if value is not None else ""))
    return digits.lstrip("0") or "0"


def _format_decimal_groups(value: Any, max_chars: Optional[int] = None) -> str:
    """Format a decimal string in readable groups, supporting very large values."""
    digits = _digits_only(value)
    groups = [digits[max(0, end - 3) : end] for end in range(len(digits), 0, -3)]
    formatted = "\u202f".join(reversed(groups or ["0"]))
    if max_chars is not None and len(formatted) > max_chars:
        return formatted[: max(1, max_chars - 1)] + "…"
    return formatted


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(str(value).strip())
        except Exception:
            return default


def _clean_text(value: Any, fallback: str, limit: int = 96) -> str:
    try:
        text = "" if value is None else str(value)
        text = text.replace("\r", " ").replace("\n", " ").strip()
    except Exception:
        text = ""
    text = " ".join(text.split())
    return (text or fallback)[:limit]


class LocalVisualProfilePlugin(BasePlugin):
    """Show a local-only fake profile summary and capture gift-sheet menu actions."""

    def on_plugin_load(self):
        self._pending_market_gift = None
        self._badge_refs = []

        try:
            self.add_menu_item(
                MenuItemData(
                    menu_type=MenuItemType.PROFILE_ACTION_MENU,
                    text="Локальная витрина (только у вас)",
                    on_click=self._on_profile_menu_click,
                    icon="msg_info",
                    subtext="Визуальные Stars, Premium и подарки",
                    priority=50,
                )
            )
        except Exception:
            self.logger.exception("Не удалось добавить пункт меню профиля")

        self._install_gift_market_hooks()
        self._install_profile_badge_hook()
        self.logger.info("Локальная витрина загружена; сетевые запросы не используются")

    def on_plugin_unload(self):
        # Remove already-rendered badges as well as the automatically-unhooked
        # Java hooks. This avoids leaving plugin UI behind after disable.
        for account, weak_badge in getattr(self, "_badge_refs", []):
            try:
                badge = weak_badge.get()
                if badge is not None:
                    parent = badge.getParent()
                    if parent is not None:
                        parent.removeView(badge)
            except Exception:
                pass
        self._badge_refs = []
        self._pending_market_gift = None

    def _install_gift_market_hooks(self):
        """Add a local-only action to StarGiftSheet's three-dot menu when present."""
        try:
            sheet_class = find_class("org.telegram.ui.Stars.StarGiftSheet")
            view_class = find_class("android.view.View")
            options_class = find_class("org.telegram.ui.Components.ItemOptions")
            if sheet_class is None or view_class is None or options_class is None:
                self.logger.info("Пункт меню маркета подарков недоступен в этой версии клиента")
                return

            menu_method = sheet_class.getDeclaredMethod("onMenuPressed", view_class)
            menu_method.setAccessible(True)
            show_method = options_class.getDeclaredMethod("show")
            show_method.setAccessible(True)

            self.hook_method(
                menu_method,
                before=self._before_star_gift_menu,
                after=self._after_star_gift_menu,
            )
            self.hook_method(show_method, before=self._before_item_options_show)
            self.logger.info("Подключено локальное действие для меню StarGiftSheet")
        except Exception:
            # The upstream UI changes between Telegram versions. A missing hook
            # must not prevent the settings/profile-only parts of the plugin.
            self.logger.exception("Не удалось подключить пункт меню подарка")

    def _install_profile_badge_hook(self):
        """Attach a small, explicitly local badge to the current user's profile."""
        try:
            profile_class = find_class("org.telegram.ui.ProfileActivity")
            context_class = find_class("android.content.Context")
            if profile_class is None or context_class is None:
                self.logger.info("Бейдж профиля недоступен в этой версии клиента")
                return
            create_view = profile_class.getDeclaredMethod("createView", context_class)
            create_view.setAccessible(True)
            self.hook_method(create_view, after=self._after_profile_create_view)
            self.logger.info("Подключен локальный бейдж собственного профиля")
        except Exception:
            self.logger.exception("Не удалось подключить бейдж профиля")

    # ---- account-scoped local storage ---------------------------------

    def _selected_account(self) -> int:
        try:
            return _safe_int(UserConfig.selectedAccount, 0)
        except Exception:
            return 0

    def _account_from_object(self, obj: Any) -> int:
        try:
            value = get_private_field(obj, "currentAccount")
            if value is not None:
                return _safe_int(value, self._selected_account())
        except Exception:
            pass
        return self._selected_account()

    def _client_user_id(self, account: int) -> int:
        try:
            return _safe_int(UserConfig.getInstance(int(account)).getClientUserId(), 0)
        except Exception:
            return 0

    def _scope(self, account: int) -> str:
        user_id = self._client_user_id(account)
        return str(user_id) if user_id > 0 else "account_" + str(max(0, int(account)))

    def _setting_keys(self, account: int) -> Tuple[str, str, str, str]:
        scope = self._scope(account)
        return (
            "local_stars_" + scope,
            "local_gifts_" + scope,
            "show_badge_" + scope,
            "visual_premium_" + scope,
        )

    def _stars(self, account: int) -> str:
        stars_key, _, _, _ = self._setting_keys(account)
        try:
            return _digits_only(self.get_setting(stars_key, "0"))
        except Exception:
            return "0"

    def _gifts(self, account: int) -> List[Dict[str, str]]:
        _, gifts_key, _, _ = self._setting_keys(account)
        try:
            raw = self.get_setting(gifts_key, "[]")
            rows = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(rows, list):
                return []
            clean_rows = []
            for row in rows[-_MAX_LOCAL_GIFTS:]:
                if not isinstance(row, dict):
                    continue
                clean_rows.append(
                    {
                        "local_id": _clean_text(row.get("local_id"), uuid.uuid4().hex[:12], 32),
                        "title": _clean_text(row.get("title"), "Звёздный подарок", 96),
                        "number": _clean_text(row.get("number"), "", 32),
                        "gift_id": _clean_text(row.get("gift_id"), "", 40),
                        "slug": _clean_text(row.get("slug"), "", 100),
                        "kind": _clean_text(row.get("kind"), "Подарок", 40),
                        "added_at": _clean_text(row.get("added_at"), "", 24),
                    }
                )
            return clean_rows
        except Exception:
            return []

    @staticmethod
    def _as_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("1", "true", "yes", "on"):
                return True
            if lowered in ("0", "false", "no", "off", ""):
                return False
        return default

    def _premium_enabled(self, account: int) -> bool:
        _, _, _, premium_key = self._setting_keys(account)
        try:
            return self._as_bool(self.get_setting(premium_key, False), False)
        except Exception:
            return False

    def _badge_enabled(self, account: int) -> bool:
        _, _, badge_key, _ = self._setting_keys(account)
        try:
            return self._as_bool(self.get_setting(badge_key, True), True)
        except Exception:
            return True

    def _has_visual_data(self, account: int) -> bool:
        return (
            _digits_only(self._stars(account)) != "0"
            or bool(self._gifts(account))
            or self._premium_enabled(account)
        )

    def _save_gifts(self, account: int, gifts: List[Dict[str, str]]):
        _, gifts_key, _, _ = self._setting_keys(account)
        self.set_setting(
            gifts_key,
            json.dumps(gifts[-_MAX_LOCAL_GIFTS:], ensure_ascii=False, separators=(",", ":")),
        )

    # ---- gift-market menu ---------------------------------------------

    def _describe_gift(self, sheet: Any) -> Optional[Dict[str, str]]:
        gift = None
        try:
            gift = sheet.getGift()
        except Exception:
            pass

        if gift is None:
            try:
                gift = get_private_field(sheet, "slugStarGift")
            except Exception:
                pass

        if gift is None:
            try:
                saved = get_private_field(sheet, "savedStarGift")
                gift = getattr(saved, "gift", None) if saved is not None else None
            except Exception:
                pass

        if gift is None:
            return None

        title = _clean_text(getattr(gift, "title", None), "Звёздный подарок", 96)
        number = _clean_text(getattr(gift, "num", None), "", 32)
        gift_id = _clean_text(getattr(gift, "id", None), "", 40)
        slug = _clean_text(getattr(gift, "slug", None), "", 100)
        kind = "Коллекционный подарок" if number or slug else "Подарок"
        return {
            "title": title,
            "number": number,
            "gift_id": gift_id,
            "slug": slug,
            "kind": kind,
        }

    def _before_star_gift_menu(self, param):
        self._pending_market_gift = None
        try:
            sheet = param.thisObject
            gift = self._describe_gift(sheet)
            if gift is None:
                return
            account = self._account_from_object(sheet)
            self._pending_market_gift = (account, gift)
        except Exception:
            self.logger.exception("Не удалось прочитать данные подарка")

    def _after_star_gift_menu(self, param):
        # If the menu was not shown, discard this transient reference.
        self._pending_market_gift = None

    def _before_item_options_show(self, param):
        pending = getattr(self, "_pending_market_gift", None)
        if not pending:
            return
        self._pending_market_gift = None
        account, gift = pending
        try:
            options = param.thisObject
            # ItemOptions.add(CharSequence, Runnable) only adds a local menu row;
            # the Runnable below writes plugin settings and makes no API request.
            callback = RunnableProxy(lambda: self._add_local_gift(account, gift))
            options.add(_MARKET_MENU_LABEL, callback)
        except Exception:
            self.logger.exception("Не удалось добавить локальное действие в меню")

    def _add_local_gift(self, account: int, gift: Dict[str, str]):
        gifts = self._gifts(account)
        if len(gifts) >= _MAX_LOCAL_GIFTS:
            BulletinHelper.show_error("Локальная витрина заполнена (максимум 500 записей).")
            return

        entry = {
            "local_id": uuid.uuid4().hex[:12],
            "title": _clean_text(gift.get("title"), "Звёздный подарок", 96),
            "number": _clean_text(gift.get("number"), "", 32),
            "gift_id": _clean_text(gift.get("gift_id"), "", 40),
            "slug": _clean_text(gift.get("slug"), "", 100),
            "kind": _clean_text(gift.get("kind"), "Подарок", 40),
            "added_at": str(int(time.time())),
        }
        gifts.append(entry)
        self._save_gifts(account, gifts)
        self._refresh_badges(account)
        BulletinHelper.show_success(
            "Добавлено в локальную витрину. Данные Telegram не изменены."
        )

    # ---- own-profile checks and local showcase ------------------------

    def _is_own_profile(self, profile: Any, account: int, context_user: Any = None) -> bool:
        own_id = self._client_user_id(account)
        if own_id <= 0:
            return False

        if context_user is not None:
            user_id = _safe_int(getattr(context_user, "id", 0), 0)
            if user_id:
                return user_id == own_id
            try:
                if bool(getattr(context_user, "self", False)):
                    return True
            except Exception:
                pass

        if profile is None:
            return False
        try:
            profile_user_id = _safe_int(get_private_field(profile, "userId"), 0)
            dialog_id = _safe_int(get_private_field(profile, "dialogId"), 0)
            return profile_user_id == own_id or dialog_id == own_id
        except Exception:
            return False

    def _on_profile_menu_click(self, context: Dict[str, Any]):
        context = context or {}
        account = _safe_int(context.get("account", self._selected_account()), self._selected_account())
        profile = context.get("fragment")
        user = context.get("user")
        if not self._is_own_profile(profile, account, user):
            BulletinHelper.show_info("Локальная витрина доступна только в вашем профиле.", profile)
            return
        self._show_local_gallery(account, profile)

    def _render_gallery_text(self, account: int) -> str:
        stars = _format_decimal_groups(self._stars(account), 48)
        gifts = self._gifts(account)
        premium = "💎 Premium (визуально)\n" if self._premium_enabled(account) else ""
        lines = [
            premium + "⭐ Stars (локально): " + stars,
            "🎁 Подарки (локально): " + str(len(gifts)),
            "",
        ]

        if gifts:
            lines.append("Сохранённые подарки:")
            for gift in gifts[-20:]:
                label = gift.get("title", "Звёздный подарок")
                if gift.get("number"):
                    label += " #" + gift["number"]
                lines.append("• " + label)
            if len(gifts) > 20:
                lines.append("…и ещё " + str(len(gifts) - 20))
        else:
            lines.append("Пока нет локальных подарков.")

        lines.extend(
            [
                "",
                "Это только визуальная витрина этого устройства. Она не выдаёт настоящий Premium/Stars и не меняет профиль на серверах Telegram.",
            ]
        )
        return "\n".join(lines)

    def _show_local_gallery(self, account: int, fragment: Any = None):
        try:
            if fragment is None:
                fragment = get_last_fragment()
            if fragment is None:
                BulletinHelper.show_info("Откройте профиль в exteraGram, чтобы посмотреть локальную витрину.")
                return
            activity = fragment.getParentActivity()
            if activity is None:
                BulletinHelper.show_info("Не удалось открыть предпросмотр витрины.", fragment)
                return

            builder = AlertDialogBuilder(activity)
            builder.set_title("Локальная витрина профиля")
            builder.set_message(self._render_gallery_text(account))
            builder.set_positive_button("Закрыть")
            builder.show()
        except Exception:
            self.logger.exception("Не удалось показать локальную витрину")
            BulletinHelper.show_info("Не удалось открыть локальную витрину.", fragment)

    def _on_stars_changed(self, account: int, value: Any):
        # Persist a plain decimal string; Python integers are deliberately not
        # used so the visual value is not limited to a machine integer size.
        stars_key, _, _, _ = self._setting_keys(account)
        self.set_setting(stars_key, _digits_only(value))
        self._refresh_badges(account)

    def _on_local_switch_changed(self, account: int, setting_key: str, value: Any):
        self.set_setting(setting_key, self._as_bool(value, False))
        self._refresh_badges(account)

    def _clear_local_data(self, account: int):
        stars_key, gifts_key, _, premium_key = self._setting_keys(account)
        try:
            self.set_setting(stars_key, "0")
            self.set_setting(gifts_key, "[]")
            self.set_setting(premium_key, False)
            self._refresh_badges(account)
            BulletinHelper.show_success("Локальные данные витрины очищены.")
        except Exception:
            self.logger.exception("Не удалось очистить локальную витрину")
            BulletinHelper.show_error("Не удалось очистить локальные данные.")

    def create_settings(self) -> List[Any]:
        account = self._selected_account()
        stars_key, _, badge_key, premium_key = self._setting_keys(account)
        gifts_count = len(self._gifts(account))
        return [
            Header(text="Только локально"),
            Text(
                text="Ничего не отправляется в Telegram",
                subtext=(
                    "Premium, баланс Stars и подарки здесь — визуальная имитация "
                    "в данных плагина на этом устройстве."
                ),
                icon="msg_info",
            ),
            Input(
                key=stars_key,
                text="Визуальный баланс Stars",
                default=self._stars(account),
                subtext="Введите любое неотрицательное количество; оно не станет настоящим балансом.",
                on_change=lambda value, acc=account: self._on_stars_changed(acc, value),
            ),
            Switch(
                key=premium_key,
                text="Показывать метку Premium (визуально)",
                default=self._premium_enabled(account),
                subtext="Метка появится только на локальном бейдже профиля.",
                on_change=lambda value, acc=account, key=premium_key: self._on_local_switch_changed(acc, key, value),
            ),
            Switch(
                key=badge_key,
                text="Показывать локальный бейдж в моём профиле",
                default=self._badge_enabled(account),
                subtext="На бейдже будут локальный баланс и количество подарков.",
                on_change=lambda value, acc=account, key=badge_key: self._on_local_switch_changed(acc, key, value),
            ),
            Text(
                text="Предпросмотр локальной витрины",
                subtext=str(gifts_count) + " локальных подарков",
                icon="msg_info",
                on_click=lambda _view, acc=account: self._show_local_gallery(acc),
            ),
            Text(
                text="Очистить локальные данные",
                subtext="Сбросить локальные Stars, Premium-метку и подарки",
                red=True,
                on_click=lambda _view, acc=account: self._clear_local_data(acc),
            ),
        ]

    # ---- profile badge rendering --------------------------------------

    def _after_profile_create_view(self, param):
        try:
            profile = param.thisObject
            root = param.getResult()
            if root is None:
                return

            account = self._account_from_object(profile)
            old_badge = root.findViewWithTag(_PROFILE_BADGE_TAG)
            if old_badge is not None:
                root.removeView(old_badge)

            if not self._is_own_profile(profile, account):
                return
            if not self._badge_enabled(account) or not self._has_visual_data(account):
                return

            badge = self._make_badge(root.getContext(), account)
            params = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
            )
            params.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL
            params.bottomMargin = AndroidUtilities.dp(82)
            params.leftMargin = AndroidUtilities.dp(12)
            params.rightMargin = AndroidUtilities.dp(12)
            root.addView(badge, params)
            self._badge_refs.append((account, WeakReference(badge)))
        except Exception:
            self.logger.exception("Не удалось отобразить локальный бейдж")

    def _make_badge(self, context: Any, account: int):
        badge = LinearLayout(context)
        badge.setOrientation(LinearLayout.VERTICAL)
        badge.setGravity(Gravity.CENTER_VERTICAL)
        badge.setPadding(
            AndroidUtilities.dp(13),
            AndroidUtilities.dp(7),
            AndroidUtilities.dp(13),
            AndroidUtilities.dp(7),
        )
        background = GradientDrawable()
        background.setColor(Color.parseColor("#252B36"))
        background.setCornerRadius(AndroidUtilities.dp(16))
        background.setStroke(AndroidUtilities.dp(1), Color.parseColor("#D2AA55"))
        badge.setBackground(background)
        badge.setTag(_PROFILE_BADGE_TAG)
        badge.setElevation(AndroidUtilities.dp(5))

        title = TextView(context)
        title.setTextColor(Color.WHITE)
        title.setTextSize(14.0)
        title.setSingleLine(True)
        title.setMaxWidth(AndroidUtilities.dp(280))
        badge.addView(
            title,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ),
        )

        subtitle = TextView(context)
        subtitle.setTextColor(Color.parseColor("#D2AA55"))
        subtitle.setTextSize(10.0)
        subtitle.setSingleLine(True)
        subtitle.setMaxWidth(AndroidUtilities.dp(280))
        badge.addView(
            subtitle,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ),
        )

        badge.setOnClickListener(
            OnClickListener(lambda _view, acc=account: self._show_local_gallery(acc))
        )
        self._update_badge(badge, account)
        return badge

    def _update_badge(self, badge: Any, account: int):
        gifts_count = len(self._gifts(account))
        stars = _format_decimal_groups(self._stars(account), 20)
        pieces = []
        if self._premium_enabled(account):
            pieces.append("💎 Premium")
        pieces.append("⭐ " + stars)
        pieces.append("🎁 " + str(gifts_count))
        try:
            badge.getChildAt(0).setText("  •  ".join(pieces))
            badge.getChildAt(1).setText("ЛОКАЛЬНО · видно только вам")
        except Exception:
            pass

    def _refresh_badges(self, account: int):
        remaining = []
        for badge_account, weak_badge in getattr(self, "_badge_refs", []):
            try:
                badge = weak_badge.get()
                if badge is None:
                    continue
                remaining.append((badge_account, weak_badge))
                if badge_account != account:
                    continue
                if not self._badge_enabled(account) or not self._has_visual_data(account):
                    parent = badge.getParent()
                    if parent is not None:
                        parent.removeView(badge)
                    continue
                self._update_badge(badge, account)
            except Exception:
                continue
        self._badge_refs = remaining

