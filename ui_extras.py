"""Attachment, search, cloud folder and assistant windows."""
from localization import tr, file_status
import os
from platform_support import open_path, wheel_units
from pathlib import Path
import queue
import threading
import time
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from assistant_bridge import AssistantRun, find_codex
from file_store import FileStore
from app_config import ai_description, load_ai
from ui_design import P, FONT, SoftButton, SlimScrollbar, new_window, heading, ScrollPane, empty_state
from attachment_widgets import TagPicker, LinkedDatePicker, split_tags
from attachment_browser import AttachmentCards

BG, INK, GREEN, MUTED = P["paper"], P["ink"], P["green"], P["muted"]


def text(parent, value, size=10, color=INK):
    return tk.Label(parent, text=value, bg=parent.cget("bg"), fg=color, font=(FONT, size), anchor="w", justify="left", wraplength=640)


def action(parent, title, command, primary=False):
    return SoftButton(parent, title, command, primary)


def window(app, title, size="780x640"):
    width, height = map(int, size.split("x"))
    return new_window(app, title, (width, height))


class Features:
    def __init__(self, app):
        self.app = app
        self.events = queue.Queue()
        self.busy_count = 0
        self.ai = None
        self.chat_window = None
        self.poll_job = app.after(100, self.poll)
        from github_sync_ui import SyncController
        self.github = SyncController(self)

    def settings(self):
        from settings_ui import about
        about(self)

    def ai_settings(self):
        from settings_ui import open_settings
        open_settings(self)

    def welcome(self):
        from settings_ui import welcome
        welcome(self)

    def run(self, operation, callback, failure=None):
        self.busy_count += 1
        data_root = self.app.store.root
        def worker():
            store = None
            try:
                store = FileStore(data_root)
                result = operation(store)
                self.events.put(("callback", (callback, result)))
            except Exception as error:
                self.events.put(("failure", (failure, str(error))))
            finally:
                if store:
                    store.close()
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            self._poll()
        except Exception:
            self.app.report_callback_exception(*sys.exc_info())
        finally:
            if self.app.winfo_exists():
                self.poll_job = self.app.after(100, self.poll)

    def _poll(self):
        try:
            for _ in range(30):
                kind, data = self.events.get_nowait()
                if kind == "callback":
                    self.busy_count -= 1
                    callback, result = data
                    callback(result)
                elif kind == "failure":
                    self.busy_count -= 1
                    callback, message = data
                    if callback:
                        callback(message)
                    else:
                        messagebox.showerror(tr('操作未完成'), message, parent=self.app)
                elif kind == "sync_progress":
                    self.github.status.set(data)
        except queue.Empty:
            pass
        if self.ai:
            try:
                for _ in range(30):
                    kind, value = self.ai_events.get_nowait()
                    if kind == "progress":
                        self.ai_progress = value
                        self.chat_status.set(value)
                    elif kind in {"done", "error"}:
                        self.chat_append(tr('助手') if kind == "done" else tr('连接或处理未完成'), value["reply"] if kind == "done" else value)
                        self.chat_status.set(tr('本轮完成，记录已保存在本机') if kind == "done" else tr('可重试；离线记录不受影响'))
                        self.ai = None
                        self.send_button.configure(state="normal")
                        self.stop_button.configure(state='disabled')
                        if kind == "error" and not self.chat_input.get("1.0", "end-1c").strip():
                            self.chat_input.insert("1.0", getattr(self, "last_question", ""))
                        self.app.refresh()
                        self.refresh_plans()
                        if kind == 'done' and value.get('plan_id'):
                            from calendar_plan_ui import open_plan
                            open_plan(self, value['plan_id'])
                        break
            except queue.Empty:
                pass
            if self.ai:
                elapsed = int(time.monotonic() - self.ai_started)
                self.chat_status.set(tr('{0} · 已等待 {1} 秒', self.ai_progress, elapsed))

    def build_files(self, parent):
        self.file_panel = tk.Frame(parent, bg=BG)
        row = tk.Frame(self.file_panel, bg=BG)
        row.pack(fill="x", pady=(0, 10))
        action(row, tr('+ 上传文件'), self.import_dialog, True).pack(side="left")
        hint = text(self.file_panel, tr('使用「打开文件」查看内容；搜索中可查看全部附件。'), 9, MUTED)
        hint.configure(wraplength=320)
        hint.pack(fill="x", pady=(0, 10))
        hint.bind('<Configure>', lambda event: hint.configure(wraplength=max(140, event.width)))
        self.file_list = AttachmentCards(self.file_panel, self)
        self.file_list.pack(fill="both", expand=True)
        self.file_signature = None

    def render_files(self):
        rows = self.app.store.files_for_day(self.app.selected.isoformat())
        signature = (self.app.selected.isoformat(), tuple((r["id"], r["version"]) for r in rows))
        if signature == self.file_signature:
            return
        self.file_signature = signature
        self.app.tab_files.configure(text=tr('附件 {0}', len(rows)) if rows else tr('附件'))
        self.file_list.show(rows)

    def open_attachment(self, identifier):
        try:
            self.open_file(self.app.store.file(identifier, content=False))
        except Exception as error:
            messagebox.showerror(tr('文件不可用'), str(error), parent=self.app)

    def edit_attachment(self, identifier):
        try:
            self.file_dialog(self.app.store.file(identifier))
        except Exception as error:
            messagebox.showerror(tr('文件不可用'), str(error), parent=self.app)

    def import_dialog(self):
        source = filedialog.askopenfilename(parent=self.app, title=tr('选择要保存在拾光的文件'))
        if source:
            self.file_dialog(None, source)

    def file_dialog(self, item=None, source=None):
        top = window(self.app, tr('附件与日期关联'), "980x780")
        hero = heading(top, tr('让文件跟着日子走'), tr('选几个标签，再点选需要这份文件的日期。'))
        hero.configure(pady=16)
        controls = tk.Frame(top, bg=P["bg"], padx=28, pady=18)
        controls.pack(side="bottom", fill="x")
        pane = ScrollPane(top, bg=P["bg"], bind_wheel=True)
        pane.pack(fill="both", expand=True, padx=28)
        content = pane.inner
        frame = tk.Frame(content, bg=BG, padx=22, pady=20)
        dates_card = tk.Frame(content, bg=BG, padx=22, pady=20)
        layout = [None]
        def arrange(event=None):
            wide = content.winfo_width() >= 760
            if wide == layout[0]:
                return
            layout[0] = wide
            frame.grid_forget()
            dates_card.grid_forget()
            content.columnconfigure(0, weight=3, uniform="" if wide else "stack")
            content.columnconfigure(1, weight=4 if wide else 0)
            frame.grid(row=0, column=0, sticky="new", padx=(0, 14) if wide else 0, pady=(0, 14))
            dates_card.grid(row=0 if wide else 1, column=1 if wide else 0, sticky="new", pady=(0, 14))
        content.bind("<Configure>", arrange, add="+")
        arrange()
        data = item or {"title": Path(source).name, "tags": "", "cloud_url": "", "notes": "", "as_of": "", "dates": [[self.app.selected.isoformat(), self.app.selected.isoformat()]]}
        text(frame, tr('文件标题'), 10).pack(anchor="w", pady=(0, 8))
        title = tk.StringVar(value=data["title"])
        ttk.Entry(frame, textvariable=title, font=(FONT, 11)).pack(fill="x")
        text(frame, tr('标签'), 10).pack(anchor="w", pady=(20, 8))
        suggestions = []
        for row in self.app.store.db.execute("SELECT tags FROM planner_files WHERE tags<>'' ORDER BY updated_at DESC LIMIT 150"):
            suggestions.extend(split_tags(row[0]))
        tags = TagPicker(frame, data["tags"], list(dict.fromkeys(suggestions))[:16])
        tags.pack(fill="x")
        text(dates_card, tr('在哪些日子查看'), 12).pack(anchor="w", pady=(0, 14))
        dates = LinkedDatePicker(dates_card, data["dates"], self.app.selected)
        dates.pack(fill="x")
        text(frame, tr('备注 / 帮助搜索的描述'), 9, MUTED).pack(fill="x", pady=(8, 5))
        note_box = tk.Frame(frame, bg=P["soft"])
        note_box.pack(fill="x")
        notes = tk.Text(note_box, height=4, width=1, font=(FONT, 10), wrap="word", bg=P["soft"], fg=INK, insertbackground=GREEN, relief="flat", highlightthickness=0, padx=10, pady=8)
        note_bar = SlimScrollbar(note_box, command=notes.yview)
        notes.configure(yscrollcommand=note_bar.set)
        note_bar.pack(side="right", fill="y")
        notes.pack(side="left", fill="x", expand=True)
        notes.insert("1.0", data["notes"])
        notes.bind("<MouseWheel>", lambda e: (notes.yview_scroll(wheel_units(e), "units"), "break")[-1])
        status = tk.StringVar(value=file_status(item["extraction_status"]) if item else tr('点击保存后复制原文件，并在后台提取可搜索文字。'))
        status_label = tk.Label(frame, textvariable=status, bg=BG, fg=MUTED, font=(FONT, 9), wraplength=280, justify="left", anchor="w")
        status_label.pack(fill="x", pady=(12, 0))
        status_label.bind("<Configure>", lambda e: status_label.configure(wraplength=max(140, e.width)))
        if item:
            preview_box = tk.Frame(frame, bg=P["soft"])
            def toggle_preview():
                if preview_box.winfo_manager():
                    preview_box.pack_forget()
                    preview_toggle.configure(text=tr('查看文件文字  ›'))
                else:
                    preview_box.pack(fill="x", pady=(8, 0))
                    preview_toggle.configure(text=tr('收起文件文字  ‹'))
            preview_toggle = action(frame, tr('查看文件文字  ›'), toggle_preview)
            preview_toggle.pack(anchor="w", pady=(12, 0))
            preview = tk.Text(preview_box, height=5, width=1, font=(FONT, 9), wrap="word", relief="flat", bg=P["soft"], highlightthickness=0, padx=10, pady=8)
            preview_bar = SlimScrollbar(preview_box, command=preview.yview)
            preview.configure(yscrollcommand=preview_bar.set)
            preview_bar.pack(side="right", fill="y")
            preview.pack(fill="x", expand=True)
            preview.insert("1.0", item["extracted_text"][:6000] or tr('未提取正文，可补充备注帮助搜索。'))
            preview.configure(state="disabled")
            preview.bind("<MouseWheel>", lambda e: (preview.yview_scroll(wheel_units(e), "units"), "break")[-1])
        def finish(result):
            if top.winfo_exists():
                top.destroy()
            self.app.refresh()
            saved = result.get('file', result)
            selected_day = self.app.selected.isoformat()
            if not any(a <= selected_day <= b for a, b in saved['dates']):
                from datetime import date
                if not self.app.select_day(date.fromisoformat(saved['dates'][0][0])):
                    self.search(show_all=True)
                    return
            self.app.switch_tab('files')
            self.file_list.reveal(saved['id'])
            library = getattr(self, 'search_browser', None)
            if library and library.top.winfo_exists():
                library.reload()
            self.app.notice(tr('附件已保存在本机并关联日期') + (tr('；重复文件已合并日期') if isinstance(result, dict) and result.get("status") == "linked" else ""))
        def failed(message):
            if top.winfo_exists():
                save.configure(state="normal")
                cancel.configure(state="normal")
                status.set(message)
                top.protocol("WM_DELETE_WINDOW", top.destroy)
        def commit():
            try:
                values = {"title": title.get().strip(), "tags": tags.value(), "notes": notes.get("1.0", "end-1c"),
                          "as_of": data.get("as_of", ""), "cloud_url": data.get("cloud_url", "")}
                selected = dates.values()
                self.app.store.validate_metadata(values)
            except Exception as error:
                status.set(str(error))
                return
            save.configure(state="disabled")
            cancel.configure(state="disabled")
            status.set(tr('正在后台保存和提取文字，日历仍可使用……'))
            top.protocol("WM_DELETE_WINDOW", lambda: status.set(tr('正在保存，请稍候。')))
            if item:
                self.run(lambda store: store.update_file(item["id"], item["version"], values, selected), finish, failed)
            else:
                self.run(lambda store: store.import_file(source, values, selected), finish, failed)
        save = action(controls, tr('保存'), commit, True)
        save.pack(side="right")
        cancel = action(controls, tr('取消'), top.destroy)
        cancel.pack(side="right", padx=8)
        if item:
            action(controls, tr('打开本机文件'), lambda: self.open_file(item)).pack(side="left")
            if item["cloud_url"]:
                action(controls, tr('打开云端链接'), lambda: webbrowser.open(item["cloud_url"])).pack(side="left", padx=6)

    def open_file(self, item):
        path = self.app.store.path_for(item)
        if not path.exists():
            messagebox.showerror(tr('文件不可用'), tr('本机附件文件缺失，请从备份恢复。'), parent=self.app)
            return
        if path.suffix.lower() in {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp3", ".mp4"}:
            open_path(str(path))
        else:
            open_path(str(path.parent))

    def search(self, show_all=False):
        from search_browser import SearchBrowser
        browser = getattr(self, 'search_browser', None)
        if browser and browser.top.winfo_exists():
            if show_all:
                browser.show_all()
            browser.top.lift()
            return
        self.search_browser = SearchBrowser(self)
        self.search_window = self.search_browser.top

    def cloud(self):
        existing = getattr(self, "cloud_window", None)
        if existing and existing.winfo_exists():
            existing.lift()
            return
        top = window(self.app, tr('云文件管理'), "760x580")
        self.cloud_window = top
        top.bind("<Escape>", lambda event: top.destroy())
        heading(top, tr('本机保存，网盘带走'), tr('支持 Google Drive、OneDrive、Dropbox 等客户端的本机同步文件夹。'), tr('云文件管理'))
        pane = ScrollPane(top, bg=BG, bind_wheel=True)
        pane.pack(fill="both", expand=True, padx=28, pady=(0, 28))
        frame = tk.Frame(pane.inner, bg=BG, padx=22, pady=22)
        frame.pack(fill="x")
        selected = tk.StringVar(value=self.app.store.setting("sync_folder"))
        ttk.Entry(frame, textvariable=selected, state="readonly").pack(fill="x", pady=8)
        status = tk.StringVar(value=tr('选择文件夹后，点击「写入同步目录」导出全部附件与日期关联。'))
        def choose():
            path = filedialog.askdirectory(parent=top, title=tr('选择网盘客户端的本机同步文件夹'))
            if path:
                self.app.store.set_setting("sync_folder", path)
                selected.set(path)
        action(frame, tr('选择同步文件夹'), choose).pack(anchor="w", pady=8)
        def done(result):
            if top.winfo_exists():
                sync.configure(state="normal")
                status.set(tr('已写入 {0} 个附件。云端上传进度请查看网盘客户端。\n{1}', result[1], result[0]))
        def fail(error):
            if top.winfo_exists():
                sync.configure(state="normal")
                status.set(error)
        def send():
            sync.configure(state="disabled")
            status.set(tr('正在后台写入同步目录……'))
            self.run(lambda store: store.sync_files(), done, fail)
        sync = action(frame, tr('写入同步目录'), send, True)
        sync.pack(anchor="w", pady=8)
        tk.Label(frame, textvariable=status, bg=BG, fg=MUTED, font=(FONT, 9), justify="left", wraplength=660).pack(fill="x", pady=10)
        text(frame, tr('这里只导出附件与关联信息；完整日记请使用「导出备份」。'), 9, MUTED).pack(anchor="w")

    def chat(self):
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.deiconify()
            self.chat_window.lift()
            return
        self.chat_window = top = window(self.app, tr('拾光助手'), "880x760")
        top.minsize(740, 550)
        top.protocol("WM_DELETE_WINDOW", top.withdraw)
        header = tk.Frame(top, bg=P['bg'], padx=22, pady=16)
        header.pack(fill='x')
        tk.Label(header, text=tr('拾光助手'), font=(FONT, 19, 'bold'), bg=P['bg'], fg=INK).pack(side='left')
        action(header, tr('AI 设置'), self.ai_settings).pack(side='right')
        quick = tk.Frame(top, bg=P["bg"])
        quick.pack(fill="x", padx=22, pady=10)
        action(quick, tr('更新我的简历'), lambda: self.set_chat_input(tr('请找到我过去的简历，读取旧简历以及之后直到今天的成果记录，生成一份更新后的简历，附修改依据。请把需要我补充的内容另外列出。')), True).pack(side="left")
        action(quick, tr('回顾最近一周'), lambda: self.set_chat_input(tr('请回顾我最近一周的记录，区分已完成成果、未完成安排和想法，并标出依据。') )).pack(side="left", padx=8)
        action(quick, tr('生成文件'), self.open_generated).pack(side="right")
        planning = tk.Frame(top, bg=P['bg'])
        planning.pack(fill='x', padx=22, pady=(0, 10))
        self.allow_calendar = tk.BooleanVar(value=False)
        action(planning, tr('帮我安排日程'), self.plan_prompt).pack(side='left')
        tk.Checkbutton(planning, text=tr('起草日程（确认后写入）'), variable=self.allow_calendar, bg=P['bg'], fg=GREEN, font=(FONT, 9)).pack(side='left', padx=8)
        self.plans_button = action(planning, tr('日程草稿'), self.show_plans)
        self.plans_button.pack(side='right')
        self.refresh_plans()
        composer = tk.Frame(top, bg=P["bg"])
        composer.pack(side="bottom", fill="x")
        area = tk.Frame(top, bg=BG)
        area.pack(fill="both", expand=True, padx=22)
        self.chat_output = tk.Text(area, wrap="word", font=(FONT, 11), bg=BG, fg=INK, relief="flat", padx=24, pady=18, spacing1=4, spacing3=8, state="disabled", cursor='arrow')
        self.chat_output.tag_configure("speaker", foreground=GREEN, font=(FONT, 10, "bold"), spacing1=12, spacing3=6)
        self.chat_output.tag_configure("message", foreground=INK, lmargin1=0, lmargin2=0, spacing3=12)
        self.chat_output.tag_configure('user_name', foreground=GREEN, font=(FONT, 9, 'bold'), justify='right', spacing1=16, spacing3=6)
        self.chat_output.tag_configure('user_message', foreground=INK, background=P['pale'], lmargin1=80, lmargin2=80, rmargin=12, justify='right', spacing1=6, spacing3=16)
        bar = SlimScrollbar(area, command=self.chat_output.yview)
        self.chat_output.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.chat_output.pack(fill="both", expand=True)
        for item in self.app.store.chat_history():
            self.chat_append({"user": tr('你'), "assistant": tr('助手'), "error": tr('未完成')}.get(item["role"], item["role"]), item["body"])
        if not self.app.store.chat_history():
            self.chat_append(tr('助手'), tr('先把旧简历上传到任意一天，再让我更新。你也可以让我查找文件、整理思路或回顾成果。\n旧简历的「内容截止日期」可以帮助我确定补充范围。'))
        self.chat_status = tk.StringVar(value=ai_description(self.app.store))
        tk.Label(composer, textvariable=self.chat_status, bg=P["bg"], fg=MUTED, font=(FONT, 9), anchor="w", wraplength=780, justify="left").pack(fill="x", padx=22, pady=8)
        self.chat_input = tk.Text(composer, height=2, wrap="word", font=(FONT, 11), relief="flat", bd=0, highlightthickness=1, highlightbackground=P["line"], highlightcolor=GREEN, padx=14, pady=12, undo=True)
        self.chat_input.pack(fill="x", padx=22)
        controls = tk.Frame(composer, bg=P["bg"])
        controls.pack(fill="x", padx=22, pady=12)
        text(controls, tr('Enter 发送 · Ctrl+Enter 换行'), 9, MUTED).pack(side="left")
        self.send_button = action(controls, tr('发送'), self.send_chat, True)
        self.send_button.pack(side="right")
        self.stop_button = action(controls, tr('停止'), self.stop_chat)
        self.stop_button.pack(side='right', padx=8)
        self.stop_button.configure(state='disabled')
        self.chat_input.bind('<Return>', self.enter_chat)
        self.chat_input.bind('<Control-Return>', self.newline_chat)
        self.chat_input.bind('<Shift-Return>', self.newline_chat)
        if sys.platform == 'darwin':
            self.chat_input.bind('<Command-Return>', self.newline_chat)
        self.chat_input.bind('<<Modified>>', self.resize_composer)
        self.chat_input.bind('<Configure>', self.resize_composer)

    def set_chat_input(self, value):
        self.chat_input.delete("1.0", "end")
        self.chat_input.insert("1.0", value)
        self.chat_input.focus_set()

    def chat_append(self, role, body):
        self.chat_output.configure(state="normal")
        user = role == tr('你')
        self.chat_output.insert("end", role + "\n", 'user_name' if user else "speaker")
        self.chat_output.insert("end", body + "\n\n", 'user_message' if user else "message")
        self.chat_output.configure(state="disabled")
        self.chat_output.see("end")

    def send_chat(self, event=None):
        if self.ai:
            return "break"
        if load_ai(self.app.store)["protocol"] == "offline":
            self.ai_settings()
            return "break"
        question = self.chat_input.get("1.0", "end-1c").strip()
        if not question or not self.app.save_note():
            return "break"
        self.chat_append(tr('你'), question)
        self.last_question = question
        self.chat_input.delete("1.0", "end")
        self.send_button.configure(state="disabled")
        self.stop_button.configure(state='normal')
        self.ai_started = time.monotonic()
        self.ai_progress = tr('正在连接所选 AI……')
        self.ai_events = queue.Queue()
        self.ai = AssistantRun(self.app.store.root, question, self.app.selected.isoformat(), self.ai_events, self.allow_calendar.get())
        threading.Thread(target=self.ai.run, daemon=True).start()
        return "break"

    def enter_chat(self, event=None):
        # Return must first finish an active Chinese IME composition.
        from chat_keys import ime_composing
        if ime_composing(self.chat_input):
            return None
        return self.send_chat(event)

    def newline_chat(self, event=None):
        self.chat_input.insert('insert', '\n')
        self.resize_composer()
        return 'break'

    def resize_composer(self, event=None):
        if self.chat_input.edit_modified():
            self.chat_input.edit_modified(False)
        count = self.chat_input.count('1.0', 'end', 'displaylines')
        self.chat_input.configure(height=max(2, min(6, count[0] if count else 2)))

    def stop_chat(self):
        if self.ai:
            self.ai_progress = tr('正在停止；已发送的请求可能仍计费。')
            self.stop_button.configure(state='disabled')
            self.ai.cancel()

    def open_generated(self):
        path = self.app.store.root / "generated"
        path.mkdir(exist_ok=True)
        open_path(str(path))

    def plan_prompt(self):
        self.allow_calendar.set(True)
        if not self.chat_input.get('1.0', 'end-1c').strip():
            self.set_chat_input(tr('请帮我起草 {0} 的日程：', self.app.selected.isoformat()))
        self.chat_input.focus_set()

    def show_plans(self):
        from calendar_plan_ui import show_plans
        show_plans(self)

    def refresh_plans(self):
        button = getattr(self, 'plans_button', None)
        if button and button.winfo_exists():
            from calendar_plans import pending_plans
            button.configure(text=tr('日程草稿 {0}', len(pending_plans(self.app.store))))

    def close(self):
        self.github.close()
        if self.ai:
            self.ai.cancel()
        self.app.after_cancel(self.poll_job)
