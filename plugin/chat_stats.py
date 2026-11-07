import base64
import datetime
import re

from android_utils import copy_to_clipboard, run_on_ui_thread
from base_plugin import BasePlugin, MenuItemData, MenuItemType
from client_utils import (
    PLUGINS_QUEUE,
    get_last_fragment,
    get_messages_controller,
    run_on_queue,
    send_request,
)
from ui.alert import AlertDialogBuilder
from ui.bulletin import BulletinHelper
from ui.settings import Custom, Divider, Header, Input, Selector, Switch, Text

try:
    from org.telegram.messenger import AndroidUtilities, UserConfig
    from org.telegram.tgnet import TLRPC
except Exception:
    AndroidUtilities = None
    UserConfig = None
    TLRPC = None


__id__ = "chat_stats"
__name__ = "Chat Stats"
__description__ = (
    "Кто сколько пишет, в какие часы чат живёт, топ слов и самые длинные паузы. "
    "Считается на телефоне: ни ботов, ни внешних сервисов."
)
__author__ = "@ox4gg"
__version__ = "1.1.1"
__icon__ = "exteraPlugins/1"
__app_version__ = ">=12.5.1"
__sdk_version__ = ">=1.4.4.3"
__category__ = ["chats", "tools"]


FILLER_SHARE = 0.35
EXPORT_CAP = 100000
PAGE_SIZE = 100
MAX_PAGES = 1200
WATCHDOG_MS = 30000
DEPTHS = (300, 1000, 2000, 5000, 10000, 0)
DEPTH_LABELS = ("300", "1 000", "2 000", "5 000", "10 000", "Вся история")
DEFAULT_DEPTH = 2
TOP_AUTHORS = 8
TOP_WORDS = 14
TOP_PAUSES = 3
MIN_PAUSE = 3600
BLOCKS = "▁▂▃▄▅▆▇█"
DAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]{3,}")


def _fmt(value):
    return f"{int(value):,}".replace(",", " ")


def _pct(part, total):
    if not total:
        return "0%"
    value = part * 100.0 / total
    return f"{value:.0f}%" if value >= 10 else f"{value:.1f}%".replace(".", ",")


def _plural(count, one, few, many):
    count = abs(int(count)) % 100
    if 11 <= count <= 14:
        return many
    count %= 10
    if count == 1:
        return one
    if 2 <= count <= 4:
        return few
    return many


def _cut(text, limit):
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def _bar(value, top, width=12):
    if top <= 0:
        return "·" * width
    filled = int(round(value * width / float(top)))
    if value > 0 and filled < 1:
        filled = 1
    return "█" * filled + "·" * (width - filled)


def _spark(values):
    top = max(values) if values else 0
    if top <= 0:
        return "·" * len(values)
    result = []
    for value in values:
        if value <= 0:
            result.append("·")
            continue
        level = int(round(value * (len(BLOCKS) - 1) / float(top)))
        result.append(BLOCKS[max(0, min(level, len(BLOCKS) - 1))])
    return "".join(result)


def _duration(seconds):
    seconds = int(max(seconds, 0))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} д {hours} ч" if hours else f"{days} д"
    if hours:
        return f"{hours} ч {minutes} мин" if minutes else f"{hours} ч"
    return f"{max(minutes, 1)} мин"


def _date(stamp):
    return datetime.datetime.fromtimestamp(stamp).strftime("%d.%m.%Y")


def _peer_key(peer):
    if peer is None or TLRPC is None:
        return None
    try:
        if isinstance(peer, TLRPC.TL_peerUser):
            return ("u", int(peer.user_id))
        if isinstance(peer, TLRPC.TL_peerChat):
            return ("c", int(peer.chat_id))
        if isinstance(peer, TLRPC.TL_peerChannel):
            return ("c", int(peer.channel_id))
    except Exception:
        return None
    return None


def _extract(message, skip_service):
    try:
        if skip_service and getattr(message, "action", None) is not None:
            return None
        if int(getattr(message, "id", 0) or 0) <= 0:
            return None
        stamp = int(getattr(message, "date", 0) or 0)
        if stamp <= 0:
            return None
        text = getattr(message, "message", None)
        if not isinstance(text, str):
            text = ""
        key = _peer_key(getattr(message, "from_id", None)) or _peer_key(getattr(message, "peer_id", None))
        if key is None:
            return None
        media = getattr(message, "media", None)
        return (stamp, key, text, media is not None)
    except Exception:
        return None


def _aggregate(records, names, stop_words, smart_words=True):
    total = len(records)
    if not total:
        return None

    ordered = sorted(records, key=lambda item: item[0])
    authors = {}
    hours = [0] * 24
    days = [0] * 7
    words = {}
    spread = {}
    media = 0
    length_sum = 0
    text_total = 0

    for stamp, key, text, has_media in ordered:
        authors[key] = authors.get(key, 0) + 1
        moment = datetime.datetime.fromtimestamp(stamp)
        hours[moment.hour] += 1
        days[moment.weekday()] += 1
        if has_media:
            media += 1
        if not text:
            continue
        length_sum += len(text)
        text_total += 1
        used = set()
        for word in WORD_RE.findall(text.lower()):
            if word in stop_words or word.isdigit():
                continue
            words[word] = words.get(word, 0) + 1
            if word not in used:
                used.add(word)
                spread[word] = spread.get(word, 0) + 1

    ranked_words = _rank_words(words, spread, text_total, smart_words)

    pauses = []
    for index in range(1, len(ordered)):
        gap = ordered[index][0] - ordered[index - 1][0]
        if gap >= MIN_PAUSE:
            pauses.append((gap, ordered[index - 1][0], ordered[index][0], ordered[index][1], ordered[index - 1][1]))
    pauses.sort(key=lambda item: item[0], reverse=True)

    first = ordered[0][0]
    last = ordered[-1][0]
    span = max(1, (last - first) // 86400 + 1)

    ranked = sorted(authors.items(), key=lambda item: (-item[1], item[0]))
    top = [(_name_of(key, names), count) for key, count in ranked[:TOP_AUTHORS]]
    pause_rows = [
        (_duration(gap), _date(stamp), _name_of(who, names))
        for gap, _before_stamp, stamp, who, _prev in pauses[:TOP_PAUSES]
    ]

    return {
        "total": total,
        "authors": len(authors),
        "first": first,
        "last": last,
        "media": media,
        "avg_len": int(round(length_sum / text_total)) if text_total else 0,
        "per_day": total / float(span),
        "top": top,
        "hours": hours,
        "days": days,
        "words": ranked_words,
        "smart_words": smart_words,
        "pauses": pause_rows,
    }


def _rank_words(words, spread, text_total, smart_words):
    if not words:
        return []
    minimum = 2 if text_total > 40 else 1
    candidates = {word: count for word, count in words.items() if count >= minimum}
    if smart_words and text_total:
        limit = max(3, int(text_total * FILLER_SHARE))
        filtered = {word: count for word, count in candidates.items() if spread.get(word, 0) < limit}
        if len(filtered) >= 4:
            candidates = filtered
    ranked = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:TOP_WORDS]


