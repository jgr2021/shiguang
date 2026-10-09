"""First-run onboarding and user-owned AI settings."""
from localization import tr, LANGUAGES, get_language
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import webbrowser

from app_config import VERSION, PRESETS, Credentials, load_ai, validate_ai, ai_description, program_dir
from api_assistant import connection_check
from ui_design import P, FONT, SoftButton, ScrollPane, new_window, heading

BG, GREEN, MUTED = P["paper"], P["green"], P["muted"]


def label(parent, value, size=10, color=MUTED):
    widget = tk.Label(parent, text=value, bg=parent.cget("bg"), fg=color, font=(FONT, size), anchor="w", justify="left", wraplength=640)
    widget.pack(fill="x", pady=5)
    return widget


def button(parent, title, command, primary=False):
    return SoftButton(parent, title, command, primary)


def dialog(app, title, height):
    top = new_window(app, title, (790, height), minimum=(640, 460))
    heading(top, title, eyebrow=tr('拾光日历'))
    pane = ScrollPane(top, bg=P["bg"], bind_wheel=True)
    pane.pack(fill="both", expand=True, padx=28, pady=(0, 24))
    body = tk.Frame(pane.inner, bg=BG, padx=24, pady=20)
    body.pack(fill="x")
    return top, body


def section(parent, title, subtitle=""):
    box = tk.Frame(parent, bg=BG, padx=22, pady=18, highlightthickness=1, highlightbackground=P["line"])
    box.pack(fill="x", pady=(0, 14))
    label(box, title, 13, P["ink"])
    if subtitle:
        label(box, subtitle, 9)
    return box


def language_picker(features, top, body, reopen):
    # Self-named choices remain recognizable from any currently selected language.
    label(body, '简体中文 / 繁體中文 / English', 10, GREEN)
    row = tk.Frame(body, bg=BG)
    row.pack(fill="x", pady=3)
    selected = tk.StringVar(value=LANGUAGES[get_language()])
    ttk.Combobox(row, textvariable=selected, values=list(LANGUAGES.values()), state="readonly", font=(FONT, 10), width=18).pack(side="left")
    def apply():
        code = next(code for code, name in LANGUAGES.items() if name == selected.get())
        features.app.apply_language(code, top, reopen)
    button(row, tr('应用语言'), apply).pack(side="left", padx=10)
    label(body, tr('切换后立即生效，助手默认使用所选语言回复。'), 9)


def open_settings(features):
    app = features.app
    if features.ai:
        app.notice(tr('当前助手正在运行，可停止后再修改 AI 设置。'))
        return
    existing = getattr(features, "settings_window", None)
    if existing and existing.winfo_exists():
        existing.lift()
        return
    top, body = dialog(app, tr('AI 设置'), 800)
    features.settings_window = top
    current = load_ai(app.store)
    credentials = Credentials(app.store.root)
    label(body, tr('用你自己的 AI'), 19, GREEN)
    label(body, tr('选择服务商，填写控制台的 API Token 与模型名。费用由对应服务商收取。'), 9)
    provider_labels = {tr(name): name for name in PRESETS}
    provider_labels.setdefault(tr(current["provider"]), current["provider"])
    provider = tk.StringVar(value=tr(current["provider"]))
    choices = ttk.Combobox(body, textvariable=provider, values=list(provider_labels), state="readonly", font=(FONT, 10))
    choices.pack(fill="x", pady=7)
    fields = {}
    def field(title, key, value, secret=False):
        line = tk.Frame(body, bg=BG)
        line.pack(fill="x", pady=5)
        tk.Label(line, text=title, width=22, anchor="w", font=(FONT, 9), bg=BG, fg=MUTED, wraplength=180, justify="left").pack(side="left", padx=(0, 12))
        fields[key] = tk.StringVar(value=value)
        entry = ttk.Entry(line, textvariable=fields[key], show="•" if secret else "", font=(FONT, 10))
        entry.pack(side="left", fill="x", expand=True)
        return entry
    field(tr('API 基础地址'), "base_url", current["base_url"])
    field(tr('模型名称'), "model", current["model"])
    token_entry = field(tr('API Token（留空保留）'), "token", "", True)
    status = tk.StringVar(value="")
    tk.Label(body, textvariable=status, bg=BG, fg=GREEN, wraplength=670, font=(FONT, 9), anchor="w", justify="left").pack(fill="x", pady=5)
    field(tr('最大输出 Token'), "max_tokens", str(current["max_tokens"]))
    field(tr('上下文预算（字符）'), "context_chars", str(current["context_chars"]))
    use_tools = tk.BooleanVar(value=current["tools"])
    tk.Checkbutton(body, text=tr('分步检索档案（需模型支持工具调用；每轮最多13次 API 请求）'), variable=use_tools, bg=BG, fg=GREEN, activebackground=BG, font=(FONT, 9), anchor="w", wraplength=600, justify="left").pack(fill="x", pady=6)
    label(body, tr('模型不支持工具调用时，可关闭分步检索；会改为按相关性和日期提供预算内的资料，并标注是否完整。'), 9)
    label(body, tr('Token 用 Windows 加密，仅此 Windows 账户可读取；不写入对话、普通备份或安装包。修改 API 地址后，需要为新地址单独填写 Token。'), 9)
    label(body, tr('点击发送时，问题、近期对话与需要的档案内容会直接发给所选服务商。本版 API 模式不带网页搜索，不会自动查证最新信息。'), 9)
    def values(complete=True):
        name = provider_labels[provider.get()]
        protocol = PRESETS.get(name, (current["protocol"], "", ""))[0]
        return validate_ai({"provider": name, "protocol": protocol, "base_url": fields["base_url"].get(), "model": fields["model"].get(), "max_tokens": fields["max_tokens"].get(), "context_chars": fields["context_chars"].get(), "tools": use_tools.get()}, complete=complete)
    def key_status(*args):
        try:
            config = values(False)
            if config["protocol"] in {"offline", "codex"}:
                status.set(tr('此模式无需在这里填写 Token。'))
            else:
                status.set(tr('此地址已有加密 Token，留空沿用。') if credentials.get(config) else tr('此地址尚未保存 Token。'))
        except Exception:
            status.set(tr('请填写完整的 API 基础地址；不同地域的地址以服务商控制台为准。'))
    def change(event=None):
        preset = PRESETS.get(provider_labels[provider.get()], (current["protocol"], current["base_url"], ""))
        fields["base_url"].set(preset[1])
        fields["model"].set("")
        fields["token"].set("")
        key_status()
    choices.bind("<<ComboboxSelected>>", change)
    fields["base_url"].trace_add("write", key_status)
    key_status()
    def save():
        try:
            config = values()
            token = fields["token"].get().strip()
            if config["protocol"] in {"openai", "anthropic"} and token:
                credentials.set(config, token)
            app.store.set_setting("ai_config", json.dumps(config, ensure_ascii=False))
            fields["token"].set("")
            if features.chat_window and features.chat_window.winfo_exists():
                features.chat_status.set(ai_description(app.store))
            app.notice(tr('AI 设置已保存到本机'))
            top.destroy()
        except Exception as error:
            status.set(str(error))
    def forget():
        try:
            config = values(False)
            credentials.set(config, "")
            fields["token"].set("")
            status.set(tr('已移除此 API 地址的 Token。'))
        except Exception as error:
            status.set(str(error))
    def done(value):
        if top.winfo_exists():
            check.configure(state="normal")
            status.set(value)
    def check_connection():
        try:
            config = values()
            token = fields["token"].get().strip() or credentials.get(config)
        except Exception as error:
            status.set(str(error))
            return
        check.configure(state="disabled")
        status.set(tr('正在发送一条简短连接检查消息（可能产生少量费用，不发送档案）……'))
        features.run(lambda store: connection_check(config, token), done, done)
    line = tk.Frame(body, bg=BG)
    line.pack(fill="x", pady=(10, 5))
    button(line, tr('保存设置'), save, True).pack(side="right")
    check = button(line, tr('检查连接'), check_connection)
    check.pack(side="right", padx=8)
    button(line, tr('移除此地址 Token'), forget).pack(side="left")
    def help_page():
        url = PRESETS.get(provider_labels[provider.get()], ("", "", ""))[2]
        if url:
            webbrowser.open(url)
        else:
            status.set(tr('自定义接口请使用服务商提供的 API 基础地址与模型名。'))
    button(body, tr('服务商官方说明 / 获取 Token'), help_page).pack(anchor="w", pady=5)


