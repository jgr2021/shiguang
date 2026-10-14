"""Account setup, sync status and explicit conflict resolution."""
import json
import os
from platform_support import open_path, wheel_units
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import urlencode
import webbrowser

from app_config import bootstrap, program_dir
from github_accounts import (Accounts, app_registration, binding, save_binding,
                             save_registration, save_token, forget_token)
from github_client import GitHub, GitHubError
from github_records import initialize
from github_sync import sync
from localization import tr
from ui_design import P, FONT, SoftButton, ScrollPane, new_window, heading


class SyncController:
    def __init__(self, features):
        self.features, self.app = features, features.app
        self.status = tk.StringVar(value=tr('GitHub 同步未开启'))
        saved = binding(self.app.store.root)
        if saved:
            self.status.set(tr('等待同步') if saved.get('enabled') else tr('自动同步已暂停'))
        self.running, self.failures = False, 0
        self.next_at = time.monotonic() + 90
        self.window = None
        self.job = self.app.after(15000, self.tick)

    def tick(self):
        try:
            account = binding(self.app.store.root)
            if account.get("enabled") and time.monotonic() >= self.next_at:
                self.start(False)
        finally:
            self.job = self.app.after(15000, self.tick)

    def start(self, manual=True):
        if self.running or self.features.busy_count or self.features.ai:
            if manual:
                self.status.set(tr('请等待当前操作完成后再同步。'))
            return
        if self.app.note_dirty and not manual:
            return
        if not self.app.save_note():
            return
        self.running = True
        self.status.set(tr('正在连接 GitHub…'))
        def progress(value):
            self.features.events.put(("sync_progress", value))
        def done(result):
            self.running, self.failures = False, 0
            self.next_at = time.monotonic() + 120
            value = tr('已同步 {0} 条记录 · {1}', result["records"], result["at"])
            if result["skipped"]:
                value += "\n" + tr('{0} 个超过10 MiB的附件仅保存在本机。', result["skipped"])
            self.status.set(value)
            if not self.app.note_dirty:
                self.app.load_note()
            self.app.refresh()
        def failed(error):
            self.running = False
            self.failures += 1
            self.next_at = time.monotonic() + min(1800, 30 * 2 ** min(self.failures, 6))
            self.status.set(error)
        self.features.run(lambda store: sync(store, progress), done, failed)

    def open(self):
        if self.window and self.window.top.winfo_exists():
            self.window.top.lift()
        else:
            self.window = SyncWindow(self)

    def close(self):
        self.app.after_cancel(self.job)
        if self.window:
            self.window.cancel.set()