def _name_of(key, names):
    if not key:
        return "Неизвестно"
    known = names.get(key)
    if known:
        return known
    prefix = "ID" if key[0] == "u" else "чат"
    return f"{prefix} {key[1]}"


def _per_day(value):
    if value >= 10:
        return _fmt(int(round(value)))
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _headline(stats):
    total = stats["total"]
    people = stats["authors"]
    lines = [
        f"{_fmt(total)} {_plural(total, 'сообщение', 'сообщения', 'сообщений')} · "
        f"{_fmt(people)} {_plural(people, 'человек', 'человека', 'человек')}",
        f"{_date(stats['first'])} → {_date(stats['last'])} · в среднем "
        f"{_per_day(stats['per_day'])} в день",
    ]
    extra = []
    if stats["media"]:
        extra.append(f"медиа {_pct(stats['media'], total)}")
    if stats["avg_len"]:
        extra.append(f"средняя длина {_fmt(stats['avg_len'])}")
    if extra:
        lines.append(" · ".join(extra))
    return lines


def _author_rows(stats):
    best = stats["top"][0][1] if stats["top"] else 0
    rows = []
    for index, (name, count) in enumerate(stats["top"], 1):
        rows.append(
            f"{index}. {_cut(name, 17):<17} {_fmt(count):>7} {_pct(count, stats['total']):>5}  "
            f"{_bar(count, best)}"
        )
    return rows


def _day_rows(stats):
    days = stats["days"]
    top = max(days)
    return [f"{DAY_NAMES[index]}  {_bar(days[index], top, 14)}  {_fmt(days[index])}" for index in range(7)]


def _hour_note(stats):
    hours = stats["hours"]
    peak = max(range(24), key=lambda index: hours[index])
    return f"чаще всего в {peak:02d}:00 — {_fmt(hours[peak])}"


def _words_title(stats):
    return "ЧАСТЫЕ СЛОВА · без филлеров" if stats.get("smart_words") else "ЧАСТЫЕ СЛОВА"


def _word_line(stats):
    return " · ".join(f"{word} {_fmt(count)}" for word, count in stats["words"])


def _pause_rows(stats):
    return [f"{gap} — {day}, {who}" for gap, day, who in stats["pauses"]]


def _find_by_id(items, value):
    for item in items or []:
        try:
            if int(getattr(item, "id", 0) or 0) == int(value):
                return item
        except Exception:
            continue
    return None


def _field_text(field):
    try:
        return str(field.getText())
    except Exception:
        return ""


def _error_text(error):
    if error is None:
        return ""
    text = str(getattr(error, "text", "") or "")
    if "FLOOD_WAIT_" in text:
        wait = text.split("FLOOD_WAIT_")[-1].split()[0].strip()
        return f"Telegram просит подождать {wait} с"
    return text


def _parse_username(raw):
    text = str(raw or "").strip()
    if not text:
        return ""
    text = text.replace("https://", "").replace("http://", "").strip()
    for host in ("t.me/", "telegram.me/", "telegram.dog/"):
        if text.lower().startswith(host):
            text = text[len(host):]
            break
    text = text.split("?")[0].strip("/ ")
    text = text.lstrip("@")
    if not text or text.startswith("+") or text.lower().startswith("joinchat"):
        return ""
    return text


def _display_name(user):
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    name = f"{first} {last}".strip()
    if not name:
        name = getattr(user, "username", None) or ""
    if not name:
        name = f"ID {int(getattr(user, 'id', 0) or 0)}"
    return str(name)


def _slug(value, fallback="chat"):
    text = re.sub(r"[^\w\-]+", "_", str(value or ""), flags=re.UNICODE).strip("_")
    return (text[:40] or fallback).lower()


def _export_record(message):
    try:
        msg_id = int(getattr(message, "id", 0) or 0)
        stamp = int(getattr(message, "date", 0) or 0)
        if msg_id <= 0 or stamp <= 0:
            return None
        text = getattr(message, "message", None)
        return {
            "id": msg_id,
            "date": stamp,
            "key": _peer_key(getattr(message, "from_id", None)) or _peer_key(getattr(message, "peer_id", None)),
            "text": text if isinstance(text, str) else "",
            "media": getattr(message, "media", None) is not None,
            "service": getattr(message, "action", None) is not None,
        }
    except Exception:
        return None


def _export_kind(record):
    if record["service"]:
        return "service"
    if record["media"]:
        return "media"
    return "text"


