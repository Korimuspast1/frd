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
__version__ = "1.0.0"
__icon__ = "exteraPlugins/1"
__app_version__ = ">=12.5.1"
__sdk_version__ = ">=1.4.4.3"
__category__ = ["chats", "tools"]


PAGE_SIZE = 100
DEPTHS = (300, 1000, 2000, 5000, 10000)
DEPTH_LABELS = ("300", "1 000", "2 000", "5 000", "10 000")
DEFAULT_DEPTH = 2
TOP_AUTHORS = 8
TOP_WORDS = 14
TOP_PAUSES = 3
MIN_PAUSE = 3600
BLOCKS = "▁▂▃▄▅▆▇█"
DAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]{3,}")

BASE_STOP_WORDS = frozenset(
    """
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по
только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если
уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей
может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз
тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом
один почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при
наконец два об другой хоть после над больше тот через эти нас про всего них какая
много разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя
такой им более всегда конечно всю между типа вообще просто очень даже кстати привет
всем нет ок окей ага угу чего щас сейчас короче блин хз имхо лол

the and for you not are but all can her was one our out day get has him his how man
new now old see two way who boy did its let put say she too use that with have this
will your from they know want been good much some time very when come here just like
long make many more only over such take than them well were what where which while
"""
    .split()
)


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


def _aggregate(records, names, stop_words):
    total = len(records)
    if not total:
        return None

    ordered = sorted(records, key=lambda item: item[0])
    authors = {}
    hours = [0] * 24
    days = [0] * 7
    words = {}
    media = 0
    length_sum = 0
    length_count = 0

    for stamp, key, text, has_media in ordered:
        authors[key] = authors.get(key, 0) + 1
        moment = datetime.datetime.fromtimestamp(stamp)
        hours[moment.hour] += 1
        days[moment.weekday()] += 1
        if has_media:
            media += 1
        if text:
            length_sum += len(text)
            length_count += 1
            for word in WORD_RE.findall(text.lower()):
                if word in stop_words or word.isdigit():
                    continue
                words[word] = words.get(word, 0) + 1

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
        "avg_len": int(round(length_sum / length_count)) if length_count else 0,
        "per_day": total / float(span),
        "top": top,
        "hours": hours,
        "days": days,
        "words": sorted(words.items(), key=lambda item: (-item[1], item[0]))[:TOP_WORDS],
        "pauses": pause_rows,
    }


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


def _word_line(stats):
    return " · ".join(f"{word} {_fmt(count)}" for word, count in stats["words"])


def _pause_rows(stats):
    return [f"{gap} — {day}, {who}" for gap, day, who in stats["pauses"]]


def _render_text(stats):
    blocks = ["\n".join(_headline(stats))]

    if stats["top"]:
        blocks.append("КТО ПИШЕТ\n" + "\n".join(_author_rows(stats)))

    hours = stats["hours"]
    blocks.append("ПО ЧАСАМ\n00 " + _spark(hours) + " 23\n" + _hour_note(stats))

    blocks.append("ПО ДНЯМ\n" + "\n".join(_day_rows(stats)))

    if stats["words"]:
        blocks.append("ЧАСТЫЕ СЛОВА\n" + _word_line(stats))

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
        blocks.append("<b>ЧАСТЫЕ СЛОВА</b><br><tt>" + words + "</tt>")

    if stats["pauses"]:
        pauses = "<br>".join(row.replace("&", "&amp;").replace("<", "&lt;") for row in _pause_rows(stats))
        blocks.append("<b>САМЫЕ ДЛИННЫЕ ПАУЗЫ</b><br><tt>" + pauses + "</tt>")

    return "<br><br>".join(blocks)