class SyncWindow:
    def __init__(self, controller):
        self.controller, self.app = controller, controller.app
        self.features = controller.features
        self.cancel = threading.Event()
        self.session = None
        self.repos = []
        self.login_running = False
        self.top = new_window(self.app, tr('账号与同步'), (800, 740), minimum=(660, 520))
        heading(self.top, tr('记录跟着账号走'), tr('离线记录，联网后同步到自己的 GitHub 私有仓库。'))
        pane = ScrollPane(self.top, bg=P["bg"], bind_wheel=True)
        pane.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.body = pane.inner
        self.state = tk.StringVar()
        self.render()
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.bind("<Escape>", lambda event: self.close())

    def text(self, parent, value, size=10, variable=None):
        label = tk.Label(parent, text=value, textvariable=variable, bg=parent.cget("bg"),
                         fg=P["muted"], font=(FONT, size), wraplength=650, justify="left", anchor="w")
        label.pack(fill="x", pady=5)
        return label

    def button(self, parent, title, command, primary=False):
        button = SoftButton(parent, tr(title), command, primary)
        button.pack(anchor="w", pady=6)
        return button

    def card(self, title):
        box = tk.Frame(self.body, bg=P["paper"], padx=20, pady=15)
        box.pack(fill="x", pady=(0, 12))
        self.text(box, tr(title), 13)
        return box

    def render(self):
        for child in self.body.winfo_children():
            child.destroy()
        registered = app_registration()
        account = binding(self.app.store.root)
        local_card = self.card('本机版无需登录')
        self.text(local_card, tr('日记、待办、附件、搜索和备份可直接离线使用。GitHub 登录与同步完全可选。'))
        if not registered["client_id"]:
            card = self.card('启用 GitHub 登录')
            self.text(card, tr('此版本尚未配置拾光的 GitHub App。维护者只需配置一次，使用者之后点击登录即可。'))
            self.text(card, tr('创建 GitHub App：启用 Device Flow，Contents 读写，允许 Any account 安装，关闭 Webhook。'))
            self.button(card, '前往 GitHub 创建应用', lambda: webbrowser.open('https://github.com/settings/apps/new'))
            self.text(card, 'Client ID')
            client_id = ttk.Entry(card)
            client_id.pack(fill="x", pady=4)
            self.text(card, tr('App 名称（安装链接末尾的名称）'))
            slug = ttk.Entry(card)
            slug.pack(fill="x", pady=4)
            def configure():
                try:
                    save_registration(client_id.get().strip(), slug.get().strip())
                    self.render()
                except Exception as error:
                    self.state.set(str(error))
            self.button(card, '保存应用配置', configure, True)
        card = self.card('GitHub 账号')
        self.text(card, tr('当前资料：{0}', account.get("login", tr('本地空间'))))
        self.button(card, '用 GitHub 登录 / 切换账号', self.login, True)
        if account:
            self.text(card, account["repo"])
            self.button(card, '退出账号', self.logout)
        self.text(card, "", variable=self.state)
        self.login_box = tk.Frame(card, bg=P["paper"])
        self.login_box.pack(fill="x")
        if account:
            card = self.card('同步状态')
            self.text(card, "", variable=self.controller.status)
            last = self.app.store.setting("github_last_sync")
            if last:
                self.text(card, tr('上次同步：{0}', last))
            enabled = tk.BooleanVar(value=bool(account.get("enabled")))
            def toggle():
                if self.controller.running:
                    enabled.set(bool(binding(self.app.store.root).get("enabled")))
                    self.state.set(tr('请等待当前操作完成后再同步。'))
                    return
                updated = binding(self.app.store.root)
                updated["enabled"] = enabled.get()
                save_binding(self.app.store.root, updated)
                self.controller.status.set(tr('等待同步') if enabled.get() else tr('自动同步已暂停'))
                self.controller.next_at = time.monotonic() + 2
            tk.Checkbutton(card, text=tr('应用运行时自动同步'), variable=enabled, command=toggle,
                           bg=P["paper"], activebackground=P["paper"]).pack(anchor="w", pady=6)
            self.button(card, '立即同步', self.controller.start, True)
            self.button(card, '处理同步冲突', self.conflicts)
        card = self.card('同步范围')
        self.text(card, tr('同步日记、待办、正式档案与小附件的日期关联。每个附件不超过10 MiB，总计100 MiB。助手聊天、AI Token 和本机配置不参与同步。'))
        self.text(card, tr('私有仓库不是端到端加密空间；删除记录后，Git 历史中仍可能保留旧内容。'))
        self.button(card, '查看同步使用说明', lambda: open_path(str(program_dir() / 'GitHub同步说明.md')))

    def login(self):
        if self.login_running or self.features.busy_count or self.features.ai:
            self.state.set(tr('请等待当前操作完成后再同步。'))
            return
        config = app_registration()
        if not config["client_id"]:
            self.state.set(tr('请先配置拾光的 GitHub App Client ID。'))
            return
        if not self.app.save_note():
            return
        self.cancel.clear()
        self.session = None
        self.login_running = True
        self.state.set(tr('正在申请 GitHub 登录验证码…'))
        for child in self.login_box.winfo_children():
            child.destroy()
        def fail(error):
            self.login_running = False
            if self.top.winfo_exists():
                self.state.set(error)
        def code_ready(code):
            if not self.top.winfo_exists() or self.cancel.is_set():
                self.login_running = False
                return
            self.state.set(tr('在 GitHub 网页输入验证码：{0}', code["user_code"]))
            def open_browser():
                self.top.clipboard_clear()
                self.top.clipboard_append(code["user_code"])
                webbrowser.open('https://github.com/login/device')
            self.button(self.login_box, '复制验证码并打开 GitHub', open_browser, True)
            self.button(self.login_box, '取消登录', self.cancel.set)
            self.features.run(lambda store: GitHub().finish_login(config["client_id"], code, self.cancel), authorized, fail)
        def authorized(user):
            self.login_running = False
            if not self.top.winfo_exists() or self.cancel.is_set():
                return
            self.session = user
            self.state.set(tr('已登录 {0}，请选择专用私有仓库。', user["login"]))
            self.setup_repository()
        self.features.run(lambda store: GitHub().begin_login(config["client_id"]), code_ready, fail)

    def setup_repository(self):
        for child in self.login_box.winfo_children():
            child.destroy()
        config = app_registration()
        self.text(self.login_box, tr('首次使用：建立私有仓库 shiguang-data，勾选 Add README；安装拾光 App 时只选择这个仓库。'))
        self.button(self.login_box, '创建专用私有仓库', lambda: webbrowser.open('https://github.com/new?' + urlencode({"name": "shiguang-data", "visibility": "private"})))
        self.button(self.login_box, '授权这个仓库', lambda: webbrowser.open('https://github.com/apps/' + config["slug"] + '/installations/new'))
        selected = tk.StringVar()
        picker = ttk.Combobox(self.login_box, textvariable=selected, state="readonly")
        picker.pack(fill="x", pady=8)
        include = tk.BooleanVar(value=False)
        can_include = not binding(self.app.store.root) and str(self.session['id']) not in Accounts(self.app.account_home).state['users']
        if can_include:
            tk.Checkbutton(self.login_box, text=tr('将当前本机记录加入此账号（首次关联）'), variable=include,
                           bg=P["paper"], activebackground=P["paper"]).pack(anchor="w", pady=5)
        def loaded(rows):
            if not self.top.winfo_exists():
                return
            self.repos = rows
            picker.configure(values=[r["name"] for r in rows])
            if rows:
                known = binding(self.app.store.root).get("repo", "")
                selected.set(next((r["name"] for r in rows if r["name"] == known or r["name"].endswith('/shiguang-data')), rows[0]["name"]))
                self.state.set(tr('请确认账号、仓库和是否加入本机记录，然后启用同步。'))
            else:
                self.state.set(tr('尚未找到可用私有仓库。请建立仓库、添加 README 并完成授权，再刷新。'))
        def refresh():
            if self.features.busy_count:
                return
            session = dict(self.session)
            self.features.run(lambda store: GitHub(session["token"]).repositories(session["id"]), loaded,
                              lambda error: self.state.set(error) if self.top.winfo_exists() else None)
        self.button(self.login_box, '刷新仓库列表', refresh)
        self.button(self.login_box, '关联并启用同步', lambda: self.connect(selected.get(), include.get()), True)
        refresh()

    def connect(self, name, include):
        if not self.session or self.features.busy_count:
            return
        repo = next((r for r in self.repos if r["name"] == name), None)
        if not repo:
            self.state.set(tr('请先选择已授权的私有仓库。'))
            return
        if not self.app.can_switch_profile(self.top):
            return
        user = dict(self.session)
        accounts = Accounts(self.app.account_home)
        try:
            destination = accounts.destination(user["id"], self.app.store.root, include)
            old = binding(destination)
            value = {"user_id": user["id"], "login": user["login"], "repo_id": repo["id"],
                     "repo": repo["name"], "branch": old.get("branch", repo["branch"]), "enabled": True}
            if old and (old["user_id"], old["repo_id"]) != (value["user_id"], value["repo_id"]):
                raise ValueError(tr('此资料空间已绑定其他账号或仓库。请使用独立空间。'))
        except Exception as error:
            self.state.set(str(error))
            return
        # Make the first transfer explicit; re-login to an existing binding is not a new upload consent.
        if not old and not messagebox.askokcancel(tr('关联私有仓库'),
                tr('目标账号：{0}\n私有仓库：{1}\n资料空间：{2}\n\n关联后将同步此空间中的日记、待办与小附件。', user["login"], name, str(destination)), parent=self.top):
            return
        def check(store):
            client = GitHub(user["token"])
            client.check_repo(value)
            try:
                client.read_head(value)
            except GitHubError as error:
                if error.status == 409:
                    raise ValueError(tr('仓库还没有分支，请先在 GitHub 添加 README 文件。')) from None
                raise
            return True
        def ready(_):
            if not self.top.winfo_exists() or self.cancel.is_set():
                return
            if not self.app.can_switch_profile(self.top):
                return
            try:
                bootstrap(destination)
                save_token(destination, user)
                save_binding(destination, value)
                accounts.remember(user["id"], destination)
                if destination == self.app.store.root:
                    self.session = None
                    self.render()
                    self.controller.start()
                else:
                    self.app.switch_profile(destination, self.top)
            except Exception as error:
                self.state.set(str(error))
        self.state.set(tr('正在检查私有仓库…'))
        self.features.run(check, ready, lambda error: self.state.set(error) if self.top.winfo_exists() else None)

    def logout(self):
        if not self.app.can_switch_profile(self.top):
            return
        try:
            destination = Accounts(self.app.account_home).offline()
            account = binding(self.app.store.root)
            account["enabled"] = False
            save_binding(self.app.store.root, account)
            forget_token(self.app.store.root)
            self.app.switch_profile(destination, self.top)
        except Exception as error:
            self.state.set(str(error))

    def conflicts(self):
        if self.controller.running:
            self.state.set(tr('请等待当前操作完成后再同步。'))
            return
        initialize(self.app.store)
        rows = list(self.app.store.db.execute("SELECT * FROM github_conflicts WHERE active=1 AND choice='' ORDER BY created_at"))
        if not rows:
            self.state.set(tr('没有待处理冲突。'))
            return
        top = new_window(self.app, tr('处理同步冲突'), (840, 660), minimum=(680, 480))
        heading(top, tr('选择要保留的版本'), tr('未选版本会保留在本机冲突历史中。选择完成后再同步。'))
        navigation = tk.Frame(top, bg=P["bg"], padx=24, pady=14)
        navigation.pack(side="bottom", fill="x")
        title = tk.StringVar()
        tk.Label(top, textvariable=title, bg=P["bg"], fg=P["ink"], font=(FONT, 12)).pack(pady=8)
        columns = tk.Frame(top, bg=P["bg"])
        columns.pack(fill="both", expand=True, padx=24)
        views = []
        for name in ('本机版本', '云端版本'):
            frame = tk.Frame(columns, bg=P["paper"])
            frame.pack(side="left", fill="both", expand=True, padx=5)
            self.text(frame, tr(name), 12)
            view = tk.Text(frame, width=36, wrap="word", font=(FONT, 10), relief="flat", padx=12, pady=10)
            view.pack(fill="both", expand=True)
            views.append(view)
        index = [0]
        def show():
            row = rows[index[0]]
            title.set(str(index[0] + 1) + '/' + str(len(rows)) + ' · ' + row['key'])
            for field, view in zip(('local', 'remote'), views):
                value = json.loads(row[field])
                if value is None:
                    content = tr('此版本已删除记录。')
                else:
                    content = '\n\n'.join(str(value[k]) for k in ('day', 'entry_date', 'at_time', 'title', 'body', 'raw_text', 'notes', 'tags', 'updated_at') if value.get(k))
                    if row['key'].startswith('task/'):
                        content += '\n\n' + tr('完成状态：{0}', tr('已完成') if value.get('done') else tr('未完成'))
                    if 'dates' in value:
                        content += '\n\n' + tr('关联日期') + '\n' + '\n'.join(a + ' — ' + b for a, b in value['dates'])
                    if 'analysis' in value or 'payload' in value:
                        content += '\n\n' + json.dumps(json.loads(value.get('analysis', value.get('payload'))), ensure_ascii=False, indent=2)
                view.configure(state="normal")
                view.delete('1.0', 'end')
                view.insert('1.0', content)
                view.configure(state="disabled")
        def choose(choice):
            with self.app.store.db:
                self.app.store.db.execute("UPDATE github_conflicts SET choice=? WHERE id=?", (choice, rows[index[0]]['id']))
            index[0] += 1
            if index[0] >= len(rows):
                top.destroy()
                self.controller.start()
            else:
                show()
        SoftButton(navigation, tr('保留本机版本'), lambda: choose('local'), True).pack(side="left")
        SoftButton(navigation, tr('使用云端版本'), lambda: choose('remote')).pack(side="right")
        show()

    def close(self):
        self.cancel.set()
        self.session = None
        self.top.destroy()