def _export_text(records, names, title):
    lines = [
        str(title),
        "выгружено " + datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "",
    ]
    for record in records:
        moment = datetime.datetime.fromtimestamp(record["date"]).strftime("%d.%m.%Y %H:%M")
        author = _name_of(record["key"], names)
        body = record["text"].replace("\r", "").replace("\n", " ⏎ ").strip()
        if record["service"]:
            body = "«служебное сообщение»"
        elif not body:
            body = "«вложение»" if record["media"] else ""
        lines.append(f"[{moment}] {author}: {body}".rstrip())
    return "\n".join(lines)


def _export_csv(records, names):
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "date", "author", "kind", "text"])
    for record in records:
        writer.writerow([
            record["id"],
            datetime.datetime.fromtimestamp(record["date"]).strftime("%Y-%m-%d %H:%M:%S"),
            _name_of(record["key"], names),
            _export_kind(record),
            record["text"],
        ])
    return buffer.getvalue()


def _export_json(records, names, title):
    import json

    payload = {
        "chat": str(title),
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "count": len(records),
        "messages": [
            {
                "id": record["id"],
                "date": datetime.datetime.fromtimestamp(record["date"]).isoformat(timespec="seconds"),
                "author": _name_of(record["key"], names),
                "kind": _export_kind(record),
                "text": record["text"],
            }
            for record in records
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=1)


def _export_stats(records, names):
    plain = [
        (record["date"], record["key"], record["text"], record["media"])
        for record in records
        if record["key"] is not None
    ]
    stats = _aggregate(plain, names, set(), True)
    return _render_text(stats) if stats else "Нечего считать"


def _write_archive(job):
    import os
    import zipfile

    from file_utils import ensure_dir_exists, get_cache_dir

    names = job["names"]
    records = sorted(job["messages"], key=lambda item: item["date"])
    title = job["target"].get("title") or "chat"

    base = get_cache_dir() or os.path.join(os.path.expanduser("~"), ".cache")
    folder = os.path.join(base, "chat_stats")
    ensure_dir_exists(folder)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    path = os.path.join(folder, f"chat_{_slug(title)}_{stamp}.zip")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("chat.txt", _export_text(records, names, title))
        archive.writestr("chat.csv", _export_csv(records, names))
        archive.writestr("chat.json", _export_json(records, names, title))
        archive.writestr("stats.txt", _export_stats(records, names))
    return path


def _render_text(stats):
    blocks = ["\n".join(_headline(stats))]

    if stats["top"]:
        blocks.append("КТО ПИШЕТ\n" + "\n".join(_author_rows(stats)))

    hours = stats["hours"]
    blocks.append("ПО ЧАСАМ\n00 " + _spark(hours) + " 23\n" + _hour_note(stats))

    blocks.append("ПО ДНЯМ\n" + "\n".join(_day_rows(stats)))

    if stats["words"]:
        blocks.append(_words_title(stats) + "\n" + _word_line(stats))

    if stats["pauses"]:
        blocks.append("САМЫЕ ДЛИННЫЕ ПАУЗЫ\n" + "\n".join(_pause_rows(stats)))

    return "\n\n".join(blocks)


def _render_html(stats):
    blocks = ["<br>".join(_headline(stats))]

    if stats["top"]:
        rows = "<br>".join(row.replace("&", "&amp;").replace("<", "&lt;") for row in _author_rows(stats))
        blocks.append("<b>КТО ПИШЕТ</b><br><tt>" + rows + "</tt>")

    hours = stats["hours"]
    blocks.append("<b>ПО ЧАСАМ</b><br><tt>00 " + _spark(hours) + " 23</tt><br>" + _hour_note(stats))

    blocks.append("<b>ПО ДНЯМ</b><br><tt>" + "<br>".join(_day_rows(stats)) + "</tt>")

    if stats["words"]:
        words = _word_line(stats).replace("&", "&amp;").replace("<", "&lt;")
        blocks.append("<b>" + _words_title(stats) + "</b><br><tt>" + words + "</tt>")

    if stats["pauses"]:
        pauses = "<br>".join(row.replace("&", "&amp;").replace("<", "&lt;") for row in _pause_rows(stats))
        blocks.append("<b>САМЫЕ ДЛИННЫЕ ПАУЗЫ</b><br><tt>" + pauses + "</tt>")

    return "<br><br>".join(blocks)


class ChatStatsPlugin(BasePlugin):
    def on_plugin_load(self):
        self._scan = None
        self._export = None
        self._busy_dialog = None
        self._menu = self.add_menu_item(
            MenuItemData(
                menu_type=MenuItemType.CHAT_ACTION_MENU,
                text="Статистика чата",
                item_id="chat_stats_open",
                icon="msg_info",
                priority=10,
                on_click=self._on_menu,
            )
        )

    def on_plugin_unload(self):
        self._cancel()
        self._export_cancel()

    def create_settings(self):
        return [
            Custom(view=self._cover_view()),
            Header(text="Статистика"),
            Selector(
                key="depth",
                text="Сколько сообщений читать",
                default=DEFAULT_DEPTH,
                items=list(DEPTH_LABELS),
                subtext="Чем глубже, тем точнее и тем дольше счёт",
                icon="msg_list",
            ),
            Switch(
                key="skip_service",
                text="Пропускать служебные",
                default=True,
                subtext="Заходы, пины, смены названия и прочая механика",
                icon="msg_info",
            ),
            Switch(
                key="smart_words",
                text="Убирать слова-филлеры",
                default=True,
                subtext="Плагин сам вычисляет заезженные слова по этому чату",
                icon="msg_info",
            ),
            Input(
                key="stop_words",
                text="Свои стоп-слова",
                default="",
                subtext="Через запятую. В топ слов не попадут",
                icon="msg_text",
            ),
            Header(text="Экспорт"),
            Text(
                text="Экспорт чата в zip",
                subtext="Переписка, таблица, json и сводка одним архивом",
                icon="msg_arrow_forward",
                on_click=self._open_export,
            ),
            Header(text="Вид"),
            Switch(
                key="show_cover",
                text="Показывать обложку",
                default=True,
                icon="msg_gallery",
            ),
            Divider(),
            Text(
                text="О плагине",
                subtext=f"Версия {__version__} · {__author__}",
                icon="msg_info",
                create_sub_fragment=self._about_page,
            ),
        ]

    def _about_page(self):
        return [
            Custom(view=self._cover_view(force=True)),
            Header(text="Chat Stats"),
            Text(
                text="Что считается",
                subtext="Сообщения, авторы, часы и дни, слова, паузы между сообщениями.",
                icon="msg_info",
            ),
            Text(
                text="Экспорт",
                subtext="Переписка в zip: txt, csv, json и сводка. Готовый архив уходит в Избранное.",
                icon="msg_arrow_forward",
            ),
            Text(
                text="Что с данными",
                subtext="История приходит с серверов Telegram, дальше всё живёт в памяти телефона и никуда не уходит. Ничего не сохраняется между запусками.",
                icon="msg_info",
            ),
            Text(
                text=__author__,
                subtext="Автор, нажми чтобы скопировать",
                icon="msg_info",
                on_click=lambda _view: copy_to_clipboard(__author__),
            ),
        ]

    def _open_export(self, _view=None):
        try:
            activity = self._activity()
            if activity is None:
                BulletinHelper.show_error("Нет активного окна")
                return
            field = self._input_field(activity)
            holder = self._input_holder(activity, field)
            dialog = AlertDialogBuilder(activity)
            dialog.set_title("Экспорт чата")
            dialog.set_message("Впиши @username или ссылку t.me/…, либо выбери чат из списка.")
            dialog.set_view(holder, -2)
            dialog.set_positive_button(
                "Дальше",
                lambda builder, which: self._export_resolve(_field_text(field), builder),
            )
            dialog.set_neutral_button("Мои чаты", lambda builder, which: self._export_list(builder))
            dialog.set_negative_button("Отмена", lambda builder, which: builder.dismiss())
            dialog.show()
        except Exception:
            self.logger.exception("export dialog failed")
            BulletinHelper.show_error("Не смог открыть окно экспорта")

    def _input_field(self, activity):
        from android.text import InputType
        from android.widget import EditText
        from org.telegram.ui.ActionBar import Theme

        field = EditText(activity)
        field.setSingleLine(True)
        field.setHint("@username или t.me/…")
        try:
            field.setInputType(InputType.TYPE_CLASS_TEXT)
        except Exception:
            pass
        try:
            field.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        except Exception:
            pass
        try:
            field.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText))
        except Exception:
            pass
        return field

    def _input_holder(self, activity, field):
        from android.widget import LinearLayout

        holder = LinearLayout(activity)
        holder.setOrientation(LinearLayout.VERTICAL)
        holder.setPadding(AndroidUtilities.dp(24), AndroidUtilities.dp(4), AndroidUtilities.dp(24), AndroidUtilities.dp(4))
        holder.addView(field, LinearLayout.LayoutParams(-1, -2))
        return holder

    def _export_resolve(self, raw, builder):
        username = _parse_username(raw)
        if not username:
            BulletinHelper.show_error("Нужен @username или ссылка t.me/name")
            return
        try:
            builder.dismiss()
        except Exception:
            pass
        account = self._current_account()
        self._busy("Ищу чат…")
        try:
            request = TLRPC.TL_contacts_resolveUsername()
            request.username = username
            callback = lambda response, error: run_on_queue(
                lambda: self._on_resolved(account, response, error)
            )
            try:
                send_request(request, callback, account=account)
            except TypeError:
                send_request(request, callback)
        except Exception:
            self.logger.exception("resolve failed")
            self._busy_close()
            BulletinHelper.show_error("Не получилось отправить запрос")

    def _on_resolved(self, account, response, error):
        self._busy_close()
        if error is not None or response is None:
            text = _error_text(error) or "такого юзернейма не знаю"
            BulletinHelper.show_error("Не нашёл: " + text)
            return
        target = self._target_from_peer(
            getattr(response, "peer", None),
            list(getattr(response, "users", None) or []),
            list(getattr(response, "chats", None) or []),
            account,
        )
        if target is None:
            BulletinHelper.show_error("Это не чат и не человек")
            return
        run_on_ui_thread(lambda: self._export_depth(target))

    def _export_list(self, builder):
        try:
            builder.dismiss()
        except Exception:
            pass
        account = self._current_account()
        self._busy("Смотрю чаты…")
        try:
            request = TLRPC.TL_messages_getDialogs()
            for key, value in (("offset_date", 0), ("offset_id", 0), ("limit", 25), ("hash", 0), ("folder_id", 0)):
                try:
                    setattr(request, key, value)
                except Exception:
                    pass
            try:
                request.offset_peer = TLRPC.TL_inputPeerEmpty()
            except Exception:
                pass
            try:
                request.exclude_pinned = False
            except Exception:
                pass
            callback = lambda response, error: run_on_queue(
                lambda: self._on_dialogs(account, response, error)
            )
            try:
                send_request(request, callback, account=account)
            except TypeError:
                send_request(request, callback)
        except Exception:
            self.logger.exception("dialogs failed")
            self._busy_close()
            BulletinHelper.show_error("Список не открылся, впиши @username")

    def _on_dialogs(self, account, response, error):
        self._busy_close()
        if error is not None or response is None:
            BulletinHelper.show_error("Список не открылся, впиши @username")
            return
        users = list(getattr(response, "users", None) or [])
        chats = list(getattr(response, "chats", None) or [])
        targets = []
        for dialog in getattr(response, "dialogs", None) or []:
            target = self._target_from_peer(getattr(dialog, "peer", None), users, chats, account)
            if target is not None:
                targets.append(target)
        if not targets:
            BulletinHelper.show_error("Пусто, впиши @username вручную")
            return
        run_on_ui_thread(lambda: self._show_dialog_list(targets))

    def _show_dialog_list(self, targets):
        try:
            shown = targets[:25]
            dialog = AlertDialogBuilder(self._activity())
            dialog.set_title("Выбери чат")
            dialog.set_items(
                [target["title"] for target in shown],
                lambda builder, index: self._pick_target(builder, shown, index),
            )
            dialog.set_negative_button("Отмена", lambda builder, which: builder.dismiss())
            dialog.show()
        except Exception:
            self.logger.exception("dialog list failed")
            BulletinHelper.show_error("Список не открылся, впиши @username")

    def _pick_target(self, builder, targets, index):
        try:
            builder.dismiss()
        except Exception:
            pass
        if 0 <= index < len(targets):
            self._export_depth(targets[index])

    def _export_depth(self, target):
        try:
            dialog = AlertDialogBuilder(self._activity())
            dialog.set_title("Сколько качать")
            dialog.set_message(f"{target['title']}: сколько сообщений выгрузить?")
            limits = [1000, 5000, 20000, 0]
            dialog.set_items(
                ["1 000", "5 000", "20 000", "Вся история"],
                lambda builder, index: self._pick_depth(builder, target, limits, index),
            )
            dialog.set_negative_button("Отмена", lambda builder, which: builder.dismiss())
            dialog.show()
        except Exception:
            self.logger.exception("depth dialog failed")

    def _pick_depth(self, builder, target, limits, index):
        try:
            builder.dismiss()
        except Exception:
            pass
        limit = limits[index] if 0 <= index < len(limits) else 0
        self._export_start(target, limit)

    def _export_start(self, target, limit):
        job = {
            "target": target,
            "account": self._current_account(),
            "limit": limit,
            "offset": 0,
            "pages": 0,
            "messages": [],
            "names": {},
            "active": True,
            "finished": False,
            "progress": None,
            "token": 0,
        }
        self._export = job
        self._export_progress(job)
        run_on_queue(lambda: self._export_request(job))

    def _export_progress(self, job):
        try:
            kind = AlertDialogBuilder.ALERT_TYPE_LOADING if job["limit"] else AlertDialogBuilder.ALERT_TYPE_SPINNER
            dialog = AlertDialogBuilder(self._activity(), kind)
            dialog.set_title("Экспорт: " + job["target"]["title"])
            dialog.set_message("Качаю историю…")
            dialog.set_negative_button("Отмена", lambda builder, which: self._export_cancel())
            dialog.set_cancelable(True)
            dialog.show()
            job["progress"] = dialog
        except Exception:
            self.logger.exception("export progress failed")

    def _export_progress_value(self, job):
        dialog = job.get("progress")
        if dialog is None or not job["limit"]:
            return
        try:
            dialog.set_progress(min(99, int(len(job["messages"]) * 100 / max(1, job["limit"]))))
        except Exception:
            pass

    def _export_request(self, job):
        if not job["active"]:
            return
        try:
            request = TLRPC.TL_messages_getHistory()
            request.peer = job["target"]["peer"]
            request.offset_id = job["offset"]
            request.offset_date = 0
            request.add_offset = 0
            request.limit = PAGE_SIZE
            request.max_id = 0
            request.min_id = 0
            request.hash = 0
            callback = lambda response, error: run_on_queue(
                lambda: self._export_page(job, response, error)
            )
            self._export_watchdog_arm(job)
            try:
                send_request(request, callback, account=job["account"])
            except TypeError:
                send_request(request, callback)
        except Exception:
            self.logger.exception("export request failed")
            self._export_fail(job, "Запрос не ушёл")

    def _export_watchdog_arm(self, job):
        try:
            job["token"] += 1
            token = job["token"]
            run_on_queue(lambda: self._export_watchdog(job, token), PLUGINS_QUEUE, WATCHDOG_MS)
        except Exception:
            pass

    def _export_watchdog(self, job, token):
        if not job["active"] or job["finished"] or job.get("token") != token:
            return
        self.logger.error("export: no answer for %s ms", WATCHDOG_MS)
        self._export_fail(job, "Telegram не ответил, попробуй ещё раз")

    def _export_page(self, job, response, error):
        if not job["active"] or job["finished"]:
            return
        try:
            self._handle_export_page(job, response, error)
        except Exception:
            self.logger.exception("export page failed")
            self._export_fail(job, "Сломалось на скачивании истории")

    def _handle_export_page(self, job, response, error):
        if error is not None:
            text = _error_text(error)
            self._export_fail(job, text or "Telegram не ответил")
            return

        messages = list(getattr(response, "messages", None) or [])
        self._collect_names(job["names"], response)
        for message in messages:
            record = _export_record(message)
            if record is not None:
                job["messages"].append(record)

        ids = [int(getattr(message, "id", 0) or 0) for message in messages]
        oldest = min([value for value in ids if value > 0], default=0)
        limit = job["limit"]
        done = (
            oldest <= 0
            or oldest == job["offset"]
            or len(messages) < PAGE_SIZE
            or len(job["messages"]) >= EXPORT_CAP
            or (limit and len(job["messages"]) >= limit)
        )
        job["offset"] = oldest
        job["pages"] += 1
        self._export_progress_value(job)
        self.logger.debug("export page %s: %s messages", job["pages"], len(job["messages"]))

        if done:
            run_on_queue(lambda: self._export_finish(job), PLUGINS_QUEUE, 30)
        else:
            run_on_queue(lambda: self._export_request(job), PLUGINS_QUEUE, 150)

    def _export_finish(self, job):
        if job["finished"]:
            return
        job["finished"] = True
        job["active"] = False
        path = ""
        try:
            path = _write_archive(job)
        except Exception:
            self.logger.exception("archive failed")
        run_on_ui_thread(lambda: self._export_done(job, path))

    def _export_done(self, job, path):
        try:
            self._render_export(job, path)
        except Exception:
            self.logger.exception("export result failed")
            self._export_close(job)
            BulletinHelper.show_error("Не смог отправить архив")

    def _render_export(self, job, path):
        self._export_close(job)
        if not path:
            BulletinHelper.show_error("Не смог собрать zip")
            return
        title = job["target"]["title"]
        count = len(job["messages"])
        sent = False
        try:
            from client_utils import send_document

            peer_id = int(UserConfig.getInstance(job["account"]).getClientUserId())
            caption = f"{title} · {_fmt(count)} сообщений"
            try:
                send_document(peer_id, path, caption=caption, account=job["account"])
            except TypeError:
                send_document(peer_id, path, caption=caption)
            sent = True
        except Exception:
            self.logger.exception("send failed")
        if sent:
            BulletinHelper.show_success(f"Готово, zip в Избранном ({_fmt(count)})")
        else:
            copy_to_clipboard(path)
            BulletinHelper.show_info("Файл на месте, путь скопирован")

    def _export_fail(self, job, message):
        if job["finished"]:
            return
        job["finished"] = True
        job["active"] = False
        self.logger.error("export failed: %s", message)
        run_on_ui_thread(lambda: self._export_failed(job, message))

    def _export_failed(self, job, message):
        try:
            self._export_close(job)
            BulletinHelper.show_error(message)
        except Exception:
            self.logger.exception("export error dialog failed")

    def _export_close(self, job):
        dialog = job.get("progress")
        if dialog is None:
            return
        job["progress"] = None
        try:
            dialog.dismiss()
        except Exception:
            pass

    def _export_cancel(self):
        job = getattr(self, "_export", None)
        self._export = None
        if job is None:
            return
        job["active"] = False
        job["finished"] = True
        self._export_close(job)

    def _target_from_peer(self, peer, users, chats, account):
        if peer is None or TLRPC is None:
            return None
        try:
            if isinstance(peer, TLRPC.TL_peerUser):
                user_id = int(peer.user_id)
                user = _find_by_id(users, user_id)
                if user is None:
                    try:
                        user = get_messages_controller(account).getUser(user_id)
                    except Exception:
                        user = None
                if user is None:
                    return None
                input_peer = TLRPC.TL_inputPeerUser()
                input_peer.user_id = user_id
                input_peer.access_hash = int(getattr(user, "access_hash", 0) or 0)
                return {"peer": input_peer, "title": _display_name(user)}

            if isinstance(peer, TLRPC.TL_peerChannel):
                channel_id = int(peer.channel_id)
                chat = _find_by_id(chats, channel_id)
                if chat is None:
                    try:
                        chat = get_messages_controller(account).getChat(channel_id)
                    except Exception:
                        chat = None
                if chat is None:
                    return None
                input_peer = TLRPC.TL_inputPeerChannel()
                input_peer.channel_id = channel_id
                input_peer.access_hash = int(getattr(chat, "access_hash", 0) or 0)
                return {"peer": input_peer, "title": str(getattr(chat, "title", "") or f"канал {channel_id}")}

            if isinstance(peer, TLRPC.TL_peerChat):
                chat_id = int(peer.chat_id)
                chat = _find_by_id(chats, chat_id)
                input_peer = TLRPC.TL_inputPeerChat()
                input_peer.chat_id = chat_id
                title = str(getattr(chat, "title", "") or "") if chat is not None else ""
                return {"peer": input_peer, "title": title or f"чат {chat_id}"}
        except Exception:
            return None
        return None

    def _current_account(self):
        return int(UserConfig.selectedAccount) if UserConfig is not None else 0

    def _busy(self, text):
        try:
            dialog = AlertDialogBuilder(self._activity(), AlertDialogBuilder.ALERT_TYPE_SPINNER)
            dialog.set_title("Chat Stats")
            dialog.set_message(text)
            dialog.set_cancelable(True)
            dialog.show()
            self._busy_dialog = dialog
        except Exception:
            self._busy_dialog = None

    def _busy_close(self):
        dialog = getattr(self, "_busy_dialog", None)
        self._busy_dialog = None
        if dialog is None:
            return
        try:
            dialog.dismiss()
        except Exception:
            pass

    def _on_menu(self, context):
        try:
            dialog_id = self._dialog_id(context)
            if not dialog_id:
                BulletinHelper.show_error("Не понял, какой это чат")
                return
            self._start(dialog_id, self._account(context))
        except Exception:
            self.logger.exception("chat stats menu failed")
            BulletinHelper.show_error("Что-то сломалось, глянь лог")

    def _dialog_id(self, context):
        for key in ("dialog_id", "dialogId"):
            try:
                value = context.get(key)
            except Exception:
                value = None
            if value:
                return int(value)
        try:
            fragment = context.get("fragment")
        except Exception:
            fragment = None
        if fragment is None:
            fragment = get_last_fragment()
        try:
            if fragment is not None:
                return int(fragment.getDialogId())
        except Exception:
            pass
        return 0

    def _account(self, context):
        try:
            value = context.get("account")
            if value is not None:
                return int(value)
        except Exception:
            pass
        return int(UserConfig.selectedAccount) if UserConfig is not None else 0

    def _skip_service(self):
        try:
            return bool(self.get_setting("skip_service", True))
        except Exception:
            return True

    def _smart_words(self):
        try:
            return bool(self.get_setting("smart_words", True))
        except Exception:
            return True

    def _depth(self):
        try:
            index = int(self.get_setting("depth", DEFAULT_DEPTH))
        except Exception:
            index = DEFAULT_DEPTH
        return DEPTHS[max(0, min(index, len(DEPTHS) - 1))]

    def _stop_words(self):
        words = set()
        try:
            raw = self.get_setting("stop_words", "") or ""
        except Exception:
            raw = ""
        for chunk in re.split(r"[,;\s]+", str(raw).lower()):
            if chunk:
                words.add(chunk)
        return words

    def _title(self, dialog_id, account):
        try:
            name = get_messages_controller(account).getPeerName(dialog_id)
            if name:
                return str(name)
        except Exception:
            pass
        return "Chat Stats"

    def _start(self, dialog_id, account):
        self._cancel()
        scan = {
            "dialog": dialog_id,
            "account": account,
            "limit": self._depth(),
            "offset": 0,
            "pages": 0,
            "fetched": 0,
            "records": [],
            "names": {},
            "active": True,
            "finished": False,
            "progress": None,
            "token": 0,
            "skip_service": self._skip_service(),
            "stop_words": self._stop_words(),
            "smart": self._smart_words(),
        }
        self._scan = scan
        self._progress_dialog(scan, self._title(dialog_id, account))
        run_on_queue(lambda: self._request(scan))

    def _progress_dialog(self, scan, title):
        try:
            kind = AlertDialogBuilder.ALERT_TYPE_LOADING if scan["limit"] else AlertDialogBuilder.ALERT_TYPE_SPINNER
            dialog = AlertDialogBuilder(self._activity(), kind)
            dialog.set_title(title)
            dialog.set_message("Читаю историю…")
            dialog.set_negative_button("Отмена", lambda builder, which: self._cancel())
            dialog.set_cancelable(True)
            dialog.show()
            scan["progress"] = dialog
        except Exception:
            self.logger.exception("progress dialog failed")

    def _request(self, scan):
        if not scan["active"] or scan["finished"]:
            return
        try:
            peer = get_messages_controller(scan["account"]).getInputPeer(scan["dialog"])
            if peer is None or TLRPC is None:
                self._fail(scan, "Не получилось открыть этот чат")
                return
            request = TLRPC.TL_messages_getHistory()
            request.peer = peer
            request.offset_id = scan["offset"]
            request.offset_date = 0
            request.add_offset = 0
            request.limit = PAGE_SIZE
            request.max_id = 0
            request.min_id = 0
            request.hash = 0
            self._arm_watchdog(scan)
            callback = lambda response, error: run_on_queue(lambda: self._page(scan, response, error))
            try:
                send_request(request, callback, account=scan["account"])
            except TypeError:
                send_request(request, callback)
        except Exception:
            self.logger.exception("history request failed")
            self._fail(scan, "Запрос не ушёл")

    def _arm_watchdog(self, scan):
        try:
            scan["token"] += 1
            token = scan["token"]
            run_on_queue(lambda: self._watchdog(scan, token), PLUGINS_QUEUE, WATCHDOG_MS)
        except Exception:
            pass

    def _watchdog(self, scan, token):
        if not scan["active"] or scan["finished"] or scan.get("token") != token:
            return
        self.logger.error("no answer for %s ms, giving up", WATCHDOG_MS)
        self._fail(scan, "Telegram не ответил, попробуй ещё раз")

    def _page(self, scan, response, error):
        if not scan["active"] or scan["finished"]:
            return
        try:
            self._handle_page(scan, response, error)
        except Exception:
            self.logger.exception("history page failed")
            self._fail(scan, "Сломалось на чтении истории, глянь лог")

    def _handle_page(self, scan, response, error):
        if error is not None:
            text = _error_text(error)
            self._fail(scan, text or "Telegram не ответил")
            return
        if response is None:
            self._fail(scan, "Telegram не ответил")
            return

        messages = list(getattr(response, "messages", None) or [])
        scan["fetched"] += len(messages)
        scan["pages"] += 1
        self._collect_names(scan["names"], response)

        skip_service = scan.get("skip_service", True)
        for message in messages:
            record = _extract(message, skip_service)
            if record is not None:
                scan["records"].append(record)

        self._progress(scan)

        ids = [int(getattr(message, "id", 0) or 0) for message in messages]
        oldest = min([value for value in ids if value > 0], default=0)
        enough = (
            oldest <= 0
            or oldest == scan["offset"]
            or len(messages) < PAGE_SIZE
            or scan["pages"] >= MAX_PAGES
            or scan["fetched"] >= EXPORT_CAP
            or (scan["limit"] and scan["fetched"] >= scan["limit"])
        )
        self.logger.debug(
            "page %s: fetched %s, kept %s, oldest %s",
            scan["pages"], scan["fetched"], len(scan["records"]), oldest,
        )

        if enough:
            run_on_queue(lambda: self._finish(scan), PLUGINS_QUEUE, 30)
            return

        scan["offset"] = oldest
        run_on_queue(lambda: self._request(scan), PLUGINS_QUEUE, 120)

    def _collect_names(self, names, response):
        try:
            for user in getattr(response, "users", None) or []:
                user_id = int(getattr(user, "id", 0) or 0)
                if not user_id:
                    continue
                first = getattr(user, "first_name", None) or ""
                last = getattr(user, "last_name", None) or ""
                name = f"{first} {last}".strip()
                if not name:
                    name = getattr(user, "username", None) or ""
                if name:
                    names[("u", user_id)] = name
        except Exception:
            pass
        try:
            for chat in getattr(response, "chats", None) or []:
                chat_id = int(getattr(chat, "id", 0) or 0)
                if not chat_id:
                    continue
                title = getattr(chat, "title", None)
                if title:
                    names[("c", chat_id)] = str(title)
        except Exception:
            pass

    def _progress(self, scan):
        dialog = scan.get("progress")
        if dialog is None or not scan["active"] or not scan["limit"]:
            return
        value = int(scan["fetched"] * 100 / max(1, scan["limit"]))
        try:
            dialog.set_progress(max(1, min(99, value)))
        except Exception:
            pass

    def _finish(self, scan):
        if scan["finished"]:
            return
        scan["finished"] = True
        scan["active"] = False
        try:
            self._resolve_names(scan)
            stats = _aggregate(
                scan["records"],
                scan["names"],
                scan.get("stop_words") or set(),
                scan.get("smart", True),
            )
        except Exception:
            self.logger.exception("aggregate failed")
            stats = None
        self.logger.info("scan done: %s pages, %s messages", scan["pages"], scan["fetched"])
        run_on_ui_thread(lambda: self._show(scan, stats))

    def _resolve_names(self, scan):
        try:
            controller = get_messages_controller(scan["account"])
        except Exception:
            return
        seen = set()
        for _stamp, key, _text, _media in scan["records"]:
            if key in scan["names"] or key in seen:
                continue
            seen.add(key)
            try:
                if key[0] == "u":
                    user = controller.getUser(key[1])
                    if user is None:
                        continue
                    first = getattr(user, "first_name", None) or ""
                    last = getattr(user, "last_name", None) or ""
                    name = f"{first} {last}".strip() or getattr(user, "username", None) or ""
                    if name:
                        scan["names"][key] = str(name)
                else:
                    chat = controller.getChat(key[1])
                    if chat is None:
                        continue
                    title = getattr(chat, "title", None)
                    if title:
                        scan["names"][key] = str(title)
            except Exception:
                continue

    def _show(self, scan, stats):
        try:
            self._render_result(scan, stats)
        except Exception:
            self.logger.exception("result dialog failed")
            self._close(scan)
            BulletinHelper.show_error("Не смог показать статистику")

    def _render_result(self, scan, stats):
        self._close(scan)
        if not stats:
            BulletinHelper.show_info("Тут пока нечего считать")
            return
        plain = _render_text(stats)
        dialog = AlertDialogBuilder(self._activity())
        dialog.set_title(self._title(scan["dialog"], scan["account"]))
        view = self._stats_view(stats)
        if view is not None:
            dialog.set_view(view, self._view_height())
        else:
            dialog.set_message(plain)
        dialog.set_neutral_button(
            "Копировать",
            lambda builder, which: copy_to_clipboard(plain),
        )
        dialog.set_positive_button("Закрыть", lambda builder, which: builder.dismiss())
        dialog.show()

    def _view_height(self):
        try:
            return int(AndroidUtilities.displaySize.y * 0.58)
        except Exception:
            return -2

    def _stats_view(self, stats):
        try:
            from android.text import Html
            from android.widget import ScrollView, TextView
            from org.telegram.ui.ActionBar import Theme

            activity = self._activity()
            if activity is None:
                return None

            text = TextView(activity)
            text.setText(Html.fromHtml(_render_html(stats)))
            text.setTextSize(14)
            text.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            text.setTextIsSelectable(True)
            text.setPadding(
                AndroidUtilities.dp(21),
                AndroidUtilities.dp(10),
                AndroidUtilities.dp(21),
                AndroidUtilities.dp(10),
            )
            text.setLineSpacing(AndroidUtilities.dp(2), 1.0)

            scroll = ScrollView(activity)
            scroll.addView(text)
            return scroll
        except Exception:
            self.logger.exception("stats view failed")
            return None

    def _cover_view(self, force=False):
        if not force:
            try:
                if not bool(self.get_setting("show_cover", True)):
                    return None
            except Exception:
                pass
        try:
            from android.graphics import BitmapFactory
            from android.graphics.drawable import BitmapDrawable
            from android.widget import ImageView, LinearLayout

            activity = self._activity()
            if activity is None:
                return None

            data = base64.b64decode(COVER_GIF)
            drawable = None
            try:
                from android.graphics import ImageDecoder
                from java.nio import ByteBuffer

                source = ImageDecoder.createSource(ByteBuffer.wrap(data))
                drawable = ImageDecoder.decodeDrawable(source)
            except Exception:
                bitmap = BitmapFactory.decodeByteArray(data, 0, len(data))
                if bitmap is not None:
                    drawable = BitmapDrawable(activity.getResources(), bitmap)
            if drawable is None:
                return None

            image = ImageView(activity)
            image.setImageDrawable(drawable)
            image.setScaleType(ImageView.ScaleType.FIT_CENTER)
            image.setAdjustViewBounds(True)

            row = LinearLayout(activity)
            row.setOrientation(LinearLayout.VERTICAL)
            row.setPadding(AndroidUtilities.dp(12), AndroidUtilities.dp(10), AndroidUtilities.dp(12), AndroidUtilities.dp(4))
            row.addView(image, LinearLayout.LayoutParams(-1, -2))
            return row
        except Exception:
            self.logger.exception("cover view failed")
            return None

    def _activity(self):
        try:
            fragment = get_last_fragment()
            if fragment is None:
                return None
            return fragment.getParentActivity()
        except Exception:
            return None

    def _fail(self, scan, message):
        if scan["finished"]:
            return
        scan["finished"] = True
        scan["active"] = False
        self.logger.error("scan failed: %s", message)
        run_on_ui_thread(lambda: self._show_error(scan, message))

    def _show_error(self, scan, message):
        try:
            self._close(scan)
            BulletinHelper.show_error(message)
        except Exception:
            self.logger.exception("error dialog failed")

    def _close(self, scan):
        dialog = scan.get("progress")
        if dialog is None:
            return
        scan["progress"] = None
        try:
            dialog.dismiss()
        except Exception:
            pass

    def _cancel(self):
        scan = self._scan
        self._scan = None
        if scan is None:
            return
        scan["active"] = False
        scan["finished"] = True
        self._close(scan)


COVER_GIF = "__COVER_GIF__"
