"""Product defaults and credentials bound to the current Windows user."""
from localization import tr
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit

from diary import atomic_write, require

VERSION = "1.5.0"
PRESETS = {
    "OpenAI": ("openai", "https://api.openai.com/v1", "https://platform.openai.com/api-keys"),
    "DeepSeek": ("openai", "https://api.deepseek.com", "https://platform.deepseek.com/api_keys"),
    "通义千问 / 百炼": ("openai", "https://dashscope.aliyuncs.com/compatible-mode/v1", "https://help.aliyun.com/zh/model-studio/base-url"),
    "Claude / Anthropic": ("anthropic", "https://api.anthropic.com/v1", "https://platform.claude.com/"),
    "自定义 OpenAI 兼容": ("openai", "", ""),
    "自定义 Claude 兼容": ("anthropic", "", ""),
    "本机模型（OpenAI 兼容）": ("openai", "http://127.0.0.1:11434/v1", ""),
    "本机 Codex 登录": ("codex", "", ""),
    "仅离线使用": ("offline", "", ""),
}


def program_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def default_data_dir():
    # Existing personal installations retain their original archive location.
    base = program_dir()
    if (base / "vault" / "diary.sqlite3").exists():
        return base
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Shiguang" / "data"


def bootstrap(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = root / "config.json"
    if not config.exists():
        atomic_write(config, json.dumps({"name": "拾光", "version": VERSION, "language": "zh-CN", "timezone": "Asia/Shanghai", "watch_topics": [], "automation": {"status": "NOT_CONFIGURED"}}, ensure_ascii=False, indent=2))


def normalize_url(value):
    value = value.strip().rstrip("/")
    p = urlsplit(value)
    require(p.hostname and not p.username and not p.password and not p.query and not p.fragment, tr('API 地址不能含用户名、密码、查询参数或片段。'))
    require(p.scheme == "https" or (p.scheme == "http" and p.hostname in {"localhost", "127.0.0.1", "::1"}), tr('云端 API 使用 HTTPS；本机模型可用 localhost 的 HTTP 地址。'))
    require(not any(c.isspace() for c in value), tr('API 地址不能包含空白字符。'))
    _ = p.port
    path = p.path.rstrip("/")
    for suffix in ("/chat/completions", "/messages"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, "", ""))


def load_ai(store):
    raw = store.setting("ai_config")
    if raw:
        return validate_ai(json.loads(raw), complete=False)
    # Preserve the previous owner's explicitly available workflow only in legacy folders.
    legacy = (store.root / "AGENT.md").exists()
    return {"provider": "本机 Codex 登录" if legacy else "仅离线使用", "protocol": "codex" if legacy else "offline", "base_url": "", "model": "", "max_tokens": 4096, "context_chars": 60000, "tools": True}


def validate_ai(config, complete=True):
    protocol = config.get("protocol", "offline")
    require(protocol in {"offline", "codex", "openai", "anthropic"}, tr('不支持的 AI 接口类型。'))
    base = normalize_url(config.get("base_url", "")) if protocol in {"openai", "anthropic"} else ""
    model = str(config.get("model", "")).strip()
    if complete and protocol in {"openai", "anthropic"}:
        require(bool(model) and len(model) < 200, tr('请填写服务商控制台里的模型名称。'))
    maximum = int(config.get("max_tokens", 4096))
    context = int(config.get("context_chars", 60000))
    require(256 <= maximum <= 32768, tr('最大输出 Token 为256–32768。'))
    require(12000 <= context <= 240000, tr('上下文预算为12000–240000字符。'))
    return {"provider": str(config.get("provider", "自定义 OpenAI 兼容")), "protocol": protocol, "base_url": base,
            "model": model, "max_tokens": maximum, "context_chars": context, "tools": bool(config.get("tools", True))}


def credential_id(config):
    return hashlib.sha256((config["protocol"] + "|" + config["base_url"]).encode()).hexdigest()


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    require(sys.platform == "win32", tr('此版本使用 Windows 加密存储 Token。'))
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ValueError(tr('无法读取此 Windows 账户的 Token，请重新填写。') if decrypt else tr('Token 加密失败，尚未保存。'))
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


class Credentials:
    def __init__(self, root):
        self.path = Path(root) / "credentials.dpapi"

    def _read(self):
        if not self.path.exists():
            return {}
        return json.loads(protect(base64.b64decode(self.path.read_bytes()), True).decode("utf-8"))

    def get(self, config):
        return self._read().get(credential_id(config), "")

    def set(self, config, token):
        require(isinstance(token, str) and len(token) <= 8192 and not any(c.isspace() for c in token), tr('Token 格式不正确，不能包含空白字符。'))
        values = self._read()
        if token:
            values[credential_id(config)] = token
        else:
            values.pop(credential_id(config), None)
        encrypted = protect(json.dumps(values).encode("utf-8"))
        atomic_write(self.path, base64.b64encode(encrypted).decode("ascii"))


def ai_description(store):
    try:
        config = load_ai(store)
        if config["protocol"] == "offline":
            return tr('尚未设置在线 AI · 点击「AI 设置」填写自己的 Token')
        if config["protocol"] == "codex":
            return tr('本机 Codex 登录 · 按该账户额度使用')
        return tr(config["provider"]) + " · " + (config["model"] or tr('未填写模型')) + tr(' · 费用由服务商收取')
    except Exception:
        return tr('AI 配置需要重新设置')
