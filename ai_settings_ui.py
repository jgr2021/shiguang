"""Guided AI connections, provider catalogs and explicit Codex model selection."""
from datetime import datetime
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog
from urllib.parse import urlsplit
import webbrowser

from ai_catalog import PRESETS, CODEX_PRESETS, REGIONS, DOCS, API_EFFORTS, provider_hint
from api_assistant import connection_check, fetch_models
from app_config import Credentials, load_ai, validate_ai, ai_description
from codex_connection import find_codex, inspect_codex, login_codex
from diary import require
from localization import tr
from ui_design import P, FONT, SoftButton, ScrollPane, new_window, heading


def note(parent, text='', variable=None, color=None):
    widget = tk.Label(parent, text=text, textvariable=variable, bg=parent.cget('bg'), fg=color or P['muted'], font=(FONT, 9), anchor='w', justify='left', wraplength=720)
    widget.pack(fill='x', pady=5)
    return widget


def card(parent, title):
    box = tk.Frame(parent, bg=P['paper'], padx=22, pady=16, highlightthickness=1, highlightbackground=P['line'])
    tk.Label(box, text=title, bg=P['paper'], fg=P['ink'], font=(FONT, 12, 'bold'), anchor='w').pack(fill='x', pady=(0, 8))
    return box


class AISettings:
    def __init__(self, features):
        self.features, self.app = features, features.app
        self.current = load_ai(self.app.store)
        self.credentials = Credentials(self.app.store.root)
        self.codex_models = {}
        self.busy = False
        self.top = top = new_window(self.app, tr('AI 设置'), (920, 830), minimum=(740, 550))
        features.settings_window = top
        heading(top, tr('连接你的 AI'), tr('先选连接方式，再选模型。每个服务商单独记住设置。'), tr('拾光助手'))
        footer = tk.Frame(top, bg=P['bg'], padx=28, pady=14)
        footer.pack(side='bottom', fill='x')
        self.status = tk.StringVar(value=tr('设置只保存在本机；保存设置不会发送模型请求。'))
        note(footer, variable=self.status, color=P['green'])
        controls = tk.Frame(footer, bg=P['bg'])
        controls.pack(fill='x', pady=(5, 0))
        self.save_button = SoftButton(controls, tr('保存并使用'), self.save, True)
        self.save_button.pack(side='right')
        self.check_button = SoftButton(controls, tr('检查连接'), self.check)
        self.check_button.pack(side='right', padx=10)
        SoftButton(controls, tr('关闭'), top.destroy).pack(side='left')
        pane = ScrollPane(top, bg=P['bg'], bind_wheel=True)
        pane.pack(fill='both', expand=True, padx=28)
        body = pane.inner
        try:
            self.profiles = json.loads(self.app.store.setting('ai_profiles') or '{}')
            if not isinstance(self.profiles, dict):
                self.profiles = {}
        except ValueError:
            self.profiles = {}
        self.drafts = {}
        self.fields = {k: tk.StringVar(value=str(self.current.get(k, default))) for k, default in [('base_url', ''), ('model', ''), ('reasoning_effort', 'auto'), ('codex_binary', ''), ('max_tokens', 4096), ('context_chars', 60000)]}
        self.fields['token'] = tk.StringVar(value='')
        self.use_tools = tk.BooleanVar(value=self.current.get('tools', True))
        self.provider_names = {tr(x): x for x in PRESETS}
        self.provider_names.setdefault(tr(self.current['provider']), self.current['provider'])
        self.provider = tk.StringVar(value=tr(self.current['provider']))
        self.previous = self.current['provider']
        self.choose_card = card(body, tr('01  选择连接方式'))
        self.choose_card.pack(fill='x', pady=(0, 12))
        combo = ttk.Combobox(self.choose_card, textvariable=self.provider, values=list(self.provider_names), state='readonly', font=(FONT, 11))
        combo.pack(fill='x', pady=5)
        combo.bind('<<ComboboxSelected>>', self.change_provider)
        self.hint = tk.StringVar()
        note(self.choose_card, variable=self.hint)

        self.api_card = card(body, tr('02  连接服务商'))
        self.region_row = tk.Frame(self.api_card, bg=P['paper'])
        self.region = tk.StringVar()
        note(self.region_row, tr('账户地域'))
        self.region_combo = ttk.Combobox(self.region_row, textvariable=self.region, state='readonly', font=(FONT, 10))
        self.region_combo.pack(fill='x', pady=4)
        self.region_combo.bind('<<ComboboxSelected>>', self.change_region)
        self.region_row.pack(fill='x')
        self.field(self.api_card, tr('API 基础地址'), 'base_url')
        self.token_entry = self.field(self.api_card, tr('API Key / Token（留空沿用此地址已保存的密钥）'), 'token', secret=True)
        self.key_hint = tk.StringVar(value='')
        note(self.api_card, variable=self.key_hint)
        key_controls = tk.Frame(self.api_card, bg=P['paper'])
        key_controls.pack(fill='x', pady=5)
        SoftButton(key_controls, tr('获取官方 API Key'), self.open_key_page).pack(side='left')
        SoftButton(key_controls, tr('接入说明'), self.open_docs).pack(side='left', padx=8)
        SoftButton(key_controls, tr('移除已保存密钥'), self.forget).pack(side='right')
        note(self.api_card, tr('Token 使用 Windows 加密保存。地址改变后，密钥不会自动转发到新地址。'))

        self.codex_card = card(body, tr('02  连接本机 Codex'))
        self.codex_status = tk.StringVar(value=tr('点击读取状态，查看本机登录、模型目录与可读取的额度。'))
        note(self.codex_card, variable=self.codex_status, color=P['green'])
        line = tk.Frame(self.codex_card, bg=P['paper'])
        line.pack(fill='x', pady=5)
        self.inspect_button = SoftButton(line, tr('读取 Codex 状态'), self.inspect)
        self.inspect_button.pack(side='left')
        self.login_button = SoftButton(line, tr('在浏览器登录 Codex'), self.login)
        self.login_button.pack(side='left', padx=8)
        self.field(self.codex_card, tr('Codex 程序位置（留空自动查找）'), 'codex_binary')
        SoftButton(self.codex_card, tr('选择 codex.exe'), self.pick_binary).pack(anchor='w', pady=5)
        note(self.codex_card, tr('登录由 Codex 自己管理。拾光不读取、复制或保存 Codex 的登录 Token。'))
        note(self.codex_card, tr('这里连接的是拾光助手；其他 Codex 对话与项目不会因此自动同步。'))

        self.model_card = card(body, tr('03  选择模型与推理强度'))
        self.quick = tk.Frame(self.model_card, bg=P['paper'])
        for i, (title, model, effort) in enumerate(CODEX_PRESETS):
            SoftButton(self.quick, title, lambda m=model, e=effort: self.choose_model(m, e)).grid(row=i // 2, column=i % 2, padx=(0, 12), pady=5, sticky='ew')
        self.quick.grid_columnconfigure(0, weight=1)
        self.quick.grid_columnconfigure(1, weight=1)
        self.quick.pack(fill='x', pady=(0, 8))
        self.model_caption = note(self.model_card, tr('模型 ID'))
        row = tk.Frame(self.model_card, bg=P['paper'])
        row.pack(fill='x', pady=5)
        self.model_combo = ttk.Combobox(row, textvariable=self.fields['model'], font=(FONT, 10))
        self.model_combo.pack(side='left', fill='x', expand=True)
        self.models_button = SoftButton(row, tr('读取模型列表'), self.read_models)
        self.models_button.pack(side='left', padx=(10, 0))
        self.fields['model'].trace_add('write', self.effort_choices)
        note(self.model_card, tr('推理强度 · medium 为中，high 为高；auto 沿用模型默认值'))
        self.effort_combo = ttk.Combobox(self.model_card, textvariable=self.fields['reasoning_effort'], state='readonly', font=(FONT, 10))
        self.effort_combo.pack(fill='x', pady=5)
        self.model_note = tk.StringVar()
        note(self.model_card, variable=self.model_note)

        self.advanced_card = card(body, tr('04  请求预算与资料范围'))
        self.advanced = tk.Frame(self.advanced_card, bg=P['paper'])
        self.field(self.advanced, tr('最大输出 Token'), 'max_tokens')
        self.field(self.advanced, tr('上下文预算（字符）'), 'context_chars')
        tk.Checkbutton(self.advanced, text=tr('分步检索档案（需模型支持工具调用；每轮最多13次 API 请求）'), variable=self.use_tools, bg=P['paper'], fg=P['ink'], font=(FONT, 9), wraplength=680, justify='left').pack(fill='x', pady=8)
        self.advanced.pack(fill='x')
        self.privacy = tk.StringVar()
        note(self.advanced_card, variable=self.privacy)
        self.fields['base_url'].trace_add('write', self.url_changed)
        self.render()

    def name(self):
        return self.provider_names[self.provider.get()]

    def field(self, parent, title, key, secret=False):
        note(parent, title)
        entry = ttk.Entry(parent, textvariable=self.fields[key], show='•' if secret else '', font=(FONT, 10))
        entry.pack(fill='x', pady=(0, 8))
        return entry

    def raw(self):
        values = {key: value.get() for key, value in self.fields.items() if key != 'token'}
        values.update(provider=self.name(), protocol=PRESETS.get(self.name(), (self.current['protocol'], '', ''))[0], tools=self.use_tools.get())
        return values

    def values(self, complete=True):
        return validate_ai(self.raw(), complete=complete)

    def fingerprint(self):
        return (self.name(), self.fields['base_url'].get(), self.fields['codex_binary'].get(), self.fields['token'].get())

    def url_changed(self, *args):
        self.key_hint.set(tr('留空时仅使用此地址已保存的密钥；首次连接请填写 API Key。'))
        if self.raw()['protocol'] not in {'codex', 'offline'}:
            self.model_note.set(tr('先读取模型列表，或粘贴控制台提供的模型 ID；模型目录不保证实际调用权限。'))

    def change_provider(self, event=None):
        # Only non-secret draft fields are retained when switching providers.
        old = {key: value.get() for key, value in self.fields.items() if key != 'token'}
        old['tools'] = self.use_tools.get()
        self.drafts[self.previous] = old
        name = self.name()
        preset = PRESETS.get(name, (self.current['protocol'], '', ''))
        saved = self.drafts.get(name) or self.profiles.get(name) or {}
        if name == self.current['provider'] and name not in self.drafts and name not in self.profiles:
            saved = self.current
        defaults = dict(base_url=preset[1], model='', reasoning_effort='auto', codex_binary='', max_tokens='4096', context_chars='60000')
        for key in defaults:
            self.fields[key].set(str(saved.get(key, defaults[key])))
        self.fields['token'].set('')
        self.use_tools.set(saved.get('tools', True))
        self.previous = name
        self.status.set(tr('设置只保存在本机；保存设置不会发送模型请求。'))
        self.render()

    def render(self):
        protocol = self.raw()['protocol']
        self.hint.set(provider_hint(self.name()))
        for box in (self.api_card, self.codex_card, self.model_card, self.advanced_card):
            box.pack_forget()
        if protocol == 'offline':
            self.check_button.configure(state='disabled')
            return
        self.check_button.configure(state='disabled' if self.busy else 'normal')
        (self.codex_card if protocol == 'codex' else self.api_card).pack(fill='x', pady=(0, 12))
        self.model_card.pack(fill='x', pady=(0, 12))
        self.advanced_card.pack(fill='x', pady=(0, 12))
        if protocol == 'codex':
            self.quick.pack(fill='x', before=self.model_caption, pady=(0, 8))
            self.model_combo.configure(values=list(self.codex_models) or list(dict.fromkeys(p[1] for p in CODEX_PRESETS)))
            self.model_note.set(tr('快捷组合保留指定模型，不会自动换成其他模型。读取 Codex 状态可刷新目录与支持的强度；最终权限以请求结果为准。'))
            self.advanced.pack_forget()
            self.privacy.set(tr('发送时，Codex 可读取拾光提供的相关资料。模型与推理强度随本次请求传入，不修改 Codex 的全局设置。'))
        else:
            self.quick.pack_forget()
            self.model_combo.configure(values=['gpt-6-luna', 'gpt-6-astra', 'gpt-6.1-sol'] if self.name() == 'OpenAI' else [])
            self.advanced.pack(fill='x', before=self.advanced_card.winfo_children()[-1])
            self.model_note.set(tr('先读取模型列表，或粘贴控制台提供的模型 ID；模型目录不保证实际调用权限。'))
            self.privacy.set(tr('点击发送时，问题、近期对话与需要的档案内容会直接发给所选服务商。本版 API 模式不带网页搜索，不会自动查证最新信息。'))
        regions = REGIONS.get(self.name(), {})
        if regions:
            self.region_row.pack(fill='x', before=self.api_card.winfo_children()[2])
            self.region_combo.configure(values=[tr(x) for x in regions])
            match = next((tr(k) for k, v in regions.items() if v == self.fields['base_url'].get()), tr('自定义地址'))
            self.region.set(match)
        else:
            self.region_row.pack_forget()
        self.effort_choices()

    def effort_choices(self, *args):
        if not hasattr(self, 'effort_combo'):
            return
        protocol = self.raw()['protocol']
        model = self.fields['model'].get()
        if protocol == 'codex':
            efforts = ['auto'] + self.codex_models.get(model, {}).get('efforts', ['low', 'medium', 'high', 'xhigh', 'max'])
        elif protocol == 'responses':
            efforts = list(API_EFFORTS)
            if model == 'gpt-6-luna':
                efforts.append('none')
        else:
            efforts = ['auto']
            if protocol == 'openai' and (self.name() in {'自定义 OpenAI 兼容', 'OpenRouter', 'Google Gemini'}):
                efforts += ['low', 'medium', 'high']
        self.effort_combo.configure(values=list(dict.fromkeys(efforts)))
        if self.fields['reasoning_effort'].get() not in efforts:
            self.fields['reasoning_effort'].set('auto')

    def choose_model(self, model, effort):
        self.fields['model'].set(model)
        self.fields['reasoning_effort'].set(effort)
        self.status.set(tr('已选择 {0} · {1}，保存后用于拾光助手。', model, effort))

    def change_region(self, event=None):
        for name, url in REGIONS.get(self.name(), {}).items():
            if tr(name) == self.region.get():
                self.fields['base_url'].set(url)
                self.fields['token'].set('')
                break

    def pick_binary(self):
        path = filedialog.askopenfilename(parent=self.top, title=tr('选择 codex.exe'), filetypes=[('Codex executable', '*.exe')])
        if path:
            self.fields['codex_binary'].set(path)
            self.codex_models = {}
            self.codex_status.set(tr('程序位置已改变，请重新读取 Codex 状态。'))

    def open_key_page(self):
        url = PRESETS.get(self.name(), ('', '', ''))[2]
        if url:
            webbrowser.open(url)
        else:
            self.status.set(tr('请向所选接口的服务商获取 API Key。'))

    def open_docs(self):
        url = DOCS.get(self.name()) or PRESETS.get(self.name(), ('', '', ''))[2]
        if url:
            webbrowser.open(url)

    def key(self, config):
        key = self.fields['token'].get().strip() or self.credentials.get(config)
        require(bool(key) or urlsplit(config['base_url']).hostname in {'localhost', '127.0.0.1', '::1'}, tr('该 API 地址尚未保存 Token，请到「AI 设置」填写。'))
        return key

    def operation(self, operation, done, message):
        if self.busy:
            return
        self.busy = True
        fingerprint = self.fingerprint()
        buttons = [self.save_button, self.check_button, self.inspect_button, self.login_button, self.models_button]
        for button in buttons:
            button.configure(state='disabled')
        self.status.set(message)
        def finish(value, failed=False):
            self.busy = False
            if not self.top.winfo_exists():
                return
            for button in buttons:
                button.configure(state='normal')
            if fingerprint != self.fingerprint():
                self.status.set(tr('连接设置已改变，请重新读取或检查。'))
                return
            if failed:
                self.status.set(value)
            else:
                done(value)
        self.features.run(operation, finish, lambda message: finish(message, True))

    def show_codex(self, result):
        self.codex_models = {m['model']: m for m in result['models']}
        self.model_combo.configure(values=list(self.codex_models))
        self.effort_choices()
        account = result['account_type']
        label = ('ChatGPT · ' + (result['plan'] or tr('计划未返回'))) if account == 'chatgpt' else ('API Key' if account == 'apiKey' else account or tr('尚未登录'))
        lines = [tr('已找到 Codex · {0} · {1} 个目录模型', label, len(self.codex_models))]
        for name, limit in (result.get('limits') or {}).items():
            for window in ('primary', 'secondary'):
                value = limit.get(window)
                if value and value.get('usedPercent') is not None:
                    remaining = max(0, min(100, 100 - value['usedPercent']))
                    reset = datetime.fromtimestamp(value['resetsAt']).strftime('%m-%d %H:%M') if value.get('resetsAt') else tr('未知')
                    lines.append(tr('{0} · {1} 分钟额度窗口：剩余 {2}% · 重置 {3}', name, value.get('windowDurationMins', '?'), round(remaining, 1), reset))
        if not result.get('limits'):
            lines.append(tr('当前未返回额度信息；这不代表额度为零。'))
        self.codex_status.set('\n'.join(lines))
        self.status.set(tr('已读取登录和模型目录，没有发起模型生成。目录不等于调用权限保证。'))

    def inspect(self):
        path = self.fields['codex_binary'].get().strip()
        self.operation(lambda store: inspect_codex(path), self.show_codex, tr('正在读取 Codex 登录、模型与额度……'))

    def login(self):
        path = self.fields['codex_binary'].get().strip()
        self.operation(lambda store: login_codex(path), self.show_codex, tr('请在打开的浏览器里完成 Codex 登录，最多等待5分钟。'))

    def read_models(self):
        if self.raw()['protocol'] == 'codex':
            self.inspect()
            return
        try:
            config = self.values(False)
            key = self.key(config)
        except Exception as error:
            self.status.set(str(error))
            return
        def done(result):
            self.model_combo.configure(values=result['models'])
            self.status.set(tr('已读取 {0} 个模型 ID；请选择文本对话模型，再检查连接。', len(result['models'])) + ('' if result['complete'] else tr('目录较长，此次仅显示部分结果。')))
        self.operation(lambda store: fetch_models(config, key), done, tr('正在读取服务商模型目录，不发送档案或生成请求……'))

    def check(self):
        if self.raw()['protocol'] == 'codex':
            self.inspect()
            return
        try:
            config = self.values()
            key = self.key(config)
        except Exception as error:
            self.status.set(str(error))
            return
        self.operation(lambda store: connection_check(config, key), self.status.set, tr('正在发送一条简短连接检查消息（可能产生少量费用，不发送档案）……'))

    def forget(self):
        if self.busy:
            return
        try:
            config = self.values(False)
            require(config['protocol'] not in {'codex', 'offline'}, tr('此模式无需在这里填写 Token。'))
            self.credentials.set(config, '')
            self.fields['token'].set('')
            self.status.set(tr('已移除此 API 地址的 Token。'))
        except Exception as error:
            self.status.set(str(error))

    def save(self):
        if self.busy:
            return
        try:
            config = self.values()
            if config['protocol'] not in {'codex', 'offline'}:
                self.key(config)
                if self.fields['token'].get().strip():
                    self.credentials.set(config, self.fields['token'].get().strip())
            elif config['protocol'] == 'codex' and self.codex_models and config['model']:
                require(config['model'] in self.codex_models, tr('此模型不在刚读取的 Codex 目录中，请选择目录中的模型。'))
                efforts = self.codex_models[config['model']]['efforts']
                require(config['reasoning_effort'] == 'auto' or config['reasoning_effort'] in efforts, tr('此 Codex 模型不支持所选推理强度。'))
            self.profiles[self.name()] = config
            self.app.store.set_setting('ai_profiles', json.dumps(self.profiles, ensure_ascii=False))
            self.app.store.set_setting('ai_config', json.dumps(config, ensure_ascii=False))
            self.fields['token'].set('')
            if self.features.chat_window and self.features.chat_window.winfo_exists():
                self.features.chat_status.set(ai_description(self.app.store))
            self.app.notice(tr('AI 设置已保存到本机'))
            self.top.destroy()
        except Exception as error:
            self.status.set(str(error))


def open_ai_settings(features):
    if features.ai:
        features.app.notice(tr('当前助手正在运行，可停止后再修改 AI 设置。'))
        return
    existing = getattr(features, 'settings_window', None)
    if existing and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        return
    AISettings(features)