class ChatStatsPlugin(BasePlugin):
    def on_plugin_load(self):
        self._scan = None
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
            Input(
                key="stop_words",
                text="Свои стоп-слова",
                default="",
                subtext="Через запятую. В топ слов не попадут",
                icon="msg_text",
            ),
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

    def _depth(self):
        try:
            index = int(self.get_setting("depth", DEFAULT_DEPTH))
        except Exception:
            index = DEFAULT_DEPTH
        return DEPTHS[max(0, min(index, len(DEPTHS) - 1))]

    def _stop_words(self):
        words = set(BASE_STOP_WORDS)
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
            "records": [],
            "names": {},
            "active": True,
            "progress": None,
        }
        self._scan = scan
        self._progress_dialog(scan, self._title(dialog_id, account))
        run_on_queue(lambda: self._request(scan))

    def _progress_dialog(self, scan, title):
        try:
            dialog = AlertDialogBuilder(self._activity(), AlertDialogBuilder.ALERT_TYPE_LOADING)
            dialog.set_title(title)
            dialog.set_message("Читаю историю…")
            dialog.set_negative_button("Отмена", lambda builder, which: self._cancel())
            dialog.set_cancelable(True)
            dialog.show()
            scan["progress"] = dialog
        except Exception:
            self.logger.exception("progress dialog failed")

    def _request(self, scan):
        if not scan["active"]:
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
            callback = lambda response, error: run_on_queue(lambda: self._page(scan, response, error))
            try:
                send_request(request, callback, account=scan["account"])
            except TypeError:
                send_request(request, callback)
        except Exception:
            self.logger.exception("history request failed")
            self._fail(scan, "Запрос не ушёл")

    def _page(self, scan, response, error):
        if not scan["active"]:
            return
        if error is not None:
            text = str(getattr(error, "text", "") or "")
            if "FLOOD_WAIT_" in text:
                wait = text.split("FLOOD_WAIT_")[-1].split()[0].strip()
                self._fail(scan, f"Telegram просит подождать {wait} с")
            elif text:
                self._fail(scan, f"Telegram: {text}")
            else:
                self._fail(scan, "Telegram не ответил")
            return

        messages = list(getattr(response, "messages", None) or [])
        self._collect_names(scan, response)

        skip = bool(self.get_setting("skip_service", True))
        for message in messages:
            record = _extract(message, skip)
            if record is not None:
                scan["records"].append(record)

        ids = [int(getattr(message, "id", 0) or 0) for message in messages]
        oldest = min([value for value in ids if value > 0], default=0)
        if oldest <= 0 or oldest == scan["offset"]:
            run_on_queue(lambda: self._finish(scan), PLUGINS_QUEUE, 30)
            return

        scan["offset"] = oldest
        scan["pages"] += 1
        self._progress(scan)

        if len(messages) < PAGE_SIZE or len(scan["records"]) >= scan["limit"]:
            run_on_queue(lambda: self._finish(scan), PLUGINS_QUEUE, 50)
        else:
            run_on_queue(lambda: self._request(scan), PLUGINS_QUEUE, 120)

    def _collect_names(self, scan, response):
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
                    scan["names"][("u", user_id)] = name
        except Exception:
            pass
        try:
            for chat in getattr(response, "chats", None) or []:
                chat_id = int(getattr(chat, "id", 0) or 0)
                if not chat_id:
                    continue
                title = getattr(chat, "title", None)
                if title:
                    scan["names"][("c", chat_id)] = str(title)
        except Exception:
            pass

    def _progress(self, scan):
        dialog = scan.get("progress")
        if dialog is None or not scan["active"]:
            return
        value = int(len(scan["records"]) * 100 / max(1, scan["limit"]))
        try:
            dialog.set_progress(min(99, value))
        except Exception:
            pass

    def _finish(self, scan):
        if not scan["active"]:
            return
        scan["active"] = False
        try:
            self._resolve_names(scan)
            stats = _aggregate(scan["records"], scan["names"], self._stop_words())
        except Exception:
            self.logger.exception("aggregate failed")
            stats = None
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
        scan["active"] = False
        run_on_ui_thread(lambda: self._show_error(scan, message))

    def _show_error(self, scan, message):
        self._close(scan)
        BulletinHelper.show_error(message)

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
        self._close(scan)


COVER_GIF = "__COVER_GIF__"
