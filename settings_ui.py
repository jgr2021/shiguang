"""First-run onboarding and user-owned AI settings."""
from localization import tr, LANGUAGES, get_language
import json
import os
import sys
from platform_support import open_path, wheel_units
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
    from ai_settings_ui import open_ai_settings
    open_ai_settings(features)


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
    from github_accounts import binding
    account = binding(app.store.root)
    sync_box = section(body, tr('账号与同步'),
                       tr('GitHub · {0}', account['login']) if account else tr('离线记录，联网后同步到自己的 GitHub 私有仓库。'))
    button(sync_box, tr('账号与同步'), features.github.open, True).pack(anchor='w', pady=(10, 0))
    from holiday_calendar import SOURCE_URL
    holiday_box = section(body, tr('节假日'), tr('中国大陆 · 已收录2026年官方放假与调休安排，离线可用。未收录年份不推算调休。'))
    button(holiday_box, tr('查看官方安排'), lambda: webbrowser.open(SOURCE_URL)).pack(anchor='w', pady=(8, 0))
    ai_box = section(body, tr('你的个人助手'), ai_description(app.store))
    button(ai_box, tr('AI 服务与 Token 设置'), lambda: open_settings(features), True).pack(anchor="w", pady=(10, 0))
    cloud_box = section(body, tr('云文件'), tr('支持 Google Drive、OneDrive、Dropbox 等客户端的本机同步文件夹。'))
    button(cloud_box, tr('云文件管理'), features.cloud).pack(anchor="w", pady=(10, 0))
    data_box = section(body, tr('资料与备份'))
    label(data_box, tr('个人数据目录：\n') + str(app.store.root), 9)
    row = tk.Frame(data_box, bg=BG)
    row.pack(fill="x", pady=10)
    button(row, tr('打开数据目录'), lambda: open_path(str(app.store.root))).pack(side="left")
    button(row, tr('导出完整备份'), app.backup).pack(side="left", padx=10)
    def guide():
        path = program_dir() / {"zh-CN": "开始使用.txt", "zh-TW": "開始使用.txt", "en": "Getting-Started.txt"}[get_language()]
        if sys.platform == 'darwin':
            path = program_dir() / 'MACOS-START.md'
        if path.exists():
            open_path(str(path))
    button(data_box, tr('使用说明与隐私说明'), guide).pack(anchor="w")
    label(body, tr('拾光日历  ') + VERSION + tr(' · 预览版'), 10, GREEN)
    label(body, tr('升级请安装新版安装包。卸载只移除程序，保留日记与加密 Token；迁移到其他账户或电脑后需重新填写 Token。'), 9)