def welcome(features):
    app = features.app
    if app.store.setting("onboarding_seen"):
        return
    top, body = dialog(app, tr('欢迎使用拾光'), 735)
    language_picker(features, top, body, lambda: welcome(features))
    label(body, tr('每天一点，慢慢向前。'), 17, GREEN)
    label(body, tr('01  选一天，记录待办、想法与成果。'), 12, GREEN)
    label(body, tr('02  上传文件，让它出现在一个或多个日期。'), 12, GREEN)
    label(body, tr('03  想用 AI 时，填自己的 Token，让助手查记录、做复盘、更新简历。'), 12, GREEN)
    label(body, tr('可以先离线使用。没有账号注册，也无需安装 Python 或 Codex。API 模式的费用与服务条款由你选择的服务商决定。'), 10)
    label(body, tr('你的资料保存在：\n') + str(app.store.root), 9)
    def finish(settings=False):
        app.store.set_setting("onboarding_seen", "1")
        top.destroy()
        if settings:
            open_settings(features)
    row = tk.Frame(body, bg=BG)
    row.pack(fill="x", pady=18)
    button(row, tr('先开始记录'), finish, True).pack(side="right")
    button(row, tr('配置我的 AI'), lambda: finish(True)).pack(side="right", padx=10)
    top.protocol("WM_DELETE_WINDOW", finish)


def about(features):
    app = features.app
    existing = getattr(features, "about_window", None)
    if existing and existing.winfo_exists():
        existing.lift()
        return
    top, body = dialog(app, tr('设置与关于'), 780)
    features.about_window = top
    body.configure(bg=P["bg"], padx=0, pady=0)
    language_box = section(body, tr('显示语言'))
    language_picker(features, top, language_box, lambda: about(features))
    ai_box = section(body, tr('你的个人助手'), ai_description(app.store))
    button(ai_box, tr('AI 服务与 Token 设置'), lambda: open_settings(features), True).pack(anchor="w", pady=(10, 0))
    data_box = section(body, tr('资料与备份'))
    label(data_box, tr('个人数据目录：\n') + str(app.store.root), 9)
    row = tk.Frame(data_box, bg=BG)
    row.pack(fill="x", pady=10)
    button(row, tr('打开数据目录'), lambda: os.startfile(str(app.store.root))).pack(side="left")
    button(row, tr('导出完整备份'), app.backup).pack(side="left", padx=10)
    def guide():
        path = program_dir() / {"zh-CN": "开始使用.txt", "zh-TW": "開始使用.txt", "en": "Getting-Started.txt"}[get_language()]
        if path.exists():
            os.startfile(str(path))
    button(data_box, tr('使用说明与隐私说明'), guide).pack(anchor="w")
    label(body, tr('拾光日历  ') + VERSION + tr(' · 预览版'), 10, GREEN)
    label(body, tr('升级请安装新版安装包。卸载只移除程序，保留日记与加密 Token；迁移到其他 Windows 账户后需重新填写 Token。'), 9)
