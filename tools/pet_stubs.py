"""Заглушки SDK-модулей для офлайн-теста движка pet.py."""
import sys, types

def _mk(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod

class _Log:
    def info(self, *a): pass
    def error(self, *a): pass
    def warning(self, *a): pass
    def exception(self, *a): pass

class _Base:
    plugin_id = "tamagochi"
    def __init__(self):
        self.logger = _Log()
        self._settings = {}
    def get_setting(self, key, default=None):
        return self._settings.get(key, default)
    def set_setting(self, key, value):
        self._settings[key] = value
    def on_plugin_load(self): pass
    def on_plugin_unload(self): pass
    def add_menu_item(self, *a, **kw): pass
    def add_on_send_message_hook(self, *a, **kw): pass

class _AppEvent:
    START = 0; STOP = 1; PAUSE = 2; RESUME = 3

def _no_op(*a, **kw): pass

_mk("base_plugin", BasePlugin=_Base, AppEvent=_AppEvent,
    MenuItemData=object, MenuItemType=object, HookStrategy=object)
_mk("android_utils", run_on_ui_thread=lambda func, delay=0: func(),
    OnClickListener=lambda fn: fn, copy_to_clipboard=_no_op, get_activity=lambda: None,
    get_context=lambda: None, log=_no_op)
_mk("client_utils", PLUGINS_QUEUE="plugins", run_on_queue=_no_op, send_request=_no_op,
    BasePluginClient=_Base, get_last_fragment=lambda: None)
class _Dialog:
    def __init__(self, *a, **kw): pass
    def __getattr__(self, name): return lambda *a, **kw: None
_mk("ui.alert", AlertDialogBuilder=_Dialog)
_mk("ui.bulletin", BulletinHelper=types.SimpleNamespace(
    show_success=_no_op, show_error=_no_op, show_info=_no_op))
class _UIRow:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

_mk("ui.settings", Custom=_UIRow, Divider=_UIRow, Header=_UIRow, Input=_UIRow,
    Switch=_UIRow, Text=_UIRow, Slider=_UIRow, EditText=_UIRow)
_mk("ui.container", LinearLayout=object)
for name in ("TLRPC", "TL_account"):
    _mk(name)
